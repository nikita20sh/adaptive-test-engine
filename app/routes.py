"""
routes.py - FastAPI Route Definitions
All API endpoints for the Adaptive Diagnostic Engine.
"""

import uuid
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from app import adaptive_logic as algo
from app.ai_plan import generate_study_plan
from app.models import (
    StartSessionResponse,
    NextQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    QuestionOut,
    StudyPlanResponse,
)

router = APIRouter()


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _question_to_out(q: dict) -> QuestionOut:
    """Convert a raw MongoDB question document to the API-safe QuestionOut model."""
    return QuestionOut(
        question_id=str(q["_id"]),
        question=q["question"],
        options=q["options"],
        topic=q["topic"],
        difficulty=q["difficulty"],
    )


# ──────────────────────────────────────────────
# POST /start-session
# ──────────────────────────────────────────────

@router.post("/start-session", response_model=StartSessionResponse, tags=["Session"])
def start_session() -> StartSessionResponse:
    """
    Create a new adaptive test session.

    Returns a unique user_id and the initial ability score of 0.5.
    Each call creates an isolated session — students can take the test multiple times.
    """
    user_id = str(uuid.uuid4())
    session = algo.create_session(user_id)

    return StartSessionResponse(
        user_id=session["user_id"],
        ability_score=session["ability_score"],
        message="Session created. Call GET /next-question?user_id=<id> to begin.",
    )


# ──────────────────────────────────────────────
# GET /next-question
# ──────────────────────────────────────────────

@router.get("/next-question", response_model=NextQuestionResponse, tags=["Session"])
def next_question(user_id: str = Query(..., description="Session user ID")) -> NextQuestionResponse:
    """
    Return the next adaptive question based on the student's current ability score.

    The question selected is the one with difficulty closest to ability_score
    that has not already been answered in this session.
    """
    session = algo.get_session(user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Call /start-session first.")

    if algo.is_test_complete(session):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Test complete ({algo.MAX_QUESTIONS} questions answered). "
                "Call GET /study-plan to retrieve your personalised learning plan."
            ),
        )

    answered_ids: list[str] = session.get("questions_answered", [])
    question = algo.select_next_question(session["ability_score"], answered_ids)

    if not question:
        raise HTTPException(status_code=404, detail="No more questions available in the question bank.")

    return NextQuestionResponse(
        question_id=str(question["_id"]),
        question=question["question"],
        options=question["options"],
        topic=question["topic"],
        difficulty=question["difficulty"],
        questions_answered=len(answered_ids),
        ability_score=session["ability_score"],
    )


# ──────────────────────────────────────────────
# POST /submit-answer
# ──────────────────────────────────────────────

@router.post("/submit-answer", response_model=SubmitAnswerResponse, tags=["Session"])
def submit_answer(payload: SubmitAnswerRequest) -> SubmitAnswerResponse:
    """
    Submit a student's answer and receive immediate feedback.

    Processing steps:
      1. Validate session and question exist.
      2. Check if question was already answered (prevent replay attacks).
      3. Compare submitted answer to correct answer.
      4. Update ability score using the IRT-inspired delta rule.
      5. Persist result and return the next question (if test not complete).
    """
    # ── Validate session ──
    session = algo.get_session(payload.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if algo.is_test_complete(session):
        raise HTTPException(
            status_code=400,
            detail="Test already complete. Retrieve your study plan at GET /study-plan.",
        )

    # ── Validate question ID format ──
    if not ObjectId.is_valid(payload.question_id):
        raise HTTPException(status_code=400, detail="Invalid question_id format.")

    # ── Fetch question from DB ──
    from app.database import get_questions_collection
    questions_col = get_questions_collection()
    question = questions_col.find_one({"_id": ObjectId(payload.question_id)})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    # ── Prevent duplicate submission ──
    if payload.question_id in session.get("questions_answered", []):
        raise HTTPException(status_code=409, detail="This question has already been answered in this session.")

    # ── Evaluate answer ──
    is_correct: bool = payload.answer.strip() == question["correct_answer"].strip()

    # ── Update ability score ──
    new_ability = algo.update_ability_score(session["ability_score"], is_correct)

    # ── Persist result ──
    updated_session = algo.record_answer(
        user_id=payload.user_id,
        question=question,
        is_correct=is_correct,
        new_ability=new_ability,
    )

    # ── Fetch next question (if test not yet complete) ──
    next_q_out: QuestionOut | None = None
    message: str | None = None

    if algo.is_test_complete(updated_session):
        message = (
            f"Test complete! You answered {algo.MAX_QUESTIONS} questions. "
            "Call GET /study-plan to get your personalised AI learning plan."
        )
    else:
        answered_ids: list[str] = updated_session.get("questions_answered", [])
        next_q = algo.select_next_question(new_ability, answered_ids)
        if next_q:
            next_q_out = _question_to_out(next_q)

    return SubmitAnswerResponse(
        correct=is_correct,
        correct_answer=question["correct_answer"],
        updated_ability=new_ability,
        questions_answered=len(updated_session.get("questions_answered", [])),
        correct_count=updated_session.get("correct_count", 0),
        next_question=next_q_out,
        message=message,
    )


# ──────────────────────────────────────────────
# GET /study-plan
# ──────────────────────────────────────────────

@router.get("/study-plan", response_model=StudyPlanResponse, tags=["Study Plan"])
def study_plan(user_id: str = Query(..., description="Session user ID")) -> StudyPlanResponse:
    """
    Generate an AI-powered personalised study plan after test completion.

    Requirements:
      - Student must have answered at least 10 questions.
      - Calls OpenAI Chat Completions with a diagnostic summary.

    The plan is generated fresh on each call (not cached), enabling
    future iteration if the student retakes the test.
    """
    session = algo.get_session(user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    answered_count = len(session.get("questions_answered", []))
    if answered_count < algo.MAX_QUESTIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Study plan is available after {algo.MAX_QUESTIONS} questions. "
                f"You have answered {answered_count} so far."
            ),
        )

    # ── Compute diagnostic metrics ──
    correct_count: int = session.get("correct_count", 0)
    accuracy: float = round((correct_count / answered_count) * 100, 1)

    difficulty_history: list[float] = session.get("difficulty_history", [])
    max_difficulty: float = max(difficulty_history) if difficulty_history else 0.5

    topics_missed: list[str] = session.get("topics_missed", [])

    # ── Call OpenAI ──
    try:
        plan = generate_study_plan(
            topics_missed=topics_missed,
            max_difficulty=max_difficulty,
            accuracy=accuracy,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StudyPlanResponse(
        user_id=user_id,
        accuracy=accuracy,
        max_difficulty_reached=max_difficulty,
        topics_missed=topics_missed,
        study_plan=plan,
    )
