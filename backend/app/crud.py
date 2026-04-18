from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_
from uuid import UUID
from datetime import datetime
from app import models, schemas, auth

# Family operations
def create_family(db: Session, family: schemas.FamilyCreate) -> models.Family:
    db_family = models.Family(**family.dict())
    db.add(db_family)
    db.commit()
    db.refresh(db_family)
    return db_family

def get_family(db: Session, family_id: UUID) -> Optional[models.Family]:
    return db.query(models.Family).filter(
        models.Family.id == family_id,
        models.Family.deleted_at.is_(None)
    ).first()

# User operations
def create_user(db: Session, user: schemas.UserCreate, family_id: UUID, role: models.Role = models.Role.MEMBER, activated: bool = False, password_required: bool = True) -> models.User:
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        family_id=family_id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        password_hash=hashed_password,
        role=role,
        active=True,
        activated=activated,        # Use the parameter
        password_required=password_required  # Use the parameter
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(
        models.User.email == email,
        models.User.deleted_at.is_(None)
    ).first()

def get_user(db: Session, user_id: UUID) -> Optional[models.User]:
    return db.query(models.User).filter(
        models.User.id == user_id,
        models.User.deleted_at.is_(None)
    ).first()

def bump_user_token_version(db: Session, user: models.User, commit: bool = True) -> models.User:
    user.token_version = (user.token_version or 0) + 1
    if commit:
        db.commit()
        db.refresh(user)
    return user

def get_family_users(db: Session, family_id: UUID, current_user: models.User) -> List[models.User]:
    query = db.query(models.User).filter(
        models.User.family_id == family_id,
        models.User.deleted_at.is_(None)
    )
    
    if current_user.role != models.Role.ADMIN:
        # Members can only see themselves and admins
        query = query.filter(
            or_(
                models.User.id == current_user.id,
                models.User.role == models.Role.ADMIN
            )
        )
    
    return query.all()

def update_user(db: Session, user_id: UUID, user_update: schemas.UserUpdate) -> Optional[models.User]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: UUID) -> bool:
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    db_user.deleted_at = datetime.utcnow()
    db_user.active = False
    db_user.token_version = (db_user.token_version or 0) + 1
    db.commit()
    return True

# Account operations
def create_account(db: Session, account: schemas.AccountCreate, family_id: UUID) -> models.Account:
    # Auto-assign sort_order: max within same family+type + 1
    max_sort = db.query(models.Account.sort_order).filter(
        models.Account.family_id == family_id,
        models.Account.type == account.type,
        models.Account.deleted_at.is_(None)
    ).order_by(models.Account.sort_order.desc()).first()
    next_sort_order = (max_sort[0] + 1) if max_sort else 0

    db_account = models.Account(
        family_id=family_id,
        sort_order=next_sort_order,
        **account.dict()
    )
    # Initialize current_balance with opening_balance
    db_account.current_balance = account.opening_balance or 0
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

def get_account(db: Session, account_id: UUID) -> Optional[models.Account]:
    account = db.query(models.Account).options(
        joinedload(models.Account.owner)
    ).filter(
        models.Account.id == account_id,
        models.Account.deleted_at.is_(None)
    ).first()
    if not account:
        return None

    _refresh_credit_card_balances(db, [account])
    return account

def get_family_accounts(db: Session, family_id: UUID, user: models.User) -> List[models.Account]:
    query = db.query(models.Account).options(
        joinedload(models.Account.owner)
    ).filter(
        models.Account.family_id == family_id,
        models.Account.deleted_at.is_(None)
    )

    if user.role != models.Role.ADMIN:
        # Members see shared accounts and their personal accounts
        query = query.filter(
            or_(
                models.Account.owner_type == models.OwnerType.SHARED,
                models.Account.owner_user_id == user.id
            )
        )

    query = query.order_by(models.Account.type, models.Account.sort_order, models.Account.created_at)
    accounts = query.all()
    _refresh_credit_card_balances(db, accounts)
    return accounts


