from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.enums import PosSettlementStatus
from app.models.pos import PosDevice, PosSettlement
from app.ui.ui_helpers import decimal_or_zero, tr_money


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]
RECENT_REALIZED_DAYS = 7


@dataclass
class PosDeviceRow:
    pos_device_id: int
    bank_id: int
    bank_account_id: int
    bank_name: str
    bank_account_name: str
    name: str
    terminal_no: str | None
    commission_rate: Any
    settlement_delay_days: int
    currency_code: str
    notes: str | None
    is_active: bool


@dataclass
class PosSettlementRow:
    pos_settlement_id: int
    pos_device_id: int
    pos_device_name: str
    terminal_no: str | None
    bank_name: str
    bank_account_name: str
    transaction_date_text: str
    expected_settlement_date_text: str
    realized_settlement_date_text: str | None
    gross_amount: Any
    commission_rate: Any
    commission_amount: Any
    net_amount: Any
    actual_net_amount: Any | None
    difference_amount: Any
    difference_reason: str | None
    currency_code: str
    status: str
    bank_transaction_id: int | None
    reference_no: str | None
    description: str | None


@dataclass
class PosPageData:
    pos_devices: list[PosDeviceRow]
    pos_settlements: list[PosSettlementRow]
    active_device_count: int
    passive_device_count: int
    planned_settlement_count: int
    realized_settlement_count: int
    cancelled_settlement_count: int
    mismatch_settlement_count: int
    planned_currency_totals: dict[str, Any]
    realized_currency_totals: dict[str, Any]
    visible_realized_days: int
    error_message: str | None = None


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)

    return str(value or "").strip().upper()


def _format_decimal_tr(value: Any) -> str:
    amount = decimal_or_zero(value)

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return tr_money(value)

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def format_rate_percent(value: Any) -> str:
    rate_value = decimal_or_zero(value)

    if rate_value == Decimal("0.00"):
        percent_value = Decimal("0.00")
    elif rate_value > Decimal("1.00"):
        percent_value = rate_value
    else:
        percent_value = rate_value * Decimal("100")

    formatted = f"{percent_value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"%{formatted}"


