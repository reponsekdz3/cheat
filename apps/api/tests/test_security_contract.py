from app.main import app
from app.models import LoginAttempt, StaffMember
from app.security import ROLES


def test_login_attempt_pseudonyms_do_not_store_raw_identity_or_network_values():
    columns = set(LoginAttempt.__table__.columns.keys())
    assert {"email_key", "ip_key", "succeeded", "created_at"}.issubset(columns)
    assert "email" not in columns
    assert "ip_address" not in columns
    assert "password" not in columns


def test_staff_record_tracks_creator_for_independent_eligibility_review():
    assert "created_by" in StaffMember.__table__.columns


def test_candidate_role_exists_for_linked_appeal_access():
    assert "CANDIDATE" in ROLES
    assert "/my/cases" in {route.path for route in app.routes}
