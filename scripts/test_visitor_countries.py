import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from update_visitor_countries import public_snapshot, refresh, report_query


END = date(2026, 11, 20)


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
        self.assertEqual((date.fromisoformat(span["endDate"]) - date.fromisoformat(span["startDate"])).days, 89)
        self.assertEqual(query["dimensionFilter"]["filter"], {"fieldName": "hostName", "stringFilter": {
            "matchType": "EXACT", "value": "eetongsu.github.io"}})

    def test_only_coarse_public_ranges(self):
        raw = report(("US", "4"), ("FR", "5"), ("JP", "19"), ("GB", "20"), ("BR", "49"),
                     ("DE", "50"), ("(not set)", "932"), ("ZZ", "329"))
        self.assertEqual(public_snapshot(raw, END), {
            "end_date": "2026-11-20", "countries": {
                "BR": "20–49", "DE": "50+", "FR": "5–19", "GB": "20–49", "JP": "5–19"}})

    def test_valid_empty_report_can_hide_map(self):
        empty = report()
        del empty["rowCount"], empty["rows"]  # GA4 may omit proto3 fields at their defaults.
        self.assertEqual(public_snapshot(empty, END), {"end_date": END.isoformat(), "countries": {}})

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
