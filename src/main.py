from src.connection import get_db
from src.import_data import import_csv
from src.indexes import create_indexes
from src.queries import req_a, req_b, req_c, req_d, req_e, req_f


def main():
    print("Connecting to MongoDB...")
    db = get_db()
    print("Connected.\n")

    print("--- Import ---")
    import_csv(db)

    print("\n--- Indexes ---")
    create_indexes(db)

    print("\n\n=== Requirement A: States with total population over 10 million ===")
    req_a.run(db)

    print("\n\n=== Requirement B: Average city population by state ===")
    req_b.run(db)

    print("\n\n=== Requirement C: Largest and smallest city in each state ===")
    req_c.run(db)

    print("\n\n=== Requirement D: Largest and smallest county in each state ===")
    req_d.run(db)

    print("\n\n=== Requirement E: Nearest 10 ZIP codes to Willis Tower ===")
    req_e.run(db)

    print("\n\n=== Requirement F: Total population 50–200 km around the Statue of Liberty ===")
    req_f.run(db)


if __name__ == "__main__":
    main()
