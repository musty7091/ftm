from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from shutil import copy2
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.runtime_paths import ensure_runtime_folders
from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck, ReceivedCheckMovement
from app.models.enums import (
    BankAccountType,
    BankTransactionStatus,
    BusinessPartnerType,
    CurrencyCode,
    FinancialSourceType,
    IssuedCheckStatus,
    PosSettlementStatus,
    ReceivedCheckMovementType,
    ReceivedCheckStatus,
    TransactionDirection,
)
from app.models.pos import PosDevice, PosSettlement
from app.services.bank_service import create_bank, create_bank_account, get_bank_by_name
from app.services.bank_transaction_service import create_bank_transaction
from app.services.business_partner_service import create_business_partner, get_business_partner_by_name
from app.services.check_service import create_issued_check, create_received_check
from app.services.pos_device_service import create_pos_device
from app.services.pos_settlement_service import create_pos_settlement
from app.utils.decimal_utils import money, rate


DEMO_PREFIX = "DEMO - "
DEMO_BANK_NAME = "DEMO - FTM Demo Bankası"
DEMO_BANK_SHORT_NAME = "DEMOFTM"
DEMO_REFERENCE_PREFIX = "DEMO"


@dataclass(frozen=True)
class DemoPartnerSpec:
    name: str
    partner_type: BusinessPartnerType
    tax_office: str
    tax_number: str
    authorized_person: str
    phone: str
    email: str
    address: str
    notes: str
    is_active: bool = True


@dataclass(frozen=True)
class DemoBankAccountSpec:
    account_name: str
    account_type: BankAccountType
    currency_code: CurrencyCode
    opening_balance: Decimal
    account_no: str


@dataclass(frozen=True)
class DemoReceivedCheckSpec:
    customer_name: str
    drawer_bank_name: str
    drawer_branch_name: str
    check_number: str
    received_offset_days: int
    due_offset_days: int
    amount: Decimal
    currency_code: CurrencyCode
    status: ReceivedCheckStatus
    description: str
    collection_account_currency: Optional[CurrencyCode] = None


@dataclass(frozen=True)
class DemoIssuedCheckSpec:
    supplier_name: str
    check_number: str
    issue_offset_days: int
    due_offset_days: int
    amount: Decimal
    currency_code: CurrencyCode
    status: IssuedCheckStatus
    description: str


@dataclass(frozen=True)
class DemoBankTransactionSpec:
    account_currency: CurrencyCode
    transaction_offset_days: int
    value_offset_days: int
    direction: TransactionDirection
    status: BankTransactionStatus
    amount: Decimal
    source_type: FinancialSourceType
    reference_no: str
    description: str


@dataclass(frozen=True)
class DemoPosSettlementSpec:
    transaction_offset_days: int
    gross_amount: Decimal
    reference_no: str
    description: str
    final_status: PosSettlementStatus
    actual_net_delta: Decimal = Decimal("0.00")
    difference_reason: Optional[str] = None


class DemoSeedError(RuntimeError):
    pass


class DemoSeedStats:
    def __init__(self) -> None:
        self.created_partners = 0
        self.skipped_partners = 0
        self.created_banks = 0
        self.skipped_banks = 0
        self.created_bank_accounts = 0
        self.skipped_bank_accounts = 0
        self.created_bank_transactions = 0
        self.skipped_bank_transactions = 0
        self.created_received_checks = 0
        self.skipped_received_checks = 0
        self.created_issued_checks = 0
        self.skipped_issued_checks = 0
        self.created_pos_devices = 0
        self.skipped_pos_devices = 0
        self.created_pos_settlements = 0
        self.skipped_pos_settlements = 0
        self.deleted_demo_rows = 0
        self.backup_path: Optional[Path] = None

    def print_summary(self) -> None:
        print("")
        print("DEMO SEED ÖZETİ")
        print("----------------")
        if self.backup_path is not None:
            print(f"Yedek dosyası                : {self.backup_path}")
        print(f"Silinen demo kayıt           : {self.deleted_demo_rows}")
        print(f"Oluşturulan muhatap          : {self.created_partners}")
        print(f"Atlanan muhatap              : {self.skipped_partners}")
        print(f"Oluşturulan banka            : {self.created_banks}")
        print(f"Atlanan banka                : {self.skipped_banks}")
        print(f"Oluşturulan banka hesabı     : {self.created_bank_accounts}")
        print(f"Atlanan banka hesabı         : {self.skipped_bank_accounts}")
        print(f"Oluşturulan banka hareketi   : {self.created_bank_transactions}")
        print(f"Atlanan banka hareketi       : {self.skipped_bank_transactions}")
        print(f"Oluşturulan alınan çek       : {self.created_received_checks}")
        print(f"Atlanan alınan çek           : {self.skipped_received_checks}")
        print(f"Oluşturulan yazılan çek      : {self.created_issued_checks}")
        print(f"Atlanan yazılan çek          : {self.skipped_issued_checks}")
        print(f"Oluşturulan POS cihazı       : {self.created_pos_devices}")
        print(f"Atlanan POS cihazı           : {self.skipped_pos_devices}")
        print(f"Oluşturulan POS kaydı        : {self.created_pos_settlements}")
        print(f"Atlanan POS kaydı            : {self.skipped_pos_settlements}")
        print("")


