from app.integrity import MODEL_VERSION, analyze_answer_patterns, normalize_answer


def test_normalization_collapses_case_and_whitespace():
    assert normalize_answer("  Kigali \n City ") == "kigali city"
    assert normalize_answer(None) == ""


def test_identical_response_patterns_produce_review_lead():
    submissions = [
        {"candidate_id": "candidate-a", "responses": {f"q{i}": f"uncommon-{i}" for i in range(1, 7)}},
        {"candidate_id": "candidate-b", "responses": {f"q{i}": f"uncommon-{i}" for i in range(1, 7)}},
        {"candidate_id": "candidate-c", "responses": {f"q{i}": f"different-{i}" for i in range(1, 7)}},
    ]
    leads = analyze_answer_patterns(submissions, min_shared_questions=4)
    assert len(leads) == 1
    assert {leads[0]["candidate_a_id"], leads[0]["candidate_b_id"]} == {"candidate-a", "candidate-b"}
    assert leads[0]["similarity_score"] >= 0.85
    assert leads[0]["evidence"]["model_version"] == MODEL_VERSION
    assert "cannot establish intent or guilt" in " ".join(leads[0]["evidence"]["limitations"])


def test_short_or_missing_responses_do_not_raise_leads():
    submissions = [
        {"candidate_id": "a", "responses": {"q1": "x", "q2": "y"}},
        {"candidate_id": "b", "responses": {"q1": "x", "q2": "y"}},
    ]
    assert analyze_answer_patterns(submissions, min_shared_questions=4) == []


def test_blank_answers_are_not_counted_as_matching():
    submissions = [
        {"candidate_id": "a", "responses": {"q1": "", "q2": None, "q3": "x", "q4": "x", "q5": "x"}},
        {"candidate_id": "b", "responses": {"q1": "", "q2": None, "q3": "x", "q4": "x", "q5": "x"}},
    ]
    assert analyze_answer_patterns(submissions, min_shared_questions=4) == []
