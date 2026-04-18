from pydantic import BaseModel, EmailStr, Field, computed_field
from typing import Optional, List, Literal
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from app.models import Role, AccountType, OwnerType, TransactionType, CategoryType, BudgetPeriod, RecurrencePattern, NotificationChannel, LIABILITY_ACCOUNT_TYPES, ExchangeRateSource, GoalType

# Family schemas
class FamilyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_currency: str = Field(default="USD", pattern="^[A-Z]{3}$")

class FamilyCreate(FamilyBase):
    pass

class FamilyResponse(FamilyBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

# User schemas
class UserBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    family_name: Optional[str] = None
    base_currency: Optional[str] = "USD"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: UUID
    family_id: UUID
    role: Role
    active: bool
    activated: bool
    password_required: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    active: Optional[bool] = None

# Member creation/invitation schemas (for in-app member addition)
class MemberCreateRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: Role = Role.MEMBER

class MemberInviteInformation(BaseModel):
    """Information returned when a member is created with activation token"""
    user_id: UUID
    email: str
    first_name: str
    last_name: str
    role: Role
    activation_token: str
    activation_expires_at: datetime
    
    class Config:
        from_attributes = True

class SetPasswordRequest(BaseModel):
    activation_token: str
    password: str = Field(..., min_length=8)

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

class PasswordResetTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    user_email: str
    message: str = "Share this token with the user to reset their password"
    
    class Config:
        from_attributes = True

class ActivationTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    
    class Config:
        from_attributes = True

class ActivationTokenVerification(BaseModel):
    valid: bool
    expires_at: Optional[datetime] = None
    user_email: Optional[str] = None
    
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenRefresh(BaseModel):
    refresh_token: str

# WebAuthn schemas
class WebAuthnRegisterCompleteRequest(BaseModel):
    credential_id: str
    client_data_json: str
    attestation_object: str
    device_name: Optional[str] = None

class WebAuthnAuthBeginRequest(BaseModel):
    user_id: UUID

class WebAuthnAuthCompleteRequest(BaseModel):
    user_id: UUID
    credential_id: str
    client_data_json: str
    authenticator_data: str
    signature: str
    user_handle: Optional[str] = None

class WebAuthnCredentialResponse(BaseModel):
    id: UUID
    credential_id: str
    device_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Account schemas
class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AccountType
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    owner_type: OwnerType
    include_in_family_overview: bool = True
    opening_balance: Decimal = Field(default=0, ge=0)
    country_code: Optional[str] = Field(default=None, pattern="^[A-Z]{2}$")

class AccountCreate(AccountBase):
    owner_user_id: Optional[UUID] = None

class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    include_in_family_overview: Optional[bool] = None
    sort_order: Optional[int] = None
    country_code: Optional[str] = Field(default=None, pattern="^[A-Z]{2}$")
    current_value: Optional[Decimal] = None
    last_valued_at: Optional[datetime] = None

class BalanceAdjustRequest(BaseModel):
    new_balance: Decimal

class AccountResponse(AccountBase):
    id: UUID
    family_id: UUID
    owner_user_id: Optional[UUID]
    owner_name: Optional[str] = None
    current_balance: Decimal
    current_value: Optional[Decimal] = None
    last_valued_at: Optional[datetime] = None
    sort_order: int = 0
    country_code: Optional[str] = None
    created_at: datetime

    @computed_field
    @property
    def account_class(self) -> Literal["ASSET", "LIABILITY"]:
        return "LIABILITY" if self.type in LIABILITY_ACCOUNT_TYPES else "ASSET"

    class Config:
        from_attributes = True

class AccountReorderItem(BaseModel):
    id: UUID
    sort_order: int

# Category schemas
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: CategoryType
    color: Optional[str] = Field(default="#3498db", pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None

class CategoryCreate(CategoryBase):
    parent_id: Optional[UUID] = None

class CategoryResponse(CategoryBase):
    id: UUID
    family_id: UUID
    parent_id: Optional[UUID]
    sort_order: int = 0
    is_system: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class CategoryReorderItem(BaseModel):
    id: UUID
    sort_order: int

# Transaction schemas
class TransactionBase(BaseModel):
    type: TransactionType
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., pattern="^[A-Z]{3}$")
    exchange_rate_to_base: Optional[Decimal] = Field(default=None)
    description: Optional[str] = None
    transaction_date: datetime
    category_id: Optional[UUID] = None

class TransactionCreate(TransactionBase):
    currency: Optional[str] = Field(default=None, pattern="^[A-Za-z]{3}$")
    account_id: UUID
    target_account_id: Optional[UUID] = None  # For transfers
    transfer_conversion_rate: Optional[Decimal] = Field(default=None, gt=0)  # Source→target rate for cross-currency transfers

class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    transaction_date: Optional[datetime] = None

class TransactionResponse(TransactionBase):
    id: UUID
    account_id: UUID
    created_by_user_id: UUID
    amount_in_base_currency: Decimal
    linked_transaction_id: Optional[UUID]
    is_source_transaction: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionListResponse(TransactionResponse):
    account: AccountResponse
    category: Optional[CategoryResponse] = None
    created_by: UserResponse

# Dashboard schemas
class DashboardSummary(BaseModel):
    total_net_worth: Decimal
    total_investments: Decimal
    total_cash: Decimal
    total_bank_balance: Decimal
    total_credit_liability: Decimal
    monthly_income: Decimal
    monthly_expense: Decimal
    monthly_savings: Decimal
    monthly_income_trend: Optional[float] = None
    monthly_expense_trend: Optional[float] = None
    base_currency: str

class CategoryBreakdown(BaseModel):
    category_id: UUID
    category_name: str
    total_amount: Decimal
    percentage: float
    color: str

class MemberSpending(BaseModel):
    user_id: UUID
    user_name: str
    total_expense: Decimal
    transaction_count: int

class DashboardData(BaseModel):
    summary: DashboardSummary
    category_breakdown: List[CategoryBreakdown]
    member_spending: List[MemberSpending]
    recent_transactions: List[TransactionListResponse]

# Export schema
class ExportRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    account_ids: Optional[List[UUID]] = None
    format: str = Field(default="csv", pattern="^(csv|excel)$")

# Member Permission schemas
class MemberPermissionBase(BaseModel):
    can_add_transaction: bool = True
    can_edit_transaction: bool = True
    can_delete_transaction: bool = False
    can_add_account: bool = False
    can_edit_account: bool = False
    can_delete_account: bool = False
    can_manage_categories: bool = False
    can_view_all_accounts: bool = True
    can_view_all_transactions: bool = True

class MemberPermissionCreate(MemberPermissionBase):
    user_id: UUID

class MemberPermissionUpdate(BaseModel):
    can_add_transaction: Optional[bool] = None
    can_edit_transaction: Optional[bool] = None
    can_delete_transaction: Optional[bool] = None
    can_add_account: Optional[bool] = None
    can_edit_account: Optional[bool] = None
    can_delete_account: Optional[bool] = None
    can_manage_categories: Optional[bool] = None
    can_view_all_accounts: Optional[bool] = None
    can_view_all_transactions: Optional[bool] = None

class MemberPermissionResponse(MemberPermissionBase):
    id: UUID
    family_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Budget Setting schemas
class BudgetSettingBase(BaseModel):
    limit_amount: Decimal = Field(..., gt=0)
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    alert_threshold: Decimal = Field(default=0.80, ge=0, le=1)
    notify_channels: str = "BOTH"
    is_active: bool = True
    fiscal_year_start: Optional[str] = None

class BudgetSettingCreate(BudgetSettingBase):
    category_id: Optional[UUID] = None
    user_id: Optional[UUID] = None

class BudgetSettingUpdate(BaseModel):
    limit_amount: Optional[Decimal] = Field(None, gt=0)
    alert_threshold: Optional[Decimal] = Field(None, ge=0, le=1)
    notify_channels: Optional[str] = None
    is_active: Optional[bool] = None

class BudgetSettingResponse(BudgetSettingBase):
    id: UUID
    family_id: UUID
    category_id: Optional[UUID]
    user_id: Optional[UUID]
    spent_amount: Decimal
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BudgetWithCategoryResponse(BudgetSettingResponse):
    category: Optional[CategoryResponse] = None

# Recurring Payment schemas
class RecurringPaymentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0)
    pattern: RecurrencePattern
    next_due_date: datetime
    notify_before_days: str = "3"
    is_active: bool = True
    description: Optional[str] = None

