"""
database.py - MongoDB Connection Management
Handles connection lifecycle and exposes collection accessors.
"""

import os
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from dotenv import load_dotenv

load_dotenv()

# Module-level client and db references (initialized on startup)
_client: MongoClient | None = None
_db: Database | None = None


def connect_db() -> None:
    """Establish connection to MongoDB using the URI from environment variables."""
    global _client, _db

    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "adaptive_engine")

    _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    # Validate connection immediately
    _client.admin.command("ping")
    _db = _client[db_name]

    print(f"[DB] Connected to MongoDB — database: '{db_name}'")


def close_db() -> None:
    """Close the MongoDB connection gracefully."""
    global _client
    if _client:
        _client.close()
        print("[DB] MongoDB connection closed.")


def get_db() -> Database:
    """Return the active database instance."""
    if _db is None:
        raise RuntimeError("Database is not connected. Call connect_db() first.")
    return _db


def get_questions_collection() -> Collection:
    """Return the 'questions' collection."""
    return get_db()["questions"]


def get_sessions_collection() -> Collection:
    """Return the 'user_sessions' collection."""
    return get_db()["user_sessions"]
