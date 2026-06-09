from . import run_explain, print_explain


def run(db):
    # Stage 1: sum ZIP-level populations to get each city's total population.
    # Stage 2: average those city totals per state.
    # A naive single-stage $avg on ZIP populations would undercount cities with many ZIPs.
    pipeline = [
        {
            "$group": {
                "_id": {"state_id": "$state_id", "city": "$city"},
                "state_name": {"$first": "$state_name"},
                "city_population": {"$sum": "$population"},
            }
        },
        {
            "$group": {
                "_id": "$_id.state_id",
                "state_name": {"$first": "$state_name"},
                "avg_city_population": {"$avg": "$city_population"},
            }
        },
        {"$sort": {"avg_city_population": -1}},
    ]

    explain_doc = run_explain(db, pipeline)
    print_explain("req_b — average city population by state", explain_doc)

    results = list(db["zips"].aggregate(pipeline))
    print(f"\n  {'State':<6} {'Name':<25} {'Avg City Pop':>15}")
    print(f"  {'-'*6} {'-'*25} {'-'*15}")
    for r in results:
        print(f"  {r['_id']:<6} {r['state_name']:<25} {r['avg_city_population']:>15,.0f}")
