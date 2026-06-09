import csv
import os
from pymongo import UpdateOne

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "uszips.csv")
BATCH_SIZE = 1000


def _build_doc(row):
    def to_int(val):
        try:
            return int(float(val)) if val else 0
        except ValueError:
            return 0

    def to_float(val):
        try:
            return float(val) if val else 0.0
        except ValueError:
            return 0.0

    lng = to_float(row.get("lng"))
    lat = to_float(row.get("lat"))

    return {
        "_id": row["zip"],
        "zip": row["zip"],
        "lat": lat,
        "lng": lng,
        "city": row.get("city", ""),
        "state_id": row.get("state_id", ""),
        "state_name": row.get("state_name", ""),
        "population": to_int(row.get("population")),
        "density": to_float(row.get("density")),
        "county_fips": row.get("county_fips", ""),
        "county_name": row.get("county_name", ""),
        "location": {
            "type": "Point",
            "coordinates": [lng, lat],  # GeoJSON: [longitude, latitude]
        },
    }


def import_csv(db, csv_path=None):
    collection = db["zips"]

    if collection.estimated_document_count() > 0:
        print(f"Collection already populated ({collection.estimated_document_count()} docs). Skipping import.")
        return

    path = csv_path or DEFAULT_CSV
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found at {path}.\n"
            "Download uszips.csv from https://simplemaps.com/data/us-zips and place it in data/"
        )

    ops = []
    total = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = _build_doc(row)
            ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True))
            if len(ops) >= BATCH_SIZE:
                result = collection.bulk_write(ops)
                total += result.upserted_count + result.modified_count
                ops = []

    if ops:
        result = collection.bulk_write(ops)
        total += result.upserted_count + result.modified_count

    print(f"Import complete. {collection.estimated_document_count()} documents in collection.")
