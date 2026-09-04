from __future__ import annotations

import csv
import html
import io
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import path

from plugin import InvenTreePlugin
from plugin.mixins import NavigationMixin, UrlsMixin

from order.models import PurchaseOrderLineItem
from order.status_codes import PurchaseOrderStatusGroups

from .logic import (
    NO_DATE,
    NO_PROJECT,
    aggregate_matrix,
    dec,
    month_key,
    month_label,
    outstanding_quantity,
    outstanding_value,
    sorted_months,
)


class PurchaseOrderCashflowPlugin(NavigationMixin, UrlsMixin, InvenTreePlugin):
    """Report outstanding PO commitments by project code, currency and target month."""

    NAME = "PurchaseOrderCashflowPlugin"
    SLUG = "po-cashflow"
    TITLE = "PO Cashflow"
    AUTHOR = "Per Vices Corporation"
    DESCRIPTION = (
        "Monthly cashflow matrix for open Purchase Order lines, grouped by "
        "Project Code and currency."
    )
    VERSION = "0.1.0"
    MIN_VERSION = "1.4.0"
    LICENSE = "MIT"

    NAVIGATION = [
        {
            "name": "PO Cashflow",
            "link": "plugin:po-cashflow:report",
            "icon": "ti ti-cash",
        }
    ]
    NAVIGATION_TAB_NAME = "Cashflow"
    NAVIGATION_TAB_ICON = "ti ti-cash"

    def setup_urls(self):
        return [
            path("", login_required(self.view_report), name="report"),
            path("matrix.csv", login_required(self.export_matrix), name="matrix-csv"),
            path("detail.csv", login_required(self.export_detail), name="detail-csv"),
        ]

    @staticmethod
    def _check_permission(request):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("order.view_purchaseorder")
        )

    @staticmethod
    def _money_amount(value):
        if value is None:
            return None
        amount = getattr(value, "amount", value)
        try:
            return Decimal(str(amount))
        except Exception:
            return None

    @staticmethod
    def _currency(line):
        currency = getattr(line, "purchase_price_currency", None)
        if currency:
            return str(currency)
        try:
            return str(line.order.currency)
        except Exception:
            return ""

    @staticmethod
    def _project_code(line):
        project = getattr(line, "project_code", None) or getattr(line.order, "project_code", None)
        if project:
            return str(getattr(project, "code", project))
        return NO_PROJECT

    @staticmethod
    def _target_date(line):
        return getattr(line, "target_date", None) or getattr(line.order, "target_date", None)

    @staticmethod
    def _part_info(line):
        supplier_part = getattr(line, "part", None)
        base_part = getattr(supplier_part, "part", None) if supplier_part else None
        return {
            "supplier_sku": str(getattr(supplier_part, "SKU", "") or ""),
            "ipn": str(getattr(base_part, "IPN", "") or ""),
            "part_name": str(getattr(base_part, "name", "") or ""),
        }

    def _rows(self):
        qs = (
            PurchaseOrderLineItem.objects
            .filter(
                order__status__in=PurchaseOrderStatusGroups.OPEN,
                quantity__gt=F("received"),
            )
            .select_related(
                "order",
                "order__supplier",
                "order__project_code",
                "project_code",
                "part",
                "part__part",
            )
            .order_by("order__reference", "line_int", "pk")
        )

        rows = []
        for line in qs:
            ordered = dec(line.quantity)
            received = dec(line.received)
            remaining = outstanding_quantity(ordered, received)
            if remaining <= 0:
                continue

            unit_price = self._money_amount(getattr(line, "purchase_price", None))
            discount = dec(getattr(line, "discount", 0))
            value = outstanding_value(ordered, received, unit_price, discount)
            target = self._target_date(line)
            order = line.order
            supplier = getattr(order, "supplier", None)
            part = self._part_info(line)

            rows.append({
                "po_id": order.pk,
                "po_reference": str(order.reference),
                "po_status": str(getattr(order, "status_text", getattr(order, "status", ""))),
                "supplier": str(getattr(supplier, "name", "") or ""),
                "line_id": line.pk,
                "line_number": str(getattr(line, "line", "") or ""),
                "project_code": self._project_code(line),
                "currency": self._currency(line),
                "target_date": target,
                "month_key": month_key(target),
                "ordered_qty": ordered,
                "received_qty": received,
                "outstanding_qty": remaining,
                "unit_price": unit_price,
                "discount": discount,
                "outstanding_value": value,
                "missing_price": unit_price is None,
                **part,
            })

        return rows

    @staticmethod
    def _fmt_qty(value):
        value = dec(value)
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    @staticmethod
    def _fmt_money(value):
        if value is None:
            return "—"
        value = dec(value)
        return f"{value:,.2f}"

    @staticmethod
    def _page_url(po_id):
        return f"/web/purchasing/purchase-order/{po_id}/"

    def view_report(self, request):
        if not self._check_permission(request):
            return HttpResponseForbidden("Purchase Order view permission is required.")

        rows = self._rows()
        matrix = aggregate_matrix(rows)
        months = sorted_months(rows)
        missing_price = sum(1 for row in rows if row["missing_price"])

        # Currency totals for quick sanity check
        currency_totals = {}
        for row in rows:
            if row["outstanding_value"] is None:
                continue
            currency = row["currency"] or "Unknown"
            currency_totals[currency] = currency_totals.get(currency, Decimal("0")) + row["outstanding_value"]

        month_headers = "".join(
            f"<th>{html.escape(month_label(month))}</th>"
            for month in months
        )

        matrix_rows = []
        for (project, currency), values in matrix.items():
            cells = "".join(
                f"<td class='num'>{self._fmt_money(values.get(month, 0)) if month in values else '—'}</td>"
                for month in months
            )
            matrix_rows.append(
                "<tr>"
                f"<td>{html.escape(project)}</td>"
                f"<td>{html.escape(currency or 'Unknown')}</td>"
                f"{cells}"
                "</tr>"
            )

        detail_rows = []
        for row in rows:
            target_text = row["target_date"].isoformat() if row["target_date"] else "No Target Date"
            price_text = self._fmt_money(row["unit_price"])
            value_text = self._fmt_money(row["outstanding_value"])
            price_class = " warning-cell" if row["missing_price"] else ""
            detail_rows.append(
                "<tr>"
                f"<td><a href='{self._page_url(row['po_id'])}'>{html.escape(row['po_reference'])}</a></td>"
                f"<td>{html.escape(row['supplier'])}</td>"
                f"<td>{html.escape(row['project_code'])}</td>"
                f"<td>{html.escape(row['currency'] or 'Unknown')}</td>"
                f"<td>{html.escape(row['line_number'] or str(row['line_id']))}</td>"
                f"<td>{html.escape(row['ipn'])}</td>"
                f"<td>{html.escape(row['part_name'])}</td>"
                f"<td class='num'>{self._fmt_qty(row['ordered_qty'])}</td>"
                f"<td class='num'>{self._fmt_qty(row['received_qty'])}</td>"
                f"<td class='num'>{self._fmt_qty(row['outstanding_qty'])}</td>"
                f"<td class='num{price_class}'>{price_text}</td>"
                f"<td class='num'>{self._fmt_qty(row['discount'])}%</td>"
                f"<td class='num{price_class}'>{value_text}</td>"
                f"<td>{html.escape(target_text)}</td>"
                f"<td>{html.escape(month_label(row['month_key']))}</td>"
                "</tr>"
            )

        totals_html = "".join(
            f"<div class='metric'><span>{html.escape(currency)}</span><strong>{self._fmt_money(value)}</strong></div>"
            for currency, value in sorted(currency_totals.items())
        ) or "<div class='metric'><span>Outstanding</span><strong>0.00</strong></div>"

        warning_html = ""
        if missing_price:
            warning_html = (
                "<div class='warning'>"
                f"<strong>Warning:</strong> {missing_price} outstanding line"
                f"{'s are' if missing_price != 1 else ' is'} missing a unit price. "
                "These lines are shown below but are excluded from matrix totals."
                "</div>"
            )

        body = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>PO Cashflow</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; background: #f7f8fa; color: #222; }}
