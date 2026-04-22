from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.services.risk_service import RISK_HORIZONS, get_bank_risk_summary
from app.utils.decimal_utils import money


def _make_account_label(summary: dict[str, Any]) -> str:
    return f"{summary['bank_name']} / {summary['account_name']}"


def get_transfer_recommendations_for_horizon(
    session: Session,
    *,
    as_of_date: date,
    horizon_days: int,
) -> dict[str, Any]:
    risk_summaries = get_bank_risk_summary(
        session,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
    )

    deficits: list[dict[str, Any]] = []
    surpluses: list[dict[str, Any]] = []

    for summary in risk_summaries:
        projected_balance = money(summary["projected_balance"], field_name="Tahmini bakiye")

        if projected_balance < Decimal("0.00"):
            deficits.append(
                {
                    "bank_account_id": summary["bank_account_id"],
                    "account_label": _make_account_label(summary),
                    "currency_code": summary["currency_code"],
                    "needed_amount": money(abs(projected_balance), field_name="Eksik tutar"),
                    "current_balance": summary["current_balance"],
                    "projected_balance": projected_balance,
                }
            )

        elif projected_balance > Decimal("0.00"):
            surpluses.append(
                {
                    "bank_account_id": summary["bank_account_id"],
                    "account_label": _make_account_label(summary),
                    "currency_code": summary["currency_code"],
                    "available_amount": money(projected_balance, field_name="Fazla tutar"),
                    "current_balance": summary["current_balance"],
                    "projected_balance": projected_balance,
                }
            )

    deficits.sort(key=lambda item: item["needed_amount"], reverse=True)
    surpluses.sort(key=lambda item: item["available_amount"], reverse=True)

    recommendations: list[dict[str, Any]] = []
    unresolved_risks: list[dict[str, Any]] = []

    for deficit in deficits:
        remaining_need = money(deficit["needed_amount"], field_name="Kalan ihtiyaç")

        for surplus in surpluses:
            if remaining_need <= Decimal("0.00"):
                break

            if surplus["currency_code"] != deficit["currency_code"]:
                continue

            available_amount = money(surplus["available_amount"], field_name="Kullanılabilir fazla")

            if available_amount <= Decimal("0.00"):
                continue

            transfer_amount = min(remaining_need, available_amount)
            transfer_amount = money(transfer_amount, field_name="Önerilen transfer tutarı")

            recommendations.append(
                {
                    "from_bank_account_id": surplus["bank_account_id"],
                    "from_account_label": surplus["account_label"],
                    "to_bank_account_id": deficit["bank_account_id"],
                    "to_account_label": deficit["account_label"],
                    "currency_code": deficit["currency_code"],
                    "amount": transfer_amount,
                    "horizon_days": horizon_days,
                    "reason": (
                        f"{deficit['account_label']} hesabında {horizon_days} gün içinde "
                        f"{deficit['needed_amount']} {deficit['currency_code']} açık görünüyor."
                    ),
                }
            )

            surplus["available_amount"] = money(
                available_amount - transfer_amount,
                field_name="Kalan fazla",
            )

            remaining_need = money(
                remaining_need - transfer_amount,
                field_name="Kalan ihtiyaç",
            )

        if remaining_need > Decimal("0.00"):
            unresolved_risks.append(
                {
                    "bank_account_id": deficit["bank_account_id"],
                    "account_label": deficit["account_label"],
                    "currency_code": deficit["currency_code"],
                    "remaining_need": remaining_need,
                    "horizon_days": horizon_days,
                }
            )

    unused_surpluses = [
        {
            "bank_account_id": surplus["bank_account_id"],
            "account_label": surplus["account_label"],
            "currency_code": surplus["currency_code"],
            "available_amount": money(surplus["available_amount"], field_name="Kalan fazla"),
            "horizon_days": horizon_days,
        }
        for surplus in surpluses
        if money(surplus["available_amount"], field_name="Kalan fazla") > Decimal("0.00")
    ]

    return {
        "as_of_date": as_of_date,
        "horizon_days": horizon_days,
        "recommendations": recommendations,
        "unresolved_risks": unresolved_risks,
        "unused_surpluses": unused_surpluses,
    }


def get_all_transfer_recommendations(
    session: Session,
    *,
    as_of_date: date,
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}

    for horizon_days in RISK_HORIZONS:
        result[horizon_days] = get_transfer_recommendations_for_horizon(
            session,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
        )

    return result