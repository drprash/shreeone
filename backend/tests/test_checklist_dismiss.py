"""
Getting-started checklist dismissal is persisted server-side:
- new users start with setup_checklist_dismissed = False
- POST /auth/checklist-dismiss marks it True
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


def test_checklist_dismiss_flag_lifecycle(app, client, db_session):
    response = client.post("/auth/register", json={
        "email": f"checklist-{uuid.uuid4()}@example.com",
        "password": "StrongPass1!",
        "first_name": "Check",
        "last_name": "Lister",
        "family_name": "Checklist Family",
        "base_currency": "USD",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    user_id = uuid.UUID(data["user"]["id"])
    try:
        assert data["user"]["setup_checklist_dismissed"] is False

        db_user = db_session.query(models.User).filter(models.User.id == user_id).first()
        app.dependency_overrides[auth_module.get_current_user] = lambda: db_user

        response = client.post("/auth/checklist-dismiss")
        assert response.status_code == 200, response.text
        assert response.json()["setup_checklist_dismissed"] is True

        db_session.refresh(db_user)
        assert db_user.setup_checklist_dismissed is True
    finally:
        _cleanup_family(db_session, data["user"]["family_id"])
