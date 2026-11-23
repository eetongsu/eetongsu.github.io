import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from update_visitor_countries import CITY_DIMENSIONS, add_locations, public_snapshot, refresh, report_query
from visitor_centers import city_centers
from zipfile import ZipFile


END = date(2027, 11, 21)


def report(*entries):
    return {
        "dimensionHeaders": [{"name": "countryId"}],
        "metricHeaders": [{"name": "activeUsers", "type": "TYPE_INTEGER"}],
        "rowCount": len(entries),
        "rows": [{"dimensionValues": [{"value": code}], "metricValues": [{"value": value}]}
                 for code, value in entries],
    }


def city_report(*entries):
    return {
        "dimensionHeaders": [{"name": name} for name in CITY_DIMENSIONS],
        "metricHeaders": [{"name": "activeUsers", "type": "TYPE_INTEGER"}],
        "rowCount": len(entries),
        "rows": [{"dimensionValues": [{"value": v} for v in row[:-1]], "metricValues": [{"value": row[-1]}]}
                 for row in entries],
    }


class CountryMapTests(unittest.TestCase):
    def test_city_markers_and_deduplicated_country_fallback(self):
        snapshot = public_snapshot(report(("US", "6"), ("CA", "1")), END)
        city_rows = city_report(("US", "101", "Springfield", "Illinois", "5"),
                               ("US", "0", "(not set)", "(not set)", "1"),
                               ("US", "999", "Missing Place", "Illinois", "1"),
                               ("CA", "0", "(not set)", "(not set)", "1"))
        reports = [city_rows, report(("US", "1"))]
        queries = []
        def fetch(query):
            queries.append(query)
            return reports.pop(0)
        with patch("update_visitor_countries.city_centers", return_value={("US", "Springfield", "Illinois"): (39.8, -89.65)}):
            add_locations(snapshot, {}, fetch, END, None)
        self.assertEqual(snapshot["country_only"], {"US": "1–4", "CA": "1–4"})
        self.assertEqual(snapshot["cities"]["101"]["band"], "5–19")
        self.assertEqual(snapshot["cities"]["101"]["lat"], 39.8)
        filters = queries[1]["dimensionFilter"]["andGroup"]["expressions"]
        self.assertEqual(filters[-1]["filter"]["inListFilter"]["values"], ["0", "999"])

    def test_city_backfill_replaces_legacy_country_dot_and_preserves_history(self):
        city = {"city": "Boston", "region": "Massachusetts", "country": "US", "lat": 42.36,
                "lon": -71.06, "band": "1–4"}
        snapshot = public_snapshot(report(("US", "2")), END)
        old = {"countries": {"US": "1–4", "DE": "5–19"}, "cities": {"1": city}}
        with patch("update_visitor_countries.city_centers", return_value={}):
            add_locations(snapshot, old, lambda q: city_report(("US", "1", "Boston", "Massachusetts", "2")), END, None)
        self.assertEqual(snapshot["country_only"], {"DE": "5–19"})
        self.assertEqual(snapshot["cities"], old["cities"])

    def test_gazetteer_uses_region_and_declines_ambiguous_places(self):
        places = {("US", "Springfield", "Ohio"), ("US", "Springfield", "(not set)"),
                  ("US", "Springfield", "Texas"), ("US", "Springfield", "Oregon")}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/"admin1CodesASCII.txt").write_text("US.OH\tOhio\tOhio\t1\nUS.OR\tOregon\tOregon\t2\n")
            with ZipFile(folder/"cities500.zip", "w") as archive:
                archive.writestr("cities500.txt", "1\tSpringfield\tSpringfield\t\t39.92\t-83.81\tP\tPPL\tUS\t\tOH\n"
                                 "2\tSpringfield\tSpringfield\t\t44.05\t-123.02\tP\tPPL\tUS\t\tOR\n")
            self.assertEqual(city_centers(places, folder), {("US", "Springfield", "Ohio"): (39.92, -83.81),
                                                            ("US", "Springfield", "Oregon"): (44.05, -123.02)})

    def test_query_scopes_domain_and_period(self):
        query = report_query(END)
        span, = query["dateRanges"]
        self.assertEqual(span, {"startDate": "2026-11-21", "endDate": END.isoformat()})
        self.assertEqual(query["dimensionFilter"]["andGroup"]["expressions"], [
            {"filter": {"fieldName": "hostName", "stringFilter": {
                "matchType": "EXACT", "value": "eetongsu.github.io"}}},
            {"filter": {"fieldName": "eventName", "stringFilter": {
                "matchType": "EXACT", "value": "page_view"}}},
            {"filter": {"fieldName": "dateHourMinute", "numericFilter": {
                "operation": "GREATER_THAN_OR_EQUAL",
                "value": {"int64Value": "202611211649"}}}}])
        self.assertEqual(query["metricFilter"]["filter"]["numericFilter"]["value"], {"int64Value": "1"})

    def test_only_coarse_public_ranges(self):
        raw = report(("US", "4"), ("CA", "1"), ("AU", "0"), ("FR", "5"), ("JP", "19"), ("GB", "20"), ("BR", "49"),
                     ("DE", "50"), ("(not set)", "932"), ("ZZ", "329"))
        self.assertEqual(public_snapshot(raw, END), {
            "start_date": "2026-11-21", "end_date": END.isoformat(), "countries": {
                "US": "1–4", "CA": "1–4", "BR": "20–49", "DE": "50+", "FR": "5–19", "GB": "20–49", "JP": "5–19"}})

    def test_valid_empty_report_has_dates_for_the_base_map(self):
        empty = report()
        del empty["rowCount"], empty["rows"]  # GA4 may omit proto3 fields at their defaults.
        self.assertEqual(public_snapshot(empty, END), {
            "start_date": "2026-11-21", "end_date": END.isoformat(), "countries": {}})

    def test_history_survives_omissions_and_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "visitor-countries.json")
            path.write_text(json.dumps({"end_date": "2026-11-21", "countries": {"DE": "5–19"}}))
            cases = [
                (report(("US", "1")), {"DE": "5–19", "US": "1–4"}),
                (report(("US", "1")), {"DE": "5–19", "US": "1–4"}),
                (report(("US", "5")), {"DE": "5–19", "US": "5–19"}),
                (report(), {"DE": "5–19", "US": "5–19"}),
            ]
            for response, expected in cases:
                with patch("update_visitor_countries.urlopen", side_effect=[
                        io.BytesIO(json.dumps(response).encode()), io.BytesIO(json.dumps(city_report()).encode())]):
                    refresh("123456", "test", END, path)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["countries"], expected)

    def test_failure_preserves_previous_snapshot(self):
        cases = [report(("US", "3.5")), report(("FR", "5"), ("FR", "7")),
                 dict(report(("DE", "12")), rowCount=6), {"error": {"code": 403}},
                 dict(report(), metadata={"dataTruncationReasons": [{}]})]
        with tempfile.TemporaryDirectory() as folder:
            result = Path(folder, "visitor-countries.json")
            result.write_bytes(b"previous snapshot")
            for case in cases:
                response = io.BytesIO(json.dumps(case).encode())
                with self.subTest(case=case), patch("update_visitor_countries.urlopen", return_value=response):
                    with self.assertRaises(ValueError):
                        refresh("123456", "test", END, result)
                self.assertEqual(result.read_bytes(), b"previous snapshot")
            with patch("update_visitor_countries.urlopen", side_effect=TimeoutError), self.assertRaises(TimeoutError):
                refresh("123456", "test", END, result)
            self.assertEqual(result.read_bytes(), b"previous snapshot")


if __name__ == "__main__":
    unittest.main()