def _refresh_credit_card_balances(db: Session, accounts: List[models.Account]) -> None:
    credit_accounts = [a for a in accounts if a.type == models.AccountType.CREDIT_CARD]
    if not credit_accounts:
        return

    from app.financial_logic import FinancialEngine

    has_updates = False
    for account in credit_accounts:
        recalculated_balance = FinancialEngine.calculate_account_balance(db, str(account.id))
        if account.current_balance != recalculated_balance:
            account.current_balance = recalculated_balance
            has_updates = True

    if has_updates:
        db.commit()
        for account in credit_accounts:
            db.refresh(account)

def update_account(db: Session, account_id: UUID, account_update: schemas.AccountUpdate) -> Optional[models.Account]:
    db_account = get_account(db, account_id)
    if not db_account:
        return None
    
    update_data = account_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_account, field, value)
    
    db.commit()

    if 'opening_balance' in update_data:
        from app.financial_logic import FinancialEngine
        FinancialEngine.update_account_balance(db, str(db_account.id))

    db.refresh(db_account)
    return db_account

def delete_account(db: Session, account_id: UUID) -> bool:
    # Check for transactions
    transaction_count = db.query(models.Transaction).filter(
        models.Transaction.account_id == account_id,
        models.Transaction.deleted_at.is_(None)
    ).count()
    
    if transaction_count > 0:
        raise ValueError("Cannot delete account with existing transactions")
    
    db_account = get_account(db, account_id)
    if not db_account:
        return False
    
    db_account.deleted_at = datetime.utcnow()
    db.commit()
    return True

# Category operations
def create_category(db: Session, category: schemas.CategoryCreate, family_id: UUID) -> models.Category:
    # Auto-assign sort_order: max within same family+type + 1
    max_sort = db.query(models.Category.sort_order).filter(
        models.Category.family_id == family_id,
        models.Category.type == category.type,
        models.Category.deleted_at.is_(None)
    ).order_by(models.Category.sort_order.desc()).first()
    next_sort_order = (max_sort[0] + 1) if max_sort else 0

    db_category = models.Category(
        family_id=family_id,
        sort_order=next_sort_order,
        **category.dict()
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def get_family_categories(db: Session, family_id: UUID, user: Optional[models.User] = None) -> List[models.Category]:
    """
    Get family categories sorted by type then sort_order.
    System categories (is_system=True) are hidden from users.
    """
    return db.query(models.Category).filter(
        models.Category.family_id == family_id,
        models.Category.deleted_at.is_(None),
        models.Category.is_system == False
    ).order_by(models.Category.type, models.Category.sort_order, models.Category.created_at).all()

def get_or_create_system_category(
    db: Session, family_id: UUID, category_type: models.CategoryType, name: str
) -> models.Category:
    """Get or create a hidden system category used for automated transactions."""
    category = db.query(models.Category).filter(
        models.Category.family_id == family_id,
        models.Category.name == name,
        models.Category.type == category_type,
        models.Category.is_system == True,
        models.Category.deleted_at.is_(None)
    ).first()

    if not category:
        category = models.Category(
            family_id=family_id,
            name=name,
            type=category_type,
            is_system=True,
            color="#94a3b8",
            sort_order=9999
        )
        db.add(category)
        db.commit()
        db.refresh(category)

    return category

def get_category(db: Session, category_id: UUID) -> Optional[models.Category]:
    return db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.deleted_at.is_(None)
    ).first()

def delete_category(db: Session, category_id: UUID) -> bool:
    db_category = get_category(db, category_id)
    if not db_category:
        return False

    db_category.deleted_at = datetime.utcnow()
    db.commit()
    return True

def reorder_accounts(db: Session, family_id: UUID, items: List[schemas.AccountReorderItem]) -> None:
    """Bulk-update sort_order for accounts belonging to the family."""
    ids = [item.id for item in items]
    accounts = db.query(models.Account).filter(
        models.Account.id.in_(ids),
        models.Account.family_id == family_id,
        models.Account.deleted_at.is_(None)
    ).all()
    account_map = {a.id: a for a in accounts}
    for item in items:
        if item.id in account_map:
            account_map[item.id].sort_order = item.sort_order
    db.commit()

