import hmac
import hashlib
import io
import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import auth, crud, models
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/admin/backup", tags=["Backup & Restore"])



def _val(v: Any) -> Any:
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "value"):  # enum
        return v.value
    return v


def _row(obj) -> dict:
    return {col.name: _val(getattr(obj, col.name)) for col in obj.__table__.columns}



def _sign(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, default=str).encode()
    return hmac.new(settings.secret_key.encode(), data, hashlib.sha256).hexdigest()


def _verify(payload: dict, sig: str) -> bool:
    return hmac.compare_digest(_sign(payload), sig)



@router.get("/preview")
def backup_preview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Return row counts per backup module so admin can make an informed choice."""
    fid = current_user.family_id
    account_ids_sq = db.query(models.Account.id).filter(models.Account.family_id == fid)
    user_ids_sq = db.query(models.User.id).filter(models.User.family_id == fid)

    return {
        "core": {
            "users": db.query(models.User).filter(
                models.User.family_id == fid, models.User.deleted_at.is_(None)
            ).count(),
            "accounts": db.query(models.Account).filter(
                models.Account.family_id == fid, models.Account.deleted_at.is_(None)
            ).count(),
            "transactions": db.query(models.Transaction).filter(
                models.Transaction.account_id.in_(account_ids_sq),
                models.Transaction.deleted_at.is_(None),
            ).count(),
            "categories": db.query(models.Category).filter(
                models.Category.family_id == fid, models.Category.deleted_at.is_(None)
            ).count(),
            "goals": db.query(models.Goal).filter(
                models.Goal.family_id == fid, models.Goal.archived_at.is_(None)
            ).count(),
            "goal_contributions": db.query(models.GoalContribution).join(
                models.Goal, models.GoalContribution.goal_id == models.Goal.id
            ).filter(models.Goal.family_id == fid).count(),
            "member_permissions": db.query(models.MemberPermission).filter(
                models.MemberPermission.family_id == fid
            ).count(),
            "family_currencies": db.query(models.FamilyCurrency).filter(
                models.FamilyCurrency.family_id == fid
            ).count(),
        },
        "automation": {
            "recurring_payments": db.query(models.RecurringPayment).filter(
                models.RecurringPayment.family_id == fid
            ).count(),
            "budget_settings": db.query(models.BudgetSetting).filter(
                models.BudgetSetting.family_id == fid
            ).count(),
        },
        "exchange_rates": {
            "exchange_rates": db.query(models.ExchangeRate).filter(
                models.ExchangeRate.family_id == fid
            ).count(),
        },
        "audit_logs": {
            "audit_logs": db.query(models.AuditLog).filter(
                models.AuditLog.user_id.in_(user_ids_sq)
            ).count(),
        },
    }



@router.post("")
def create_backup(
    include_automation: bool = True,
    include_exchange_rates: bool = False,
    include_audit_logs: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """
    Generate a JSON backup of the family's data and return it as a file download.

    Core (always included): family, users, accounts, transactions, categories,
    member_permissions, family_preference, family_currencies.

    Optional:
    - include_automation: recurring_payments, budget_settings (default: true)
    - include_exchange_rates: exchange_rates (default: false — auto-fetched daily)
    - include_audit_logs: audit_logs (default: false — can be large)
    """
    fid = current_user.family_id
    account_ids_sq = db.query(models.Account.id).filter(models.Account.family_id == fid)

    family = db.query(models.Family).filter(models.Family.id == fid).first()
    users = db.query(models.User).filter(
        models.User.family_id == fid, models.User.deleted_at.is_(None)
    ).all()
    accounts = db.query(models.Account).filter(
        models.Account.family_id == fid, models.Account.deleted_at.is_(None)
    ).all()
    transactions = db.query(models.Transaction).filter(
        models.Transaction.account_id.in_(account_ids_sq),
        models.Transaction.deleted_at.is_(None),
    ).all()
    categories = db.query(models.Category).filter(
        models.Category.family_id == fid, models.Category.deleted_at.is_(None)
    ).all()
    member_permissions = db.query(models.MemberPermission).filter(
        models.MemberPermission.family_id == fid
    ).all()
    family_preference = db.query(models.FamilyPreference).filter(
        models.FamilyPreference.family_id == fid
    ).first()
    family_currencies = db.query(models.FamilyCurrency).filter(
        models.FamilyCurrency.family_id == fid
    ).all()
    goals = db.query(models.Goal).filter(
        models.Goal.family_id == fid, models.Goal.archived_at.is_(None)
    ).all()
    goal_contributions = db.query(models.GoalContribution).join(
        models.Goal, models.GoalContribution.goal_id == models.Goal.id
    ).filter(models.Goal.family_id == fid).all()

    included_modules = ["core"]
    payload: dict = {
        "family": _row(family),
        "users": [_row(u) for u in users],
        "accounts": [_row(a) for a in accounts],
        "transactions": [_row(t) for t in transactions],
        "categories": [_row(c) for c in categories],
        "member_permissions": [_row(p) for p in member_permissions],
        "family_preference": _row(family_preference) if family_preference else None,
        "family_currencies": [_row(fc) for fc in family_currencies],
        "goals": [_row(g) for g in goals],
        "goal_contributions": [_row(gc) for gc in goal_contributions],
    }

    if include_automation:
        included_modules.append("automation")
        payload["recurring_payments"] = [
            _row(r) for r in db.query(models.RecurringPayment).filter(
                models.RecurringPayment.family_id == fid
            ).all()
        ]
        payload["budget_settings"] = [
            _row(b) for b in db.query(models.BudgetSetting).filter(
                models.BudgetSetting.family_id == fid
            ).all()
        ]

    if include_exchange_rates:
        included_modules.append("exchange_rates")
        payload["exchange_rates"] = [
            _row(r) for r in db.query(models.ExchangeRate).filter(
                models.ExchangeRate.family_id == fid
            ).all()
        ]

    if include_audit_logs:
        included_modules.append("audit_logs")
        user_ids_sq = db.query(models.User.id).filter(models.User.family_id == fid)
        payload["audit_logs"] = [
            _row(al) for al in db.query(models.AuditLog).filter(
                models.AuditLog.user_id.in_(user_ids_sq)
            ).all()
        ]

    # Sign payload before adding manifest
    signature = _sign(payload)
    backup_type = (
        "full"
        if include_automation and include_exchange_rates and include_audit_logs
        else "selective"
    )
    payload["backup_manifest"] = {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "family_id": str(fid),
        "backup_type": backup_type,
        "included_modules": included_modules,
        "signature": signature,
    }

    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="BACKUP_CREATED",
        entity_type="Family",
        entity_id=fid,
        new_values=f"modules={included_modules}",
    )

    filename = (
        f"shreeone_backup_{str(fid)[:8]}"
        f"_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    )
    content = json.dumps(payload, default=str, indent=2).encode()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.post("/restore")
async def restore_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """
    Restore family data from a backup JSON file.

    - Only the admin of the target family can restore.
    - The backup family_id must match the admin's family_id.
    - Signature is verified before any data is touched.
    - All active sessions are invalidated at the start of restore.
    - The entire operation is wrapped in a single DB transaction; any failure
      rolls back completely.
    - Password hashes are not restored — all users must reset their passwords.
    - WebAuthn credentials are not restored — passkey users must re-register.
    """
    try:
        raw = await file.read()
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot parse backup file as JSON")

    manifest = payload.get("backup_manifest")
    if not manifest:
        raise HTTPException(status_code=400, detail="Missing backup_manifest in file")

    if manifest.get("family_id") != str(current_user.family_id):
        raise HTTPException(
            status_code=403,
            detail="This backup belongs to a different family and cannot be restored here",
        )

    if manifest.get("schema_version") != "1.0":
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported schema version: {manifest.get('schema_version')}",
        )

    # Verify HMAC over the payload (without the manifest block)
    signature = manifest.pop("signature", None)
    payload_to_verify = {k: v for k, v in payload.items() if k != "backup_manifest"}
    if not signature or not _verify(payload_to_verify, signature):
        raise HTTPException(
            status_code=422,
            detail="Backup signature is invalid — file may be corrupted or tampered with",
        )
    manifest["signature"] = signature  # restore for later reference

    included_modules = manifest.get("included_modules", [])
    fid = current_user.family_id

    # Invalidate all active sessions for the family before touching data
    family_users_before = db.query(models.User).filter(models.User.family_id == fid).all()
    for u in family_users_before:
        crud.bump_user_token_version(db, u)

    # Track users in live DB but absent from backup — their permissions will be gone
    backup_user_ids = {u["id"] for u in payload.get("users", [])}
    orphaned_count = sum(
        1 for u in family_users_before if str(u.id) not in backup_user_ids
    )

    try:
        # wipe in reverse FK order
        live_account_ids = [
            r[0] for r in db.query(models.Account.id).filter(
                models.Account.family_id == fid
            ).all()
        ]
        live_user_ids = [u.id for u in family_users_before]

        db.query(models.RecurringPayment).filter(
            models.RecurringPayment.family_id == fid
        ).delete(synchronize_session=False)
        db.query(models.BudgetSetting).filter(
            models.BudgetSetting.family_id == fid
        ).delete(synchronize_session=False)
        db.query(models.ExchangeRate).filter(
            models.ExchangeRate.family_id == fid
        ).delete(synchronize_session=False)

        if live_account_ids:
            # Nullify self-referencing FK before deleting transfer pairs
            db.query(models.Transaction).filter(
                models.Transaction.account_id.in_(live_account_ids)
            ).update({"linked_transaction_id": None}, synchronize_session=False)
            db.query(models.Transaction).filter(
                models.Transaction.account_id.in_(live_account_ids)
            ).delete(synchronize_session=False)

        db.query(models.MemberPermission).filter(
            models.MemberPermission.family_id == fid
        ).delete(synchronize_session=False)
        db.query(models.FamilyPreference).filter(
            models.FamilyPreference.family_id == fid
        ).delete(synchronize_session=False)
        db.query(models.FamilyCurrency).filter(
            models.FamilyCurrency.family_id == fid
        ).delete(synchronize_session=False)

        if live_user_ids:
            db.query(models.AuditLog).filter(
                models.AuditLog.user_id.in_(live_user_ids)
            ).delete(synchronize_session=False)
            db.query(models.WebAuthnChallenge).filter(
                models.WebAuthnChallenge.user_id.in_(live_user_ids)
            ).delete(synchronize_session=False)
            db.query(models.WebAuthnCredential).filter(
                models.WebAuthnCredential.user_id.in_(live_user_ids)
            ).delete(synchronize_session=False)
            db.query(models.ActivationToken).filter(
                models.ActivationToken.user_id.in_(live_user_ids)
            ).delete(synchronize_session=False)
            db.query(models.RefreshToken).filter(
                models.RefreshToken.user_id.in_(live_user_ids)
            ).delete(synchronize_session=False)

        live_goal_ids = [
            r[0] for r in db.query(models.Goal.id).filter(
                models.Goal.family_id == fid
            ).all()
        ]
        if live_goal_ids:
            db.query(models.GoalContribution).filter(
                models.GoalContribution.goal_id.in_(live_goal_ids)
            ).delete(synchronize_session=False)
        db.query(models.Goal).filter(
            models.Goal.family_id == fid
        ).delete(synchronize_session=False)

        db.query(models.Account).filter(
            models.Account.family_id == fid
        ).delete(synchronize_session=False)
        db.query(models.Category).filter(
            models.Category.family_id == fid
        ).delete(synchronize_session=False)
        db.query(models.User).filter(
            models.User.family_id == fid
        ).delete(synchronize_session=False)

        # Update family record in-place to preserve the FK anchor
        fam = payload["family"]
        db.query(models.Family).filter(models.Family.id == fid).update({
            "name": fam["name"],
            "base_currency": fam["base_currency"],
            "fiscal_month_start": fam["fiscal_month_start"],
            "privacy_level": fam["privacy_level"],
        }, synchronize_session=False)

        db.flush()

        # re-insert

        # Users — password_hash intentionally excluded; users must reset passwords
        for u in payload["users"]:
            db.execute(text("""
                INSERT INTO users (id, family_id, first_name, last_name, email, role,
                                   token_version, active, activated, password_required, created_at)
                VALUES (:id, :family_id, :first_name, :last_name, :email, :role,
                        0, :active, :activated, TRUE, :created_at)
            """), {
                "id": u["id"], "family_id": u["family_id"],
                "first_name": u["first_name"], "last_name": u["last_name"],
                "email": u["email"], "role": u["role"],
                "active": u["active"], "activated": u.get("activated", False),
                "created_at": u["created_at"],
            })

        # Accounts
        for a in payload["accounts"]:
            db.execute(text("""
                INSERT INTO accounts (id, family_id, name, type, currency, owner_type,
                                      owner_user_id, include_in_family_overview,
                                      opening_balance, current_balance, current_value,
                                      last_valued_at, country_code,
                                      sort_order, created_at, updated_at, deleted_at)
                VALUES (:id, :family_id, :name, :type, :currency, :owner_type,
                        :owner_user_id, :include_in_family_overview,
                        :opening_balance, :current_balance, :current_value,
                        :last_valued_at, :country_code,
                        :sort_order, :created_at, :updated_at, :deleted_at)
            """), {k: a.get(k) for k in [
                "id", "family_id", "name", "type", "currency", "owner_type",
                "owner_user_id", "include_in_family_overview",
                "opening_balance", "current_balance", "current_value",
                "last_valued_at", "country_code",
                "sort_order", "created_at", "updated_at", "deleted_at",
            ]})

        # Categories — parents before children
        cats_sorted = sorted(
            payload["categories"],
            key=lambda c: (c["parent_id"] is not None, c.get("sort_order", 0)),
        )
        for c in cats_sorted:
            db.execute(text("""
                INSERT INTO categories (id, family_id, name, type, parent_id, color, icon,
                                        sort_order, is_system, created_at, updated_at, deleted_at)
                VALUES (:id, :family_id, :name, :type, :parent_id, :color, :icon,
                        :sort_order, :is_system, :created_at, :updated_at, :deleted_at)
            """), {k: c.get(k) for k in [
                "id", "family_id", "name", "type", "parent_id", "color", "icon",
                "sort_order", "is_system", "created_at", "updated_at", "deleted_at",
            ]})

        # Transactions — first pass: insert without linked_transaction_id
        for t in payload["transactions"]:
            db.execute(text("""
                INSERT INTO transactions (id, account_id, created_by_user_id, type, amount,
                                          currency, exchange_rate_to_base, amount_in_base_currency,
                                          category_id, description, transaction_date,
                                          linked_transaction_id, is_source_transaction,
                                          receipt_url, is_recurring, recurring_pattern,
                                          created_at, updated_at, deleted_at)
                VALUES (:id, :account_id, :created_by_user_id, :type, :amount,
                        :currency, :exchange_rate_to_base, :amount_in_base_currency,
                        :category_id, :description, :transaction_date,
                        NULL, :is_source_transaction,
                        :receipt_url, :is_recurring, :recurring_pattern,
                        :created_at, :updated_at, :deleted_at)
            """), {k: t.get(k) for k in [
                "id", "account_id", "created_by_user_id", "type", "amount",
                "currency", "exchange_rate_to_base", "amount_in_base_currency",
                "category_id", "description", "transaction_date",
                "is_source_transaction", "receipt_url", "is_recurring",
                "recurring_pattern", "created_at", "updated_at", "deleted_at",
            ]})

        # Transactions — second pass: restore transfer links
        for t in payload["transactions"]:
            if t.get("linked_transaction_id"):
                db.execute(
                    text("UPDATE transactions SET linked_transaction_id = :lid WHERE id = :id"),
                    {"lid": t["linked_transaction_id"], "id": t["id"]},
                )

        # Member permissions
        for p in payload["member_permissions"]:
            db.execute(text("""
                INSERT INTO member_permissions (id, family_id, user_id, can_add_transaction,
                    can_edit_transaction, can_delete_transaction, can_add_account,
                    can_edit_account, can_delete_account, can_manage_categories,
                    can_view_all_accounts, can_view_all_transactions, created_at, updated_at)
                VALUES (:id, :family_id, :user_id, :can_add_transaction,
                    :can_edit_transaction, :can_delete_transaction, :can_add_account,
                    :can_edit_account, :can_delete_account, :can_manage_categories,
                    :can_view_all_accounts, :can_view_all_transactions, :created_at, :updated_at)
            """), {k: p.get(k) for k in [
                "id", "family_id", "user_id", "can_add_transaction",
                "can_edit_transaction", "can_delete_transaction", "can_add_account",
                "can_edit_account", "can_delete_account", "can_manage_categories",
                "can_view_all_accounts", "can_view_all_transactions",
                "created_at", "updated_at",
            ]})

        # Family preference
        if payload.get("family_preference"):
            fp = payload["family_preference"]
            db.execute(text("""
                INSERT INTO family_preferences (id, family_id, theme, language,
                    show_budget_alerts, two_factor_enabled,
                    show_net_worth_by_country, show_member_spending,
                    ai_categorization_enabled, ai_monthly_narrative_enabled,
                    ai_weekly_digest_enabled, ai_receipt_ocr_enabled,
                    ai_voice_entry_enabled, ai_statement_upload_enabled,
                    ai_provider, ai_model_override,
                    created_at, updated_at)
                VALUES (:id, :family_id, :theme, :language,
                    :show_budget_alerts, :two_factor_enabled,
                    :show_net_worth_by_country, :show_member_spending,
                    :ai_categorization_enabled, :ai_monthly_narrative_enabled,
                    :ai_weekly_digest_enabled, :ai_receipt_ocr_enabled,
                    :ai_voice_entry_enabled, :ai_statement_upload_enabled,
                    :ai_provider, :ai_model_override,
                    :created_at, :updated_at)
            """), {k: fp.get(k) for k in [
                "id", "family_id", "theme", "language",
                "show_budget_alerts", "two_factor_enabled",
                "show_net_worth_by_country", "show_member_spending",
                "ai_categorization_enabled", "ai_monthly_narrative_enabled",
                "ai_weekly_digest_enabled", "ai_receipt_ocr_enabled",
                "ai_voice_entry_enabled", "ai_statement_upload_enabled",
                "ai_provider", "ai_model_override",
                "created_at", "updated_at",
            ]})

        # Family currencies
        for fc in payload.get("family_currencies", []):
            db.execute(text("""
                INSERT INTO family_currencies (id, family_id, currency_code, added_at)
                VALUES (:id, :family_id, :currency_code, :added_at)
                ON CONFLICT ON CONSTRAINT uq_family_currency DO NOTHING
            """), {k: fc.get(k) for k in ["id", "family_id", "currency_code", "added_at"]})

        # Goals
        for g in payload.get("goals", []):
            db.execute(text("""
                INSERT INTO goals (id, family_id, name, type, target_amount, current_amount,
                    currency, target_date, linked_account_id, notes,
                    created_at, updated_at, archived_at)
                VALUES (:id, :family_id, :name, :type, :target_amount, :current_amount,
                    :currency, :target_date, :linked_account_id, :notes,
                    :created_at, :updated_at, :archived_at)
            """), {k: g.get(k) for k in [
                "id", "family_id", "name", "type", "target_amount", "current_amount",
                "currency", "target_date", "linked_account_id", "notes",
                "created_at", "updated_at", "archived_at",
            ]})

        # Goal contributions
        for gc in payload.get("goal_contributions", []):
            db.execute(text("""
                INSERT INTO goal_contributions (id, goal_id, amount, note, contributed_at, created_at)
                VALUES (:id, :goal_id, :amount, :note, :contributed_at, :created_at)
            """), {k: gc.get(k) for k in [
                "id", "goal_id", "amount", "note", "contributed_at", "created_at",
            ]})

        if "automation" in included_modules:
            for r in payload.get("recurring_payments", []):
                db.execute(text("""
                    INSERT INTO recurring_payments (id, family_id, account_id, category_id,
                        assigned_to_user_id, name, amount, pattern, next_due_date,
                        last_paid_date, end_date, notify_before_days, is_active,
                        description, created_by_user_id, created_at, updated_at)
                    VALUES (:id, :family_id, :account_id, :category_id,
                        :assigned_to_user_id, :name, :amount, :pattern, :next_due_date,
                        :last_paid_date, :end_date, :notify_before_days, :is_active,
                        :description, :created_by_user_id, :created_at, :updated_at)
                """), {k: r.get(k) for k in [
                    "id", "family_id", "account_id", "category_id",
                    "assigned_to_user_id", "name", "amount", "pattern", "next_due_date",
                    "last_paid_date", "end_date", "notify_before_days", "is_active",
                    "description", "created_by_user_id", "created_at", "updated_at",
                ]})

            for b in payload.get("budget_settings", []):
                db.execute(text("""
                    INSERT INTO budget_settings (id, family_id, category_id, user_id,
                        limit_amount, period, spent_amount, alert_threshold,
                        notify_channels, is_active, fiscal_year_start, created_at, updated_at)
                    VALUES (:id, :family_id, :category_id, :user_id,
                        :limit_amount, :period, :spent_amount, :alert_threshold,
                        :notify_channels, :is_active, :fiscal_year_start, :created_at, :updated_at)
                """), {k: b.get(k) for k in [
                    "id", "family_id", "category_id", "user_id",
                    "limit_amount", "period", "spent_amount", "alert_threshold",
                    "notify_channels", "is_active", "fiscal_year_start",
                    "created_at", "updated_at",
                ]})

        if "exchange_rates" in included_modules:
            for er in payload.get("exchange_rates", []):
                db.execute(text("""
                    INSERT INTO exchange_rates (id, family_id, from_currency, to_currency,
                        rate, source, valid_date, fetched_at)
                    VALUES (:id, :family_id, :from_currency, :to_currency,
                        :rate, :source, :valid_date, :fetched_at)
                    ON CONFLICT ON CONSTRAINT uq_family_exchange_rate DO NOTHING
                """), {k: er.get(k) for k in [
                    "id", "family_id", "from_currency", "to_currency",
                    "rate", "source", "valid_date", "fetched_at",
                ]})

        if "audit_logs" in included_modules:
            for al in payload.get("audit_logs", []):
                db.execute(text("""
                    INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id,
                        old_values, new_values, ip_address, created_at)
                    VALUES (:id, :user_id, :action, :entity_type, :entity_id,
                        :old_values, :new_values, :ip_address, :created_at)
                """), {k: al.get(k) for k in [
                    "id", "user_id", "action", "entity_type", "entity_id",
                    "old_values", "new_values", "ip_address", "created_at",
                ]})

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Restore failed and was fully rolled back: {str(e)}",
        )

    # Audit log written after successful commit using admin's preserved user ID
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="RESTORE_COMPLETED",
        entity_type="Family",
        entity_id=fid,
        new_values=(
            f"Restore completed from backup generated at {manifest.get('generated_at')}; "
            f"modules={included_modules}"
        ),
    )

    warnings = [
        "All active sessions have been invalidated — all family members must log in again.",
        "Password hashes are not restored — all users must set a new password via the admin "
        "reset flow (/api/admin/users/{id}/reset-password).",
        "Passkey (WebAuthn) credentials are not restored — affected users must re-register "
        "their passkeys after setting a new password.",
    ]
    if orphaned_count:
        warnings.append(
            f"{orphaned_count} user(s) existed in the live database but not in the backup — "
            "they have been removed. Reinvite them via /api/admin/members if needed."
        )
    if "automation" not in included_modules:
        warnings.append(
            "Recurring payments and budget settings were not included in this backup "
            "and have been removed from the database. Recreate them via /api/settings/recurring."
        )

    return {
        "status": "restored",
        "modules_restored": included_modules,
        "backup_generated_at": manifest.get("generated_at"),
        "warnings": warnings,
    }
