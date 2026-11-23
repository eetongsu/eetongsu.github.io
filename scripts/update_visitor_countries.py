"""Publish coarse city and country ranges from cumulative GA4 reports. Raw rows stay in memory."""
import json
import os
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path
from visitor_centers import city_centers
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "visitor-countries.json"
# The cumulative map went live at 16:48:23 in the GA4 property's New York time.
# GA4 reports event times by minute, so omit the mixed rollout minute.
TRACKING_START = datetime(2026, 11, 21, 16, 49)
BANDS = ("1–4", "5–19", "20–49", "50+")


CITY_DIMENSIONS = ("countryId", "cityId", "city", "region")


def report_query(end, dimensions=("countryId",)):
    if end < TRACKING_START.date():
        raise ValueError("End date precedes the first day of collection.")
    return {
        "dateRanges": [{"startDate": TRACKING_START.date().isoformat(),
                        "endDate": end.isoformat()}],
        "dimensions": [{"name": name} for name in dimensions],
        "metrics": [{"name": "activeUsers"}],
        "dimensionFilter": {"andGroup": {"expressions": [
            {"filter": {"fieldName": "hostName", "stringFilter": {
                "matchType": "EXACT", "value": "eetongsu.github.io"}}},
            {"filter": {"fieldName": "eventName", "stringFilter": {
                "matchType": "EXACT", "value": "page_view"}}},
            {"filter": {"fieldName": "dateHourMinute", "numericFilter": {
                "operation": "GREATER_THAN_OR_EQUAL",
                "value": {"int64Value": TRACKING_START.strftime("%Y%m%d%H%M")}}}},
        ]}},
        "metricFilter": {"filter": {"fieldName": "activeUsers", "numericFilter": {
            "operation": "GREATER_THAN_OR_EQUAL", "value": {"int64Value": "1"}}}},
        "limit": "250000",
    }


def report_rows(report, dimensions):
    if (report.get("dimensionHeaders") != [{"name": name} for name in dimensions]
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

    seen = set()
    for row in rows:
        values = tuple(d["value"] for d in row["dimensionValues"])
        if len(values) != len(dimensions):
            raise ValueError("Unexpected row shape.")
        metric, = row["metricValues"]
        value = metric["value"]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Invalid active user count.")
        if not re.fullmatch(r"[A-Z]{2}", values[0]) or values[0] == "ZZ":
            continue
        if values in seen:
            raise ValueError("Duplicate location.")
        seen.add(values)
        count = int(value)
        if count:
            yield values, BANDS[bisect_right((5, 20, 50), count)]


def public_snapshot(report, end):
    return {"start_date": TRACKING_START.date().isoformat(), "end_date": end.isoformat(),
            "countries": {code: band for (code,), band in report_rows(report, ("countryId",))}}


def add_locations(snapshot, previous, get_report, end, folder):
    rows = list(report_rows(get_report(report_query(end, CITY_DIMENSIONS)), CITY_DIMENSIONS))
    places = {(code, city, region) for (code, city_id, city, region), band in rows
              if city_id.isdecimal() and city_id != "0" and city and city != "(not set)"}
    centers = city_centers(places, folder)
    cities = previous.get("cities", {}).copy()
    located = set()
    unresolved = {}
    for (code, city_id, city, region), band in rows:
        center = centers.get((code, city, region))
        item = cities.get(city_id)
        if center:
            item = {"city": city, "region": region if region != "(not set)" else "",
                    "country": code, "lat": center[0], "lon": center[1]}
        if item and item["country"] == code:
            if city_id in located:
                raise ValueError("Duplicate city ID.")
            cities[city_id] = {**item, "band": band}
            located.add(city_id)
        else:
            unresolved.setdefault(code, set()).add(city_id)

    city_countries = {cities[i]["country"] for i in located}
    totals = snapshot["countries"]
    country_only = {code: band for code, band in totals.items() if code not in city_countries}
    mixed = city_countries & unresolved.keys()
    if mixed:
        # Ask GA4 to deduplicate active users across all unlocated rows in these countries.
        ids = sorted({i for code in mixed for i in unresolved[code]})
        query = report_query(end)
        filters = query["dimensionFilter"]["andGroup"]["expressions"]
        filters.extend({"filter": {"fieldName": field, "inListFilter": {"values": values}}}
                       for field, values in (("countryId", sorted(mixed)), ("cityId", ids)))
        country_only.update(public_snapshot(get_report(query), end)["countries"])
    for code, band in previous.get("country_only", previous.get("countries", {})).items():
        if code not in totals and code not in city_countries:
            country_only.setdefault(code, band)
    snapshot["cities"] = dict(sorted(cities.items()))
    snapshot["country_only"] = dict(sorted(country_only.items()))


def refresh(property_id, access_token, end, path=OUTPUT, folder=None):
    if not re.fullmatch(r"[1-9][0-9]*", property_id) or not access_token:
        raise ValueError("Missing analytics configuration.")
    endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"

    def get_report(query):
        request = Request(endpoint, data=json.dumps(query).encode(), headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + access_token})
        with urlopen(request, timeout=45) as response:
            return json.load(response)

    snapshot = public_snapshot(get_report(report_query(end)), end)
    previous = {}
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("end_date") and date.fromisoformat(previous["end_date"]) > end:
            raise ValueError("A more recent snapshot already exists.")
    add_locations(snapshot, previous, get_report, end, folder)
    for code, band in previous.get("countries", {}).items():
        if not re.fullmatch(r"[A-Z]{2}", code) or code == "ZZ" or band not in BANDS:
            raise ValueError("Invalid archived country or band.")
        snapshot["countries"].setdefault(code, band)
    snapshot["countries"] = dict(sorted(snapshot["countries"].items()))
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


if __name__ == "__main__":
    end = datetime.now(ZoneInfo("America/New_York")).date()
    try:
        refresh(os.environ.get("GA4_PROPERTY_ID", ""), os.environ.get("GA4_ACCESS_TOKEN", ""), end,
                folder=Path(os.environ["VISITOR_GAZETTEER"]))
    except (HTTPError, URLError, OSError, TimeoutError, TypeError, ValueError, KeyError, AttributeError) as error:
        # Report the error category only. Never print tokens, response bodies or raw country metrics.
        reason = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
        sys.exit(f"Could not validate the GA4 report ({reason}). Previous map retained.")
