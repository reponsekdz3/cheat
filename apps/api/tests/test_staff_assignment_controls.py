from app.main import app
from app.models import StaffAssignment


def test_staff_assignment_has_separate_requester_and_reviewer():
    columns = set(StaffAssignment.__table__.columns.keys())
    assert {"created_by", "approved_by", "reviewed_by", "status", "approval_note", "reviewed_at"}.issubset(columns)


def test_staff_assignment_approval_api_is_registered():
    paths = {route.path for route in app.routes}
    assert "/staff-assignments" in paths
    assert "/staff-assignments/{assignment_id}/approval" in paths
