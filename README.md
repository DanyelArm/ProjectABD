# US Zips MongoDB Analysis

Statistical analysis of ~33,000 US ZIP codes using MongoDB aggregation pipelines and geospatial queries.

## Prerequisites

- Python 3.10+
- Docker + Docker Compose (or a MongoDB Atlas account)

## Setup

**1. Get the dataset**

Download `uszips.csv` from [simplemaps.com/data/us-zips](https://simplemaps.com/data/us-zips) (free tier) and place it in the `data/` folder.

**2. Configure environment**

```bash
cp .env.example .env
# Edit .env if needed (defaults work for Docker setup)
```

**3. Create a virtual environment and install dependencies**

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**4. Start MongoDB**

```bash
docker compose up -d
```

**5. Run the analysis**

```bash
python -m src.main
```

The first run imports the dataset (~33k documents) and creates indexes. Subsequent runs skip the import automatically.

## Using MongoDB Atlas instead of Docker

Set `MONGO_URI` in your `.env` file to your Atlas connection string:

```
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=usZipsDB
```

No other changes are needed.

## Project Structure

```
ProjectABD/
├── data/               ← place uszips.csv here (not committed)
├── src/
│   ├── connection.py   ← MongoDB connection helper
│   ├── import_data.py  ← CSV import with GeoJSON transformation
│   ├── indexes.py      ← index creation
│   ├── main.py         ← entry point
│   └── queries/
│       ├── req_a.py    ← states with population > 10M
│       ├── req_b.py    ← average city population by state
│       ├── req_c.py    ← largest and smallest city per state
│       ├── req_d.py    ← largest and smallest county per state
│       ├── req_e.py    ← nearest 10 ZIPs to Willis Tower
│       └── req_f.py    ← total population 50–200 km from Statue of Liberty
├── docker-compose.yml
├── requirements.txt
└── DOCUMENTATION.md
```

## Requirements Implemented

| | Description |
|---|---|
| **A** | States whose total ZIP-level population exceeds 10 million |
| **B** | Average city population per state (cities aggregated from ZIP codes first) |
| **C** | Largest and smallest city in each state by aggregated population |
| **D** | Largest and smallest county in each state by aggregated population |
| **E** | 10 nearest ZIP codes to Willis Tower, Chicago (41.878876, -87.635918) |
| **F** | Total population within the 50–200 km ring around the Statue of Liberty (40.689247, -74.044502) |

## Understanding the explain() output

Each query prints execution statistics before its results:

- **Winning plan stage** — the primary index operation used (e.g. `IXSCAN`, `GEO_NEAR_2DSPHERE`, `COLLSCAN`)
- **Docs examined** — number of documents read from disk
- **Keys examined** — number of index entries scanned
- **Execution time** — wall-clock time in milliseconds

For aggregation pipelines the first stage drives index use. A `COLLSCAN` on a `$group` pipeline is expected when there is no selective filter before the group stage; the index still benefits subsequent stages. For geospatial queries (`$geoNear`), `GEO_NEAR_2DSPHERE` confirms the 2dsphere index is active.

See `DOCUMENTATION.md` for a full discussion.
