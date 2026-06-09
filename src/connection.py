import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def get_db():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "usZipsDB")
    client = MongoClient(uri)
    client.admin.command("ping")
    return client[db_name]
