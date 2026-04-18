import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Enum, Numeric, Text, Integer, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class Role(enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"

class AccountType(enum.Enum):
    CASH = "CASH"
    BANK = "BANK"
    CREDIT_CARD = "CREDIT_CARD"
    INVESTMENT = "INVESTMENT"

# Account types that represent liabilities (inverted balance sign convention).
# Add new liability types here (e.g. LOAN, MORTGAGE) without changing financial logic.
LIABILITY_ACCOUNT_TYPES: frozenset = frozenset({AccountType.CREDIT_CARD})

class OwnerType(enum.Enum):
    PERSONAL = "PERSONAL"
    SHARED = "SHARED"

class TransactionType(enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"

class CategoryType(enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

class PrivacyLevel(enum.Enum):
    PRIVATE = "PRIVATE"    # Members only see their own transactions
    SHARED = "SHARED"      # Members see shared accounts + their own
    FAMILY = "FAMILY"      # Everyone sees everything

class BudgetPeriod(enum.Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"

class RecurrencePattern(enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"

class NotificationChannel(enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    BOTH = "BOTH"

class ExchangeRateSource(enum.Enum):
    MANUAL = "MANUAL"
    AUTO_FETCHED = "AUTO_FETCHED"

class Family(Base):
    __tablename__ = "families"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    base_currency = Column(String(3), default="USD")
    fiscal_month_start = Column(String(2), default="01")  # Month for budget calculation
    privacy_level = Column(Enum(PrivacyLevel), default=PrivacyLevel.FAMILY)  # Who can see what
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    users = relationship("User", back_populates="family")
    accounts = relationship("Account", back_populates="family")
    categories = relationship("Category", back_populates="family")
    member_permissions = relationship("MemberPermission", back_populates="family")
    budget_settings = relationship("BudgetSetting", back_populates="family")
    recurring_payments = relationship("RecurringPayment", back_populates="family")
    family_preferences = relationship("FamilyPreference", back_populates="family")
    family_currencies = relationship("FamilyCurrency", back_populates="family")
    exchange_rates = relationship("ExchangeRate", back_populates="family")

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable until user sets password
    role = Column(Enum(Role), default=Role.MEMBER)
    token_version = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True)
    activated = Column(Boolean, default=False)  # True after user sets password for first time
    password_required = Column(Boolean, default=True)  # True if user must set password on first login
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    family = relationship("Family", back_populates="users")
    personal_accounts = relationship("Account", foreign_keys="Account.owner_user_id", back_populates="owner")
    created_transactions = relationship("Transaction", back_populates="created_by")
    activation_tokens = relationship("ActivationToken", back_populates="user")
    
    @property
    def full_name(self):
        """Get full name (first and last)"""
        return f"{self.first_name} {self.last_name}".strip()

class ActivationToken(Base):
    __tablename__ = "activation_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)  # NULL if not used yet
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="activation_tokens")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    credential_id = Column(String(512), unique=True, nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0, nullable=False)
    device_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class WebAuthnChallenge(Base):
    __tablename__ = "webauthn_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    challenge = Column(String(512), nullable=False)
    purpose = Column(String(20), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(Enum(AccountType), nullable=False)
    currency = Column(String(3), default="USD")
    owner_type = Column(Enum(OwnerType), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    include_in_family_overview = Column(Boolean, default=True)
    opening_balance = Column(Numeric(15, 2), default=0)
    current_balance = Column(Numeric(15, 2), default=0)
    country_code = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    family = relationship("Family", back_populates="accounts")
    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="personal_accounts")
    transactions = relationship("Transaction", back_populates="account")
    
    @property
    def owner_name(self):
        """Get owner's first name for serialization"""
        return self.owner.first_name if self.owner else None

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(Enum(CategoryType), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    color = Column(String(7), default="#3498db")
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    family = relationship("Family", back_populates="categories")
    parent = relationship("Category", remote_side="Category.id", backref="children")
    transactions = relationship("Transaction", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    exchange_rate_to_base = Column(Numeric(10, 6), default=1.0)
    amount_in_base_currency = Column(Numeric(15, 2), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    transaction_date = Column(DateTime, nullable=False)
    linked_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    is_source_transaction = Column(Boolean, default=True)  # True for source/outgoing, False for target/incoming of transfers
    receipt_url = Column(String(255), nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurring_pattern = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="transactions")
    created_by = relationship("User", back_populates="created_transactions")
    category = relationship("Category", back_populates="transactions")
    linked_transaction = relationship("Transaction", remote_side="Transaction.id", backref="linked_to")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MemberPermission(Base):
    __tablename__ = "member_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    can_add_transaction = Column(Boolean, default=True)
    can_edit_transaction = Column(Boolean, default=True)
    can_delete_transaction = Column(Boolean, default=False)
    can_add_account = Column(Boolean, default=False)
    can_edit_account = Column(Boolean, default=False)
    can_delete_account = Column(Boolean, default=False)
    can_manage_categories = Column(Boolean, default=False)
    can_view_all_accounts = Column(Boolean, default=True)
    can_view_all_transactions = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    family = relationship("Family", back_populates="member_permissions")
    user = relationship("User")

class BudgetSetting(Base):
    __tablename__ = "budget_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # NULL for family budget
    limit_amount = Column(Numeric(15, 2), nullable=False)
    period = Column(Enum(BudgetPeriod), default=BudgetPeriod.MONTHLY)
    spent_amount = Column(Numeric(15, 2), default=0)
    alert_threshold = Column(Numeric(3, 2), default=0.80)  # Alert at 80% spent
    notify_channels = Column(String(50), default="BOTH")  # Comma-separated: IN_APP, EMAIL
    is_active = Column(Boolean, default=True)
    fiscal_year_start = Column(String(5), nullable=True)  # MM-DD format
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    family = relationship("Family", back_populates="budget_settings")
    category = relationship("Category")
    user = relationship("User")

class RecurringPayment(Base):
    __tablename__ = "recurring_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name = Column(String(100), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    pattern = Column(Enum(RecurrencePattern), nullable=False)
    next_due_date = Column(DateTime, nullable=False)
    last_paid_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)  # NULL means ongoing
    notify_before_days = Column(String(5), default="3")  # Days before due date
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    family = relationship("Family", back_populates="recurring_payments")
    account = relationship("Account")
    category = relationship("Category")
    assigned_to_user = relationship("User", foreign_keys=[assigned_to_user_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

class FamilyPreference(Base):
    __tablename__ = "family_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), unique=True, nullable=False)
    theme = Column(String(20), default="light")
    language = Column(String(10), default="en")
    show_budget_alerts = Column(Boolean, default=True)
    two_factor_enabled = Column(Boolean, default=False)
    show_net_worth_by_country = Column(Boolean, default=True)
    show_member_spending = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    family = relationship("Family", back_populates="family_preferences")


class FamilyCurrency(Base):
    __tablename__ = "family_currencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    currency_code = Column(String(3), nullable=False)  # ISO 4217
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("family_id", "currency_code", name="uq_family_currency"),
    )

    family = relationship("Family", back_populates="family_currencies")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(10, 6), nullable=False)
    source = Column(Enum(ExchangeRateSource), nullable=False)
    valid_date = Column(Date, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "family_id", "from_currency", "to_currency", "valid_date",
            name="uq_family_exchange_rate"
        ),
    )

    family = relationship("Family", back_populates="exchange_rates")

