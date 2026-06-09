from . import run_explain, print_explain


def run(db):
    pipeline = [
        {
            "$group": {
                "_id": {"state_id": "$state_id", "county_name": "$county_name"},
                "state_name": {"$first": "$state_name"},
                "county_population": {"$sum": "$population"},
            }
        },
        {"$sort": {"_id.state_id": 1, "county_population": -1}},
        {
            "$group": {
                "_id": "$_id.state_id",
                "state_name": {"$first": "$state_name"},
                "largest_county": {"$first": "$_id.county_name"},
                "largest_pop": {"$first": "$county_population"},
                "smallest_county": {"$last": "$_id.county_name"},
                "smallest_pop": {"$last": "$county_population"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    explain_doc = run_explain(db, pipeline)
    print_explain("req_d — largest and smallest county per state", explain_doc)

    results = list(db["zips"].aggregate(pipeline))
    print(f"\n  {'State':<6} {'Largest County':<30} {'Pop':>12}   {'Smallest County':<30} {'Pop':>12}")
    print(f"  {'-'*6} {'-'*30} {'-'*12}   {'-'*30} {'-'*12}")
    for r in results:
        print(
            f"  {r['_id']:<6} {r['largest_county']:<30} {r['largest_pop']:>12,}   "
            f"{r['smallest_county']:<30} {r['smallest_pop']:>12,}"
        )
