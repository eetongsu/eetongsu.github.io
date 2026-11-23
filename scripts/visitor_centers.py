"""Resolve GA4 city names against a local GeoNames gazetteer, without sending visitor data anywhere."""
from collections import defaultdict
import csv
import io
import unicodedata
from zipfile import ZipFile


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())


def city_centers(places, folder):
    wanted = {(code, normalize(city)) for code, city, region in places}
    if not wanted:
        return {}
    countries = {code for code, name in wanted}
    regions = {}
    with (folder / "admin1CodesASCII.txt").open(encoding="utf-8") as stream:
        for key, local, ascii_name, _ in csv.reader(stream, delimiter="\t", quoting=csv.QUOTE_NONE):
            regions[key] = {normalize(local), normalize(ascii_name), normalize(key.split(".")[-1])}

    candidates = defaultdict(list)
    with ZipFile(folder / "cities500.zip") as archive, archive.open("cities500.txt") as raw:
        for row in csv.reader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
            code = row[8]
            if code not in countries:
                continue
            primary = {normalize(row[1]), normalize(row[2])}
            aliases = {normalize(name) for name in row[3].split(",") if name}
            for name in primary | aliases:
                key = (code, name)
                if key in wanted:
                    candidates[key].append((name in primary, code + "." + row[10], row[4], row[5]))

    centers = {}
    for place in places:
        code, city, region = place
        matches = candidates[code, normalize(city)]
        if region and region != "(not set)":
            matches = [r for r in matches if normalize(region) in regions.get(r[1], ())]
        primary = [r for r in matches if r[0]]
        points = {(round(float(lat), 2), round(float(lon), 2)) for _, _, lat, lon in primary or matches}
        if len(points) == 1:
            centers[place] = points.pop()
    return centers