class RecurringPaymentCreate(RecurringPaymentBase):
    account_id: UUID
    category_id: UUID
    assigned_to_user_id: Optional[UUID] = None
    end_date: Optional[datetime] = None

class RecurringPaymentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(None, gt=0)
    next_due_date: Optional[datetime] = None
    notify_before_days: Optional[str] = None
    assigned_to_user_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    end_date: Optional[datetime] = None

class RecurringPaymentResponse(RecurringPaymentBase):
    id: UUID
    family_id: UUID
    account_id: UUID
    category_id: UUID
    assigned_to_user_id: Optional[UUID]
    last_paid_date: Optional[datetime]
    end_date: Optional[datetime]
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class RecurringPaymentDetailResponse(RecurringPaymentResponse):
    account: AccountResponse
    category: CategoryResponse
    assigned_to_user: Optional[UserResponse] = None
    created_by_user: UserResponse

# Family Preference schemas
class FamilyPreferenceBase(BaseModel):
    theme: str = "light"
    language: str = "en"
    show_budget_alerts: bool = True
    two_factor_enabled: bool = False
    show_net_worth_by_country: bool = True
    show_member_spending: bool = True

class FamilyPreferenceCreate(FamilyPreferenceBase):
    pass

class FamilyPreferenceUpdate(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    show_budget_alerts: Optional[bool] = None
    two_factor_enabled: Optional[bool] = None
    show_net_worth_by_country: Optional[bool] = None
    show_member_spending: Optional[bool] = None
    ai_categorization_enabled: Optional[bool] = None
    ai_monthly_narrative_enabled: Optional[bool] = None
    ai_weekly_digest_enabled: Optional[bool] = None
    ai_receipt_ocr_enabled: Optional[bool] = None
    ai_voice_entry_enabled: Optional[bool] = None
    # AI provider selection (NULL = use server default)
    ai_provider: Optional[str] = None     # "local" | "openai" | "anthropic" | "google"
    ai_model_override: Optional[str] = None

class FamilyPreferenceResponse(FamilyPreferenceBase):
    id: UUID
    family_id: UUID
    # AI feature flags
    ai_categorization_enabled: bool = True
    ai_monthly_narrative_enabled: bool = True
    ai_weekly_digest_enabled: bool = True
    ai_receipt_ocr_enabled: bool = True
    ai_voice_entry_enabled: bool = True
    ai_statement_upload_enabled: bool = True
    # AI provider selection
    ai_provider: Optional[str] = None
    ai_model_override: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Family Profile Update
class FamilyProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_currency: Optional[str] = Field(None, pattern="^[A-Z]{3}$")
    fiscal_month_start: Optional[str] = Field(None, pattern="^(0[1-9]|1[0-2])$")
    privacy_level: Optional[str] = None

class FamilyProfileResponse(BaseModel):
    id: UUID
    name: str
    base_currency: str
    fiscal_month_start: str
    privacy_level: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Member Invite schemas
class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: Optional[Role] = Role.MEMBER

class MemberInviteResponse(BaseModel):
    id: UUID
    email: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Transfer Admin Role
class TransferAdminRequest(BaseModel):
    new_admin_user_id: UUID

# Family currency

class FamilyCurrencyCreate(BaseModel):
    currency_code: str = Field(..., pattern="^[A-Z]{3}$")

class FamilyCurrencyResponse(BaseModel):
    id: UUID
    family_id: UUID
    currency_code: str
    added_at: datetime
    # Current rate vs base currency (injected at query time, not stored on model)
    current_rate: Optional[Decimal] = None

    class Config:
        from_attributes = True

# Exchange rates

class ExchangeRateResponse(BaseModel):
    id: UUID
    family_id: UUID
    from_currency: str
    to_currency: str
    rate: Decimal
    source: ExchangeRateSource
    valid_date: date
    fetched_at: datetime

    class Config:
        from_attributes = True

class ExchangeRateManualUpdate(BaseModel):
    from_currency: str = Field(..., pattern="^[A-Z]{3}$")
    to_currency: str = Field(..., pattern="^[A-Z]{3}$")
    rate: Decimal = Field(..., gt=0)
    valid_date: date

# Dashboard

class CountryBreakdown(BaseModel):
    country_code: Optional[str]      # None = "Other / Unassigned"
    country_name: Optional[str]
    total_in_base: Decimal
    base_currency: str

class DashboardDataWithCountry(DashboardData):
    country_breakdown: List[CountryBreakdown] = []
    rates_as_of: Optional[date] = None


# AI

class AIStatusResponse(BaseModel):
    ai_service_available: bool
    ai_categorization_enabled: bool
    ai_monthly_narrative_enabled: bool
    ai_weekly_digest_enabled: bool
    ai_receipt_ocr_enabled: bool
    ai_voice_entry_enabled: bool
    ai_statement_upload_enabled: bool
    ai_provider: str = "local"           # effective provider: local | openai | anthropic | google
    ai_model: str = ""                   # effective model name in use
    configured_providers: list[str] = [] # providers with API keys configured on this server


class CategorizationRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)


