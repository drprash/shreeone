"""
Registration must seed a starter set of categories for the new family so a
first-time user can log transactions immediately (onboarding smoothing).
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
def client(db_session):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=False)


def _cleanup_family(db, family_id):
    db.query(models.Category).filter(models.Category.family_id == family_id).delete()
    db.query(models.MemberPermission).filter(models.MemberPermission.family_id == family_id).delete()
    user_ids = [u.id for u in db.query(models.User).filter(models.User.family_id == family_id).all()]
    if user_ids:
        db.query(models.RefreshToken).filter(models.RefreshToken.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(models.AuditLog).filter(models.AuditLog.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.family_id == family_id).delete()
    db.query(models.Family).filter(models.Family.id == family_id).delete()
    db.commit()


def test_register_seeds_default_categories(client, db_session):
    email = f"seed-test-{uuid.uuid4()}@example.com"
    response = client.post("/auth/register", json={
        "email": email,
        "password": "StrongPass1!",
        "first_name": "Seed",
        "last_name": "Tester",
        "family_name": "Seed Family",
        "base_currency": "USD",
    })
    assert response.status_code == 200, response.text

    family_id = uuid.UUID(response.json()["user"]["family_id"])
    try:
        categories = db_session.query(models.Category).filter(
            models.Category.family_id == family_id,
            models.Category.is_system == False,  # noqa: E712
            models.Category.deleted_at.is_(None),
        ).all()

        expense = [c for c in categories if c.type == models.CategoryType.EXPENSE]
        income = [c for c in categories if c.type == models.CategoryType.INCOME]

        assert len(expense) >= 5, "expected a starter set of expense categories"
        assert len(income) >= 2, "expected a starter set of income categories"
        assert all(c.color for c in categories), "seeded categories need a color for the UI"
        assert len({c.name for c in categories}) == len(categories), "seeded names must be unique"
    finally:
        _cleanup_family(db_session, family_id)
