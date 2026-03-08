"""
adaptive_logic.py - Adaptive Testing Algorithm
Implements a simplified 1-Parameter IRT-inspired ability tracking system.

Core idea:
  - Ability score starts at 0.5 (mid-range).
  - Correct answer  → ability_score += 0.1
  - Incorrect answer → ability_score -= 0.1
  - Score is always clamped to [0.1, 1.0].
  - Next question is the one whose difficulty is CLOSEST to the current ability score
    that hasn't already been answered in this session.
"""

from bson import ObjectId
from app.database import get_questions_collection, get_sessions_collection

# Constants
ABILITY_MIN: float = 0.1
ABILITY_MAX: float = 1.0
CORRECT_DELTA: float = 0.1
INCORRECT_DELTA: float = 0.1
MAX_QUESTIONS: int = 10


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a float value between min_val and max_val."""
    return max(min_val, min(max_val, value))


def update_ability_score(current_score: float, is_correct: bool) -> float:
    """
    Update and return the new ability score after an answer.

    Args:
        current_score: The student's score before this answer.
        is_correct:    Whether the submitted answer was correct.

    Returns:
        Updated ability score clamped to [ABILITY_MIN, ABILITY_MAX].
    """
    delta = CORRECT_DELTA if is_correct else -INCORRECT_DELTA
    return round(clamp(current_score + delta, ABILITY_MIN, ABILITY_MAX), 2)


def select_next_question(ability_score: float, answered_ids: list[str]) -> dict | None:
    """
    Select the next question whose difficulty is closest to the student's ability score.

    Args:
        ability_score: Current ability estimate.
        answered_ids:  List of question ObjectId strings already answered.

    Returns:
        A question document dict, or None if no questions remain.
    """
    questions_col = get_questions_collection()

    # Exclude already-answered questions
    excluded = [ObjectId(qid) for qid in answered_ids if ObjectId.is_valid(qid)]

    pipeline = [
        {"$match": {"_id": {"$nin": excluded}}},
        # Compute absolute distance between question difficulty and ability score
        {
            "$addFields": {
                "diff_distance": {
                    "$abs": {"$subtract": ["$difficulty", ability_score]}
                }
            }
        },
        {"$sort": {"diff_distance": 1}},
        {"$limit": 1},
    ]

    results = list(questions_col.aggregate(pipeline))
    return results[0] if results else None


def get_session(user_id: str) -> dict | None:
    """Fetch a user session by user_id string."""
    sessions_col = get_sessions_collection()
    return sessions_col.find_one({"user_id": user_id})


def create_session(user_id: str) -> dict:
    """
    Create and persist a new blank session document.

    Returns the newly created session dict.
    """
    sessions_col = get_sessions_collection()
    session = {
        "user_id": user_id,
        "ability_score": 0.5,          # IRT starting point
        "questions_answered": [],       # List of question _id strings answered
        "correct_count": 0,
        "topics_missed": [],            # Topics where user answered incorrectly
        "difficulty_history": [],       # Difficulty of each question answered
    }
    sessions_col.insert_one(session)
    return session


def record_answer(
    user_id: str,
    question: dict,
    is_correct: bool,
    new_ability: float,
) -> dict:
    """
    Persist the result of a submitted answer to the session document.

    Args:
        user_id:     Session owner.
        question:    The full question document from MongoDB.
        is_correct:  Result of the answer check.
        new_ability: Updated ability score after this answer.

    Returns:
        The updated session document.
    """
    sessions_col = get_sessions_collection()

    update_ops: dict = {
        "$set": {"ability_score": new_ability},
        "$push": {
            "questions_answered": str(question["_id"]),
            "difficulty_history": question["difficulty"],
        },
    }

    if is_correct:
        update_ops["$inc"] = {"correct_count": 1}
    else:
        # Record the missed topic (avoid duplicates via $addToSet)
        update_ops["$addToSet"] = {"topics_missed": question["topic"]}

    sessions_col.update_one({"user_id": user_id}, update_ops)
    return sessions_col.find_one({"user_id": user_id})  # type: ignore[return-value]


def is_test_complete(session: dict) -> bool:
    """Return True if the student has answered the required number of questions."""
    return len(session.get("questions_answered", [])) >= MAX_QUESTIONS
