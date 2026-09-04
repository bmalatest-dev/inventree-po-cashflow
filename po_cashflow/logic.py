from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation


D = Decimal
NO_PROJECT = "No Project Code"
NO_DATE = "No Target Date"


def dec(value, default="0"):
    if value is None or value == "":
        return D(default)
    try:
        return D(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return D(default)


def outstanding_quantity(quantity, received):
    """Return the unreceived portion of a PO line, never below zero."""
    return max(dec(quantity) - dec(received), D("0"))


def outstanding_value(quantity, received, unit_price, discount=0):
    """Return outstanding line value after the InvenTree line discount."""
    remaining = outstanding_quantity(quantity, received)
    if unit_price is None:
        return None
    price = dec(unit_price)
    discount_factor = D("1") - (dec(discount) / D("100"))
    return remaining * price * discount_factor


def month_key(target_date):
    if not target_date:
        return NO_DATE
    if isinstance(target_date, str):
        try:
            target_date = date.fromisoformat(target_date)
        except ValueError:
            return NO_DATE
    return f"{target_date.year:04d}-{target_date.month:02d}"


def month_label(key):
    if key == NO_DATE:
        return NO_DATE
    year, month = [int(x) for x in key.split("-")]
    return date(year, month, 1).strftime("%b %Y")


def aggregate_matrix(rows):
    """Aggregate normalized line rows by project code, currency and month."""
    matrix = defaultdict(lambda: defaultdict(D))
    for row in rows:
        value = row.get("outstanding_value")
        if value is None:
            continue
        project = row.get("project_code") or NO_PROJECT
        currency = row.get("currency") or ""
        month = row.get("month_key") or NO_DATE
        matrix[(project, currency)][month] += dec(value)

    return {
        key: dict(months)
        for key, months in sorted(matrix.items(), key=lambda x: (x[0][0].casefold(), x[0][1]))
    }


def sorted_months(rows):
    months = {row.get("month_key") or NO_DATE for row in rows}
    normal = sorted(x for x in months if x != NO_DATE)
    if NO_DATE in months:
        normal.append(NO_DATE)
    return normal