class CategorizationResponse(BaseModel):
    category: str
    category_id: Optional[UUID] = None
    confidence: str  # "high" | "medium" | "low"


class ReceiptParseResponse(BaseModel):
    is_receipt: bool
    merchant: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    date: Optional[str] = None          # YYYY-MM-DD string
    category_hint: Optional[str] = None


class VoiceParseResponse(BaseModel):
    is_transaction: bool
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    category_hint: Optional[str] = None


class VoiceTranscriptRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=1000)


class StatementTransaction(BaseModel):
    """One row extracted from a bank/credit-card statement."""
    date: Optional[str] = None          # YYYY-MM-DD
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None      # populated after AI categorisation
    category_hint: Optional[str] = None
    duplicate: bool = False             # True if a matching transaction already exists


class StatementParseResponse(BaseModel):
    transactions: list[StatementTransaction]
    raw_count: int    # how many rows the AI found before duplicate check
    currency_hint: Optional[str] = None  # inferred from statement if detectable


class BulkTransactionItem(BaseModel):
    """Single item in a bulk create request (EXPENSE only)."""
    type: str = "EXPENSE"
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    description: str = Field("", max_length=500)
    transaction_date: str                # ISO datetime string
    account_id: UUID
    category_id: Optional[UUID] = None
    exchange_rate_to_base: Optional[Decimal] = None


