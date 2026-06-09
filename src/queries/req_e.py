from . import run_explain, print_explain

# Willis Tower, Chicago
WILLIS_TOWER = [-87.635918, 41.878876]  # [longitude, latitude]


def run(db):
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": WILLIS_TOWER},
                "distanceField": "distance_meters",
                "spherical": True,
            }
        },
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "zip": 1,
                "city": 1,
                "state_id": 1,
                "distance_meters": 1,
            }
        },
    ]

    explain_doc = run_explain(db, pipeline)
    print_explain("req_e — nearest 10 ZIPs to Willis Tower", explain_doc)

    results = list(db["zips"].aggregate(pipeline))
    print(f"\n  {'ZIP':<8} {'City':<25} {'State':<6} {'Distance':>12}")
    print(f"  {'-'*8} {'-'*25} {'-'*6} {'-'*12}")
    for r in results:
        km = r["distance_meters"] / 1000
        print(f"  {r['zip']:<8} {r['city']:<25} {r['state_id']:<6} {km:>11.2f} km")
