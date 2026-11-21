import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from update_visitor_countries import public_snapshot, refresh, report_query


END = date(2027, 11, 21)


def report(*entries):
    return {
        "dimensionHeaders": [{"name": "countryId"}],
        "metricHeaders": [{"name": "activeUsers", "type": "TYPE_INTEGER"}],
        "rowCount": len(entries),
        "rows": [{"dimensionValues": [{"value": code}], "metricValues": [{"value": value}]}
                 for code, value in entries],
    }


class CountryMapTests(unittest.TestCase):
    def test_query_scopes_domain_and_period(self):
        query = report_query(END)
        span, = query["dateRanges"]
        self.assertEqual(span, {"startDate": "2026-11-21", "endDate": END.isoformat()})
        self.assertEqual(query["dimensionFilter"]["andGroup"]["expressions"], [
            {"filter": {"fieldName": "hostName", "stringFilter": {
                "matchType": "EXACT", "value": "eetongsu.github.io"}}},
            {"filter": {"fieldName": "contentGroup", "stringFilter": {
                "matchType": "EXACT", "value": "public-visitor-map-v2"}}}])
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
                with patch("update_visitor_countries.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
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