class BulkTransactionCreate(BaseModel):
    transactions: list[BulkTransactionItem] = Field(..., min_length=1, max_length=200)


class BulkTransactionResponse(BaseModel):
    created: int
    failed: int
    transaction_ids: list[UUID]


class AINarrativeResponse(BaseModel):
    id: UUID
    family_id: UUID
    narrative_type: str
    period_label: str
    content: str
    generated_at: datetime
    dismissed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NetWorthSnapshotResponse(BaseModel):
    id: UUID
    family_id: UUID
    snapshot_date: date
    total_net_worth: Decimal
    breakdown_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GoalCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: GoalType
    target_amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    target_date: Optional[date] = None
    linked_account_id: Optional[UUID] = None
    notes: Optional[str] = None


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    target_amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    target_date: Optional[date] = None
    linked_account_id: Optional[UUID] = None
    notes: Optional[str] = None
    archived_at: Optional[datetime] = None


class GoalResponse(BaseModel):
    id: UUID
    family_id: UUID
    name: str
    type: GoalType
    target_amount: Decimal
    current_amount: Decimal = Decimal("0")
    currency: str
    target_date: Optional[date] = None
    linked_account_id: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GoalProgress(BaseModel):
    goal_id: UUID
    name: str
    type: GoalType
    target_amount: Decimal
    current_amount: Decimal
    currency: str
    percent: float
    target_date: Optional[date] = None
    months_remaining: Optional[int] = None
    monthly_needed: Optional[Decimal] = None
    days_remaining: Optional[int] = None


class GoalContributeRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    note: Optional[str] = Field(None, max_length=500)
    contributed_at: Optional[date] = None


class GoalContributionResponse(BaseModel):
    id: UUID
    goal_id: UUID
    amount: Decimal
    note: Optional[str] = None
    contributed_at: date
    created_at: datetime

    class Config:
        from_attributes = True



