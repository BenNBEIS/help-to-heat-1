import bz2
import csv
import datetime
import pathlib

import httpx
from django.conf import settings

from help_to_heat.portal import models

DATA_DIR = settings.BASE_DIR / "temp-data"
CHUNK_SIZE = 16 * 1024


def save_url_in_chunks(url):
    decompressor = bz2.BZ2Decompressor()
    filename = pathlib.Path(url).stem
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Downloading to: {filepath}")  # noqa: T201
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
        with filepath.open("wb") as f:
            with httpx.stream("GET", url) as response:
                for chunk in response.iter_bytes(CHUNK_SIZE):
                    text = decompressor.decompress(chunk)
                    f.write(text)
    else:
        print(f"Skipping download: {filepath} already exists")  # noqa: T201

    sorted_filepath = DATA_DIR / "".join((filepath.stem, "-sorted", filepath.suffix))
    if not sorted_filepath.exists():
        print(f"Sorting to: {sorted_filepath}")  # noqa: T201
        with filepath.open("r") as f:
            lines = f.readlines()
        header = lines[0]
        lines = lines[1:]
        lines.sort()
        with sorted_filepath.open("w") as f:
            f.writelines([header])
            f.writelines(lines)
    else:
        print(f"Skipping sort: {sorted_filepath} already exists")  # noqa: T201
    return sorted_filepath


def read_rows(filepath):
    with filepath.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def get_latest_date():
    if models.EpcRating.objects.exists():
        latest_date = str(models.EpcRating.objects.latest("date").date)
        print(f"Resuming from {latest_date}")  # noqa: T201
    else:
        latest_date = str(datetime.date(1970, 1, 1))
        print("Starting from beginning")  # noqa: T201
    return latest_date


def write_rows(rows):
    print("Loading to database")  # noqa: T201
    latest_date = get_latest_date()
    for row in rows:
        if row["date"] >= latest_date:
            models.EpcRating.objects.update_or_create(
                uprn=row["uprn"],
                defaults={"rating": row["epc_rating"], "date": row["date"]},
            )
    print("Finished loading")  # noqa: T201