def reorder_categories(db: Session, family_id: UUID, items: List[schemas.CategoryReorderItem]) -> None:
    """Bulk-update sort_order for categories belonging to the family."""
    ids = [item.id for item in items]
    categories = db.query(models.Category).filter(
        models.Category.id.in_(ids),
        models.Category.family_id == family_id,
        models.Category.deleted_at.is_(None)
    ).all()
    category_map = {c.id: c for c in categories}
    for item in items:
        if item.id in category_map:
            category_map[item.id].sort_order = item.sort_order
    db.commit()

# Transaction operations
def get_transaction(db: Session, transaction_id: UUID) -> Optional[models.Transaction]:
    return db.query(models.Transaction).options(
        selectinload(models.Transaction.account).selectinload(models.Account.owner),
        selectinload(models.Transaction.category),
        selectinload(models.Transaction.created_by)
    ).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.deleted_at.is_(None)
    ).first()

def get_family_transactions(
    db: Session, 
    family_id: UUID, 
    user: models.User,
    skip: int = 0, 
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    transaction_type: Optional[str] = None
) -> List[models.Transaction]:
    """
    Get family transactions with privacy-level filtering.
    
    Privacy Levels:
    - PRIVATE: Members only see their own transactions
    - SHARED: Members see shared account transactions + their own
    - FAMILY: Members see all family transactions
    - ADMIN: Always sees all transactions
    """
    # Get family privacy level
    family = db.query(models.Family).filter_by(id=family_id).first()
    privacy_level = family.privacy_level if family else models.PrivacyLevel.FAMILY
    
    query = db.query(models.Transaction).join(
        models.Account, models.Transaction.account_id == models.Account.id
    ).options(
        selectinload(models.Transaction.account).selectinload(models.Account.owner),
        selectinload(models.Transaction.category),
        selectinload(models.Transaction.created_by)
    ).filter(
        models.Account.family_id == family_id,
        models.Transaction.deleted_at.is_(None)
    )
    
    # APPLY PRIVACY FILTERING (non-admin users only)
    if user.role != models.Role.ADMIN:
        if privacy_level == models.PrivacyLevel.PRIVATE:
            # Members only see their own transactions
            query = query.filter(models.Transaction.created_by_user_id == user.id)
        elif privacy_level == models.PrivacyLevel.SHARED:
            # Members see shared account transactions + their own
            query = query.filter(
                or_(
                    models.Account.owner_type == models.OwnerType.SHARED,
                    models.Transaction.created_by_user_id == user.id
                )
            )
        # else PrivacyLevel.FAMILY: see all (no additional filtering)
    
    # Apply optional filters
    if transaction_type:
        query = query.filter(models.Transaction.type == transaction_type)
    if start_date:
        query = query.filter(models.Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(models.Transaction.transaction_date <= end_date)
    
    return query.order_by(models.Transaction.transaction_date.desc()).offset(skip).limit(limit).all()

def get_account_transactions(
    db: Session, 
    account_id: UUID, 
    skip: int = 0, 
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    transaction_type: Optional[str] = None
) -> List[models.Transaction]:
    query = db.query(models.Transaction).options(
        selectinload(models.Transaction.account).selectinload(models.Account.owner),
        selectinload(models.Transaction.category),
        selectinload(models.Transaction.created_by)
    ).filter(
        models.Transaction.account_id == account_id,
        models.Transaction.deleted_at.is_(None)
    )
    
    if start_date:
        # Strip timezone info to match timezone-naive DB column
        naive_start = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        query = query.filter(models.Transaction.transaction_date >= naive_start)
    if end_date:
        naive_end = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
        query = query.filter(models.Transaction.transaction_date <= naive_end)
    if transaction_type:
        try:
            tx_type = models.TransactionType(transaction_type)
            query = query.filter(models.Transaction.type == tx_type)
        except ValueError:
            pass  # Ignore invalid transaction types
    
    return query.order_by(models.Transaction.transaction_date.desc()).offset(skip).limit(limit).all()

def update_transaction(
    db: Session, 
    transaction_id: UUID, 
    transaction_update: schemas.TransactionUpdate,
    user: models.User
) -> Optional[models.Transaction]:
    db_transaction = get_transaction(db, transaction_id)
    if not db_transaction:
        return None
    
    # Check permissions
    if user.role != models.Role.ADMIN and db_transaction.created_by_user_id != user.id:
        raise PermissionError("Cannot modify transaction created by another user")
    
    update_data = transaction_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_transaction, field, value)
    
    # Recalculate base currency amount if amount changed
    if 'amount' in update_data and db_transaction.exchange_rate_to_base:
        db_transaction.amount_in_base_currency = update_data['amount'] * db_transaction.exchange_rate_to_base
    
    db.commit()
    db.refresh(db_transaction)
    
    # Update account balance
    from app.financial_logic import FinancialEngine
    FinancialEngine.update_account_balance(db, str(db_transaction.account_id))
    
    return db_transaction

