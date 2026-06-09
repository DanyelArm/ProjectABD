from . import run_explain, print_explain


def run(db):
    pipeline = [
        {
            "$group": {
                "_id": "$state_id",
                "state_name": {"$first": "$state_name"},
                "total_population": {"$sum": "$population"},
            }
        },
        {"$match": {"total_population": {"$gt": 10_000_000}}},
        {"$sort": {"total_population": -1}},
    ]

    explain_doc = run_explain(db, pipeline)
    print_explain("req_a — states with population > 10M", explain_doc)

    results = list(db["zips"].aggregate(pipeline))
    print(f"\n  {'State':<6} {'Name':<25} {'Population':>15}")
    print(f"  {'-'*6} {'-'*25} {'-'*15}")
    for r in results:
        print(f"  {r['_id']:<6} {r['state_name']:<25} {r['total_population']:>15,}")
    print(f"\n  {len(results)} states with population over 10 million.")
