from sqlalchemy import select
from app.db import SessionLocal
from app.models import Department, User
from app.security import hash_password
from .conftest import account


def test_health_and_registration(client):
    assert client.get("/api/health").json()["status"] == "ok"
    headers = account(client, "Asha Rao", "asha@example.test")
    assert client.get("/api/users/me", headers=headers).json()["role"] == "citizen"


def test_citizen_can_submit_and_only_see_own_reports(client):
    one = account(client, "Asha Rao", "asha2@example.test")
    two = account(client, "Ravi Kumar", "ravi@example.test")
    payload = {"title": "Large pothole on main road", "description": "A deep pothole near the bus stop", "category": "Roads", "address": "Main Road"}
    created = client.post("/api/complaints", json=payload, headers=one)
    assert created.status_code == 201
    assert created.json()["reference"].startswith("JS-")
    assert len(client.get("/api/complaints", headers=one).json()) == 1
    assert client.get(f"/api/complaints/{created.json()['id']}", headers=two).status_code == 403
    assert client.get("/api/complaints", headers=two).json() == []


def test_registration_cannot_choose_elevated_role(client):
    response = client.post("/api/auth/register", json={"name": "Eve Admin", "email": "eve@example.test", "password": "long-password", "role": "admin"})
    assert response.status_code == 201
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "eve@example.test"))
        assert user.role == "citizen"


def test_ai_fallback_is_advisory(client):
    headers = account(client, "Mina", "mina@example.test")
    response = client.post("/api/ai/analyze", json={"title": "Water leak", "description": "A pipe is leaking", "category": "Water & Drainage"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["provider"] == "rule-based fallback"
    assert response.json()["advisory"] is True
    guidance = client.post("/api/ai/guidance", json={"question": "How do I track my status?"}, headers=headers)
    assert "My complaints" in guidance.json()["answer"]
    duplicate = client.post("/api/ai/possible-duplicates", json={"title": "Water leak", "description": "A pipe is leaking again", "category": "Water & Drainage"}, headers=headers)
    assert "will not be rejected automatically" in duplicate.json()["notice"]


def test_status_history_and_resolution_evidence_requirement(client):
    citizen = account(client, "Nila", "nila@example.test")
    payload = {"title": "Streetlight is broken", "description": "The light has been off for several nights", "category": "Streetlights", "address": "Lake Road"}
    complaint = client.post("/api/complaints", json=payload, headers=citizen).json()
    with SessionLocal() as db:
        db.add(User(name="Local Admin", email="admin-test@example.test", password_hash=hash_password("administrator-password"), role="admin"))
        db.commit()
    account(client, "Test Official", "staff-test@example.test")
    with SessionLocal() as db:
        staff = db.scalar(select(User).where(User.email == "staff-test@example.test"))
        dept = db.scalar(select(Department).where(Department.name == "Electrical Department"))
        staff.role = "official"
        staff.department_id = dept.id
        db.commit()
    token = client.post("/api/auth/login", json={"email": "admin-test@example.test", "password": "administrator-password"}).json()["access_token"]
    official_token = client.post("/api/auth/login", json={"email": "staff-test@example.test", "password": "test-password-123"}).json()["access_token"]
    official = {"Authorization": f"Bearer {official_token}"}
    url = f"/api/complaints/{complaint['id']}/status"
    assert client.patch(url, json={"status": "Resolved", "resolution_details": "Fixed"}, headers=official).status_code == 409
    assert client.patch(url, json={"status": "Under Review"}, headers=official).status_code == 200
    assert client.patch(url, json={"status": "Assigned"}, headers=official).status_code == 200
    assert client.patch(url, json={"status": "In Progress"}, headers=official).status_code == 200
    missing_evidence = client.patch(url, json={"status": "Resolved", "resolution_details": "Replaced the bulb"}, headers=official)
    assert missing_evidence.status_code == 422
    bad_upload = client.post(f"/api/complaints/{complaint['id']}/attachments", headers=official, files={"file": ("bad.jpg", b"not an image", "image/jpeg")})
    assert bad_upload.status_code == 415
    image = b"\x89PNG\r\n\x1a\n" + b"demo"
    good_upload = client.post(f"/api/complaints/{complaint['id']}/attachments", headers=official, files={"file": ("evidence.png", image, "image/png")})
    assert good_upload.status_code == 201
    resolved = client.patch(url, json={"status": "Resolved", "resolution_details": "Replaced the bulb"}, headers=official)
    assert resolved.status_code == 200
    history = client.get(f"/api/complaints/{complaint['id']}/history", headers=citizen).json()
    assert [event["new_status"] for event in history] == ["Submitted", "Under Review", "Assigned", "In Progress", "Resolved"]
    notices = client.get("/api/notifications", headers=citizen).json()
    assert len(notices) == 4
    marked = client.patch(f"/api/notifications/{notices[0]['id']}/read", headers=citizen)
    assert marked.json()["is_read"] is True
