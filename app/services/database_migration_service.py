from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import settings
from app.db.session import engine
from app.services.backup_service import BackupServiceError, create_database_backup


class DatabaseMigrationServiceError(RuntimeError):
    pass


MIGRATION_TRACKING_TABLE = "schema_migrations"
CURRENT_SCHEMA_VERSION = 8


@dataclass(frozen=True)
class DatabaseMigration:
    migration_id: str
    name: str
    target_version: int
    statements: tuple[str, ...]
    description: str = ""

    @property
    def checksum(self) -> str:
        checksum_source = "\n".join(
            [
                self.migration_id,
                self.name,
                str(self.target_version),
                self.description,
                *self.statements,
            ]
        )

        return hashlib.sha256(checksum_source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AppliedMigrationInfo:
    migration_id: str
    migration_name: str
    target_version: int
    checksum: str
    applied_at: str
    execution_time_ms: int
    success: bool
    error_message: str | None


@dataclass(frozen=True)
class DatabaseMigrationStatus:
    database_engine: str
    database_path: str
    database_file_exists: bool
    tracking_table_exists: bool
    current_user_version: int
    expected_schema_version: int
    applied_migration_count: int
    pending_migration_ids: list[str]
    is_up_to_date: bool


@dataclass(frozen=True)
class DatabaseMigrationResult:
    database_path: str
    backup_file: str | None
    applied_migration_ids: list[str]
    current_user_version: int
    expected_schema_version: int
    message: str


MIGRATIONS: tuple[DatabaseMigration, ...] = (
    DatabaseMigration(
        migration_id="20260502_0001_baseline_schema_tracking",
        name="Baseline schema tracking",
        target_version=1,
        statements=(
            "SELECT 1",
        ),
        description=(
            "FTM SQLite veritabanı için migration takip sisteminin başlangıç kaydı."
        ),
    ),
    DatabaseMigration(
        migration_id="20260509_0002_credit_accounts_cards",
        name="Credit accounts and cards tables",
        target_version=2,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS credit_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_id INTEGER NOT NULL,
                card_name VARCHAR(150) NOT NULL,
                card_type VARCHAR(30) NOT NULL DEFAULT 'BUSINESS',
                card_network VARCHAR(30) NOT NULL DEFAULT 'OTHER',
                last_four_digits VARCHAR(4),
                currency_code VARCHAR(10) NOT NULL DEFAULT 'TRY',
                credit_limit NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                statement_cut_day INTEGER,
                payment_due_day INTEGER,
                default_payment_bank_account_id INTEGER,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_credit_cards_bank_id_card_name
                    UNIQUE (bank_id, card_name),
                CONSTRAINT uq_credit_cards_bank_id_last_four_digits
                    UNIQUE (bank_id, last_four_digits),
                CONSTRAINT fk_credit_cards_bank_id
                    FOREIGN KEY (bank_id)
                    REFERENCES banks (id)
                    ON DELETE RESTRICT,
                CONSTRAINT fk_credit_cards_default_payment_bank_account_id
                    FOREIGN KEY (default_payment_bank_account_id)
                    REFERENCES bank_accounts (id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_cards_bank_id
            ON credit_cards (bank_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_cards_card_name
            ON credit_cards (card_name)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_cards_last_four_digits
            ON credit_cards (last_four_digits)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_cards_default_payment_bank_account_id
            ON credit_cards (default_payment_bank_account_id)
            """,
            """
            CREATE TABLE IF NOT EXISTS credit_card_statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_card_id INTEGER NOT NULL,
                period_label VARCHAR(20) NOT NULL,
                statement_date DATE NOT NULL,
                due_date DATE NOT NULL,
                statement_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                minimum_payment_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                paid_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                remaining_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(30) NOT NULL DEFAULT 'ISSUED',
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_credit_card_statements_card_id_period_label
                    UNIQUE (credit_card_id, period_label),
                CONSTRAINT fk_credit_card_statements_credit_card_id
                    FOREIGN KEY (credit_card_id)
                    REFERENCES credit_cards (id)
                    ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_statements_credit_card_id
            ON credit_card_statements (credit_card_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_statements_period_label
            ON credit_card_statements (period_label)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_statements_statement_date
            ON credit_card_statements (statement_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_statements_due_date
            ON credit_card_statements (due_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_statements_status
            ON credit_card_statements (status)
            """,
            """
            CREATE TABLE IF NOT EXISTS credit_card_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id INTEGER NOT NULL,
                payment_bank_account_id INTEGER,
                payment_date DATE NOT NULL,
                amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                reference_no VARCHAR(100),
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_credit_card_payments_statement_id
                    FOREIGN KEY (statement_id)
                    REFERENCES credit_card_statements (id)
                    ON DELETE RESTRICT,
                CONSTRAINT fk_credit_card_payments_payment_bank_account_id
                    FOREIGN KEY (payment_bank_account_id)
                    REFERENCES bank_accounts (id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_statement_id
            ON credit_card_payments (statement_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_payment_bank_account_id
            ON credit_card_payments (payment_bank_account_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_payment_date
            ON credit_card_payments (payment_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_reference_no
            ON credit_card_payments (reference_no)
            """,
            """
            CREATE TABLE IF NOT EXISTS bank_account_credit_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_account_id INTEGER NOT NULL,
                limit_name VARCHAR(150) NOT NULL,
                limit_type VARCHAR(30) NOT NULL DEFAULT 'KMH',
                currency_code VARCHAR(10) NOT NULL DEFAULT 'TRY',
                limit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                usage_mode VARCHAR(40) NOT NULL DEFAULT 'MANUAL',
                manual_used_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                interest_rate NUMERIC(18, 6) NOT NULL DEFAULT 0.000000,
                interest_period VARCHAR(30) NOT NULL DEFAULT 'MONTHLY',
                interest_day INTEGER,
                contract_start_date DATE,
                contract_end_date DATE,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_bank_account_credit_limits_account_id_limit_name
                    UNIQUE (bank_account_id, limit_name),
                CONSTRAINT fk_bank_account_credit_limits_bank_account_id
                    FOREIGN KEY (bank_account_id)
                    REFERENCES bank_accounts (id)
                    ON DELETE RESTRICT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limits_bank_account_id
            ON bank_account_credit_limits (bank_account_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limits_limit_name
            ON bank_account_credit_limits (limit_name)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limits_limit_type
            ON bank_account_credit_limits (limit_type)
            """,
        ),
        description=(
            "Kredili Hesaplar / Kartlar modülü için kredi kartı, ekstre, ödeme "
            "ve kredili/limitli mevduat hesap tablolarını oluşturur."
        ),
    ),
    DatabaseMigration(
        migration_id="20260509_0003_credit_card_transactions",
        name="Credit card transaction table",
        target_version=3,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS credit_card_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_card_id INTEGER NOT NULL,
                statement_id INTEGER,
                transaction_date DATE NOT NULL,
                merchant_name VARCHAR(200) NOT NULL,
                description TEXT,
                amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                currency_code VARCHAR(10) NOT NULL DEFAULT 'TRY',
                installment_count INTEGER NOT NULL DEFAULT 1,
                installment_no INTEGER NOT NULL DEFAULT 1,
                status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                reference_no VARCHAR(100),
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_credit_card_transactions_credit_card_id
                    FOREIGN KEY (credit_card_id)
                    REFERENCES credit_cards (id)
                    ON DELETE RESTRICT,
                CONSTRAINT fk_credit_card_transactions_statement_id
                    FOREIGN KEY (statement_id)
                    REFERENCES credit_card_statements (id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_credit_card_id
            ON credit_card_transactions (credit_card_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_statement_id
            ON credit_card_transactions (statement_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_transaction_date
            ON credit_card_transactions (transaction_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_merchant_name
            ON credit_card_transactions (merchant_name)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_status
            ON credit_card_transactions (status)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_reference_no
            ON credit_card_transactions (reference_no)
            """,
        ),
        description=(
            "Kredi kartı harcama girişi için işlem tablosunu oluşturur. "
            "İşlemler ilk aşamada bekleyen harcama olarak kaydedilir; ekstre bağlantısı sonraki fazda yapılır."
        ),
    ),
    DatabaseMigration(
        migration_id="20260510_0004_credit_cards_try_only",
        name="Credit cards TRY only normalization",
        target_version=4,
        statements=(
            """
            UPDATE credit_cards
            SET currency_code = 'TRY'
            WHERE currency_code IS NULL
               OR currency_code <> 'TRY'
            """,
            """
            UPDATE credit_card_transactions
            SET currency_code = 'TRY'
            WHERE currency_code IS NULL
               OR currency_code <> 'TRY'
            """,
            """
            UPDATE credit_cards
            SET default_payment_bank_account_id = NULL
            WHERE default_payment_bank_account_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM bank_accounts
                  WHERE bank_accounts.id = credit_cards.default_payment_bank_account_id
                    AND (
                        bank_accounts.currency_code IS NULL
                        OR bank_accounts.currency_code <> 'TRY'
                    )
              )
            """,
        ),
        description=(
            "Kredi kartı ürün kararı gereği kart ve harcama para birimini TRY olarak sabitler. "
            "TL olmayan varsayılan ödeme hesabı bağlantılarını temizler. "
            "Banka, kasa, çek ve kredili/limitli mevduat döviz mantığına dokunmaz."
        ),
    ),

    DatabaseMigration(
        migration_id="20260511_0005_credit_card_direct_payments",
        name="Credit card direct payments",
        target_version=5,
        statements=(
            """
            CREATE TABLE credit_card_payments_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_card_id INTEGER,
                statement_id INTEGER,
                payment_bank_account_id INTEGER,
                bank_transaction_id INTEGER,
                payment_date DATE NOT NULL,
                amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(30) NOT NULL DEFAULT 'RECORDED',
                reference_no VARCHAR(100),
                notes TEXT,
                created_by_user_id INTEGER,
                cancelled_by_user_id INTEGER,
                cancelled_at DATETIME,
                cancel_reason TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_credit_card_payments_bank_transaction_id
                    UNIQUE (bank_transaction_id),
                CONSTRAINT fk_credit_card_payments_credit_card_id
                    FOREIGN KEY (credit_card_id)
                    REFERENCES credit_cards (id)
                    ON DELETE RESTRICT,
                CONSTRAINT fk_credit_card_payments_statement_id
                    FOREIGN KEY (statement_id)
                    REFERENCES credit_card_statements (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_credit_card_payments_payment_bank_account_id
                    FOREIGN KEY (payment_bank_account_id)
                    REFERENCES bank_accounts (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_credit_card_payments_bank_transaction_id
                    FOREIGN KEY (bank_transaction_id)
                    REFERENCES bank_transactions (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_credit_card_payments_created_by_user_id
                    FOREIGN KEY (created_by_user_id)
                    REFERENCES users (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_credit_card_payments_cancelled_by_user_id
                    FOREIGN KEY (cancelled_by_user_id)
                    REFERENCES users (id)
                    ON DELETE SET NULL
            )
            """,
            """
            INSERT INTO credit_card_payments_new (
                id,
                credit_card_id,
                statement_id,
                payment_bank_account_id,
                bank_transaction_id,
                payment_date,
                amount,
                status,
                reference_no,
                notes,
                created_by_user_id,
                cancelled_by_user_id,
                cancelled_at,
                cancel_reason,
                created_at,
                updated_at
            )
            SELECT
                credit_card_payments.id,
                credit_card_statements.credit_card_id,
                credit_card_payments.statement_id,
                credit_card_payments.payment_bank_account_id,
                NULL,
                credit_card_payments.payment_date,
                credit_card_payments.amount,
                'RECORDED',
                credit_card_payments.reference_no,
                credit_card_payments.notes,
                NULL,
                NULL,
                NULL,
                NULL,
                credit_card_payments.created_at,
                credit_card_payments.updated_at
            FROM credit_card_payments
            LEFT JOIN credit_card_statements
                ON credit_card_statements.id = credit_card_payments.statement_id
            """,
            """
            DROP TABLE credit_card_payments
            """,
            """
            ALTER TABLE credit_card_payments_new
            RENAME TO credit_card_payments
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_credit_card_id
            ON credit_card_payments (credit_card_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_statement_id
            ON credit_card_payments (statement_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_payment_bank_account_id
            ON credit_card_payments (payment_bank_account_id)
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_credit_card_payments_bank_transaction_id
            ON credit_card_payments (bank_transaction_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_payment_date
            ON credit_card_payments (payment_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_status
            ON credit_card_payments (status)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_reference_no
            ON credit_card_payments (reference_no)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_created_by_user_id
            ON credit_card_payments (created_by_user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_payments_cancelled_by_user_id
            ON credit_card_payments (cancelled_by_user_id)
            """,
        ),
        description=(
            "Kredi kartı ödemelerini ekstreye zorunlu bağlı olmadan doğrudan karta kaydedebilecek hale getirir. "
            "Mevcut ekstre ödemelerini korur, kredi kartı bağlantısını statement kaydından taşır ve banka hareketi bağlantısı için alan açar."
        ),
    ),
    DatabaseMigration(
        migration_id="20260512_0006_credit_limit_transactions",
        name="Credit limit transaction table",
        target_version=6,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS bank_account_credit_limit_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_limit_id INTEGER NOT NULL,
                transaction_type VARCHAR(30) NOT NULL,
                transaction_date DATE NOT NULL,
                effective_date DATE NOT NULL,
                amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
                currency_code VARCHAR(10) NOT NULL DEFAULT 'TRY',
                bank_transaction_id INTEGER,
                status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
                reference_no VARCHAR(100),
                description TEXT,
                notes TEXT,
                created_by_user_id INTEGER,
                cancelled_by_user_id INTEGER,
                cancelled_at DATETIME,
                cancel_reason TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_bank_account_credit_limit_transactions_bank_transaction_id
                    UNIQUE (bank_transaction_id),
                CONSTRAINT fk_bank_account_credit_limit_transactions_credit_limit_id
                    FOREIGN KEY (credit_limit_id)
                    REFERENCES bank_account_credit_limits (id)
                    ON DELETE RESTRICT,
                CONSTRAINT fk_bank_account_credit_limit_transactions_bank_transaction_id
                    FOREIGN KEY (bank_transaction_id)
                    REFERENCES bank_transactions (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_bank_account_credit_limit_transactions_created_by_user_id
                    FOREIGN KEY (created_by_user_id)
                    REFERENCES users (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_bank_account_credit_limit_transactions_cancelled_by_user_id
                    FOREIGN KEY (cancelled_by_user_id)
                    REFERENCES users (id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_credit_limit_id
            ON bank_account_credit_limit_transactions (credit_limit_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_transaction_type
            ON bank_account_credit_limit_transactions (transaction_type)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_transaction_date
            ON bank_account_credit_limit_transactions (transaction_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_effective_date
            ON bank_account_credit_limit_transactions (effective_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_currency_code
            ON bank_account_credit_limit_transactions (currency_code)
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_bank_transaction_id
            ON bank_account_credit_limit_transactions (bank_transaction_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_status
            ON bank_account_credit_limit_transactions (status)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_reference_no
            ON bank_account_credit_limit_transactions (reference_no)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_created_by_user_id
            ON bank_account_credit_limit_transactions (created_by_user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_bank_account_credit_limit_transactions_cancelled_by_user_id
            ON bank_account_credit_limit_transactions (cancelled_by_user_id)
            """,
        ),
        description=(
            "Kredili / limitli mevduat hareket altyapısını oluşturur. "
            "Limit kullanımı, ödeme, faiz, masraf ve düzeltme hareketleri için işlem tarihi ile faize etki tarihini ayrı tutar. "
            "Ödeme valörü T+1 mantığı servis katmanında bu tablo üzerinden uygulanacaktır."
        ),
    ),
    DatabaseMigration(
        migration_id="20260512_0007_credit_limit_payment_allocation",
        name="Credit limit payment allocation fields",
        target_version=7,
        statements=(
            """
            ALTER TABLE bank_account_credit_limit_transactions
            ADD COLUMN principal_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00
            """,
            """
            ALTER TABLE bank_account_credit_limit_transactions
            ADD COLUMN interest_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00
            """,
            """
            ALTER TABLE bank_account_credit_limit_transactions
            ADD COLUMN fee_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00
            """,
            """
            UPDATE bank_account_credit_limit_transactions
            SET principal_amount = amount
            WHERE transaction_type IN ('USAGE', 'PAYMENT', 'ADJUSTMENT')
            """,
            """
            UPDATE bank_account_credit_limit_transactions
            SET interest_amount = amount
            WHERE transaction_type = 'INTEREST'
            """,
            """
            UPDATE bank_account_credit_limit_transactions
            SET fee_amount = amount
            WHERE transaction_type = 'FEE'
            """,
        ),
        description=(
            "Kredili / limitli mevduat hareketlerine ödeme dağılım alanları ekler. "
            "Limit kullanımı ana para, faiz tahakkuku faiz, masraf hareketi masraf ve eski ödeme hareketleri ana para dağılımı olarak geriye dönük doldurulur."
        ),
    ),

    DatabaseMigration(
        migration_id="20260513_0008_credit_card_transaction_audit_fields",
        name="Credit card transaction audit fields",
        target_version=8,
        statements=(
            """
            ALTER TABLE credit_card_transactions
            ADD COLUMN created_by_user_id INTEGER
            """,
            """
            ALTER TABLE credit_card_transactions
            ADD COLUMN cancelled_by_user_id INTEGER
            """,
            """
            ALTER TABLE credit_card_transactions
            ADD COLUMN cancelled_at DATETIME
            """,
            """
            ALTER TABLE credit_card_transactions
            ADD COLUMN cancel_reason TEXT
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_created_by_user_id
            ON credit_card_transactions (created_by_user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_credit_card_transactions_cancelled_by_user_id
            ON credit_card_transactions (cancelled_by_user_id)
            """,
        ),
        description=(
            "Kredi kartı harcama kayıtlarına oluşturan kullanıcı ve iptal bilgileri ekler. "
            "Kredi kartı ödemeleri ve kredili/limitli mevduat hareketleriyle audit tutarlılığını sağlar."
        ),
    ),

)


def ensure_sqlite_mode() -> None:
    if not settings.is_sqlite:
        raise DatabaseMigrationServiceError(
            "Migration sistemi şu anda yalnızca SQLite Local modu için aktiftir."
        )


def get_database_migration_status() -> DatabaseMigrationStatus:
    ensure_sqlite_mode()
    _validate_migration_definitions()

    database_path = _sqlite_database_path()
    expected_schema_version = _expected_schema_version()

    if not database_path.exists() or not database_path.is_file():
        return DatabaseMigrationStatus(
            database_engine=settings.database_engine,
            database_path=str(database_path),
            database_file_exists=False,
            tracking_table_exists=False,
            current_user_version=0,
            expected_schema_version=expected_schema_version,
            applied_migration_count=0,
            pending_migration_ids=[],
            is_up_to_date=False,
        )

    with engine.connect() as connection:
        current_user_version = _get_sqlite_user_version(connection)
        tracking_table_exists = _tracking_table_exists(connection)

        if tracking_table_exists:
            applied_migrations = _get_applied_migrations(connection)
            _verify_applied_migration_records(applied_migrations)
        else:
            applied_migrations = []

        pending_migrations = _get_pending_migrations_from_applied(applied_migrations)

    pending_migration_ids = [
        migration.migration_id
        for migration in pending_migrations
    ]

    is_up_to_date = (
        tracking_table_exists
        and not pending_migration_ids
        and current_user_version == expected_schema_version
    )

    return DatabaseMigrationStatus(
        database_engine=settings.database_engine,
        database_path=str(database_path),
        database_file_exists=True,
        tracking_table_exists=tracking_table_exists,
        current_user_version=current_user_version,
        expected_schema_version=expected_schema_version,
        applied_migration_count=len(applied_migrations),
        pending_migration_ids=pending_migration_ids,
        is_up_to_date=is_up_to_date,
    )


def assert_database_migration_readiness() -> DatabaseMigrationStatus:
    ensure_sqlite_mode()
    _validate_migration_definitions()

    status = get_database_migration_status()
    _assert_database_migration_status_is_ready(status)

    with engine.connect() as connection:
        _assert_required_migrations_are_applied(connection)

    return status


def run_database_migrations(*, require_backup: bool = True) -> DatabaseMigrationResult:
    ensure_sqlite_mode()
    _validate_migration_definitions()

    database_path = _sqlite_database_path()

    if not database_path.exists() or not database_path.is_file():
        raise DatabaseMigrationServiceError(
            f"Migration çalıştırılamadı. SQLite veritabanı dosyası bulunamadı:\n{database_path}"
        )

    status_before = get_database_migration_status()

    if status_before.is_up_to_date:
        ready_status = assert_database_migration_readiness()

        return DatabaseMigrationResult(
            database_path=str(database_path),
            backup_file=None,
            applied_migration_ids=[],
            current_user_version=ready_status.current_user_version,
            expected_schema_version=ready_status.expected_schema_version,
            message="Veritabanı şeması güncel. Çalıştırılacak migration yok.",
        )

    backup_file_text: str | None = None

    if require_backup:
        backup_file_text = _create_safe_backup_before_migration()

    applied_migration_ids: list[str] = []

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.exec_driver_sql("PRAGMA busy_timeout = 10000")

            _ensure_tracking_table(connection)

            applied_migrations = _get_applied_migrations(connection)
            _verify_applied_migration_records(applied_migrations)

            pending_migrations = _get_pending_migrations_from_applied(applied_migrations)

            for migration in pending_migrations:
                _apply_single_migration(
                    connection=connection,
                    migration=migration,
                )
                applied_migration_ids.append(migration.migration_id)
                _set_sqlite_user_version(connection, migration.target_version)

        status_after = assert_database_migration_readiness()

        return DatabaseMigrationResult(
            database_path=str(database_path),
            backup_file=backup_file_text,
            applied_migration_ids=applied_migration_ids,
            current_user_version=status_after.current_user_version,
            expected_schema_version=status_after.expected_schema_version,
            message=(
                "Migration işlemi başarıyla tamamlandı. "
                f"Uygulanan migration sayısı: {len(applied_migration_ids)}"
            ),
        )

    except Exception as exc:
        backup_note = ""

        if backup_file_text:
            backup_note = f"\n\nMigration öncesi alınan güvenli yedek:\n{backup_file_text}"

        raise DatabaseMigrationServiceError(
            "Migration işlemi başarısız oldu. "
            "Veritabanı güncellemesi tamamlanamadı."
            f"{backup_note}\n\nHata:\n{exc}"
        ) from exc


def _sqlite_database_path() -> Path:
    sqlite_path = settings.sqlite_database_path

    if sqlite_path.is_absolute():
        return sqlite_path

    return Path.cwd() / sqlite_path


def _expected_schema_version() -> int:
    if not MIGRATIONS:
        return 0

    return max(migration.target_version for migration in MIGRATIONS)


def _validate_migration_definitions() -> None:
    migration_ids: set[str] = set()
    target_versions: set[int] = set()
    previous_target_version = 0

    for migration in MIGRATIONS:
        migration_id = str(migration.migration_id or "").strip()
        migration_name = str(migration.name or "").strip()

        if not migration_id:
            raise DatabaseMigrationServiceError("Migration ID boş olamaz.")

        if not migration_name:
            raise DatabaseMigrationServiceError(
                f"Migration adı boş olamaz. Migration ID: {migration_id}"
            )

        if migration_id in migration_ids:
            raise DatabaseMigrationServiceError(
                f"Tekrarlanan migration ID bulundu: {migration_id}"
            )

        if migration.target_version <= 0:
            raise DatabaseMigrationServiceError(
                f"Migration target_version sıfırdan büyük olmalıdır: {migration_id}"
            )

        if migration.target_version in target_versions:
            raise DatabaseMigrationServiceError(
                f"Tekrarlanan migration target_version bulundu: {migration.target_version}"
            )

        if migration.target_version <= previous_target_version:
            raise DatabaseMigrationServiceError(
                "Migration listesi target_version değerine göre küçükten büyüğe sıralı olmalıdır."
            )

        migration_ids.add(migration_id)
        target_versions.add(migration.target_version)
        previous_target_version = migration.target_version

    expected_schema_version = _expected_schema_version()

    if CURRENT_SCHEMA_VERSION != expected_schema_version:
        raise DatabaseMigrationServiceError(
            "CURRENT_SCHEMA_VERSION ile migration hedef sürümü uyuşmuyor.\n\n"
            f"CURRENT_SCHEMA_VERSION: {CURRENT_SCHEMA_VERSION}\n"
            f"Migration hedef sürümü: {expected_schema_version}"
        )


def _assert_database_migration_status_is_ready(
    status: DatabaseMigrationStatus,
) -> None:
    if not status.database_file_exists:
        raise DatabaseMigrationServiceError(
            "Migration doğrulaması başarısız. SQLite veritabanı dosyası bulunamadı.\n\n"
            f"Beklenen veritabanı yolu:\n{status.database_path}"
        )

    if not status.tracking_table_exists:
        raise DatabaseMigrationServiceError(
            f"Migration doğrulaması başarısız. {MIGRATION_TRACKING_TABLE} tablosu bulunamadı."
        )

    if status.pending_migration_ids:
        raise DatabaseMigrationServiceError(
            "Migration doğrulaması başarısız. Bekleyen migration kayıtları var:\n"
            + "\n".join(f"- {migration_id}" for migration_id in status.pending_migration_ids)
        )

    if status.current_user_version < status.expected_schema_version:
        raise DatabaseMigrationServiceError(
            "Migration doğrulaması başarısız. SQLite user_version beklenen sürümden eski.\n\n"
            f"Mevcut user_version: {status.current_user_version}\n"
            f"Beklenen schema version: {status.expected_schema_version}"
        )

    if status.current_user_version > status.expected_schema_version:
        raise DatabaseMigrationServiceError(
            "Migration doğrulaması başarısız. SQLite user_version uygulamanın bildiği sürümden yeni.\n\n"
            f"Mevcut user_version: {status.current_user_version}\n"
            f"Uygulamanın beklediği schema version: {status.expected_schema_version}\n\n"
            "Bu veritabanı daha yeni bir FTM sürümüyle güncellenmiş olabilir."
        )

    if not status.is_up_to_date:
        raise DatabaseMigrationServiceError(
            "Migration doğrulaması başarısız. Veritabanı güncel görünmüyor."
        )


def _assert_required_migrations_are_applied(connection: Any) -> None:
    if not _tracking_table_exists(connection):
        raise DatabaseMigrationServiceError(
            f"Migration doğrulaması başarısız. {MIGRATION_TRACKING_TABLE} tablosu yok."
        )

    applied_migrations = _get_applied_migrations(connection)
    _verify_applied_migration_records(applied_migrations)

    applied_map = {
        migration.migration_id: migration
        for migration in applied_migrations
    }

    for migration in MIGRATIONS:
        applied_migration = applied_map.get(migration.migration_id)

        if applied_migration is None:
            raise DatabaseMigrationServiceError(
                "Migration doğrulaması başarısız. Zorunlu migration kaydı bulunamadı.\n\n"
                f"Migration ID: {migration.migration_id}"
            )

        if not applied_migration.success:
            raise DatabaseMigrationServiceError(
                "Migration doğrulaması başarısız. Zorunlu migration başarısız kayıtlı görünüyor.\n\n"
                f"Migration ID: {migration.migration_id}\n"
                f"Hata: {applied_migration.error_message or '-'}"
            )

        if applied_migration.target_version != migration.target_version:
            raise DatabaseMigrationServiceError(
                "Migration doğrulaması başarısız. Migration hedef sürümü değişmiş görünüyor.\n\n"
                f"Migration ID: {migration.migration_id}\n"
                f"Beklenen target_version: {migration.target_version}\n"
                f"Bulunan target_version: {applied_migration.target_version}"
            )

        if applied_migration.checksum != migration.checksum:
            raise DatabaseMigrationServiceError(
                "Migration doğrulaması başarısız. Migration checksum değeri uyuşmuyor.\n\n"
                f"Migration ID: {migration.migration_id}"
            )

    current_user_version = _get_sqlite_user_version(connection)
    expected_schema_version = _expected_schema_version()

    if current_user_version != expected_schema_version:
        raise DatabaseMigrationServiceError(
            "Migration doğrulaması başarısız. SQLite user_version beklenen değerle uyuşmuyor.\n\n"
            f"Mevcut user_version: {current_user_version}\n"
            f"Beklenen schema version: {expected_schema_version}"
        )


def _tracking_table_exists(connection: Any) -> bool:
    row = connection.exec_driver_sql(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (MIGRATION_TRACKING_TABLE,),
    ).first()

    return row is not None


def _ensure_tracking_table(connection: Any) -> None:
    connection.exec_driver_sql(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TRACKING_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_id TEXT NOT NULL UNIQUE,
            migration_name TEXT NOT NULL,
            target_version INTEGER NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            execution_time_ms INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT
        )
        """
    )

    connection.exec_driver_sql(
        f"""
        CREATE INDEX IF NOT EXISTS ix_{MIGRATION_TRACKING_TABLE}_migration_id
        ON {MIGRATION_TRACKING_TABLE} (migration_id)
        """
    )

    connection.exec_driver_sql(
        f"""
        CREATE INDEX IF NOT EXISTS ix_{MIGRATION_TRACKING_TABLE}_target_version
        ON {MIGRATION_TRACKING_TABLE} (target_version)
        """
    )


def _get_sqlite_user_version(connection: Any) -> int:
    row = connection.exec_driver_sql("PRAGMA user_version").first()

    if row is None:
        return 0

    try:
        return int(row[0] or 0)
    except (TypeError, ValueError):
        return 0


def _set_sqlite_user_version(connection: Any, version: int) -> None:
    clean_version = int(version)

    if clean_version < 0:
        raise DatabaseMigrationServiceError("SQLite user_version negatif olamaz.")

    connection.exec_driver_sql(f"PRAGMA user_version = {clean_version}")


def _get_applied_migrations(connection: Any) -> list[AppliedMigrationInfo]:
    if not _tracking_table_exists(connection):
        return []

    rows = connection.exec_driver_sql(
        f"""
        SELECT
            migration_id,
            migration_name,
            target_version,
            checksum,
            applied_at,
            execution_time_ms,
            success,
            error_message
        FROM {MIGRATION_TRACKING_TABLE}
        ORDER BY target_version ASC, id ASC
        """
    ).mappings().all()

    result: list[AppliedMigrationInfo] = []

    for row in rows:
        result.append(
            AppliedMigrationInfo(
                migration_id=str(row["migration_id"]),
                migration_name=str(row["migration_name"]),
                target_version=int(row["target_version"]),
                checksum=str(row["checksum"]),
                applied_at=str(row["applied_at"]),
                execution_time_ms=int(row["execution_time_ms"] or 0),
                success=bool(row["success"]),
                error_message=(
                    None
                    if row["error_message"] is None
                    else str(row["error_message"])
                ),
            )
        )

    return result


def _verify_applied_migration_records(
    applied_migrations: list[AppliedMigrationInfo],
) -> None:
    migration_map = {
        migration.migration_id: migration
        for migration in MIGRATIONS
    }

    seen_ids: set[str] = set()
    seen_target_versions: set[int] = set()

    for applied_migration in applied_migrations:
        if not applied_migration.migration_id.strip():
            raise DatabaseMigrationServiceError(
                "schema_migrations içinde boş migration_id bulundu."
            )

        if applied_migration.migration_id in seen_ids:
            raise DatabaseMigrationServiceError(
                "schema_migrations içinde tekrarlanan migration_id bulundu.\n\n"
                f"Migration ID: {applied_migration.migration_id}"
            )

        if applied_migration.target_version in seen_target_versions:
            raise DatabaseMigrationServiceError(
                "schema_migrations içinde tekrarlanan target_version bulundu.\n\n"
                f"Target version: {applied_migration.target_version}"
            )

        seen_ids.add(applied_migration.migration_id)
        seen_target_versions.add(applied_migration.target_version)

        expected_migration = migration_map.get(applied_migration.migration_id)

        if expected_migration is None:
            raise DatabaseMigrationServiceError(
                "schema_migrations içinde bu uygulama sürümünün tanımadığı bir migration kaydı var.\n\n"
                f"Migration ID: {applied_migration.migration_id}\n"
                "Bu veritabanı farklı veya daha yeni bir FTM sürümüyle güncellenmiş olabilir."
            )

        if applied_migration.migration_name != expected_migration.name:
            raise DatabaseMigrationServiceError(
                "Daha önce uygulanmış migration adı değişmiş görünüyor.\n\n"
                f"Migration ID: {applied_migration.migration_id}\n"
                f"Beklenen: {expected_migration.name}\n"
                f"Bulunan: {applied_migration.migration_name}"
            )

        if applied_migration.target_version != expected_migration.target_version:
            raise DatabaseMigrationServiceError(
                "Daha önce uygulanmış migration target_version değeri değişmiş görünüyor.\n\n"
                f"Migration ID: {applied_migration.migration_id}\n"
                f"Beklenen: {expected_migration.target_version}\n"
                f"Bulunan: {applied_migration.target_version}"
            )

        if applied_migration.checksum != expected_migration.checksum:
            raise DatabaseMigrationServiceError(
                "Daha önce uygulanmış bir migration tanımı değiştirilmiş görünüyor.\n\n"
                f"Migration ID: {applied_migration.migration_id}\n"
                "Bu güvenlik nedeniyle durduruldu."
            )

        if not applied_migration.success:
            raise DatabaseMigrationServiceError(
                "schema_migrations içinde başarısız migration kaydı bulundu.\n\n"
                f"Migration ID: {applied_migration.migration_id}\n"
                f"Hata: {applied_migration.error_message or '-'}"
            )


def _get_pending_migrations_from_applied(
    applied_migrations: list[AppliedMigrationInfo],
) -> list[DatabaseMigration]:
    applied_ids = {
        migration.migration_id
        for migration in applied_migrations
        if migration.success
    }

    return [
        migration
        for migration in MIGRATIONS
        if migration.migration_id not in applied_ids
    ]


def _apply_single_migration(
    *,
    connection: Any,
    migration: DatabaseMigration,
) -> None:
    started_at = perf_counter()

    for statement in migration.statements:
        clean_statement = str(statement or "").strip()

        if not clean_statement:
            continue

        connection.exec_driver_sql(clean_statement)

    execution_time_ms = int((perf_counter() - started_at) * 1000)

    _record_successful_migration(
        connection=connection,
        migration=migration,
        execution_time_ms=execution_time_ms,
    )


def _record_successful_migration(
    *,
    connection: Any,
    migration: DatabaseMigration,
    execution_time_ms: int,
) -> None:
    connection.exec_driver_sql(
        f"""
        INSERT INTO {MIGRATION_TRACKING_TABLE} (
            migration_id,
            migration_name,
            target_version,
            checksum,
            applied_at,
            execution_time_ms,
            success,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
        """,
        (
            migration.migration_id,
            migration.name,
            migration.target_version,
            migration.checksum,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            int(execution_time_ms),
        ),
    )


def _create_safe_backup_before_migration() -> str:
    try:
        backup_result = create_database_backup()

    except BackupServiceError as exc:
        raise DatabaseMigrationServiceError(
            f"Migration öncesi otomatik yedek alınamadı:\n{exc}"
        ) from exc

    except Exception as exc:
        raise DatabaseMigrationServiceError(
            f"Migration öncesi otomatik yedek alınırken beklenmeyen hata oluştu:\n{exc}"
        ) from exc

    if not backup_result.success or backup_result.backup_file is None:
        raise DatabaseMigrationServiceError(
            "Migration öncesi otomatik yedek alınamadı. "
            f"Yedekleme mesajı: {backup_result.message}"
        )

    return str(backup_result.backup_file)


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MIGRATION_TRACKING_TABLE",
    "DatabaseMigration",
    "AppliedMigrationInfo",
    "DatabaseMigrationStatus",
    "DatabaseMigrationResult",
    "DatabaseMigrationServiceError",
    "ensure_sqlite_mode",
    "get_database_migration_status",
    "assert_database_migration_readiness",
    "run_database_migrations",
]