def delete_transaction(db: Session, transaction_id: UUID, user: models.User) -> bool:
    db_transaction = get_transaction(db, transaction_id)
    if not db_transaction:
        return False
    
    # Check permissions
    if user.role != models.Role.ADMIN and db_transaction.created_by_user_id != user.id:
        raise PermissionError("Cannot delete transaction created by another user")
    
    db_transaction.deleted_at = datetime.utcnow()
    db.commit()
    
    # Update account balance
    from app.financial_logic import FinancialEngine
    FinancialEngine.update_account_balance(db, str(db_transaction.account_id))
    
    # If transfer, delete linked transaction too
    if db_transaction.linked_transaction_id:
        linked = get_transaction(db, db_transaction.linked_transaction_id)
        if linked:
            linked.deleted_at = datetime.utcnow()
            FinancialEngine.update_account_balance(db, str(linked.account_id))
            db.commit()
    
    return True

# Audit log
def create_audit_log(
    db: Session,
    user_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    old_values: Optional[str] = None,
    new_values: Optional[str] = None,
    ip_address: Optional[str] = None
):
    log = models.AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()

# Member Permission operations
def create_member_permission(db: Session, family_id: UUID, perm: schemas.MemberPermissionCreate) -> models.MemberPermission:
    # Check if permission already exists
    existing = db.query(models.MemberPermission).filter(
        models.MemberPermission.family_id == family_id,
        models.MemberPermission.user_id == perm.user_id
    ).first()
    
    if existing:
        # Update existing
        for key, value in perm.dict().items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    
    db_perm = models.MemberPermission(
        family_id=family_id,
        **perm.dict()
    )
    db.add(db_perm)
    db.commit()
    db.refresh(db_perm)
    return db_perm

def get_member_permission(db: Session, family_id: UUID, user_id: UUID) -> Optional[models.MemberPermission]:
    return db.query(models.MemberPermission).filter(
        models.MemberPermission.family_id == family_id,
        models.MemberPermission.user_id == user_id
    ).first()

def get_family_member_permissions(db: Session, family_id: UUID) -> List[models.MemberPermission]:
    return db.query(models.MemberPermission).filter(
        models.MemberPermission.family_id == family_id
    ).all()

def update_member_permission(db: Session, family_id: UUID, user_id: UUID, perm: schemas.MemberPermissionUpdate) -> Optional[models.MemberPermission]:
    db_perm = get_member_permission(db, family_id, user_id)
    if not db_perm:
        return None
    
    for key, value in perm.dict(exclude_unset=True).items():
        setattr(db_perm, key, value)
    db_perm.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_perm)
    return db_perm

