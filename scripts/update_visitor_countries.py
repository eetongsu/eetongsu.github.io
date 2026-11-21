"""Publish coarse country ranges from a single GA4 report. Raw rows stay in memory."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "visitor-countries.json"


def report_query(end):
    return {
        "dateRanges": [{"startDate": (end - timedelta(days=89)).isoformat(),
                        "endDate": end.isoformat()}],
        "dimensions": [{"name": "countryId"}],
        "metrics": [{"name": "activeUsers"}],
        "dimensionFilter": {"filter": {"fieldName": "hostName", "stringFilter": {
            "matchType": "EXACT", "value": "eetongsu.github.io"}}},
        "metricFilter": {"filter": {"fieldName": "activeUsers", "numericFilter": {
            "operation": "GREATER_THAN_OR_EQUAL", "value": {"int64Value": "5"}}}},
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
        if count >= 5:
            countries[code] = "50+" if count >= 50 else "20–49" if count >= 20 else "5–19"
    return {"end_date": end.isoformat(), "countries": dict(sorted(countries.items()))}


def refresh(property_id, access_token, end, path=OUTPUT):
    if not re.fullmatch(r"[1-9][0-9]*", property_id) or not access_token:
        raise ValueError("Missing analytics configuration.")
    endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    request = Request(endpoint, data=json.dumps(report_query(end)).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + access_token})
    with urlopen(request, timeout=45) as response:
        report = json.load(response)
    snapshot = public_snapshot(report, end)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


if __name__ == "__main__":
    end = datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)
    try:
        refresh(os.environ.get("GA4_PROPERTY_ID", ""), os.environ.get("GA4_ACCESS_TOKEN", ""), end)
    except (HTTPError, URLError, OSError, TimeoutError, TypeError, ValueError, KeyError, AttributeError) as error:
        # Report the error category only. Never print tokens, response bodies or raw country metrics.
        reason = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
        sys.exit(f"Could not validate the GA4 report ({reason}). Previous map retained.")
