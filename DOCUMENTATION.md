# Technical Documentation: US Zips MongoDB Analysis

This document covers the design decisions, failed approaches, lessons learned, and index performance analysis for each query. It is written to support a walkthrough of the code in a live exam or code review.

---

## Dataset

**Source:** [simplemaps.com/data/us-zips](https://simplemaps.com/data/us-zips) — free tier CSV, ~33,000 rows.

**Key fields used:**

| Field | Type | Notes |
|---|---|---|
| `zip` | string | 5-digit ZIP code — used as `_id` |
| `lat` / `lng` | float | ZIP centroid coordinates |
| `city` | string | City name |
| `state_id` | string | 2-letter state abbreviation |
| `state_name` | string | Full state name |
| `population` | int | Population estimate for the ZIP area |
| `density` | float | Population per km² |
| `county_name` | string | Primary county for this ZIP |
| `county_fips` | string | County FIPS code |

**GeoJSON transformation:**

A `location` field is added to every document during import:

```python
"location": {
    "type": "Point",
    "coordinates": [lng, lat]
}
```

The order is **longitude first, then latitude** — this follows the GeoJSON standard (RFC 7946) and is what MongoDB requires. It is the opposite of the intuitive (lat, lng) order used by most mapping APIs. Getting this wrong produces silently incorrect results: queries run without errors but match ZIPs in the wrong hemisphere.

---

## Architecture Decisions

**Why pymongo directly, not an ODM?**
Aggregation pipelines map directly to Python dicts. Using Motor/MongoEngine would add abstraction that obscures what the pipeline actually does — unhelpful when the goal is to understand and explain the queries.

**Why Docker for MongoDB?**
A `docker compose up -d` gives a clean, reproducible instance that matches what you would get on any other machine. The named volume `mongo_data` persists data across container restarts. Swapping to Atlas requires only changing `MONGO_URI` in `.env`.

**Why upsert on import?**
`UpdateOne(..., upsert=True)` makes the import idempotent — running the script twice does not duplicate data. The `_id` is set to the ZIP code string, which is already unique in the dataset, so the upsert key is the natural primary key.

---

## Index Design

Five indexes are created, each chosen for a specific query pattern.

### 1. `idx_location_2dsphere` — `{ location: "2dsphere" }`

MongoDB **requires** a 2dsphere index to use `$geoNear`, `$near`, or `$geoWithin` with spherical geometry. Without it, the query fails with:
> "unable to find index for $geoNear query"

This index encodes the GeoJSON `Point` geometry into a B-tree-adjacent structure that supports range queries on a sphere. It increases insert time by roughly 2–3x but turns a full collection scan of 33k documents (for a proximity search) into an O(log n) index lookup.

**Serves:** req_e, req_f

### 2. `idx_state_city` — `{ state_id: 1, city: 1 }`

The two-stage grouping in req_b and req_c groups first by `(state_id, city)`. A compound index on these two fields allows MongoDB to satisfy the initial `$group` stage with an index scan rather than loading every document field. Because documents with the same `(state_id, city)` pair are adjacent in the index, the engine can accumulate sums without random I/O.

**Serves:** req_b, req_c

### 3. `idx_state_county` — `{ state_id: 1, county_name: 1 }`

Mirrors the above for county-level grouping. The `county_name` field has low cardinality per state (most states have 50–100 counties), so this index is narrow and cheap to maintain.

**Serves:** req_d

### 4. `idx_state_id` — `{ state_id: 1 }`

State-level group and filter in req_a. Single-field index on the group key. With only 50 distinct values this index is small; its benefit is reducing the I/O for a grouped scan over 33k documents.

**Serves:** req_a

### 5. `idx_population_desc` — `{ population: -1 }`

Population is queried in sort and filter contexts (the post-group `$match` in req_a does not use this because the `$match` is on a computed group field, not a document field). This index is most useful for ad-hoc `find` queries and ensures the optimizer has a population-ordered scan available.

**Serves:** general / req_a (partial)

---

## Requirement A — States with total population over 10 million

### Approach

Group all ZIP documents by `state_id`, summing `population` to get the state total. Filter states above 10 million, sort descending.

```python
pipeline = [
    {"$group": {
        "_id": "$state_id",
        "state_name": {"$first": "$state_name"},
        "total_population": {"$sum": "$population"}
    }},
    {"$match": {"total_population": {"$gt": 10_000_000}}},
    {"$sort": {"total_population": -1}}
]
```

### What was considered

An alternative would push the `$match` to before `$group` to filter individual ZIPs first. That would not work here because there are no individual ZIP rows whose `population` field exceeds 10 million — the filter only makes sense on the aggregated state total.

### explain() analysis

The winning plan for the `$group` stage is typically `COLLSCAN` or `IXSCAN` on `idx_state_id`. MongoDB's aggregation optimizer can use the index to order the scan by `state_id`, which makes the hash-based `$group` more cache-friendly. The `$match` after `$group` does not use an index because it filters on a computed field, not an indexed document field.

**Expected result:** ~10 states (California, Texas, Florida, New York, Pennsylvania, Illinois, Ohio, Georgia, North Carolina, Michigan).

---

## Requirement B — Average city population by state

### Initial approach (incorrect)

First instinct: group by `state_id` and use `$avg` on the `population` field directly.

```python
# WRONG
{"$group": {"_id": "$state_id", "avg": {"$avg": "$population"}}}
```

**Why this is wrong:** A city like Chicago spans roughly 60 ZIP codes. If you average ZIP-level populations, Chicago contributes 60 separate values to the average, each a small fraction of the city's total. This inflates the count of "cities" in the average — Chicago is counted as 60 cities instead of one. Smaller cities with only one ZIP code are proportionally over-represented. The result is statistically meaningless.

### Correct approach (two-stage grouping)

Stage 1 collapses all ZIP codes belonging to the same `(state_id, city)` into a single city-level total. Stage 2 then averages those totals per state.

```python
pipeline = [
    # Stage 1: ZIP → city totals
    {"$group": {
        "_id": {"state_id": "$state_id", "city": "$city"},
        "city_population": {"$sum": "$population"}
    }},
    # Stage 2: city totals → state average
    {"$group": {
        "_id": "$_id.state_id",
        "avg_city_population": {"$avg": "$city_population"}
    }},
    {"$sort": {"avg_city_population": -1}}
]
```

### explain() analysis

Stage 1 uses the `idx_state_city` compound index, reducing the number of document reads by grouping on an already-indexed prefix. Stage 2 operates on the ~30k intermediate documents produced by Stage 1 and has no further index to use — this is expected behavior for a second `$group` stage.

---

## Requirement C — Largest and smallest city in each state

### Initial approach (invalid)

Attempted to use `$sort` inside `$group`:

```python
# INVALID — MongoDB does not support $sort inside $group
{"$group": {
    "_id": "$state_id",
    "cities": {"$push": {"$sort": {"city_population": -1}, "city": "$_id.city"}}
}}
```

MongoDB raises: *"unknown group operator '$sort'"*. Sorting within `$group` is not a valid accumulator.

### Correct approach (sort before group)

The canonical MongoDB pattern is to sort the documents into the desired order **before** the `$group` stage, then use `$first` and `$last` accumulators to pick the extremes. After sorting by `(state_id ASC, city_population DESC)`, the first document for each state in the group is the highest-population city, and the last is the lowest.

```python
pipeline = [
    # Stage 1: city-level totals (same as req_b)
    {"$group": {
        "_id": {"state_id": "$state_id", "city": "$city"},
        "city_population": {"$sum": "$population"}
    }},
    # Stage 2: sort so $first/$last are meaningful
    {"$sort": {"_id.state_id": 1, "city_population": -1}},
    # Stage 3: pick first (largest) and last (smallest) per state
    {"$group": {
        "_id": "$_id.state_id",
        "largest_city": {"$first": "$_id.city"},
        "largest_pop": {"$first": "$city_population"},
        "smallest_city": {"$last": "$_id.city"},
        "smallest_pop": {"$last": "$city_population"}
    }},
    {"$sort": {"_id": 1}}
]
```

### explain() analysis

The `$sort` after the first `$group` works on intermediate in-memory results and does not use an index. This is acceptable — the intermediate set is small (~30k entries). The 2dsphere and state-level indexes are not relevant here.

---

## Requirement D — Largest and smallest county in each state

### Approach

Identical pattern to requirement C, substituting `county_name` for `city`. The `idx_state_county` compound index supports the initial group stage.

One edge case: a small number of ZIP codes have a blank or missing `county_name`. These appear as a group with an empty string key. In practice they represent ZIP codes that span county boundaries or belong to independent cities (common in Virginia). The results include them with the empty string label — this is the honest representation of what the data contains.

### explain() analysis

Stage 1 group on `(state_id, county_name)` can use the `idx_state_county` index scan. Stage 2 sort and final group operate on ~3,000 intermediate county documents (much smaller than the city intermediates in req_c).

---

## Requirement E — Nearest 10 ZIP codes to Willis Tower

**Coordinates:** Willis Tower is at latitude 41.878876, longitude -87.635918.
**GeoJSON Point:** `[-87.635918, 41.878876]` — longitude first.

### Initial approach

Used a `find()` query with `$near`:

```python
collection.find({"location": {"$near": {"$geometry": {"type": "Point",
    "coordinates": [-87.635918, 41.878876]}}}}).limit(10)
```

This works and returns correct results but capturing the `explain()` output is awkward — `find().explain()` returns a different structure than `aggregate().explain()`, and `$near` does not populate `distanceField` so you cannot print distances without a separate calculation.

### Final approach ($geoNear aggregation)

`$geoNear` as the first pipeline stage solves both problems: it populates a `distanceField` on each document, and the explain is captured uniformly via `db.command("explain", ...)`.

```python
pipeline = [
    {"$geoNear": {
        "near": {"type": "Point", "coordinates": [-87.635918, 41.878876]},
        "distanceField": "distance_meters",
        "spherical": True,
        "limit": 10
    }},
    {"$project": {"zip": 1, "city": 1, "state_id": 1, "distance_meters": 1, "_id": 0}}
]
```

**`$geoNear` must be the first stage** — MongoDB raises an error if any stage precedes it in the pipeline.

**`spherical: true`** means distances are computed as great-circle (haversine) distances on the Earth's surface, reported in **meters**. Divide by 1000 to convert to km.

### explain() analysis

The winning plan shows `GEO_NEAR_2DSPHERE`, confirming the `idx_location_2dsphere` index is used. Documents examined is typically 10–20 (only the nearest cluster is accessed). Without the index the query would require a full collection scan to compute distances for all 33k documents.

**Sanity check:** All 10 results should be Chicago-area ZIP codes starting with `606xx`, with the nearest under 1 km from the tower.

---

## Requirement F — Total population 50–200 km from the Statue of Liberty

**Coordinates:** Statue of Liberty at latitude 40.689247, longitude -74.044502.
**GeoJSON Point:** `[-74.044502, 40.689247]`
**Ring:** minDistance 50,000 m (50 km), maxDistance 200,000 m (200 km).

### Interpretation

"Around" is interpreted as: all ZIP codes whose centroid coordinates fall within the annulus bounded by 50 km and 200 km from the Statue of Liberty. Distance is great-circle distance. This covers much of New Jersey, southern New York state, parts of Connecticut, Pennsylvania, and Delaware.

### Approach

`$geoNear` with `minDistance` and `maxDistance`, followed by `$group` to sum `population`.

```python
pipeline = [
    {"$geoNear": {
        "near": {"type": "Point", "coordinates": [-74.044502, 40.689247]},
        "distanceField": "distance_meters",
        "minDistance": 50_000,
        "maxDistance": 200_000,
        "spherical": True
    }},
    {"$group": {
        "_id": None,
        "total_population": {"$sum": "$population"},
        "zip_count": {"$sum": 1}
    }}
]
```

The `$group` stage with `_id: null` is the standard MongoDB pattern for a full-set aggregate — equivalent to SQL's `SELECT SUM(...)` with no `GROUP BY`.

### explain() analysis

`$geoNear` with bounded distance uses the 2dsphere index to efficiently identify only the documents within the ring, rather than computing distances for all 33k ZIPs. The total docs examined is the number of ZIPs within the ring, not the full 33k. This is the key performance benefit of the 2dsphere index for range queries.

**Expected result:** Hundreds of ZIPs, total population in the tens of millions.

---

## explain() Structure Notes

The explain document returned by MongoDB changes shape depending on the query type:

| Query type | Path to executionStats |
|---|---|
| `find()` | `result["executionStats"]` |
| `aggregate()` with simple pipeline | `result["stages"][0]["$cursor"]["executionStats"]` |
| `aggregate()` with `$geoNear` | `result["stages"][0]["$geoNearCursor"]["executionStats"]` |

The helper in `src/queries/__init__.py` handles all three paths so each requirement module does not need to know which path to follow.

---

## Performance Summary

These figures are representative; actual times vary by machine and whether the MongoDB page cache is warm.

| Req | Description | Winning Plan | Docs Examined | Keys Examined | Time (ms) |
|---|---|---|---|---|---|
| A | State population totals | COLLSCAN | ~33,000 | 0 | ~20 |
| B | Avg city pop by state | COLLSCAN | ~33,000 | 0 | ~35 |
| C | Largest/smallest city | COLLSCAN | ~33,000 | 0 | ~60 |
| D | Largest/smallest county | COLLSCAN | ~33,000 | 0 | ~25 |
| E | Nearest ZIPs (Willis Tower) | GEO_NEAR_2DSPHERE | 10–20 | 10–20 | 1–5 |
| F | Population ring (Statue of Liberty) | GEO_NEAR_2DSPHERE | ~2,000–4,000 | varies | 5–20 |

**Key observation:** Requirements A–D must read most or all documents because the aggregation groups every ZIP code. The indexes help order the scan but cannot reduce document reads below the full set. Requirements E and F benefit dramatically from the 2dsphere index — they examine only the geometrically relevant documents.

**Note on MongoDB 7 explain output:** The top-level `executionStages.stage` for an aggregation pipeline is often `PROJECTION_SIMPLE` or `PROJECTION_DEFAULT` — a thin wrapper added by the query planner. The actual scan stage (`COLLSCAN`, `IXSCAN`, `GEO_NEAR_2DSPHERE`) sits one level deeper under `inputStage`. The reporting helper in `src/queries/__init__.py` descends through these passthrough stages automatically to surface the meaningful stage name.

---

## Key Points for Exam Defense

1. **Two-stage grouping (req_b, c, d):** A city spans multiple ZIP codes. Averaging ZIP populations gives the wrong answer. The correct approach aggregates ZIPs to city totals first, then averages the totals.

2. **Sort before group (req_c, d):** MongoDB does not allow `$sort` as a `$group` accumulator. The pipeline must sort documents *before* the `$group` stage; `$first` and `$last` then pick the correct extremes.

3. **GeoJSON coordinate order:** `[longitude, latitude]`, not `[latitude, longitude]`. MongoDB follows the GeoJSON RFC 7946 spec. Swapping them produces wrong query results silently — Chicago would appear near the coast of West Africa.

4. **$geoNear must be the first pipeline stage:** MongoDB enforces this constraint. You cannot filter or project before `$geoNear`. Post-filtering must come after.

5. **Distances in meters:** When `spherical: true`, `$geoNear` returns distances as great-circle meters on a WGS84 sphere. `minDistance`/`maxDistance` are also in meters. Convert to km by dividing by 1000.

6. **explain() path differs by query type:** The path to `executionStats` inside the explain document is different for `find` vs. `aggregate`, and for pipelines that start with `$geoNear`. A robust helper function must check all three paths.
