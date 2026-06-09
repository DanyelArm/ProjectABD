from pymongo import ASCENDING, DESCENDING, GEOSPHERE


def create_indexes(db):
    col = db["zips"]
    existing = set(col.index_information().keys())

    indexes = [
        ([("location", GEOSPHERE)], "idx_location_2dsphere"),
        ([("state_id", ASCENDING), ("city", ASCENDING)], "idx_state_city"),
        ([("state_id", ASCENDING), ("county_name", ASCENDING)], "idx_state_county"),
        ([("state_id", ASCENDING)], "idx_state_id"),
        ([("population", DESCENDING)], "idx_population_desc"),
    ]

    for key, name in indexes:
        if name in existing:
            print(f"  Index already exists: {name}")
        else:
            col.create_index(key, name=name)
            print(f"  Created index: {name}")
