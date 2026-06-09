from . import run_explain, print_explain


def run(db):
    # Sort by (state, city_population DESC) before $group so $first/$last
    # reliably pick the largest and smallest city respectively.
    pipeline = [
        {
            "$group": {
                "_id": {"state_id": "$state_id", "city": "$city"},
                "state_name": {"$first": "$state_name"},
                "city_population": {"$sum": "$population"},
            }
        },
        {"$sort": {"_id.state_id": 1, "city_population": -1}},
        {
            "$group": {
                "_id": "$_id.state_id",
                "state_name": {"$first": "$state_name"},
                "largest_city": {"$first": "$_id.city"},
                "largest_pop": {"$first": "$city_population"},
                "smallest_city": {"$last": "$_id.city"},
                "smallest_pop": {"$last": "$city_population"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    explain_doc = run_explain(db, pipeline)
    print_explain("req_c — largest and smallest city per state", explain_doc)

    results = list(db["zips"].aggregate(pipeline))
    print(f"\n  {'State':<6} {'Largest City':<25} {'Pop':>12}   {'Smallest City':<25} {'Pop':>12}")
    print(f"  {'-'*6} {'-'*25} {'-'*12}   {'-'*25} {'-'*12}")
    for r in results:
        print(
            f"  {r['_id']:<6} {r['largest_city']:<25} {r['largest_pop']:>12,}   "
            f"{r['smallest_city']:<25} {r['smallest_pop']:>12,}"
        )
