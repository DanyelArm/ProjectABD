def run_explain(db, pipeline):
    return db.command(
        "explain",
        {"aggregate": "zips", "pipeline": pipeline, "cursor": {}},
        verbosity="executionStats",
    )


_PASSTHROUGH_STAGES = {"FETCH", "LIMIT", "PROJECTION_SIMPLE", "PROJECTION_DEFAULT", "SHARDING_FILTER"}


def _dig_stage(exec_stages):
    stage = exec_stages.get("stage", "N/A")
    if stage in _PASSTHROUGH_STAGES and "inputStage" in exec_stages:
        return _dig_stage(exec_stages["inputStage"])
    return stage


def _extract_stats(explain_doc):
    es = {}
    if "executionStats" in explain_doc:
        es = explain_doc["executionStats"]
    elif "stages" in explain_doc:
        for stage in explain_doc["stages"]:
            for key in ("$cursor", "$geoNearCursor"):
                if key in stage:
                    es = stage[key].get("executionStats", {})
                    break
            if es:
                break

    exec_stages = es.get("executionStages", {})
    winning_stage = _dig_stage(exec_stages)

    return {
        "winningPlan": winning_stage,
        "totalDocsExamined": es.get("totalDocsExamined", "N/A"),
        "totalKeysExamined": es.get("totalKeysExamined", "N/A"),
        "executionTimeMillis": es.get("executionTimeMillis", "N/A"),
    }


def print_explain(label, explain_doc):
    stats = _extract_stats(explain_doc)
    print(f"\n  [explain] {label}")
    print(f"    Winning plan stage : {stats['winningPlan']}")
    print(f"    Docs examined      : {stats['totalDocsExamined']}")
    print(f"    Keys examined      : {stats['totalKeysExamined']}")
    print(f"    Execution time     : {stats['executionTimeMillis']} ms")