PARTNER_SPECS: list[DemoPartnerSpec] = [
    DemoPartnerSpec(
        name="DEMO - Akdeniz Market Ltd",
        partner_type=BusinessPartnerType.CUSTOMER,
        tax_office="Mersin",
        tax_number="1000000001",
        authorized_person="Ayhan Demir",
        phone="0324 111 11 01",
        email="akdeniz.market@example.com",
        address="Mersin / Yenişehir",
        notes="Demo müşteri. Alınan çek testleri için kullanılır.",
    ),
    DemoPartnerSpec(
        name="DEMO - Toros Gıda A.Ş.",
        partner_type=BusinessPartnerType.CUSTOMER,
        tax_office="Mersin",
        tax_number="1000000002",
        authorized_person="Selin Arslan",
        phone="0324 111 11 02",
        email="toros.gida@example.com",
        address="Mersin / Toroslar",
        notes="Demo müşteri. Yakın vade tahsilat senaryosu.",
    ),
    DemoPartnerSpec(
        name="DEMO - Mersin Restoran Grubu",
        partner_type=BusinessPartnerType.CUSTOMER,
        tax_office="Mersin",
        tax_number="1000000003",
        authorized_person="Murat Kaya",
        phone="0324 111 11 03",
        email="restoran.grubu@example.com",
        address="Mersin / Mezitli",
        notes="Demo müşteri. Çoklu çek senaryosu.",
    ),
    DemoPartnerSpec(
        name="DEMO - Deniz Büfe ve Tekel",
        partner_type=BusinessPartnerType.CUSTOMER,
        tax_office="Mersin",
        tax_number="1000000004",
        authorized_person="Deniz Yılmaz",
        phone="0324 111 11 04",
        email="deniz.bufetekel@example.com",
        address="Mersin / Akdeniz",
        notes="Demo müşteri. Problemli çek senaryosu.",
    ),
    DemoPartnerSpec(
        name="DEMO - Metgin Tedarik Ltd",
        partner_type=BusinessPartnerType.SUPPLIER,
        tax_office="Mersin",
        tax_number="2000000001",
        authorized_person="Hasan Metgin",
        phone="0324 222 22 01",
        email="metgin.tedarik@example.com",
        address="Mersin / Yenişehir",
        notes="Demo tedarikçi. Yazılan çek testleri için kullanılır.",
    ),
    DemoPartnerSpec(
        name="DEMO - Çukurova Ambalaj",
        partner_type=BusinessPartnerType.SUPPLIER,
        tax_office="Adana",
        tax_number="2000000002",
        authorized_person="Elif Korkmaz",
        phone="0322 222 22 02",
        email="cukurova.ambalaj@example.com",
        address="Adana / Seyhan",
        notes="Demo tedarikçi. Yakın ödeme vadesi.",
    ),
    DemoPartnerSpec(
        name="DEMO - Kuzey Lojistik",
        partner_type=BusinessPartnerType.SUPPLIER,
        tax_office="Mersin",
        tax_number="2000000003",
        authorized_person="Eren Aydın",
        phone="0324 222 22 03",
        email="kuzey.lojistik@example.com",
        address="Mersin / Tarsus",
        notes="Demo tedarikçi. Lojistik ödeme senaryosu.",
    ),
    DemoPartnerSpec(
        name="DEMO - Vega Yazılım Bayi",
        partner_type=BusinessPartnerType.SUPPLIER,
        tax_office="İstanbul",
        tax_number="2000000004",
        authorized_person="Cem Sönmez",
        phone="0212 222 22 04",
        email="vega.bayi@example.com",
        address="İstanbul / Kadıköy",
        notes="Demo tedarikçi. Yazılım/hizmet ödeme senaryosu.",
    ),
    DemoPartnerSpec(
        name="DEMO - Ada Ticaret",
        partner_type=BusinessPartnerType.BOTH,
        tax_office="Mersin",
        tax_number="3000000001",
        authorized_person="Ada Özkan",
        phone="0324 333 33 01",
        email="ada.ticaret@example.com",
        address="Mersin / Mezitli",
        notes="Demo muhatap. Hem müşteri hem tedarikçi senaryosu.",
    ),
    DemoPartnerSpec(
        name="DEMO - Pasif Eski Tedarikçi",
        partner_type=BusinessPartnerType.SUPPLIER,
        tax_office="Mersin",
        tax_number="9000000001",
        authorized_person="Eski Yetkili",
        phone="0324 999 99 01",
        email="pasif.tedarikci@example.com",
        address="Mersin",
        notes="Demo pasif muhatap. Tablo görsel ayrımı testi için kullanılır.",
        is_active=False,
    ),
]