# Budget Setting operations
def create_budget_setting(db: Session, family_id: UUID, budget: schemas.BudgetSettingCreate) -> models.BudgetSetting:
    db_budget = models.BudgetSetting(
        family_id=family_id,
        **budget.dict()
    )
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget

def get_budget_setting(db: Session, budget_id: UUID) -> Optional[models.BudgetSetting]:
    return db.query(models.BudgetSetting).filter(
        models.BudgetSetting.id == budget_id
    ).options(
        selectinload(models.BudgetSetting.category),
        selectinload(models.BudgetSetting.user)
    ).first()

def get_family_budget_settings(db: Session, family_id: UUID) -> List[models.BudgetSetting]:
    return db.query(models.BudgetSetting).filter(
        models.BudgetSetting.family_id == family_id,
        models.BudgetSetting.is_active == True
    ).options(
        selectinload(models.BudgetSetting.category),
        selectinload(models.BudgetSetting.user)
    ).all()

def get_category_budget(db: Session, family_id: UUID, category_id: UUID) -> Optional[models.BudgetSetting]:
    return db.query(models.BudgetSetting).filter(
        models.BudgetSetting.family_id == family_id,
        models.BudgetSetting.category_id == category_id
    ).first()

def get_member_budget(db: Session, family_id: UUID, user_id: UUID) -> Optional[models.BudgetSetting]:
    return db.query(models.BudgetSetting).filter(
        models.BudgetSetting.family_id == family_id,
        models.BudgetSetting.user_id == user_id
    ).first()

def update_budget_setting(db: Session, budget_id: UUID, budget: schemas.BudgetSettingUpdate) -> Optional[models.BudgetSetting]:
    db_budget = get_budget_setting(db, budget_id)
    if not db_budget:
        return None
    
    for key, value in budget.dict(exclude_unset=True).items():
        setattr(db_budget, key, value)
    db_budget.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_budget)
    return db_budget

def delete_budget_setting(db: Session, budget_id: UUID) -> bool:
    db_budget = get_budget_setting(db, budget_id)
    if not db_budget:
        return False
    
    db.delete(db_budget)
    db.commit()
    return True

# Recurring Payment operations
def create_recurring_payment(db: Session, family_id: UUID, user_id: UUID, payment: schemas.RecurringPaymentCreate) -> models.RecurringPayment:
    db_payment = models.RecurringPayment(
        family_id=family_id,
        created_by_user_id=user_id,
        **payment.dict()
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_recurring_payment(db: Session, payment_id: UUID) -> Optional[models.RecurringPayment]:
    return db.query(models.RecurringPayment).filter(
        models.RecurringPayment.id == payment_id
    ).options(
        selectinload(models.RecurringPayment.family),
        selectinload(models.RecurringPayment.account),
        selectinload(models.RecurringPayment.category),
        selectinload(models.RecurringPayment.assigned_to_user),
        selectinload(models.RecurringPayment.created_by_user)
    ).first()

def get_family_recurring_payments(db: Session, family_id: UUID) -> List[models.RecurringPayment]:
    return db.query(models.RecurringPayment).filter(
        models.RecurringPayment.family_id == family_id,
        models.RecurringPayment.is_active == True
    ).options(
        selectinload(models.RecurringPayment.family),
        selectinload(models.RecurringPayment.account),
        selectinload(models.RecurringPayment.category),
        selectinload(models.RecurringPayment.assigned_to_user),
        selectinload(models.RecurringPayment.created_by_user)
    ).all()

def get_due_recurring_payments(db: Session, family_id: UUID) -> List[models.RecurringPayment]:
    """Get recurring payments that are due soon"""
    return db.query(models.RecurringPayment).filter(
        models.RecurringPayment.family_id == family_id,
        models.RecurringPayment.is_active == True,
        models.RecurringPayment.next_due_date <= datetime.utcnow()
    ).all()

def update_recurring_payment(db: Session, payment_id: UUID, payment: schemas.RecurringPaymentUpdate) -> Optional[models.RecurringPayment]:
    db_payment = get_recurring_payment(db, payment_id)
    if not db_payment:
        return None
    
    for key, value in payment.dict(exclude_unset=True).items():
        setattr(db_payment, key, value)
    db_payment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_payment)
    return db_payment

