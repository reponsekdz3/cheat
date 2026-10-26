from app.main import app


def test_core_operational_routes_are_registered():
    paths = {route.path for route in app.routes}
    required = {
        "/auth/token", "/auth/me", "/examinations", "/candidates", "/candidates/{candidate_id}/portal-access", "/my/cases", "/staff",
        "/staff-assignments", "/paper-batches", "/paper-batches/{batch_id}/verify",
        "/answer-submissions", "/integrity/analyze/{examination_id}", "/integrity/findings",
        "/cases", "/cases/{case_id}/decision", "/cases/{case_id}/appeals",
        "/appeals/{appeal_id}/resolution", "/audit/status", "/health/ready",
    }
    assert required.issubset(paths)


def test_openapi_documents_human_review_guardrail():
    schema = app.openapi()
    assert "never decide misconduct" in schema["info"]["description"]
