"""
Recurring Payment Processor

Handles automatic processing of recurring payments:
- Identifies payments due today or overdue
- Creates corresponding transactions
- Calculates next due date based on recurrence pattern
"""

from decimal import Decimal
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from app import models, schemas
from app.financial_logic import FinancialEngine
from typing import Optional


class RecurringPaymentProcessor:
    """Process recurring payments and create transactions"""
    
    @staticmethod
    def calculate_next_due_date(
        current_due_date: datetime,
        pattern: models.RecurrencePattern
    ) -> datetime:
        """
        Calculate next due date based on recurrence pattern.
        
        Args:
            current_due_date: Current due date
            pattern: RecurrencePattern enum (DAILY, WEEKLY, MONTHLY, etc.)
            
        Returns:
            Next due date
        """
        if pattern == models.RecurrencePattern.DAILY:
            return current_due_date + timedelta(days=1)
        elif pattern == models.RecurrencePattern.WEEKLY:
            return current_due_date + timedelta(weeks=1)
        elif pattern == models.RecurrencePattern.BIWEEKLY:
            return current_due_date + timedelta(weeks=2)
        elif pattern == models.RecurrencePattern.MONTHLY:
            return current_due_date + relativedelta(months=1)
        elif pattern == models.RecurrencePattern.QUARTERLY:
            return current_due_date + relativedelta(months=3)
        elif pattern == models.RecurrencePattern.YEARLY:
            return current_due_date + relativedelta(years=1)
        else:
            # Default to monthly if pattern not recognized
            return current_due_date + relativedelta(months=1)
    
    @staticmethod
    def process_due_recurring_payment(
        db: Session,
        recurring_payment: models.RecurringPayment,
        account: models.Account,
        creator: models.User,
    ) -> Optional[models.Transaction]:
        """
        Process a single due recurring payment by creating a transaction.

        Accounts and creator are passed in to avoid per-payment DB queries when
        called from process_all_due_recurring_payments (which pre-fetches them in bulk).

        Returns:
            Created Transaction object, or None if processing failed
        """
        # Check if payment has expired (end_date passed)
        if recurring_payment.end_date and datetime.utcnow() > recurring_payment.end_date:
            recurring_payment.is_active = False
            db.commit()
            return None

        # Get base currency for exchange rate calculation
        base_currency = account.family.base_currency
        account_currency = account.currency

        # Calculate exchange rate if currencies differ
        if account_currency == base_currency:
            exchange_rate = Decimal('1.0')
        else:
            exchange_rate = FinancialEngine.get_exchange_rate(
                db,
                account_currency,
                base_currency
            )

        amount_in_base = recurring_payment.amount * exchange_rate

        # Create transaction for the recurring payment
        transaction = models.Transaction(
            account_id=recurring_payment.account_id,
            created_by_user_id=recurring_payment.created_by_user_id,
            type=models.TransactionType.EXPENSE,
            amount=recurring_payment.amount,
            currency=account_currency,
            exchange_rate_to_base=exchange_rate,
            amount_in_base_currency=amount_in_base,
            category_id=recurring_payment.category_id,
            description=f"[Recurring] {recurring_payment.name}",
            transaction_date=datetime.utcnow(),
            is_source_transaction=True
        )

        db.add(transaction)
        db.flush()

        # Update recurring payment: mark as paid and calculate next due date
        recurring_payment.last_paid_date = datetime.utcnow()
        recurring_payment.next_due_date = RecurringPaymentProcessor.calculate_next_due_date(
            recurring_payment.next_due_date,
            recurring_payment.pattern
        )
        recurring_payment.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(transaction)

        return transaction

    @staticmethod
    def process_all_due_recurring_payments(db: Session) -> int:
        """
        Process all recurring payments that are due.

        Safety: Prevents double-processing by checking if payment was already
        processed within the last hour (i.e., last_paid_date is recent).

        Returns:
            Count of processed payments
        """
        # Find all active recurring payments that are due or overdue
        due_payments = db.query(models.RecurringPayment).filter(
            models.RecurringPayment.is_active == True,
            models.RecurringPayment.next_due_date <= datetime.utcnow()
        ).all()

        if not due_payments:
            return 0

        now = datetime.utcnow()

        # Filter out recently-processed payments before bulk-fetching related rows
        payments_to_process = []
        for payment in due_payments:
            if payment.last_paid_date:
                time_since_last_paid = now - payment.last_paid_date
                if time_since_last_paid.total_seconds() < 3600:
                    print(f"⊘ Skipping recurring payment (already processed recently): {payment.name} (ID: {payment.id})")
                    continue
            payments_to_process.append(payment)

        if not payments_to_process:
            return 0

        # Bulk-fetch all referenced accounts and users in 2 queries instead of 2N
        account_ids = {p.account_id for p in payments_to_process}
        user_ids = {p.created_by_user_id for p in payments_to_process}

        accounts_map = {
            a.id: a for a in db.query(models.Account).filter(
                models.Account.id.in_(account_ids)
            ).all()
        }
        users_map = {
            u.id: u for u in db.query(models.User).filter(
                models.User.id.in_(user_ids)
            ).all()
        }

        processed_count = 0
        processed_account_ids: set = set()

        for payment in payments_to_process:
            account = accounts_map.get(payment.account_id)
            creator = users_map.get(payment.created_by_user_id)

            if not account or not creator:
                continue

            try:
                transaction = RecurringPaymentProcessor.process_due_recurring_payment(
                    db,
                    payment,
                    account,
                    creator,
                )
                if transaction:
                    processed_count += 1
                    processed_account_ids.add(payment.account_id)
                    print(f"✓ Processed recurring payment: {payment.name} (ID: {payment.id})")
            except Exception as e:
                print(f"✗ Failed to process recurring payment {payment.id}: {str(e)}")
                db.rollback()
                continue

        # Update account balances once per unique account (not once per payment)
        for account_id in processed_account_ids:
            FinancialEngine.update_account_balance(db, str(account_id))

        return processed_count