def deactivate_recurring_payment(db: Session, payment_id: UUID) -> Optional[models.RecurringPayment]:
    db_payment = get_recurring_payment(db, payment_id)
    if not db_payment:
        return None
    
    db_payment.is_active = False
    db_payment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_payment)
    return db_payment

# Family Preference operations
def get_or_create_family_preference(db: Session, family_id: UUID) -> models.FamilyPreference:
    pref = db.query(models.FamilyPreference).filter(
        models.FamilyPreference.family_id == family_id
    ).first()
    
    if not pref:
        pref = models.FamilyPreference(family_id=family_id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    
    return pref

def update_family_preference(db: Session, family_id: UUID, pref: schemas.FamilyPreferenceUpdate) -> models.FamilyPreference:
    db_pref = get_or_create_family_preference(db, family_id)
    
    for key, value in pref.dict(exclude_unset=True).items():
        setattr(db_pref, key, value)
    db_pref.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_pref)
    return db_pref

# Family Profile operations
def update_family_profile(db: Session, family_id: UUID, profile: schemas.FamilyProfileUpdate) -> Optional[models.Family]:
    db_family = get_family(db, family_id)
    if not db_family:
        return None
    
    for key, value in profile.dict(exclude_unset=True).items():
        setattr(db_family, key, value)
    db.commit()
    db.refresh(db_family)
    return db_family

def get_family_profile(db: Session, family_id: UUID) -> Optional[models.Family]:
    return get_family(db, family_id)
