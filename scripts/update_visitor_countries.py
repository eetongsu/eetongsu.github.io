"""Publish coarse country ranges from a single GA4 report. Raw rows stay in memory."""
import json
import os
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "visitor-countries.json"
TRACKING_START = date(2026, 11, 21)
BANDS = ("1–4", "5–19", "20–49", "50+")


def report_query(end):
    if end < TRACKING_START:
        raise ValueError("End date precedes the first day of collection.")
    return {
        "dateRanges": [{"startDate": TRACKING_START.isoformat(),
                        "endDate": end.isoformat()}],
        "dimensions": [{"name": "countryId"}],
        "metrics": [{"name": "activeUsers"}],
        "dimensionFilter": {"andGroup": {"expressions": [
            {"filter": {"fieldName": "hostName", "stringFilter": {
                "matchType": "EXACT", "value": "eetongsu.github.io"}}},
            {"filter": {"fieldName": "contentGroup", "stringFilter": {
                "matchType": "EXACT", "value": "public-visitor-map-v2"}}},
        ]}},
        "metricFilter": {"filter": {"fieldName": "activeUsers", "numericFilter": {
            "operation": "GREATER_THAN_OR_EQUAL", "value": {"int64Value": "1"}}}},
        "limit": "1000",
    }


def public_snapshot(report, end):
    if (report.get("dimensionHeaders") != [{"name": "countryId"}]
            or report.get("metricHeaders") != [{"name": "activeUsers", "type": "TYPE_INTEGER"}]):
        raise ValueError("Unexpected report columns.")
    metadata = report.get("metadata", {})
    if (metadata.get("dataLossFromOtherRow") or metadata.get("samplingMetadatas")
            or metadata.get("dataTruncationReasons")
            or metadata.get("schemaRestrictionResponse", {}).get("activeMetricRestrictions")):
        raise ValueError("Incomplete report.")
    rows = report.get("rows", [])
    if not isinstance(rows, list) or report.get("rowCount", 0) != len(rows):
        raise ValueError("Incomplete rows.")

    countries = {}
    seen = set()
    for row in rows:
        dim, = row["dimensionValues"]
        metric, = row["metricValues"]
        code = dim["value"]
        value = metric["value"]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Invalid active user count.")
        if not re.fullmatch(r"[A-Z]{2}", code) or code == "ZZ":
            continue
        if code in seen:
            raise ValueError("Duplicate country.")
        seen.add(code)
        count = int(value)
        if count:
            countries[code] = BANDS[bisect_right((5, 20, 50), count)]
    return {"start_date": TRACKING_START.isoformat(), "end_date": end.isoformat(), "countries": countries}


def refresh(property_id, access_token, end, path=OUTPUT):
    if not re.fullmatch(r"[1-9][0-9]*", property_id) or not access_token:
        raise ValueError("Missing analytics configuration.")
    endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    request = Request(endpoint, data=json.dumps(report_query(end)).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + access_token})
    with urlopen(request, timeout=45) as response:
        report = json.load(response)
    snapshot = public_snapshot(report, end)
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("end_date") and date.fromisoformat(previous["end_date"]) > end:
            raise ValueError("A more recent snapshot already exists.")
        for code, band in previous["countries"].items():
            if not re.fullmatch(r"[A-Z]{2}", code) or code == "ZZ" or band not in BANDS:
                raise ValueError("Invalid archived country or band.")
            # Keep the last reported range if GA4 later omits this country.
            snapshot["countries"].setdefault(code, band)
    snapshot["countries"] = dict(sorted(snapshot["countries"].items()))
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


if __name__ == "__main__":
    end = datetime.now(ZoneInfo("America/New_York")).date()
    try:
        refresh(os.environ.get("GA4_PROPERTY_ID", ""), os.environ.get("GA4_ACCESS_TOKEN", ""), end)
    except (HTTPError, URLError, OSError, TimeoutError, TypeError, ValueError, KeyError, AttributeError) as error:
        # Report the error category only. Never print tokens, response bodies or raw country metrics.
        reason = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
        sys.exit(f"Could not validate the GA4 report ({reason}). Previous map retained.")
