from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.pos import PosDevice, PosSettlement
from app.utils.decimal_utils import money


def _zero() -> Decimal:
    return Decimal("0.00")


def _as_money(value: object, field_name: str) -> Decimal:
    if value is None:
        return _zero()

    return money(value, field_name=field_name)


def _add_total(
    totals: dict[str, Decimal],
    *,
    currency_code: str,
    amount: object,
    field_name: str,
) -> None:
    if currency_code not in totals:
        totals[currency_code] = _zero()

    totals[currency_code] = money(
        totals[currency_code] + _as_money(amount, field_name),
        field_name=field_name,
    )


def _format_bank_account_label(bank: Bank, bank_account: BankAccount) -> str:
    return f"{bank.name} / {bank_account.account_name}"


def _format_pos_label(pos_device: PosDevice) -> str:
    if pos_device.terminal_no:
        return f"{pos_device.name} ({pos_device.terminal_no})"

    return pos_device.name


def get_pos_reconciliation_report(
    session: Session,
    *,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz.")

    statement = (
        select(PosSettlement, PosDevice, BankAccount, Bank)
        .join(PosDevice, PosSettlement.pos_device_id == PosDevice.id)
        .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
        .join(Bank, BankAccount.bank_id == Bank.id)
        .where(
            PosSettlement.transaction_date >= start_date,
            PosSettlement.transaction_date <= end_date,
        )
        .order_by(
            PosSettlement.transaction_date,
            Bank.name,
            PosDevice.name,
            PosSettlement.id,
        )
    )

    rows = session.execute(statement).all()

    detail_rows: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []

    totals_by_status: dict[str, dict[str, Decimal]] = {}
    totals_by_bank: dict[str, dict[str, Decimal]] = {}

    overall_totals = {
        "gross_total": {},
        "commission_total": {},
        "expected_net_total": {},
        "actual_net_total": {},
        "difference_total": {},
    }

    for pos_settlement, pos_device, bank_account, bank in rows:
        currency_code = pos_settlement.currency_code.value
        status = pos_settlement.status.value
        bank_label = _format_bank_account_label(bank, bank_account)
        pos_label = _format_pos_label(pos_device)

        gross_amount = _as_money(pos_settlement.gross_amount, "Brüt POS tutarı")
        commission_amount = _as_money(pos_settlement.commission_amount, "POS komisyon tutarı")
        expected_net_amount = _as_money(pos_settlement.net_amount, "Beklenen net POS tutarı")
        actual_net_amount = _as_money(pos_settlement.actual_net_amount, "Gerçek yatan POS tutarı")
        difference_amount = _as_money(pos_settlement.difference_amount, "POS yatış farkı")

        row = {
            "id": pos_settlement.id,
            "pos_label": pos_label,
            "bank_label": bank_label,
            "transaction_date": pos_settlement.transaction_date,
            "expected_settlement_date": pos_settlement.expected_settlement_date,
            "realized_settlement_date": pos_settlement.realized_settlement_date,
            "gross_amount": gross_amount,
            "commission_rate": pos_settlement.commission_rate,
            "commission_amount": commission_amount,
            "expected_net_amount": expected_net_amount,
            "actual_net_amount": actual_net_amount,
            "difference_amount": difference_amount,
            "difference_reason": pos_settlement.difference_reason,
            "currency_code": currency_code,
            "status": status,
            "bank_transaction_id": pos_settlement.bank_transaction_id,
            "reference_no": pos_settlement.reference_no,
            "description": pos_settlement.description,
        }

        detail_rows.append(row)

        if status == "MISMATCH":
            mismatch_rows.append(row)

        if status not in totals_by_status:
            totals_by_status[status] = {
                "gross_total": _zero(),
                "commission_total": _zero(),
                "expected_net_total": _zero(),
                "actual_net_total": _zero(),
                "difference_total": _zero(),
            }

        totals_by_status[status]["gross_total"] = money(
            totals_by_status[status]["gross_total"] + gross_amount,
            field_name="Duruma göre brüt toplam",
        )
        totals_by_status[status]["commission_total"] = money(
            totals_by_status[status]["commission_total"] + commission_amount,
            field_name="Duruma göre komisyon toplamı",
        )
        totals_by_status[status]["expected_net_total"] = money(
            totals_by_status[status]["expected_net_total"] + expected_net_amount,
            field_name="Duruma göre beklenen net toplam",
        )
        totals_by_status[status]["actual_net_total"] = money(
            totals_by_status[status]["actual_net_total"] + actual_net_amount,
            field_name="Duruma göre gerçek yatan toplam",
        )
        totals_by_status[status]["difference_total"] = money(
            totals_by_status[status]["difference_total"] + difference_amount,
            field_name="Duruma göre fark toplamı",
        )

        if bank_label not in totals_by_bank:
            totals_by_bank[bank_label] = {
                "gross_total": _zero(),
                "commission_total": _zero(),
                "expected_net_total": _zero(),
                "actual_net_total": _zero(),
                "difference_total": _zero(),
            }

        totals_by_bank[bank_label]["gross_total"] = money(
            totals_by_bank[bank_label]["gross_total"] + gross_amount,
            field_name="Banka bazlı brüt toplam",
        )
        totals_by_bank[bank_label]["commission_total"] = money(
            totals_by_bank[bank_label]["commission_total"] + commission_amount,
            field_name="Banka bazlı komisyon toplamı",
        )
        totals_by_bank[bank_label]["expected_net_total"] = money(
            totals_by_bank[bank_label]["expected_net_total"] + expected_net_amount,
            field_name="Banka bazlı beklenen net toplam",
        )
        totals_by_bank[bank_label]["actual_net_total"] = money(
            totals_by_bank[bank_label]["actual_net_total"] + actual_net_amount,
            field_name="Banka bazlı gerçek yatan toplam",
        )
        totals_by_bank[bank_label]["difference_total"] = money(
            totals_by_bank[bank_label]["difference_total"] + difference_amount,
            field_name="Banka bazlı fark toplamı",
        )

        _add_total(
            overall_totals["gross_total"],
            currency_code=currency_code,
            amount=gross_amount,
            field_name="Genel brüt toplam",
        )
        _add_total(
            overall_totals["commission_total"],
            currency_code=currency_code,
            amount=commission_amount,
            field_name="Genel komisyon toplamı",
        )
        _add_total(
            overall_totals["expected_net_total"],
            currency_code=currency_code,
            amount=expected_net_amount,
            field_name="Genel beklenen net toplam",
        )
        _add_total(
            overall_totals["actual_net_total"],
            currency_code=currency_code,
            amount=actual_net_amount,
            field_name="Genel gerçek yatan toplam",
        )
        _add_total(
            overall_totals["difference_total"],
            currency_code=currency_code,
            amount=difference_amount,
            field_name="Genel fark toplamı",
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "detail_rows": detail_rows,
        "mismatch_rows": mismatch_rows,
        "totals_by_status": totals_by_status,
        "totals_by_bank": totals_by_bank,
        "overall_totals": overall_totals,
    }