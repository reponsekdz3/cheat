from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

MODEL_VERSION = "answer-pattern-v1.0.0"


def normalize_answer(answer: Any) -> str:
    if answer is None:
        return ""
    return re.sub(r"\s+", " ", str(answer).casefold()).strip()


def analyze_answer_patterns(
    submissions: list[dict[str, Any]], *, min_shared_questions: int = 4,
    similarity_threshold: float = 0.85, rarity_threshold: float = 0.72,
) -> list[dict[str, Any]]:
    """Return explainable review leads; matching responses do not establish intent or guilt."""
    prepared = []
    frequencies: Counter[tuple[str, str]] = Counter()
    for submission in submissions:
        responses = {
            str(question): normalize_answer(answer)
            for question, answer in submission.get("responses", {}).items()
        }
        prepared.append({"candidate_id": str(submission["candidate_id"]), "responses": responses})
        for question, answer in responses.items():
            if answer:
                frequencies[(question, answer)] += 1

    leads = []
    for index, left in enumerate(prepared):
        for right in prepared[index + 1:]:
            a, b = left["responses"], right["responses"]
            common = sorted(set(a) & set(b))
            comparable = [q for q in common if a[q] and b[q]]
            if len(comparable) < min_shared_questions:
                continue
            matched = [q for q in comparable if a[q] == b[q]]
            agreement = len(matched) / len(comparable)
            weights = {q: 1.0 / math.log2(2 + max(0, frequencies[(q, a[q])] - 1)) for q in comparable}
            total_weight = sum(weights.values())
            rare_score = sum(weights[q] for q in matched) / total_weight if total_weight else 0.0
            if agreement < similarity_threshold and rare_score < rarity_threshold:
                continue
            leads.append({
                "candidate_a_id": left["candidate_id"], "candidate_b_id": right["candidate_id"],
                "similarity_score": round(max(agreement, rare_score), 4),
                "evidence": {
                    "model_version": MODEL_VERSION,
                    "comparable_question_count": len(comparable),
                    "matching_question_count": len(matched),
                    "exact_agreement": round(agreement, 4),
                    "cohort_rarity_score": round(rare_score, 4),
                    "matched_question_ids": matched,
                    "limitations": [
                        "Common answers may be legitimate, especially for constrained-response questions.",
                        "The cohort may not include all candidates or scripts.",
                        "A triage lead cannot establish intent or guilt.",
                    ],
                },
            })
    return sorted(leads, key=lambda item: item["similarity_score"], reverse=True)
