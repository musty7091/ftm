from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    FINANCE = "FINANCE"
    DATA_ENTRY = "DATA_ENTRY"
    VIEWER = "VIEWER"


class BankAccountType(StrEnum):
    CHECKING = "CHECKING"
    CHECK = "CHECK"
    POS = "POS"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    SAVINGS = "SAVINGS"
    OTHER = "OTHER"


class CurrencyCode(StrEnum):
    TRY = "TRY"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class TransactionDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"


class BankTransactionStatus(StrEnum):
    PLANNED = "PLANNED"
    REALIZED = "REALIZED"
    CANCELLED = "CANCELLED"


class BankTransferStatus(StrEnum):
    PLANNED = "PLANNED"
    REALIZED = "REALIZED"
    CANCELLED = "CANCELLED"


class FinancialSourceType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    BANK_TRANSFER = "BANK_TRANSFER"
    ISSUED_CHECK = "ISSUED_CHECK"
    RECEIVED_CHECK = "RECEIVED_CHECK"
    POS_SETTLEMENT = "POS_SETTLEMENT"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"
    OTHER = "OTHER"


class BusinessPartnerType(StrEnum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    BOTH = "BOTH"
    OTHER = "OTHER"


class IssuedCheckStatus(StrEnum):
    PREPARED = "PREPARED"
    GIVEN = "GIVEN"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    RISK = "RISK"


class ReceivedCheckStatus(StrEnum):
    PORTFOLIO = "PORTFOLIO"
    GIVEN_TO_BANK = "GIVEN_TO_BANK"
    IN_COLLECTION = "IN_COLLECTION"
    COLLECTED = "COLLECTED"
    BOUNCED = "BOUNCED"
    RETURNED = "RETURNED"
    ENDORSED = "ENDORSED"
    DISCOUNTED = "DISCOUNTED"
    CANCELLED = "CANCELLED"


class ReceivedCheckMovementType(StrEnum):
    REGISTERED = "REGISTERED"
    SENT_TO_BANK_COLLECTION = "SENT_TO_BANK_COLLECTION"
    MARKED_IN_COLLECTION = "MARKED_IN_COLLECTION"
    COLLECTED = "COLLECTED"
    ENDORSED = "ENDORSED"
    DISCOUNTED = "DISCOUNTED"
    BOUNCED = "BOUNCED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class PosSettlementStatus(StrEnum):
    PLANNED = "PLANNED"
    REALIZED = "REALIZED"
    CANCELLED = "CANCELLED"
    MISMATCH = "MISMATCH"


class CreditCardType(StrEnum):
    BUSINESS = "BUSINESS"
    COMPANY = "COMPANY"
    PERSONAL = "PERSONAL"
    OTHER = "OTHER"


class CreditCardNetwork(StrEnum):
    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    TROY = "TROY"
    AMEX = "AMEX"
    OTHER = "OTHER"


class CreditCardStatementStatus(StrEnum):
    PLANNED = "PLANNED"
    ISSUED = "ISSUED"
    PARTIAL_PAID = "PARTIAL_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class CreditCardTransactionStatus(StrEnum):
    PENDING = "PENDING"
    IN_STATEMENT = "IN_STATEMENT"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class CreditLimitType(StrEnum):
    KMH = "KMH"
    LIMITED_DEPOSIT = "LIMITED_DEPOSIT"
    ROTATIVE_LIMIT = "ROTATIVE_LIMIT"
    OTHER = "OTHER"


class CreditLimitUsageMode(StrEnum):
    AUTO_FROM_BANK_BALANCE = "AUTO_FROM_BANK_BALANCE"
    MANUAL = "MANUAL"


class InterestPeriod(StrEnum):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    OTHER = "OTHER"