BANK_ACCOUNT_SPECS: list[DemoBankAccountSpec] = [
    DemoBankAccountSpec(
        account_name="DEMO TRY Vadesiz",
        account_type=BankAccountType.CHECKING,
        currency_code=CurrencyCode.TRY,
        opening_balance=Decimal("650000.00"),
        account_no="DEMO-TRY-001",
    ),
    DemoBankAccountSpec(
        account_name="DEMO EUR Vadesiz",
        account_type=BankAccountType.CHECKING,
        currency_code=CurrencyCode.EUR,
        opening_balance=Decimal("2500.00"),
        account_no="DEMO-EUR-001",
    ),
    DemoBankAccountSpec(
        account_name="DEMO GBP Vadesiz",
        account_type=BankAccountType.CHECKING,
        currency_code=CurrencyCode.GBP,
        opening_balance=Decimal("1500.00"),
        account_no="DEMO-GBP-001",
    ),
    DemoBankAccountSpec(
        account_name="DEMO USD Vadesiz",
        account_type=BankAccountType.CHECKING,
        currency_code=CurrencyCode.USD,
        opening_balance=Decimal("5000.00"),
        account_no="DEMO-USD-001",
    ),
]


RECEIVED_CHECK_SPECS: list[DemoReceivedCheckSpec] = [
    DemoReceivedCheckSpec(
        customer_name="DEMO - Akdeniz Market Ltd",
        drawer_bank_name="DEMO Garanti",
        drawer_branch_name="Mersin Şube",
        check_number="DEMO-AC-001",
        received_offset_days=-8,
        due_offset_days=0,
        amount=Decimal("185000.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.PORTFOLIO,
        description="Bugün tahsil edilecek demo müşteri çeki.",
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Toros Gıda A.Ş.",
        drawer_bank_name="DEMO İş Bankası",
        drawer_branch_name="Pozcu Şube",
        check_number="DEMO-AC-002",
        received_offset_days=-10,
        due_offset_days=2,
        amount=Decimal("72500.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.GIVEN_TO_BANK,
        description="Yakın vadeli tahsilat demo çeki.",
        collection_account_currency=CurrencyCode.TRY,
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Mersin Restoran Grubu",
        drawer_bank_name="DEMO Yapı Kredi",
        drawer_branch_name="Mezitli Şube",
        check_number="DEMO-AC-003",
        received_offset_days=-12,
        due_offset_days=7,
        amount=Decimal("4250.00"),
        currency_code=CurrencyCode.EUR,
        status=ReceivedCheckStatus.IN_COLLECTION,
        description="EUR tahsilat senaryosu.",
        collection_account_currency=CurrencyCode.EUR,
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Ada Ticaret",
        drawer_bank_name="DEMO Akbank",
        drawer_branch_name="Yenişehir Şube",
        check_number="DEMO-AC-004",
        received_offset_days=-6,
        due_offset_days=14,
        amount=Decimal("130000.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.PORTFOLIO,
        description="14 günlük tahsilat senaryosu.",
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Akdeniz Market Ltd",
        drawer_bank_name="DEMO DenizBank",
        drawer_branch_name="Akdeniz Şube",
        check_number="DEMO-AC-005",
        received_offset_days=-9,
        due_offset_days=22,
        amount=Decimal("2100.00"),
        currency_code=CurrencyCode.GBP,
        status=ReceivedCheckStatus.PORTFOLIO,
        description="GBP tahsilat senaryosu.",
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Toros Gıda A.Ş.",
        drawer_bank_name="DEMO QNB",
        drawer_branch_name="Çarşı Şube",
        check_number="DEMO-AC-006",
        received_offset_days=-11,
        due_offset_days=30,
        amount=Decimal("210000.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.GIVEN_TO_BANK,
        description="30 günlük tahsilat senaryosu.",
        collection_account_currency=CurrencyCode.TRY,
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Deniz Büfe ve Tekel",
        drawer_bank_name="DEMO Halkbank",
        drawer_branch_name="Tarsus Şube",
        check_number="DEMO-AC-007",
        received_offset_days=-20,
        due_offset_days=-4,
        amount=Decimal("52000.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.BOUNCED,
        description="Problemli çek senaryosu: karşılıksız / iade.",
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Mersin Restoran Grubu",
        drawer_bank_name="DEMO Ziraat",
        drawer_branch_name="Forum Şube",
        check_number="DEMO-AC-008",
        received_offset_days=-25,
        due_offset_days=-10,
        amount=Decimal("3000.00"),
        currency_code=CurrencyCode.USD,
        status=ReceivedCheckStatus.RETURNED,
        description="Problemli USD çek senaryosu.",
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Akdeniz Market Ltd",
        drawer_bank_name="DEMO VakıfBank",
        drawer_branch_name="Liman Şube",
        check_number="DEMO-AC-009",
        received_offset_days=-35,
        due_offset_days=-15,
        amount=Decimal("45000.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.COLLECTED,
        description="Tahsil edilmiş geçmiş çek senaryosu.",
        collection_account_currency=CurrencyCode.TRY,
    ),
    DemoReceivedCheckSpec(
        customer_name="DEMO - Ada Ticaret",
        drawer_bank_name="DEMO TEB",
        drawer_branch_name="Sanayi Şube",
        check_number="DEMO-AC-010",
        received_offset_days=-18,
        due_offset_days=5,
        amount=Decimal("98000.00"),
        currency_code=CurrencyCode.TRY,
        status=ReceivedCheckStatus.PORTFOLIO,
        description="5 günlük tahsilat senaryosu.",
    ),
]


ISSUED_CHECK_SPECS: list[DemoIssuedCheckSpec] = [
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Metgin Tedarik Ltd",
        check_number="DEMO-YC-001",
        issue_offset_days=-14,
        due_offset_days=0,
        amount=Decimal("95000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.GIVEN,
        description="Bugün ödenecek demo tedarikçi çeki.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Çukurova Ambalaj",
        check_number="DEMO-YC-002",
        issue_offset_days=-12,
        due_offset_days=1,
        amount=Decimal("110000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.GIVEN,
        description="Yarın ödenecek demo çek.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Metgin Tedarik Ltd",
        check_number="DEMO-YC-003",
        issue_offset_days=-10,
        due_offset_days=4,
        amount=Decimal("1000.00"),
        currency_code=CurrencyCode.EUR,
        status=IssuedCheckStatus.GIVEN,
        description="EUR yazılan çek senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Kuzey Lojistik",
        check_number="DEMO-YC-004",
        issue_offset_days=-6,
        due_offset_days=8,
        amount=Decimal("180000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.PREPARED,
        description="Hazırlanmış ama verilmemiş çek senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Vega Yazılım Bayi",
        check_number="DEMO-YC-005",
        issue_offset_days=-9,
        due_offset_days=12,
        amount=Decimal("1200.00"),
        currency_code=CurrencyCode.GBP,
        status=IssuedCheckStatus.GIVEN,
        description="GBP yazılan çek senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Çukurova Ambalaj",
        check_number="DEMO-YC-006",
        issue_offset_days=-7,
        due_offset_days=18,
        amount=Decimal("260000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.GIVEN,
        description="18 günlük yüksek ödeme senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Ada Ticaret",
        check_number="DEMO-YC-007",
        issue_offset_days=-5,
        due_offset_days=26,
        amount=Decimal("90000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.GIVEN,
        description="26 günlük yazılan çek senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Kuzey Lojistik",
        check_number="DEMO-YC-008",
        issue_offset_days=-20,
        due_offset_days=-2,
        amount=Decimal("40000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.GIVEN,
        description="Vadesi geçmiş bekleyen yazılan çek senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Metgin Tedarik Ltd",
        check_number="DEMO-YC-009",
        issue_offset_days=-8,
        due_offset_days=15,
        amount=Decimal("75000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.RISK,
        description="Riskli yazılan çek senaryosu.",
    ),
    DemoIssuedCheckSpec(
        supplier_name="DEMO - Vega Yazılım Bayi",
        check_number="DEMO-YC-010",
        issue_offset_days=-40,
        due_offset_days=-20,
        amount=Decimal("35000.00"),
        currency_code=CurrencyCode.TRY,
        status=IssuedCheckStatus.PAID,
        description="Ödenmiş geçmiş çek senaryosu.",
    ),
]


BANK_TRANSACTION_SPECS: list[DemoBankTransactionSpec] = [
    DemoBankTransactionSpec(
        account_currency=CurrencyCode.TRY,
        transaction_offset_days=-6,
        value_offset_days=-6,
        direction=TransactionDirection.IN,
        status=BankTransactionStatus.REALIZED,
        amount=Decimal("245000.00"),
        source_type=FinancialSourceType.CASH_DEPOSIT,
        reference_no="DEMO-BH-001",
        description="Demo banka girişi: nakit/kasa aktarımı.",
    ),
    DemoBankTransactionSpec(
        account_currency=CurrencyCode.TRY,
        transaction_offset_days=-5,
        value_offset_days=-5,
        direction=TransactionDirection.OUT,
        status=BankTransactionStatus.REALIZED,
        amount=Decimal("85000.00"),
        source_type=FinancialSourceType.OTHER,
        reference_no="DEMO-BH-002",
        description="Demo banka çıkışı: tedarikçi ödemesi.",
    ),
    DemoBankTransactionSpec(
        account_currency=CurrencyCode.TRY,
        transaction_offset_days=-2,
        value_offset_days=-2,
        direction=TransactionDirection.IN,
        status=BankTransactionStatus.REALIZED,
        amount=Decimal("132500.00"),
        source_type=FinancialSourceType.RECEIVED_CHECK,
        reference_no="DEMO-BH-003",
        description="Demo banka girişi: çek tahsilatı.",
    ),
    DemoBankTransactionSpec(
        account_currency=CurrencyCode.TRY,
        transaction_offset_days=3,
        value_offset_days=3,
        direction=TransactionDirection.OUT,
        status=BankTransactionStatus.PLANNED,
        amount=Decimal("115000.00"),
        source_type=FinancialSourceType.OTHER,
        reference_no="DEMO-BH-004",
        description="Demo planlanan banka çıkışı.",
    ),
    DemoBankTransactionSpec(
        account_currency=CurrencyCode.EUR,
        transaction_offset_days=-4,
        value_offset_days=-4,
        direction=TransactionDirection.IN,
        status=BankTransactionStatus.REALIZED,
        amount=Decimal("1500.00"),
        source_type=FinancialSourceType.RECEIVED_CHECK,
        reference_no="DEMO-BH-005",
        description="Demo EUR banka girişi.",
    ),
    DemoBankTransactionSpec(
        account_currency=CurrencyCode.GBP,
        transaction_offset_days=10,
        value_offset_days=10,
        direction=TransactionDirection.OUT,
        status=BankTransactionStatus.PLANNED,
        amount=Decimal("600.00"),
        source_type=FinancialSourceType.OTHER,
        reference_no="DEMO-BH-006",
        description="Demo GBP planlanan çıkış.",
    ),
]


POS_SETTLEMENT_SPECS: list[DemoPosSettlementSpec] = [
    DemoPosSettlementSpec(
        transaction_offset_days=-3,
        gross_amount=Decimal("58000.00"),
        reference_no="DEMO-POS-001",
        description="Demo POS beklenen yatış.",
        final_status=PosSettlementStatus.PLANNED,
    ),
    DemoPosSettlementSpec(
        transaction_offset_days=-2,
        gross_amount=Decimal("73500.00"),
        reference_no="DEMO-POS-002",
        description="Demo POS beklenen yatış.",
        final_status=PosSettlementStatus.PLANNED,
    ),
    DemoPosSettlementSpec(
        transaction_offset_days=-6,
        gross_amount=Decimal("46250.00"),
        reference_no="DEMO-POS-003",
        description="Demo POS gerçekleşmiş yatış.",
        final_status=PosSettlementStatus.REALIZED,
    ),
    DemoPosSettlementSpec(
        transaction_offset_days=-5,
        gross_amount=Decimal("39500.00"),
        reference_no="DEMO-POS-004",
        description="Demo POS mutabakat farkı.",
        final_status=PosSettlementStatus.MISMATCH,
        actual_net_delta=Decimal("-120.00"),
        difference_reason="Demo mutabakat farkı: banka kesintisi fazla göründü.",
    ),
    DemoPosSettlementSpec(
        transaction_offset_days=0,
        gross_amount=Decimal("88000.00"),
        reference_no="DEMO-POS-005",
        description="Bugünkü demo POS satışı.",
        final_status=PosSettlementStatus.PLANNED,
    ),
]


def _confirm_or_exit(args: argparse.Namespace) -> None:
    if args.yes:
        return

    print("Bu işlem DEMO veri yüklemesi yapacak.")
    print("Gerçek kullanım veritabanında çalıştırmadan önce mutlaka yedek alınmalıdır.")
    print("Devam etmek için komuta --yes ekleyin.")
    raise SystemExit(2)


def _create_database_backup() -> Optional[Path]:
    if not settings.is_sqlite:
        return None

    runtime_paths = ensure_runtime_folders()
    source_path = settings.sqlite_database_path

    if not source_path.exists():
        raise DemoSeedError(f"SQLite veritabanı bulunamadı: {source_path}")

    backup_path = runtime_paths.backups_folder / f"demo_seed_pre_backup_{date.today().strftime('%Y%m%d')}.db"

    counter = 1
    while backup_path.exists():
        backup_path = runtime_paths.backups_folder / f"demo_seed_pre_backup_{date.today().strftime('%Y%m%d')}_{counter:02d}.db"
        counter += 1

    try:
        source_connection = sqlite3.connect(str(source_path))
        backup_connection = sqlite3.connect(str(backup_path))

        try:
            source_connection.backup(backup_connection)
        finally:
            backup_connection.close()
            source_connection.close()
    except Exception:
        backup_path.unlink(missing_ok=True)
        fallback_path = backup_path.with_suffix(".copy.db")
        copy2(source_path, fallback_path)
        return fallback_path

    return backup_path


def _count_existing_core_tables(session: Session) -> dict[str, int]:
    return {
        "business_partners": int(session.execute(select(func.count(BusinessPartner.id))).scalar_one() or 0),
        "banks": int(session.execute(select(func.count(Bank.id))).scalar_one() or 0),
        "bank_accounts": int(session.execute(select(func.count(BankAccount.id))).scalar_one() or 0),
        "received_checks": int(session.execute(select(func.count(ReceivedCheck.id))).scalar_one() or 0),
        "issued_checks": int(session.execute(select(func.count(IssuedCheck.id))).scalar_one() or 0),
    }


def _delete_demo_data(session: Session) -> int:
    deleted_count = 0

    demo_received_ids = list(
        session.execute(
            select(ReceivedCheck.id).where(ReceivedCheck.check_number.like("DEMO-AC-%"))
        ).scalars().all()
    )

    if demo_received_ids:
        result = session.execute(
            delete(ReceivedCheckMovement).where(
                ReceivedCheckMovement.received_check_id.in_(demo_received_ids)
            )
        )
        deleted_count += int(result.rowcount or 0)

    result = session.execute(delete(ReceivedCheck).where(ReceivedCheck.check_number.like("DEMO-AC-%")))
    deleted_count += int(result.rowcount or 0)

    result = session.execute(delete(IssuedCheck).where(IssuedCheck.check_number.like("DEMO-YC-%")))
    deleted_count += int(result.rowcount or 0)

    result = session.execute(delete(PosSettlement).where(PosSettlement.reference_no.like("DEMO-POS-%")))
    deleted_count += int(result.rowcount or 0)

    result = session.execute(delete(PosDevice).where(PosDevice.name.like("DEMO -%")))
    deleted_count += int(result.rowcount or 0)

    result = session.execute(delete(BankTransaction).where(BankTransaction.reference_no.like("DEMO-BH-%")))
    deleted_count += int(result.rowcount or 0)

    demo_bank_ids = list(
        session.execute(select(Bank.id).where(Bank.name == DEMO_BANK_NAME)).scalars().all()
    )

    if demo_bank_ids:
        result = session.execute(delete(BankAccount).where(BankAccount.bank_id.in_(demo_bank_ids)))
        deleted_count += int(result.rowcount or 0)

        result = session.execute(delete(Bank).where(Bank.id.in_(demo_bank_ids)))
        deleted_count += int(result.rowcount or 0)

    result = session.execute(delete(BusinessPartner).where(BusinessPartner.name.like(f"{DEMO_PREFIX}%")))
    deleted_count += int(result.rowcount or 0)

    session.flush()
    return deleted_count


def _get_or_create_partner(session: Session, spec: DemoPartnerSpec, stats: DemoSeedStats) -> BusinessPartner:
    existing_partner = get_business_partner_by_name(session, spec.name)

    if existing_partner is not None:
        stats.skipped_partners += 1
        return existing_partner

    partner = create_business_partner(
        session,
        name=spec.name,
        partner_type=spec.partner_type,
        tax_office=spec.tax_office,
        tax_number=spec.tax_number,
        authorized_person=spec.authorized_person,
        phone=spec.phone,
        email=spec.email,
        address=spec.address,
        notes=spec.notes,
        created_by_user_id=None,
    )

    partner.is_active = spec.is_active
    session.flush()

    stats.created_partners += 1
    return partner


def _get_or_create_demo_bank(session: Session, stats: DemoSeedStats) -> Bank:
    existing_bank = get_bank_by_name(session, DEMO_BANK_NAME)

    if existing_bank is not None:
        stats.skipped_banks += 1
        return existing_bank

    bank = create_bank(
        session,
        name=DEMO_BANK_NAME,
        short_name=DEMO_BANK_SHORT_NAME,
        notes="Demo seed verisi için oluşturulan banka.",
        created_by_user_id=None,
    )

    stats.created_banks += 1
    return bank


def _get_bank_account_by_name(session: Session, bank_id: int, account_name: str) -> Optional[BankAccount]:
    return session.execute(
        select(BankAccount).where(
            BankAccount.bank_id == bank_id,
            BankAccount.account_name == account_name,
        )
    ).scalar_one_or_none()


def _get_or_create_bank_account(
    session: Session,
    *,
    bank: Bank,
    spec: DemoBankAccountSpec,
    stats: DemoSeedStats,
) -> BankAccount:
    existing_account = _get_bank_account_by_name(session, bank.id, spec.account_name)

    if existing_account is not None:
        stats.skipped_bank_accounts += 1
        return existing_account

    account = create_bank_account(
        session,
        bank_id=bank.id,
        account_name=spec.account_name,
        account_type=spec.account_type,
        currency_code=spec.currency_code,
        iban=None,
        branch_name="Demo Şube",
        branch_code="0001",
        account_no=spec.account_no,
        opening_balance=spec.opening_balance,
        opening_date=date.today() - timedelta(days=60),
        notes="Demo seed verisi için oluşturulan banka hesabı.",
        created_by_user_id=None,
    )

    stats.created_bank_accounts += 1
    return account


def _account_for_currency(accounts_by_currency: dict[CurrencyCode, BankAccount], currency_code: CurrencyCode) -> BankAccount:
    account = accounts_by_currency.get(currency_code)

    if account is None:
        raise DemoSeedError(f"Demo banka hesabı bulunamadı: {currency_code.value}")

    return account


def _get_partner_by_name_or_raise(session: Session, name: str) -> BusinessPartner:
    partner = get_business_partner_by_name(session, name)

    if partner is None:
        raise DemoSeedError(f"Demo muhatap bulunamadı: {name}")

    return partner


def _received_check_exists(session: Session, check_number: str) -> bool:
    return session.execute(
        select(ReceivedCheck.id).where(ReceivedCheck.check_number == check_number)
    ).scalar_one_or_none() is not None


def _issued_check_exists(session: Session, check_number: str) -> bool:
    return session.execute(
        select(IssuedCheck.id).where(IssuedCheck.check_number == check_number)
    ).scalar_one_or_none() is not None


def _bank_transaction_exists(session: Session, reference_no: str) -> bool:
    return session.execute(
        select(BankTransaction.id).where(BankTransaction.reference_no == reference_no)
    ).scalar_one_or_none() is not None


def _pos_settlement_exists(session: Session, reference_no: str) -> bool:
    return session.execute(
        select(PosSettlement.id).where(PosSettlement.reference_no == reference_no)
    ).scalar_one_or_none() is not None


def _create_final_received_check_movement(
    session: Session,
    *,
    check: ReceivedCheck,
    from_status: ReceivedCheckStatus,
    to_status: ReceivedCheckStatus,
    movement_date: date,
    bank_account_id: Optional[int],
    description: str,
) -> None:
    movement_type_map = {
        ReceivedCheckStatus.COLLECTED: ReceivedCheckMovementType.COLLECTED,
        ReceivedCheckStatus.BOUNCED: ReceivedCheckMovementType.BOUNCED,
        ReceivedCheckStatus.RETURNED: ReceivedCheckMovementType.RETURNED,
        ReceivedCheckStatus.CANCELLED: ReceivedCheckMovementType.CANCELLED,
        ReceivedCheckStatus.ENDORSED: ReceivedCheckMovementType.ENDORSED,
        ReceivedCheckStatus.DISCOUNTED: ReceivedCheckMovementType.DISCOUNTED,
    }

    movement_type = movement_type_map.get(to_status)

    if movement_type is None:
        return

    movement = ReceivedCheckMovement(
        received_check_id=check.id,
        movement_type=movement_type,
        movement_date=movement_date,
        from_status=from_status,
        to_status=to_status,
        bank_account_id=bank_account_id,
        counterparty_text="Demo seed",
        purpose_text="Demo seed final durum hareketi.",
        reference_no=f"{check.check_number}-MOV",
        description=description,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        discount_rate=None,
        discount_expense_amount=None,
        net_bank_amount=None,
        created_by_user_id=None,
    )

    session.add(movement)
    session.flush()


def _seed_received_checks(
    session: Session,
    *,
    accounts_by_currency: dict[CurrencyCode, BankAccount],
    stats: DemoSeedStats,
) -> None:
    today = date.today()

    for spec in RECEIVED_CHECK_SPECS:
        if _received_check_exists(session, spec.check_number):
            stats.skipped_received_checks += 1
            continue

        customer = _get_partner_by_name_or_raise(session, spec.customer_name)

        collection_bank_account_id = None
        if spec.collection_account_currency is not None:
            collection_bank_account_id = _account_for_currency(
                accounts_by_currency,
                spec.collection_account_currency,
            ).id

        initial_status = spec.status
        if initial_status not in {
            ReceivedCheckStatus.PORTFOLIO,
            ReceivedCheckStatus.GIVEN_TO_BANK,
            ReceivedCheckStatus.IN_COLLECTION,
        }:
            initial_status = ReceivedCheckStatus.PORTFOLIO

        check = create_received_check(
            session,
            customer_id=customer.id,
            collection_bank_account_id=collection_bank_account_id,
            drawer_bank_name=spec.drawer_bank_name,
            drawer_branch_name=spec.drawer_branch_name,
            check_number=spec.check_number,
            received_date=today + timedelta(days=spec.received_offset_days),
            due_date=today + timedelta(days=spec.due_offset_days),
            amount=spec.amount,
            currency_code=spec.currency_code,
            status=initial_status,
            reference_no=f"{DEMO_REFERENCE_PREFIX}-ALINAN-{spec.check_number}",
            description=spec.description,
            created_by_user_id=None,
            acting_user=None,
        )

        if spec.status != initial_status:
            old_status = check.status
            check.status = spec.status
            _create_final_received_check_movement(
                session,
                check=check,
                from_status=old_status,
                to_status=spec.status,
                movement_date=today + timedelta(days=min(spec.due_offset_days + 1, 0)),
                bank_account_id=collection_bank_account_id,
                description=spec.description,
            )

        session.flush()
        stats.created_received_checks += 1


def _seed_issued_checks(
    session: Session,
    *,
    accounts_by_currency: dict[CurrencyCode, BankAccount],
    stats: DemoSeedStats,
) -> None:
    today = date.today()

    for spec in ISSUED_CHECK_SPECS:
        if _issued_check_exists(session, spec.check_number):
            stats.skipped_issued_checks += 1
            continue

        supplier = _get_partner_by_name_or_raise(session, spec.supplier_name)
        bank_account = _account_for_currency(accounts_by_currency, spec.currency_code)

        initial_status = spec.status
        if initial_status not in {IssuedCheckStatus.PREPARED, IssuedCheckStatus.GIVEN}:
            initial_status = IssuedCheckStatus.GIVEN

        check = create_issued_check(
            session,
            supplier_id=supplier.id,
            bank_account_id=bank_account.id,
            check_number=spec.check_number,
            issue_date=today + timedelta(days=spec.issue_offset_days),
            due_date=today + timedelta(days=spec.due_offset_days),
            amount=spec.amount,
            status=initial_status,
            reference_no=f"{DEMO_REFERENCE_PREFIX}-YAZILAN-{spec.check_number}",
            description=spec.description,
            created_by_user_id=None,
            acting_user=None,
        )

        if spec.status != initial_status:
            check.status = spec.status

        session.flush()
        stats.created_issued_checks += 1


def _seed_bank_transactions(
    session: Session,
    *,
    accounts_by_currency: dict[CurrencyCode, BankAccount],
    stats: DemoSeedStats,
) -> None:
    today = date.today()

    for spec in BANK_TRANSACTION_SPECS:
        if _bank_transaction_exists(session, spec.reference_no):
            stats.skipped_bank_transactions += 1
            continue

        bank_account = _account_for_currency(accounts_by_currency, spec.account_currency)

        create_bank_transaction(
            session,
            bank_account_id=bank_account.id,
            transaction_date=today + timedelta(days=spec.transaction_offset_days),
            value_date=today + timedelta(days=spec.value_offset_days),
            direction=spec.direction,
            status=spec.status,
            amount=spec.amount,
            currency_code=spec.account_currency,
            source_type=spec.source_type,
            source_id=None,
            reference_no=spec.reference_no,
            description=spec.description,
            created_by_user_id=None,
            acting_user=None,
        )

        stats.created_bank_transactions += 1


def _get_or_create_pos_device(
    session: Session,
    *,
    bank_account: BankAccount,
    stats: DemoSeedStats,
) -> PosDevice:
    name = "DEMO - FTM POS Cihazı"
    terminal_no = "DEMO-POS-TERM-001"

    existing_device = session.execute(
        select(PosDevice).where(
            PosDevice.bank_account_id == bank_account.id,
            PosDevice.terminal_no == terminal_no,
        )
    ).scalar_one_or_none()

    if existing_device is not None:
        stats.skipped_pos_devices += 1
        return existing_device

    pos_device = create_pos_device(
        session,
        bank_account_id=bank_account.id,
        name=name,
        terminal_no=terminal_no,
        commission_rate=rate("2.25", field_name="Komisyon oranı"),
        settlement_delay_days=1,
        currency_code=CurrencyCode.TRY,
        notes="Demo POS cihazı.",
        created_by_user_id=None,
        acting_user=None,
    )

    stats.created_pos_devices += 1
    return pos_device


def _seed_pos_settlements(
    session: Session,
    *,
    pos_device: PosDevice,
    stats: DemoSeedStats,
) -> None:
    today = date.today()

    for spec in POS_SETTLEMENT_SPECS:
        if _pos_settlement_exists(session, spec.reference_no):
            stats.skipped_pos_settlements += 1
            continue

        settlement = create_pos_settlement(
            session,
            pos_device_id=pos_device.id,
            transaction_date=today + timedelta(days=spec.transaction_offset_days),
            gross_amount=spec.gross_amount,
            reference_no=spec.reference_no,
            description=spec.description,
            created_by_user_id=None,
            acting_user=None,
        )

        if spec.final_status == PosSettlementStatus.REALIZED:
            settlement.status = PosSettlementStatus.REALIZED
            settlement.realized_settlement_date = settlement.expected_settlement_date
            settlement.actual_net_amount = settlement.net_amount
            settlement.difference_amount = Decimal("0.00")
        elif spec.final_status == PosSettlementStatus.MISMATCH:
            settlement.status = PosSettlementStatus.MISMATCH
            settlement.realized_settlement_date = settlement.expected_settlement_date
            settlement.actual_net_amount = money(
                settlement.net_amount + spec.actual_net_delta,
                field_name="Gerçek POS net tutarı",
            )
            settlement.difference_amount = money(
                settlement.actual_net_amount - settlement.net_amount,
                field_name="POS fark tutarı",
            )
            settlement.difference_reason = spec.difference_reason

        session.flush()
        stats.created_pos_settlements += 1


def seed_demo_data(*, reset_demo: bool = False) -> DemoSeedStats:
    stats = DemoSeedStats()
    stats.backup_path = _create_database_backup()

    with session_scope() as session:
        _count_existing_core_tables(session)

        if reset_demo:
            stats.deleted_demo_rows = _delete_demo_data(session)

        for partner_spec in PARTNER_SPECS:
            _get_or_create_partner(session, partner_spec, stats)

        bank = _get_or_create_demo_bank(session, stats)

        accounts_by_currency: dict[CurrencyCode, BankAccount] = {}
        for account_spec in BANK_ACCOUNT_SPECS:
            account = _get_or_create_bank_account(
                session,
                bank=bank,
                spec=account_spec,
                stats=stats,
            )
            accounts_by_currency[account.currency_code] = account

        _seed_bank_transactions(
            session,
            accounts_by_currency=accounts_by_currency,
            stats=stats,
        )
        _seed_received_checks(
            session,
            accounts_by_currency=accounts_by_currency,
            stats=stats,
        )
        _seed_issued_checks(
            session,
            accounts_by_currency=accounts_by_currency,
            stats=stats,
        )

        try_account = _account_for_currency(accounts_by_currency, CurrencyCode.TRY)
        pos_device = _get_or_create_pos_device(session, bank_account=try_account, stats=stats)
        _seed_pos_settlements(session, pos_device=pos_device, stats=stats)

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.db.seed_demo_data",
        description="FTM local geliştirme ortamına demo müşteri, tedarikçi, çek, banka ve POS verisi yükler.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Demo veri yüklemesini onaylar.",
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Önce bu scriptin oluşturduğu DEMO kayıtlarını siler, sonra yeniden yükler.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    _confirm_or_exit(args)

    print("FTM Demo Seed Veri Yükleme")
    print("--------------------------")
    print(f"Veritabanı: {settings.sqlite_database_path}")
    print(f"Reset demo: {'Evet' if args.reset_demo else 'Hayır'}")

    try:
        stats = seed_demo_data(reset_demo=args.reset_demo)
    except Exception as exc:
        print("")
        print(f"Demo seed işlemi başarısız oldu: {exc}")
        raise SystemExit(1) from exc

    stats.print_summary()
    print("Demo veri yüklemesi tamamlandı.")
    print("Uygulama açıksa kapatıp yeniden açman önerilir.")


if __name__ == "__main__":
    main()