# Activation Token operations
def create_activation_token(db: Session, user_id: UUID, expires_in_hours: int = 72) -> models.ActivationToken:
    """Create an activation token for a user. Valid for specified hours (default 72)."""
    import secrets
    from datetime import timedelta
    
    token_string = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
    
    db_token = models.ActivationToken(
        user_id=user_id,
        token=token_string,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def get_activation_token(db: Session, token: str) -> Optional[models.ActivationToken]:
    """Get activation token by token string."""
    return db.query(models.ActivationToken).filter(
        models.ActivationToken.token == token,
        models.ActivationToken.used_at.is_(None)  # Only unused tokens
    ).first()

def verify_activation_token(db: Session, token: str) -> Tuple[bool, Optional[models.ActivationToken]]:
    """
    Verify if activation token is valid (exists, not expired, not used).
    Returns (is_valid, token_object)
    """
    db_token = get_activation_token(db, token)
    if not db_token:
        return False, None
    
    if db_token.expires_at < datetime.utcnow():
        return False, db_token  # Expired
    
    return True, db_token

def mark_activation_token_used(db: Session, token_id: UUID) -> bool:
    """Mark activation token as used."""
    db_token = db.query(models.ActivationToken).filter(
        models.ActivationToken.id == token_id
    ).first()
    
    if not db_token:
        return False
    
    db_token.used_at = datetime.utcnow()
    db.commit()
    return True

def create_member_with_activation_token(
    db: Session, 
    email: str, 
    first_name: str,
    last_name: str,
    family_id: UUID, 
    role: models.Role = models.Role.MEMBER,
    activation_token_hours: int = 72
) -> Tuple[models.User, models.ActivationToken]:
    """
    Create a new family member with activation token.
    User needs to set password using activation token before they can log in.
    """
    # Create user without password (will set later)
    db_user = models.User(
        family_id=family_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        password_hash=None,  # Will be set when user sets password
        password_required=True,
        activated=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create activation token
    activation_token = create_activation_token(db, db_user.id, activation_token_hours)
    
    return db_user, activation_token

def set_user_password_from_token(
    db: Session, 
    token: str, 
    password: str
) -> Optional[models.User]:
    """
    Set user password using activation token.
    Mark the token as used and activate the user.
    """
    # Verify token
    is_valid, db_token = verify_activation_token(db, token)
    if not is_valid:
        return None
    
    # Get user
    user = db.query(models.User).filter(
        models.User.id == db_token.user_id
    ).first()
    
    if not user:
        return None
    
    # Set password
    hashed_password = auth.get_password_hash(password)
    user.password_hash = hashed_password
    user.password_required = False
    user.activated = True
    
    # Mark token as used
    mark_activation_token_used(db, db_token.id)

    db.commit()
    db.refresh(user)
    return user


# ============ Refresh Token Rotation ============

def store_refresh_token(db: Session, jti: str, user_id, token_version: int, expires_at: datetime) -> None:
    rt = models.RefreshToken(
        jti=jti, user_id=user_id, token_version=token_version, expires_at=expires_at
    )
    db.add(rt)
    db.commit()

def consume_refresh_token(db: Session, jti: str) -> bool:
    """Mark token as used. Returns False if not found or already used (reuse detected)."""
    rt = db.query(models.RefreshToken).filter(
        models.RefreshToken.jti == jti,
        models.RefreshToken.used_at.is_(None)
    ).first()
    if not rt:
        return False
    rt.used_at = datetime.utcnow()
    db.commit()
    return True

def prune_expired_refresh_tokens(db: Session) -> int:
    deleted = db.query(models.RefreshToken).filter(
        models.RefreshToken.expires_at < datetime.utcnow()
    ).delete(synchronize_session=False)
    db.commit()
    return deleted


# ============ WebAuthn ============

def store_webauthn_challenge(db: Session, user_id, challenge_b64: str, purpose: str) -> models.WebAuthnChallenge:
    from datetime import timedelta
    ch = models.WebAuthnChallenge(
        user_id=user_id,
        challenge=challenge_b64,
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )
    db.add(ch)
    db.commit()
    return ch

def consume_webauthn_challenge(db: Session, user_id, purpose: str) -> Optional[str]:
    ch = db.query(models.WebAuthnChallenge).filter(
        models.WebAuthnChallenge.user_id == user_id,
        models.WebAuthnChallenge.purpose == purpose,
        models.WebAuthnChallenge.used == False,
        models.WebAuthnChallenge.expires_at > datetime.utcnow()
    ).order_by(models.WebAuthnChallenge.created_at.desc()).first()
    if not ch:
        return None
    ch.used = True
    db.commit()
    return ch.challenge

def store_webauthn_credential(
    db: Session, user_id, credential_id: str, public_key: str,
    sign_count: int, device_name: Optional[str]
) -> models.WebAuthnCredential:
    cred = models.WebAuthnCredential(
        user_id=user_id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=sign_count,
        device_name=device_name
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred

def get_webauthn_credentials(db: Session, user_id) -> List[models.WebAuthnCredential]:
    return db.query(models.WebAuthnCredential).filter(
        models.WebAuthnCredential.user_id == user_id
    ).all()

def get_webauthn_credential_by_id(db: Session, credential_id: str) -> Optional[models.WebAuthnCredential]:
    return db.query(models.WebAuthnCredential).filter(
        models.WebAuthnCredential.credential_id == credential_id
    ).first()

def update_webauthn_sign_count(db: Session, credential: models.WebAuthnCredential, sign_count: int) -> None:
    credential.sign_count = sign_count
    db.commit()

def delete_webauthn_credential(db: Session, credential_id: str, user_id) -> bool:
    cred = db.query(models.WebAuthnCredential).filter(
        models.WebAuthnCredential.credential_id == credential_id,
        models.WebAuthnCredential.user_id == user_id
    ).first()
    if not cred:
        return False
    db.delete(cred)
    db.commit()
    return True

def prune_expired_webauthn_challenges(db: Session) -> int:
    deleted = db.query(models.WebAuthnChallenge).filter(
        models.WebAuthnChallenge.expires_at < datetime.utcnow()
    ).delete(synchronize_session=False)
    db.commit()
    return deleted

