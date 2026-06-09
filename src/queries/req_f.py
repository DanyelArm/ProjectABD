from . import run_explain, print_explain

# Statue of Liberty
STATUE_OF_LIBERTY = [-74.044502, 40.689247]  # [longitude, latitude]

MIN_DISTANCE_M = 50_000   # 50 km
MAX_DISTANCE_M = 200_000  # 200 km


def run(db):
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": STATUE_OF_LIBERTY},
                "distanceField": "distance_meters",
                "minDistance": MIN_DISTANCE_M,
                "maxDistance": MAX_DISTANCE_M,
                "spherical": True,
            }
        },
        {
            "$group": {
                "_id": None,
                "total_population": {"$sum": "$population"},
                "zip_count": {"$sum": 1},
            }
        },
    ]

    explain_doc = run_explain(db, pipeline)
    print_explain("req_f — total population 50–200 km from Statue of Liberty", explain_doc)

    results = list(db["zips"].aggregate(pipeline))
    if results:
        r = results[0]
        print(f"\n  ZIP codes in range : {r['zip_count']:,}")
        print(f"  Total population   : {r['total_population']:,}")
    else:
        print("\n  No results returned.")
