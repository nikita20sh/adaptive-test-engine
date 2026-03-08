"""
ai_plan.py - OpenAI Integration for Personalised Study Plan Generation
Sends diagnostic summary to the OpenAI Chat API and returns a structured study plan.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialise the OpenAI client (reads OPENAI_API_KEY from environment)
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The model to use — swap to "gpt-4o" if available on your account
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def build_prompt(
    topics_missed: list[str],
    max_difficulty: float,
    accuracy: float,
) -> str:
    """
    Build the diagnostic prompt sent to OpenAI.

    Args:
        topics_missed:  Topics where the student answered at least one question wrong.
        max_difficulty: Highest difficulty level reached during the test.
        accuracy:       Percentage of questions answered correctly (0–100).

    Returns:
        A formatted prompt string.
    """
    missed_str = ", ".join(topics_missed) if topics_missed else "None"
    return (
        f"A student completed a GRE-style adaptive diagnostic test.\n\n"
        f"Test Summary:\n"
        f"- Topics with incorrect answers: {missed_str}\n"
        f"- Highest difficulty level reached: {max_difficulty:.1f} (scale 0.1–1.0)\n"
        f"- Overall accuracy: {accuracy:.1f}%\n\n"
        f"Based on this performance data, generate a concise, actionable "
        f"3-step personalised study plan. Each step should:\n"
        f"1. Identify a specific weak area.\n"
        f"2. Recommend a concrete study action.\n"
        f"3. Suggest a measurable goal or milestone.\n\n"
        f"Format the plan clearly with numbered steps."
    )


def generate_study_plan(
    topics_missed: list[str],
    max_difficulty: float,
    accuracy: float,
) -> str:
    """
    Call the OpenAI Chat Completions API to generate a personalised study plan.

    Args:
        topics_missed:  List of topic names where the student struggled.
        max_difficulty: Highest difficulty question the student encountered.
        accuracy:       Test accuracy as a percentage float.

    Returns:
        The AI-generated study plan as a plain string.

    Raises:
        RuntimeError: If the OpenAI API call fails.
    """
    prompt = build_prompt(topics_missed, max_difficulty, accuracy)

    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert academic tutor specialising in GRE preparation. "
                        "You provide clear, motivating, and actionable study advice."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        )

        plan = response.choices[0].message.content
        return plan.strip() if plan else "No study plan could be generated."

    except Exception as exc:
        raise RuntimeError(f"OpenAI API error: {exc}") from exc
