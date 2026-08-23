"""
Server-side onboarding state:
- new users start with onboarding_completed = False
- POST /auth/onboarding-complete marks it True
- login for a not-yet-activated member returns a structured PASSWORD_SETUP_REQUIRED
  error code (frontend must not rely on string-matching the message)
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth as auth_module
from app import models
from app.database import SessionLocal, Base, engine, get_db
from app.routers.auth import router


@pytest.fixture()
def db_session():
    db = SessionLocal()
    Base.metadata.create_all(bind=engine)
    yield db
    db.rollback()
    db.close()


@pytest.fixture()
def app(db_session):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    return app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _register(client, email):
    response = client.post("/auth/register", json={
        "email": email,
        "password": "StrongPass1!",
        "first_name": "Onboard",
        "last_name": "Tester",
        "family_name": "Onboarding Family",
        "base_currency": "USD",
    })
    assert response.status_code == 200, response.text
    return response.json()


def _cleanup_family(db, family_id):
    family_id = uuid.UUID(str(family_id))
    db.query(models.Category).filter(models.Category.family_id == family_id).delete()
    db.query(models.MemberPermission).filter(models.MemberPermission.family_id == family_id).delete()
    user_ids = [u.id for u in db.query(models.User).filter(models.User.family_id == family_id).all()]
    if user_ids:
        db.query(models.RefreshToken).filter(models.RefreshToken.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(models.AuditLog).filter(models.AuditLog.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.family_id == family_id).delete()
    db.query(models.Family).filter(models.Family.id == family_id).delete()
    db.commit()


def test_new_user_starts_with_onboarding_incomplete(client, db_session):
    data = _register(client, f"onboard-{uuid.uuid4()}@example.com")
    try:
        assert data["user"]["onboarding_completed"] is False
    finally:
        _cleanup_family(db_session, data["user"]["family_id"])


def test_onboarding_complete_endpoint_sets_flag(app, client, db_session):
    data = _register(client, f"onboard-{uuid.uuid4()}@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    try:
        db_user = db_session.query(models.User).filter(models.User.id == user_id).first()
        app.dependency_overrides[auth_module.get_current_user] = lambda: db_user

        response = client.post("/auth/onboarding-complete")
        assert response.status_code == 200, response.text
        assert response.json()["onboarding_completed"] is True

        db_session.refresh(db_user)
        assert db_user.onboarding_completed is True
    finally:
        _cleanup_family(db_session, data["user"]["family_id"])


def test_login_before_password_setup_returns_structured_code(client, db_session):
    data = _register(client, f"onboard-admin-{uuid.uuid4()}@example.com")
    family_id = uuid.UUID(data["user"]["family_id"])
    member_email = f"onboard-member-{uuid.uuid4()}@example.com"
    try:
        member = models.User(
            family_id=family_id,
            first_name="Pending",
            last_name="Member",
            email=member_email,
            password_hash=None,
            role=models.Role.MEMBER,
            active=True,
            activated=False,
            password_required=True,
        )
        db_session.add(member)
        db_session.commit()

        response = client.post("/auth/login", json={
            "email": member_email,
            "password": "whatever123",
        })
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["code"] == "PASSWORD_SETUP_REQUIRED"
        assert "activation" in detail["message"].lower()
    finally:
        _cleanup_family(db_session, family_id)
