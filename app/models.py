"""
models.py - Pydantic Data Models
Defines all request/response schemas used across the API.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Question Models
# ──────────────────────────────────────────────

class QuestionOut(BaseModel):
    """Outbound representation of a question (no correct answer exposed)."""
    question_id: str
    question: str
    options: list[str]
    topic: str
    difficulty: float


# ──────────────────────────────────────────────
# Session Models
# ──────────────────────────────────────────────

class StartSessionResponse(BaseModel):
    """Response returned when a new test session is created."""
    user_id: str
    ability_score: float
    message: str


class NextQuestionResponse(BaseModel):
    """Response returned for the next adaptive question."""
    question_id: str
    question: str
    options: list[str]
    topic: str
    difficulty: float
    questions_answered: int
    ability_score: float


# ──────────────────────────────────────────────
# Answer Submission Models
# ──────────────────────────────────────────────

class SubmitAnswerRequest(BaseModel):
    """Payload sent when a student submits an answer."""
    user_id: str = Field(..., description="The session's user ID")
    question_id: str = Field(..., description="MongoDB ObjectId of the question")
    answer: str = Field(..., description="The option text chosen by the student")


class SubmitAnswerResponse(BaseModel):
    """Response after processing a submitted answer."""
    correct: bool
    correct_answer: str
    updated_ability: float
    questions_answered: int
    correct_count: int
    next_question: Optional[QuestionOut] = None
    message: Optional[str] = None


# ──────────────────────────────────────────────
# Study Plan Models
# ──────────────────────────────────────────────

class StudyPlanResponse(BaseModel):
    """AI-generated personalised study plan returned after 10 questions."""
    user_id: str
    accuracy: float
    max_difficulty_reached: float
    topics_missed: list[str]
    study_plan: str
