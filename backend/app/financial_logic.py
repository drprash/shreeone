import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, case, or_
from app import models, schemas

log = logging.getLogger(__name__)

class FinancialEngine:
    # Default exchange rates relative to USD (1 unit of currency = X USD)
    # Source: Real-world approximate rates as of 2026
    DEFAULT_RATES = {
        # Major reserve currencies
        'USD': Decimal('1.0'),        # Base reference
        'EUR': Decimal('1.10'),       # 1 EUR ≈ 1.10 USD
        'GBP': Decimal('1.28'),       # 1 GBP ≈ 1.28 USD
        'CHF': Decimal('1.10'),       # 1 CHF ≈ 1.10 USD
        # Asia-Pacific
        'JPY': Decimal('0.0067'),     # 1 JPY ≈ 0.0067 USD  (1 USD ≈ 150 JPY)
        'CNY': Decimal('0.138'),      # 1 CNY ≈ 0.138 USD   (1 USD ≈ 7.25 CNY)
        'HKD': Decimal('0.128'),      # 1 HKD ≈ 0.128 USD   (1 USD ≈ 7.80 HKD)
        'KRW': Decimal('0.00073'),    # 1 KRW ≈ 0.00073 USD (1 USD ≈ 1,370 KRW)
        'TWD': Decimal('0.031'),      # 1 TWD ≈ 0.031 USD   (1 USD ≈ 32.5 TWD)
        'SGD': Decimal('0.74'),       # 1 SGD ≈ 0.74 USD    (1 USD ≈ 1.35 SGD)
        'AUD': Decimal('0.67'),       # 1 AUD ≈ 0.67 USD
        'NZD': Decimal('0.60'),       # 1 NZD ≈ 0.60 USD
        # South & Southeast Asia
        'INR': Decimal('0.012'),      # 1 INR ≈ 0.012 USD   (1 USD ≈ 83 INR)
        'BDT': Decimal('0.0091'),     # 1 BDT ≈ 0.0091 USD  (1 USD ≈ 110 BDT)
        'PKR': Decimal('0.0036'),     # 1 PKR ≈ 0.0036 USD  (1 USD ≈ 278 PKR)
        'LKR': Decimal('0.0034'),     # 1 LKR ≈ 0.0034 USD  (1 USD ≈ 295 LKR)
        'NPR': Decimal('0.0075'),     # 1 NPR ≈ 0.0075 USD  (1 USD ≈ 133 NPR)
        'MYR': Decimal('0.22'),       # 1 MYR ≈ 0.22 USD    (1 USD ≈ 4.50 MYR)
        'THB': Decimal('0.028'),      # 1 THB ≈ 0.028 USD   (1 USD ≈ 36 THB)
        'PHP': Decimal('0.017'),      # 1 PHP ≈ 0.017 USD   (1 USD ≈ 58 PHP)
        'IDR': Decimal('0.000062'),   # 1 IDR ≈ 0.000062 USD (1 USD ≈ 16,000 IDR)
        # Gulf / Middle East
        'AED': Decimal('0.272'),      # 1 AED ≈ 0.272 USD   (1 USD ≈ 3.67 AED, pegged)
        'SAR': Decimal('0.267'),      # 1 SAR ≈ 0.267 USD   (1 USD ≈ 3.75 SAR, pegged)
        'QAR': Decimal('0.275'),      # 1 QAR ≈ 0.275 USD   (1 USD ≈ 3.64 QAR, pegged)
        'KWD': Decimal('3.25'),       # 1 KWD ≈ 3.25 USD    (1 USD ≈ 0.308 KWD)
        'BHD': Decimal('2.65'),       # 1 BHD ≈ 2.65 USD    (1 USD ≈ 0.376 BHD, pegged)
        'OMR': Decimal('2.60'),       # 1 OMR ≈ 2.60 USD    (1 USD ≈ 0.385 OMR, pegged)
        # Canada
        'CAD': Decimal('0.74'),       # 1 CAD ≈ 0.74 USD
        # Europe (non-EUR)
        'SEK': Decimal('0.096'),      # 1 SEK ≈ 0.096 USD   (1 USD ≈ 10.4 SEK)
        'NOK': Decimal('0.094'),      # 1 NOK ≈ 0.094 USD   (1 USD ≈ 10.6 NOK)
        'DKK': Decimal('0.147'),      # 1 DKK ≈ 0.147 USD   (1 USD ≈ 6.80 DKK)
        'PLN': Decimal('0.25'),       # 1 PLN ≈ 0.25 USD    (1 USD ≈ 4.00 PLN)
        'CZK': Decimal('0.044'),      # 1 CZK ≈ 0.044 USD   (1 USD ≈ 22.7 CZK)
        # Americas
        'BRL': Decimal('0.18'),       # 1 BRL ≈ 0.18 USD    (1 USD ≈ 5.50 BRL)
        'MXN': Decimal('0.058'),      # 1 MXN ≈ 0.058 USD   (1 USD ≈ 17.2 MXN)
        # Africa
        'ZAR': Decimal('0.054'),      # 1 ZAR ≈ 0.054 USD   (1 USD ≈ 18.5 ZAR)
        'KES': Decimal('0.0077'),     # 1 KES ≈ 0.0077 USD  (1 USD ≈ 130 KES)
        'NGN': Decimal('0.00063'),    # 1 NGN ≈ 0.00063 USD (1 USD ≈ 1,580 NGN)
    }

    @staticmethod
    def get_rate_relative_to_base(currency: str, base_usd_rate: Optional[Decimal] = None) -> Decimal:
        """Get the rate for a currency relative to a common base (USD).
        
        DEFAULT_RATES represents: 1 unit of currency X = Y USD
        Example: EUR: 1.1 means 1 EUR = 1.1 USD
        """
        if base_usd_rate is None:
            base_usd_rate = FinancialEngine.DEFAULT_RATES.get(currency, Decimal('1.0'))
        return base_usd_rate

    @staticmethod
    def get_exchange_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        family_id=None,
        for_date=None,
    ) -> Decimal:
        """Get exchange rate from one currency to another.

        Lookup order:
        1. Stored rate in `exchange_rates` table for this family (if family_id given)
        2. DEFAULT_RATES fallback (hardcoded approximates)

        Returns: factor to multiply amount_in_from_currency by to get amount_in_to_currency
        """
        if from_currency == to_currency:
            return Decimal('1.0')

        # 1. DB lookup (only if we know which family's rates to use)
        if family_id is not None:
            try:
                from app.exchange_rate_service import get_stored_rate
                stored = get_stored_rate(db, family_id, from_currency, to_currency, for_date)
                if stored is not None:
                    return stored
            except Exception:
                pass  # Fall through to DEFAULT_RATES

        # 2. DEFAULT_RATES fallback
        for currency in (from_currency, to_currency):
            if currency not in FinancialEngine.DEFAULT_RATES:
                log.warning(
                    "No exchange rate available for %s (%s→%s) — falling back to 1.0. "
                    "Converted amounts will be wrong until a rate is stored.",
                    currency, from_currency, to_currency,
                )
        from_rate = FinancialEngine.DEFAULT_RATES.get(from_currency, Decimal('1.0'))
        to_rate = FinancialEngine.DEFAULT_RATES.get(to_currency, Decimal('1.0'))

        if to_rate == 0 or from_rate == 0:
            return Decimal('1.0')

        return from_rate / to_rate

    @staticmethod
    def calculate_account_balance(db: Session, account_id: str) -> Decimal:
        """Calculate current balance based on transactions.

        For liability accounts the sign convention is inverted:
        - EXPENSE increases the balance (debt goes up)
        - INCOME decreases the balance (payment reduces debt)
        - A positive balance represents money owed (liability)

        For asset accounts:
        - INCOME increases the balance
        - EXPENSE decreases the balance

        Returns balance in the account's own currency.
        """
        account = db.query(models.Account).filter(models.Account.id == account_id).first()
        if not account:
            return Decimal('0')

        is_liability = account.type in models.LIABILITY_ACCOUNT_TYPES

        def signed_amount(col):
            """Apply the income/expense/transfer sign convention to an amount column."""
            if is_liability:
                income_amount, expense_amount = -col, col
                transfer_source_amount, transfer_target_amount = col, -col
            else:
                income_amount, expense_amount = col, -col
                transfer_source_amount, transfer_target_amount = -col, col
            return case(
                (models.Transaction.type == models.TransactionType.INCOME, income_amount),
                (models.Transaction.type == models.TransactionType.EXPENSE, expense_amount),
                (models.Transaction.type == models.TransactionType.TRANSFER,
                    case(
                        (models.Transaction.is_source_transaction == True, transfer_source_amount),
                        (models.Transaction.is_source_transaction == False, transfer_target_amount),
                        else_=Decimal('0')
                    )
                ),
                else_=Decimal('0')
            )

        # Transactions denominated in the account's own currency are summed
        # natively so the balance never drifts with exchange-rate changes.
        # Cross-currency transactions are carried in base currency and
        # converted to the account currency at the current rate below.
        native_sum, cross_base_sum = db.query(
            func.sum(case(
                (models.Transaction.currency == account.currency,
                 signed_amount(models.Transaction.amount)),
                else_=Decimal('0')
            )),
            func.sum(case(
                (models.Transaction.currency != account.currency,
                 signed_amount(models.Transaction.amount_in_base_currency)),
                else_=Decimal('0')
            )),
        ).filter(
            models.Transaction.account_id == account_id,
            models.Transaction.deleted_at.is_(None)
        ).one()

        balance = (account.opening_balance or Decimal('0')) + (native_sum or Decimal('0'))

        cross_base_sum = cross_base_sum or Decimal('0')
        if cross_base_sum:
            family = db.query(models.Family).filter(models.Family.id == account.family_id).first()
            base_currency = family.base_currency if family else account.currency
            if account.currency == base_currency:
                balance += cross_base_sum
            else:
                base_to_acc = FinancialEngine.get_exchange_rate(
                    db, base_currency, account.currency, family_id=account.family_id
                )
                balance += cross_base_sum * base_to_acc

        return balance

    @staticmethod
    def update_account_balance(db: Session, account_id: str):
        """Update stored balance — lock the row first to prevent concurrent overwrites."""
        account = db.query(models.Account).filter(
            models.Account.id == account_id
        ).with_for_update().first()
        if account:
            new_balance = FinancialEngine.calculate_account_balance(db, account_id)
            account.current_balance = new_balance
            db.commit()

    @staticmethod
    def validate_category(
        db: Session,
        family_id,
        tx_type: models.TransactionType,
        category_id,
    ) -> None:
        """Ensure a transaction's category belongs to the family and matches
        the transaction type. Raises ValueError on any violation."""
        if category_id is None:
            return
        if tx_type == models.TransactionType.TRANSFER:
            raise ValueError("Transfers cannot have a category")
        category = db.query(models.Category).filter(
            models.Category.id == category_id,
            models.Category.family_id == family_id,
            models.Category.deleted_at.is_(None),
        ).first()
        if not category:
            raise ValueError("Category not found")
        expected = (
            models.CategoryType.INCOME
            if tx_type == models.TransactionType.INCOME
            else models.CategoryType.EXPENSE
        )
        if category.type != expected:
            raise ValueError(
                f"Category type {category.type.value} does not match "
                f"transaction type {tx_type.value}"
            )

    @staticmethod
    def process_transaction(
        db: Session,
        user: models.User,
        transaction_data: schemas.TransactionCreate
    ) -> Tuple[models.Transaction, Optional[models.Transaction]]:
        """
        Process a transaction with proper financial logic:
        - Income: Increases account balance
        - Expense: Decreases account balance  
        - Transfer: Creates two linked transactions
        """
        account = db.query(models.Account).filter(
            models.Account.id == transaction_data.account_id
        ).first()
        
        if not account:
            raise ValueError("Account not found")

        FinancialEngine.validate_category(
            db, user.family_id, transaction_data.type, transaction_data.category_id
        )

        # Calculate amount in base currency
        base_currency = user.family.base_currency
        exchange_rate = transaction_data.exchange_rate_to_base
        
        if not exchange_rate:
            # Calculate exchange rate if not provided
            if transaction_data.currency == base_currency:
                exchange_rate = Decimal('1.0')
            else:
                tx_date = transaction_data.transaction_date.date() if transaction_data.transaction_date else None
                exchange_rate = FinancialEngine.get_exchange_rate(
                    db,
                    transaction_data.currency,
                    base_currency,
                    family_id=user.family_id,
                    for_date=tx_date,
                )
        
        amount_in_base = transaction_data.amount * exchange_rate
        
        # Create main transaction
        transaction = models.Transaction(
            account_id=transaction_data.account_id,
            created_by_user_id=user.id,
            type=transaction_data.type,
            amount=transaction_data.amount,
            currency=transaction_data.currency,
            exchange_rate_to_base=exchange_rate,
            amount_in_base_currency=amount_in_base,
            category_id=transaction_data.category_id,
            description=transaction_data.description,
            transaction_date=transaction_data.transaction_date,
            is_source_transaction=True  # This is the source transaction
        )
        
        db.add(transaction)
        db.flush()  # Get ID without committing
        
        linked_transaction = None
        
        # Handle transfers
        if transaction_data.type == models.TransactionType.TRANSFER and transaction_data.target_account_id:
            target_account = db.query(models.Account).filter(
                models.Account.id == transaction_data.target_account_id
            ).first()
            
            if not target_account:
                raise ValueError("Target account not found")
            
            # Convert source amount to target account's currency if needed
            if transaction_data.currency == target_account.currency:
                # Same currency, no conversion needed
                target_amount = transaction_data.amount
            else:
                # Different currencies — use user-supplied rate if provided, else auto-calculate
                if transaction_data.transfer_conversion_rate:
                    conversion_rate = transaction_data.transfer_conversion_rate
                else:
                    tx_date = transaction_data.transaction_date.date() if transaction_data.transaction_date else None
                    conversion_rate = FinancialEngine.get_exchange_rate(
                        db,
                        transaction_data.currency,
                        target_account.currency,
                        family_id=user.family_id,
                        for_date=tx_date,
                    )
                target_amount = transaction_data.amount * conversion_rate

            # Calculate exchange rate from target currency to base
            if target_account.currency == base_currency:
                target_exchange_rate = Decimal('1.0')
            else:
                tx_date = transaction_data.transaction_date.date() if transaction_data.transaction_date else None
                target_exchange_rate = FinancialEngine.get_exchange_rate(
                    db,
                    target_account.currency,
                    base_currency,
                    family_id=user.family_id,
                    for_date=tx_date,
                )
            
            target_amount_in_base = target_amount * target_exchange_rate
            
            linked_transaction = models.Transaction(
                account_id=transaction_data.target_account_id,
                created_by_user_id=user.id,
                type=models.TransactionType.TRANSFER,
                amount=target_amount,  # Amount in target account's currency
                currency=target_account.currency,
                exchange_rate_to_base=target_exchange_rate,
                amount_in_base_currency=target_amount_in_base,
                description=f"Transfer from {account.name}: {transaction_data.description or ''}",
                transaction_date=transaction_data.transaction_date,
                linked_transaction_id=transaction.id,
                is_source_transaction=False  # This is the target/incoming transaction
            )
            
            db.add(linked_transaction)
            db.flush()
            
            # Link back
            transaction.linked_transaction_id = linked_transaction.id
        
        db.commit()
        
        # Update balances
        FinancialEngine.update_account_balance(db, transaction_data.account_id)
        if linked_transaction:
            FinancialEngine.update_account_balance(db, transaction_data.target_account_id)
        
        return transaction, linked_transaction

    @staticmethod
    def get_period_stats(
        db: Session,
        family_id: str,
        user: "models.User",
        start_date: "date",
        end_date: "date",
    ) -> dict:
        """
        Return income, expenses, savings, savings_rate, categories, member_spending,
        and daily_totals for [start_date, end_date] inclusive.
        All amounts use amount_in_base_currency (family base currency).
        Privacy filtering mirrors get_family_dashboard_data().
        """
        from datetime import datetime, timedelta, date as date_type

        family = db.query(models.Family).filter_by(id=family_id).first()
        privacy_level = family.privacy_level if family else models.PrivacyLevel.FAMILY

        period_start = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
        period_end = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999)

        base_account_query = db.query(models.Account).filter(
            models.Account.family_id == family_id,
            models.Account.deleted_at.is_(None),
        )
        if user.role != models.Role.ADMIN:
            if privacy_level == models.PrivacyLevel.PRIVATE:
                base_account_query = base_account_query.filter(
                    models.Account.owner_user_id == user.id
                )
            elif privacy_level == models.PrivacyLevel.SHARED:
                base_account_query = base_account_query.filter(
                    or_(
                        models.Account.owner_type == models.OwnerType.SHARED,
                        models.Account.owner_user_id == user.id,
                    )
                )
        accounts = base_account_query.all()
        account_ids = [a.id for a in accounts]

        income = Decimal('0')
        expenses = Decimal('0')
        category_breakdown: list = []
        member_spending: list = []
        daily_totals: list = []

        if account_ids:
            base_tx_query = db.query(models.Transaction).join(
                models.Account, models.Transaction.account_id == models.Account.id
            ).filter(
                models.Transaction.account_id.in_(account_ids),
                models.Transaction.transaction_date >= period_start,
                models.Transaction.transaction_date <= period_end,
                models.Transaction.deleted_at.is_(None),
            )

            if user.role != models.Role.ADMIN:
                if privacy_level == models.PrivacyLevel.PRIVATE:
                    base_tx_query = base_tx_query.filter(
                        models.Transaction.created_by_user_id == user.id
                    )
                elif privacy_level == models.PrivacyLevel.SHARED:
                    base_tx_query = base_tx_query.filter(
                        or_(
                            models.Transaction.created_by_user_id == user.id,
                            models.Account.owner_type == models.OwnerType.SHARED,
                        )
                    )

            # Income / expense totals
            totals = base_tx_query.with_entities(
                models.Transaction.type,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
            ).group_by(models.Transaction.type).all()

            for tx_type, total in totals:
                if tx_type == models.TransactionType.INCOME:
                    income = Decimal(str(total or 0))
                elif tx_type == models.TransactionType.EXPENSE:
                    expenses = Decimal(str(total or 0))

            # Category breakdown (expenses with a category only)
            cat_totals = base_tx_query.with_entities(
                models.Transaction.category_id,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
            ).filter(
                models.Transaction.type == models.TransactionType.EXPENSE,
                models.Transaction.category_id.is_not(None),
            ).group_by(models.Transaction.category_id).all()

            if cat_totals:
                cat_ids = [cid for cid, _ in cat_totals if cid]
                cats = db.query(models.Category).filter(models.Category.id.in_(cat_ids)).all()
                cat_map = {c.id: c for c in cats}
                total_for_pct = sum(Decimal(str(a or 0)) for _, a in cat_totals) or Decimal('1')

                for cat_id, amount in cat_totals:
                    cat = cat_map.get(cat_id)
                    if not cat:
                        continue
                    d_amount = Decimal(str(amount or 0))
                    category_breakdown.append(schemas.CategoryBreakdown(
                        category_id=cat.id,
                        category_name=cat.name,
                        total_amount=d_amount,
                        percentage=float(d_amount / total_for_pct * 100),
                        color=cat.color or '#94a3b8',
                    ))

            # Member spending (expenses only)
            member_totals = base_tx_query.with_entities(
                models.Transaction.created_by_user_id,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0),
                func.count(models.Transaction.id),
            ).filter(
                models.Transaction.type == models.TransactionType.EXPENSE,
            ).group_by(models.Transaction.created_by_user_id).all()

            if member_totals:
                m_ids = [mid for mid, _, _ in member_totals if mid]
                members = db.query(models.User).filter(models.User.id.in_(m_ids)).all()
                member_map = {m.id: m for m in members}

                for member_id, total_amount, tx_count in member_totals:
                    member = member_map.get(member_id)
                    if not member:
                        continue
                    member_spending.append(schemas.MemberSpending(
                        user_id=member.id,
                        user_name=member.first_name,
                        total_expense=Decimal(str(total_amount or 0)),
                        transaction_count=int(tx_count or 0),
                    ))

            # Daily totals — one entry per calendar day in [start_date, end_date]
            day_map: dict = {}
            current_day = start_date
            while current_day <= end_date:
                day_map[current_day] = {'income': Decimal('0'), 'expenses': Decimal('0')}
                current_day += timedelta(days=1)

            daily_rows = base_tx_query.with_entities(
                func.date(models.Transaction.transaction_date),
                models.Transaction.type,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0),
            ).filter(
                models.Transaction.type.in_([
                    models.TransactionType.INCOME,
                    models.TransactionType.EXPENSE,
                ])
            ).group_by(
                func.date(models.Transaction.transaction_date),
                models.Transaction.type,
            ).all()

            for tx_date, tx_type, total in daily_rows:
                if tx_date in day_map:
                    if tx_type == models.TransactionType.INCOME:
                        day_map[tx_date]['income'] = Decimal(str(total or 0))
                    elif tx_type == models.TransactionType.EXPENSE:
                        day_map[tx_date]['expenses'] = Decimal(str(total or 0))

            daily_totals = [
                schemas.StatsDailyTotal(date=d, income=v['income'], expenses=v['expenses'])
                for d, v in sorted(day_map.items())
            ]

        savings = income - expenses
        savings_rate = round(float(savings / income * 100), 1) if income > 0 else 0.0

        return {
            'income': income,
            'expenses': expenses,
            'savings': savings,
            'savings_rate': savings_rate,
            'categories': category_breakdown,
            'member_spending': member_spending,
            'daily_totals': daily_totals,
        }

    @staticmethod
    def get_family_dashboard_data(db: Session, family_id: str, user: models.User) -> schemas.DashboardData:
        """Generate comprehensive dashboard data with privacy-level filtering"""
        from datetime import datetime, timedelta
        
        # Get date range for this month
        today = datetime.utcnow()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get family privacy level
        family = db.query(models.Family).filter_by(id=family_id).first()
        privacy_level = family.privacy_level if family else models.PrivacyLevel.FAMILY
        
        # Base query for included accounts
        base_account_query = db.query(models.Account).filter(
            models.Account.family_id == family_id,
            models.Account.deleted_at.is_(None)
        )
        
        # APPLY PRIVACY FILTERING
        if user.role != models.Role.ADMIN:
            if privacy_level == models.PrivacyLevel.PRIVATE:
                # Members only see their own personal accounts
                base_account_query = base_account_query.filter(
                    models.Account.owner_user_id == user.id
                )
            elif privacy_level == models.PrivacyLevel.SHARED:
                # Members see shared and their personal accounts
                base_account_query = base_account_query.filter(
                    or_(
                        models.Account.owner_type == models.OwnerType.SHARED,
                        models.Account.owner_user_id == user.id
                    )
                )
            # else PrivacyLevel.FAMILY: see all accounts (no additional filtering)
        
        accounts = base_account_query.all()
        account_ids = [a.id for a in accounts]
        account_lookup = {a.id: a for a in accounts}
        base_currency = user.family.base_currency
        
        # Calculate totals
        total_net_worth = Decimal('0')
        total_investments = Decimal('0')
        total_cash = Decimal('0')
        total_bank = Decimal('0')
        total_credit = Decimal('0')
        
        for account in accounts:
            # Excluded accounts stay out of family totals for everyone so the
            # net worth tile matches the snapshot chart (which also skips them)
            if not account.include_in_family_overview:
                continue

            balance = FinancialEngine.calculate_account_balance(db, str(account.id))
            if account.current_balance != balance:
                account.current_balance = balance
                db.commit()

            # Convert to base currency if needed
            if account.currency != base_currency:
                exchange_rate = FinancialEngine.get_exchange_rate(db, account.currency, base_currency, family_id=family_id)
                balance_in_base = balance * exchange_rate
            else:
                balance_in_base = balance

            if account.type in models.LIABILITY_ACCOUNT_TYPES:
                # Positive balance = debt owed; negative = overpayment (treated as no liability)
                total_credit += balance_in_base if balance_in_base > 0 else Decimal('0')
                # Liability debt reduces net worth
                total_net_worth -= balance_in_base
            elif account.type == models.AccountType.CASH:
                total_cash += balance_in_base
                total_net_worth += balance_in_base
            elif account.type == models.AccountType.BANK:
                total_bank += balance_in_base
                total_net_worth += balance_in_base
            elif account.type == models.AccountType.INVESTMENT:
                total_investments += balance_in_base
                total_net_worth += balance_in_base

        monthly_income = Decimal('0')
        monthly_expense = Decimal('0')

        category_breakdown = []
        member_spending = []

        if account_ids:
            monthly_base_query = db.query(models.Transaction).join(
                models.Account, models.Transaction.account_id == models.Account.id
            ).filter(
                models.Transaction.account_id.in_(account_ids),
                models.Transaction.transaction_date >= month_start,
                models.Transaction.deleted_at.is_(None)
            )

            if user.role != models.Role.ADMIN:
                if privacy_level == models.PrivacyLevel.PRIVATE:
                    monthly_base_query = monthly_base_query.filter(models.Transaction.created_by_user_id == user.id)
                elif privacy_level == models.PrivacyLevel.SHARED:
                    monthly_base_query = monthly_base_query.filter(
                        or_(
                            models.Transaction.created_by_user_id == user.id,
                            models.Account.owner_type == models.OwnerType.SHARED
                        )
                    )

            monthly_totals = monthly_base_query.with_entities(
                models.Transaction.type,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
            ).group_by(models.Transaction.type).all()

            for tx_type, total in monthly_totals:
                if tx_type == models.TransactionType.INCOME:
                    monthly_income = Decimal(total or 0)
                elif tx_type == models.TransactionType.EXPENSE:
                    monthly_expense = Decimal(total or 0)

            category_totals = monthly_base_query.with_entities(
                models.Transaction.category_id,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
            ).filter(
                models.Transaction.type == models.TransactionType.EXPENSE,
                models.Transaction.category_id.is_not(None)
            ).group_by(models.Transaction.category_id).all()

            category_ids = [category_id for category_id, _ in category_totals if category_id is not None]
            categories = db.query(models.Category).filter(models.Category.id.in_(category_ids)).all() if category_ids else []
            category_map = {category.id: category for category in categories}

            total_expense = sum([Decimal(amount or 0) for _, amount in category_totals], Decimal('0')) or Decimal('1')
            for category_id, amount in category_totals:
                category = category_map.get(category_id)
                if not category:
                    continue
                decimal_amount = Decimal(amount or 0)
                category_breakdown.append(schemas.CategoryBreakdown(
                    category_id=category.id,
                    category_name=category.name,
                    total_amount=decimal_amount,
                    percentage=float(decimal_amount / total_expense * 100),
                    color=category.color
                ))

            member_totals = monthly_base_query.with_entities(
                models.Transaction.created_by_user_id,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0),
                func.count(models.Transaction.id)
            ).filter(
                models.Transaction.type == models.TransactionType.EXPENSE
            ).group_by(models.Transaction.created_by_user_id).all()

            member_ids = [member_id for member_id, _, _ in member_totals]
            members = db.query(models.User).filter(models.User.id.in_(member_ids)).all() if member_ids else []
            member_map = {member.id: member for member in members}

            for member_id, total_amount, tx_count in member_totals:
                member = member_map.get(member_id)
                if not member:
                    continue
                member_spending.append(schemas.MemberSpending(
                    user_id=member.id,
                    user_name=member.first_name,
                    total_expense=Decimal(total_amount or 0),
                    transaction_count=int(tx_count or 0)
                ))
        
        # Recent transactions
        recent_transactions_query = db.query(models.Transaction).options(
            selectinload(models.Transaction.account).selectinload(models.Account.owner),
            selectinload(models.Transaction.category),
            selectinload(models.Transaction.created_by)
        ).filter(
            models.Transaction.account_id.in_(account_ids),
            models.Transaction.deleted_at.is_(None)
        )

        if user.role != models.Role.ADMIN:
            if privacy_level == models.PrivacyLevel.PRIVATE:
                recent_transactions_query = recent_transactions_query.filter(
                    models.Transaction.created_by_user_id == user.id
                )
            elif privacy_level == models.PrivacyLevel.SHARED:
                shared_account_ids = [
                    account_id for account_id, account in account_lookup.items()
                    if account.owner_type == models.OwnerType.SHARED
                ]
                recent_transactions_query = recent_transactions_query.filter(
                    or_(
                        models.Transaction.created_by_user_id == user.id,
                        models.Transaction.account_id.in_(shared_account_ids if shared_account_ids else [None])
                    )
                )

        recent_transactions = recent_transactions_query.order_by(
            models.Transaction.transaction_date.desc()
        ).limit(10).all()
        
        monthly_savings = monthly_income - monthly_expense

        summary = schemas.DashboardSummary(
            total_net_worth=total_net_worth,
            total_investments=total_investments,
            total_cash=total_cash,
            total_bank_balance=total_bank,
            total_credit_liability=total_credit,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            monthly_savings=monthly_savings,
            base_currency=user.family.base_currency,
            monthly_income_trend=None,
            monthly_expense_trend=None
        )
        
        # Calculate trends (vs last month)
        # 1. Determine previous month date range
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = month_start - timedelta(seconds=1)
        
        # 2. Get previous month transactions
        prev_monthly_income = Decimal('0')
        prev_monthly_expense = Decimal('0')

        if account_ids:
            prev_month_query = db.query(models.Transaction).join(
                models.Account, models.Transaction.account_id == models.Account.id
            ).filter(
                models.Transaction.account_id.in_(account_ids),
                models.Transaction.transaction_date >= prev_month_start,
                models.Transaction.transaction_date <= prev_month_end,
                models.Transaction.deleted_at.is_(None)
            )

            if user.role != models.Role.ADMIN:
                if privacy_level == models.PrivacyLevel.PRIVATE:
                    prev_month_query = prev_month_query.filter(models.Transaction.created_by_user_id == user.id)
                elif privacy_level == models.PrivacyLevel.SHARED:
                    prev_month_query = prev_month_query.filter(
                        or_(
                            models.Transaction.created_by_user_id == user.id,
                            models.Account.owner_type == models.OwnerType.SHARED
                        )
                    )

            prev_month_totals = prev_month_query.with_entities(
                models.Transaction.type,
                func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
            ).group_by(models.Transaction.type).all()

            for tx_type, total in prev_month_totals:
                if tx_type == models.TransactionType.INCOME:
                    prev_monthly_income = Decimal(total or 0)
                elif tx_type == models.TransactionType.EXPENSE:
                    prev_monthly_expense = Decimal(total or 0)
                
        # 5. Calculate percentage change
        def calculate_trend(current, previous):
            if previous == 0:
                return None
            return float((current - previous) / previous * 100)

        summary.monthly_income_trend = calculate_trend(monthly_income, prev_monthly_income)
        summary.monthly_expense_trend = calculate_trend(monthly_expense, prev_monthly_expense)
        
        return schemas.DashboardData(
            summary=summary,
            category_breakdown=category_breakdown,
            member_spending=member_spending,
            recent_transactions=recent_transactions
        )

    @staticmethod
    def get_member_dashboard_summary(db: Session, family_id: str, member_id: str, base_currency: str) -> schemas.DashboardSummary:
        """Compute dashboard summary scoped to a single family member (admin use only)."""
        from datetime import datetime, timedelta

        today = datetime.utcnow()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Accounts owned personally by this member within the family
        member_accounts = db.query(models.Account).filter(
            models.Account.family_id == family_id,
            models.Account.owner_user_id == member_id,
            models.Account.deleted_at.is_(None)
        ).all()
        account_ids = [a.id for a in member_accounts]

        # Account balance totals
        total_net_worth = Decimal('0')
        total_investments = Decimal('0')
        total_cash = Decimal('0')
        total_bank = Decimal('0')
        total_credit = Decimal('0')

        for account in member_accounts:
            balance = FinancialEngine.calculate_account_balance(db, str(account.id))
            if account.current_balance != balance:
                account.current_balance = balance
                db.commit()

            if account.currency != base_currency:
                rate = FinancialEngine.get_exchange_rate(db, account.currency, base_currency, family_id=family_id)
                balance_in_base = balance * rate
            else:
                balance_in_base = balance

            if account.type in models.LIABILITY_ACCOUNT_TYPES:
                total_credit += balance_in_base if balance_in_base > 0 else Decimal('0')
                total_net_worth -= balance_in_base
            elif account.type == models.AccountType.CASH:
                total_cash += balance_in_base
                total_net_worth += balance_in_base
            elif account.type == models.AccountType.BANK:
                total_bank += balance_in_base
                total_net_worth += balance_in_base
            elif account.type == models.AccountType.INVESTMENT:
                total_investments += balance_in_base
                total_net_worth += balance_in_base

        # Monthly income/expense transactions created by this member (across any family account)
        def _monthly_tx_query(db, family_id, member_id, date_start, date_end=None):
            q = db.query(models.Transaction).join(
                models.Account, models.Transaction.account_id == models.Account.id
            ).filter(
                models.Account.family_id == family_id,
                models.Transaction.created_by_user_id == member_id,
                models.Transaction.transaction_date >= date_start,
                models.Transaction.deleted_at.is_(None)
            )
            if date_end:
                q = q.filter(models.Transaction.transaction_date <= date_end)
            return q

        monthly_query = _monthly_tx_query(db, family_id, member_id, month_start)
        monthly_totals = monthly_query.with_entities(
            models.Transaction.type,
            func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
        ).group_by(models.Transaction.type).all()

        monthly_income = Decimal('0')
        monthly_expense = Decimal('0')
        for tx_type, total in monthly_totals:
            if tx_type == models.TransactionType.INCOME:
                monthly_income = Decimal(total or 0)
            elif tx_type == models.TransactionType.EXPENSE:
                monthly_expense = Decimal(total or 0)

        # Previous month trends
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = month_start - timedelta(seconds=1)
        prev_query = _monthly_tx_query(db, family_id, member_id, prev_month_start, prev_month_end)
        prev_totals = prev_query.with_entities(
            models.Transaction.type,
            func.coalesce(func.sum(models.Transaction.amount_in_base_currency), 0)
        ).group_by(models.Transaction.type).all()

        prev_income = Decimal('0')
        prev_expense = Decimal('0')
        for tx_type, total in prev_totals:
            if tx_type == models.TransactionType.INCOME:
                prev_income = Decimal(total or 0)
            elif tx_type == models.TransactionType.EXPENSE:
                prev_expense = Decimal(total or 0)

        def _trend(current, previous):
            if previous == 0:
                return None
            return float((current - previous) / previous * 100)

        return schemas.DashboardSummary(
            total_net_worth=total_net_worth,
            total_investments=total_investments,
            total_cash=total_cash,
            total_bank_balance=total_bank,
            total_credit_liability=total_credit,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            monthly_savings=monthly_income - monthly_expense,
            base_currency=base_currency,
            monthly_income_trend=_trend(monthly_income, prev_income),
            monthly_expense_trend=_trend(monthly_expense, prev_expense),
        )

    @staticmethod
    def compute_net_worth_history(
        db: Session,
        accounts: list,
        snapshots: list,
        base_currency: str,
        family_id,
    ) -> list:
        """Reconstruct net worth at each snapshot date from account transaction history.

        Used for both non-admin members (privacy-filtered accounts) and admin
        per-member drill-down (member-owned accounts). Valuation accounts (property,
        funds) have no transaction history so their current value is used as a proxy.
        """
        from collections import defaultdict

        if not accounts:
            return [
                schemas.NetWorthSnapshotResponse(
                    id=s.id,
                    family_id=s.family_id,
                    snapshot_date=s.snapshot_date,
                    total_net_worth=Decimal("0"),
                    breakdown_json=None,
                    created_at=s.created_at,
                )
                for s in snapshots
            ]

        account_ids = [a.id for a in accounts]

        last_snapshot_end = None
        if snapshots:
            last_snapshot_date = max(s.snapshot_date for s in snapshots)
            last_snapshot_end = datetime.combine(last_snapshot_date, datetime.max.time())

        tx_query = db.query(models.Transaction).filter(
            models.Transaction.account_id.in_(account_ids),
            models.Transaction.deleted_at.is_(None),
        )
        if last_snapshot_end is not None:
            tx_query = tx_query.filter(
                models.Transaction.transaction_date <= last_snapshot_end
            )
        all_txs = tx_query.all()
        txs_by_account: dict = defaultdict(list)
        for tx in all_txs:
            txs_by_account[tx.account_id].append(tx)

        fallback_rates: dict = {}
        for account in accounts:
            if account.currency != base_currency and account.currency not in fallback_rates:
                fallback_rates[account.currency] = FinancialEngine.get_exchange_rate(
                    db, account.currency, base_currency, family_id=family_id
                )

        result = []
        for snapshot in snapshots:
            # Build per-snapshot rate cache: start from today's fallback rates,
            # then override with rates embedded at snapshot creation time so
            # historical net worth reflects the exchange rate that day, not today.
            import json as _json
            rate_cache = fallback_rates.copy()
            if snapshot.breakdown_json:
                try:
                    bd = _json.loads(snapshot.breakdown_json)
                    for currency, rate in bd.get("rates", {}).items():
                        rate_cache[currency] = Decimal(str(rate))
                except Exception:
                    pass
            snapshot_end = datetime.combine(snapshot.snapshot_date, datetime.max.time())
            net_worth = Decimal("0")

            for account in accounts:
                is_liability = account.type in models.LIABILITY_ACCOUNT_TYPES

                # Use amount_in_base_currency — it was stored at transaction creation time
                # using the historical exchange rate, so it correctly handles transactions
                # entered in a currency different from the account's own currency.
                tx_sum_in_base = Decimal("0")
                for tx in txs_by_account.get(account.id, []):
                    if tx.transaction_date > snapshot_end:
                        continue
                    tx_base = tx.amount_in_base_currency or Decimal("0")
                    if is_liability:
                        if tx.type == models.TransactionType.INCOME:
                            tx_sum_in_base -= tx_base
                        elif tx.type == models.TransactionType.EXPENSE:
                            tx_sum_in_base += tx_base
                        elif tx.type == models.TransactionType.TRANSFER:
                            tx_sum_in_base += tx_base if tx.is_source_transaction else -tx_base
                    else:
                        if tx.type == models.TransactionType.INCOME:
                            tx_sum_in_base += tx_base
                        elif tx.type == models.TransactionType.EXPENSE:
                            tx_sum_in_base -= tx_base
                        elif tx.type == models.TransactionType.TRANSFER:
                            tx_sum_in_base += -tx_base if tx.is_source_transaction else tx_base

                # Convert opening_balance (in account currency) to base using the
                # snapshot's historical rate (rate_cache falls back to today's rate).
                account_rate = rate_cache.get(account.currency, Decimal("1"))
                opening_in_base = (account.opening_balance or Decimal("0")) * account_rate
                balance_in_base = opening_in_base + tx_sum_in_base

                if is_liability:
                    net_worth -= balance_in_base
                else:
                    net_worth += balance_in_base

            result.append(
                schemas.NetWorthSnapshotResponse(
                    id=snapshot.id,
                    family_id=snapshot.family_id,
                    snapshot_date=snapshot.snapshot_date,
                    total_net_worth=net_worth,
                    breakdown_json=None,
                    created_at=snapshot.created_at,
                )
            )

        return result
