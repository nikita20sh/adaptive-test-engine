"""
seed_questions.py - Database Seeder
Reads questions from data/questions_seed.json and inserts them into MongoDB.

Usage:
    python scripts/seed_questions.py

Options:
    --reset   Drop the existing questions collection before seeding.
              Use this if you want a clean slate (e.g. after modifying the JSON).
"""

import json
import sys
import os
import argparse

# Allow imports from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from app.database import connect_db, get_questions_collection, close_db

load_dotenv()

SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "questions_seed.json")


def seed(reset: bool = False) -> None:
    """
    Load questions from the seed JSON and insert into MongoDB.

    Args:
        reset: If True, drops the collection before inserting.
    """
    connect_db()
    col = get_questions_collection()

    if reset:
        col.drop()
        print("[Seed] Existing 'questions' collection dropped.")

    # Load seed data
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        questions: list[dict] = json.load(f)

    # Skip questions that already exist (match on question text to avoid duplicates)
    new_questions = []
    for q in questions:
        exists = col.find_one({"question": q["question"]})
        if not exists:
            new_questions.append(q)

    if not new_questions:
        print("[Seed] All questions already exist in the database. Nothing to insert.")
        close_db()
        return

    result = col.insert_many(new_questions)
    print(f"[Seed] Successfully inserted {len(result.inserted_ids)} question(s).")

    # Create an index on difficulty for faster adaptive queries
    col.create_index("difficulty")
    col.create_index("topic")
    print("[Seed] Indexes created on 'difficulty' and 'topic' fields.")

    close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed GRE questions into MongoDB.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the questions collection before seeding.",
    )
    args = parser.parse_args()
    seed(reset=args.reset)