def status_text(status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "PLANNED":
        return "Planlandı"

    if normalized_status == "REALIZED":
        return "Gerçekleşti"

    if normalized_status == "CANCELLED":
        return "İptal"

    if normalized_status == "MISMATCH":
        return "Fark Var"

    return normalized_status


def currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return (CURRENCY_DISPLAY_ORDER.index(normalized_currency_code), normalized_currency_code)

    return (999, normalized_currency_code)


def build_currency_totals_text(currency_totals: dict[str, Any]) -> str:
    if not currency_totals:
        return "Kayıt yok"

    lines: list[str] = []

    for currency_code in sorted(currency_totals.keys(), key=currency_sort_key):
        lines.append(
            f"{currency_code}: {format_currency_amount(currency_totals[currency_code], currency_code)}"
        )

    return "\n".join(lines)


def load_pos_page_data() -> PosPageData:
    try:
        with session_scope() as session:
            device_statement = (
                select(PosDevice, BankAccount, Bank)
                .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .order_by(Bank.name, PosDevice.name)
            )

            device_rows = session.execute(device_statement).all()

            pos_devices: list[PosDeviceRow] = []
            active_device_count = 0
            passive_device_count = 0

            for pos_device, bank_account, bank in device_rows:
                if pos_device.is_active:
                    active_device_count += 1
                else:
                    passive_device_count += 1

                pos_devices.append(
                    PosDeviceRow(
                        pos_device_id=pos_device.id,
                        bank_id=bank.id,
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        bank_account_name=bank_account.account_name,
                        name=pos_device.name,
                        terminal_no=pos_device.terminal_no,
                        commission_rate=pos_device.commission_rate,
                        settlement_delay_days=pos_device.settlement_delay_days,
                        currency_code=_enum_value(pos_device.currency_code),
                        notes=pos_device.notes,
                        is_active=pos_device.is_active,
                    )
                )

            today = date.today()
            recent_realized_start_date = today - timedelta(days=RECENT_REALIZED_DAYS)

            settlement_statement = (
                select(PosSettlement, PosDevice, BankAccount, Bank)
                .join(PosDevice, PosSettlement.pos_device_id == PosDevice.id)
                .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .where(
                    or_(
                        PosSettlement.status == PosSettlementStatus.PLANNED,
                        PosSettlement.status == PosSettlementStatus.MISMATCH,
                        PosSettlement.realized_settlement_date >= recent_realized_start_date,
                    )
                )
                .order_by(
                    PosSettlement.transaction_date.desc(),
                    PosSettlement.id.desc(),
                )
                .limit(300)
            )

            settlement_rows = session.execute(settlement_statement).all()

            pos_settlements: list[PosSettlementRow] = []

            planned_settlement_count = 0
            realized_settlement_count = 0
            cancelled_settlement_count = 0
            mismatch_settlement_count = 0
            planned_currency_totals: dict[str, Any] = {}
            realized_currency_totals: dict[str, Any] = {}

            for settlement, pos_device, bank_account, bank in settlement_rows:
                status_value = _enum_value(settlement.status)
                currency_code = _enum_value(settlement.currency_code)

                if status_value == PosSettlementStatus.PLANNED.value:
                    planned_settlement_count += 1
                    planned_currency_totals[currency_code] = decimal_or_zero(
                        planned_currency_totals.get(currency_code, "0.00")
                    ) + decimal_or_zero(settlement.net_amount)

                elif status_value == PosSettlementStatus.REALIZED.value:
                    realized_settlement_count += 1
                    realized_currency_totals[currency_code] = decimal_or_zero(
                        realized_currency_totals.get(currency_code, "0.00")
                    ) + decimal_or_zero(
                        settlement.actual_net_amount
                        if settlement.actual_net_amount is not None
                        else settlement.net_amount
                    )

                elif status_value == PosSettlementStatus.CANCELLED.value:
                    cancelled_settlement_count += 1

                elif status_value == PosSettlementStatus.MISMATCH.value:
                    mismatch_settlement_count += 1

                pos_settlements.append(
                    PosSettlementRow(
                        pos_settlement_id=settlement.id,
                        pos_device_id=pos_device.id,
                        pos_device_name=pos_device.name,
                        terminal_no=pos_device.terminal_no,
                        bank_name=bank.name,
                        bank_account_name=bank_account.account_name,
                        transaction_date_text=settlement.transaction_date.strftime("%d.%m.%Y"),
                        expected_settlement_date_text=settlement.expected_settlement_date.strftime("%d.%m.%Y"),
                        realized_settlement_date_text=(
                            settlement.realized_settlement_date.strftime("%d.%m.%Y")
                            if settlement.realized_settlement_date
                            else None
                        ),
                        gross_amount=settlement.gross_amount,
                        commission_rate=settlement.commission_rate,
                        commission_amount=settlement.commission_amount,
                        net_amount=settlement.net_amount,
                        actual_net_amount=settlement.actual_net_amount,
                        difference_amount=settlement.difference_amount,
                        difference_reason=settlement.difference_reason,
                        currency_code=currency_code,
                        status=status_value,
                        bank_transaction_id=settlement.bank_transaction_id,
                        reference_no=settlement.reference_no,
                        description=settlement.description,
                    )
                )

            return PosPageData(
                pos_devices=pos_devices,
                pos_settlements=pos_settlements,
                active_device_count=active_device_count,
                passive_device_count=passive_device_count,
                planned_settlement_count=planned_settlement_count,
                realized_settlement_count=realized_settlement_count,
                cancelled_settlement_count=cancelled_settlement_count,
                mismatch_settlement_count=mismatch_settlement_count,
                planned_currency_totals=planned_currency_totals,
                realized_currency_totals=realized_currency_totals,
                visible_realized_days=RECENT_REALIZED_DAYS,
            )

    except Exception as exc:
        return PosPageData(
            pos_devices=[],
            pos_settlements=[],
            active_device_count=0,
            passive_device_count=0,
            planned_settlement_count=0,
            realized_settlement_count=0,
            cancelled_settlement_count=0,
            mismatch_settlement_count=0,
            planned_currency_totals={},
            realized_currency_totals={},
            visible_realized_days=RECENT_REALIZED_DAYS,
            error_message=str(exc),
        )