header {{ background: #fff; border-bottom: 1px solid #ddd; padding: 18px 28px; }}
main {{ padding: 24px 28px 50px; }}
h1 {{ margin: 0 0 6px; font-size: 26px; }}
h2 {{ margin-top: 28px; }}
.subtle {{ color: #666; font-size: 14px; }}
.actions {{ display: flex; gap: 10px; margin: 16px 0 20px; flex-wrap: wrap; }}
.button {{ display: inline-block; padding: 9px 13px; border: 1px solid #bbb; border-radius: 5px;
           text-decoration: none; color: #222; background: #fff; }}
.button:hover {{ background: #f1f1f1; }}
.cards {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0 20px; }}
.metric {{ background: #fff; border: 1px solid #ddd; border-radius: 6px; min-width: 150px; padding: 10px 14px; }}
.metric span {{ display: block; color: #666; font-size: 12px; }}
.metric strong {{ font-size: 20px; }}
.warning {{ background: #fff4d6; border: 1px solid #e6c55a; padding: 12px 14px; border-radius: 5px; margin: 14px 0; }}
.table-wrap {{ overflow-x: auto; background: #fff; border: 1px solid #ddd; border-radius: 6px; }}
table {{ width: 100%; border-collapse: collapse; white-space: nowrap; }}
th {{ text-align: left; background: #f0f2f5; border-bottom: 1px solid #ccc; padding: 9px 10px; font-size: 13px; }}
td {{ border-bottom: 1px solid #eee; padding: 8px 10px; font-size: 13px; }}
tr:last-child td {{ border-bottom: 0; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.warning-cell {{ background: #fff4d6; }}
.note {{ margin: 10px 0 0; color: #666; font-size: 13px; }}
a {{ color: #1c6dd0; }}
</style>
</head>
<body>
<header>
  <h1>PO Cashflow</h1>
  <div class="subtle">Outstanding Purchase Order commitments by Project Code, currency and PO line target month.</div>
</header>
<main>
  <div class="actions">
    <a class="button" href="matrix.csv">Export Matrix CSV</a>
    <a class="button" href="detail.csv">Export Detail CSV</a>
    <a class="button" href="/web/purchasing/">Purchasing</a>
  </div>

  <div class="cards">{totals_html}</div>
  {warning_html}

  <h2>Monthly Matrix</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Project Code</th><th>Currency</th>{month_headers}</tr></thead>
      <tbody>{''.join(matrix_rows) if matrix_rows else '<tr><td colspan="3">No outstanding PO lines found.</td></tr>'}</tbody>
    </table>
  </div>
  <div class="note">
    Outstanding Qty = Ordered Qty − Received Qty. Received quantity is treated as paid for this V1 report.
    Line target date is used first; PO target date is used when the line target date is blank.
  </div>

  <h2>Outstanding PO Line Detail</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>PO</th><th>Supplier</th><th>Project Code</th><th>Currency</th><th>Line</th>
          <th>IPN</th><th>Part</th><th>Ordered</th><th>Received</th><th>Outstanding</th>
          <th>Unit Price</th><th>Discount</th><th>Outstanding Value</th><th>Target Date</th><th>Forecast Month</th>
        </tr>
      </thead>
      <tbody>{''.join(detail_rows) if detail_rows else '<tr><td colspan="15">No outstanding PO lines found.</td></tr>'}</tbody>
    </table>
  </div>
</main>
</body>
</html>"""
        return HttpResponse(body)

    def export_matrix(self, request):
        if not self._check_permission(request):
            return HttpResponseForbidden("Purchase Order view permission is required.")

        rows = self._rows()
        matrix = aggregate_matrix(rows)
        months = sorted_months(rows)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="po-cashflow-matrix.csv"'
        writer = csv.writer(response)
        writer.writerow(["Project Code", "Currency", *[month_label(x) for x in months]])

        for (project, currency), values in matrix.items():
            writer.writerow([
                project,
                currency,
                *[
                    format(values[month], "f") if month in values else ""
                    for month in months
                ],
            ])

        return response

    def export_detail(self, request):
        if not self._check_permission(request):
            return HttpResponseForbidden("Purchase Order view permission is required.")

        rows = self._rows()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="po-cashflow-detail.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "PO",
            "Supplier",
            "PO Status",
            "Project Code",
            "Currency",
            "Line",
            "IPN",
            "Part",
            "Supplier SKU",
            "Ordered Qty",
            "Received Qty",
            "Outstanding Qty",
            "Unit Price",
            "Discount %",
            "Outstanding Value",
            "Target Date",
            "Forecast Month",
            "Missing Price",
        ])

        for row in rows:
            writer.writerow([
                row["po_reference"],
                row["supplier"],
                row["po_status"],
                row["project_code"],
                row["currency"],
                row["line_number"] or row["line_id"],
                row["ipn"],
                row["part_name"],
                row["supplier_sku"],
                format(row["ordered_qty"], "f"),
                format(row["received_qty"], "f"),
                format(row["outstanding_qty"], "f"),
                "" if row["unit_price"] is None else format(row["unit_price"], "f"),
                format(row["discount"], "f"),
                "" if row["outstanding_value"] is None else format(row["outstanding_value"], "f"),
                row["target_date"].isoformat() if row["target_date"] else "",
                month_label(row["month_key"]),
                "YES" if row["missing_price"] else "",
            ])

        return response
