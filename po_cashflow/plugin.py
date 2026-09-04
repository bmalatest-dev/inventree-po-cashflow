from __future__ import annotations

import csv
import html
import io
from decimal import Decimal

from django.db.models import F

from rest_framework import serializers

from plugin import InvenTreePlugin
from plugin.mixins import DataExportMixin

from order.models import PurchaseOrder, PurchaseOrderLineItem
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



class PurchaseOrderCashflowExportOptionsSerializer(serializers.Serializer):
    """Export options shown in the Purchase Order download dialog."""

    export_report_type = serializers.ChoiceField(
        choices=[
            ("matrix", "Monthly Matrix"),
            ("detail", "Outstanding PO Line Detail"),
        ],
        default="matrix",
        label="Cashflow Report",
        help_text=(
            "Monthly Matrix groups outstanding PO line value by Project Code, "
            "currency and target month. Detail exports the underlying open PO lines."
        ),
    )


class PurchaseOrderCashflowPlugin(DataExportMixin, InvenTreePlugin):
    """Report outstanding PO commitments by project code, currency and target month."""

    NAME = "PurchaseOrderCashflowPlugin"
    SLUG = "po-cashflow"
    TITLE = "PO Cashflow"
    AUTHOR = "Per Vices Corporation"
    DESCRIPTION = (
        "Monthly cashflow matrix for open Purchase Order lines, grouped by "
        "Project Code and currency."
    )
    VERSION = "0.1.5"
    MIN_VERSION = "1.4.0"
    LICENSE = "MIT"

    ExportOptionsSerializer = PurchaseOrderCashflowExportOptionsSerializer

    def supports_export(
        self,
        model_class: type,
        user=None,
        serializer_class=None,
        view_class=None,
        *args,
        **kwargs,
    ) -> bool:
        """Only expose this exporter for the main Purchase Order dataset."""
        return model_class == PurchaseOrder

    def generate_filename(self, model_class, export_format: str) -> str:
        return f"PO_Cashflow.{export_format}"


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

    def _rows(self, purchase_orders=None):
        # The supplied PurchaseOrder queryset already contains any filters/search
        # applied on the main PO table. Always narrow it to open PO states for cashflow.
        if purchase_orders is None:
            purchase_orders = PurchaseOrder.objects.all()

        purchase_orders = purchase_orders.filter(
            status__in=PurchaseOrderStatusGroups.OPEN
        )

        qs = (
            PurchaseOrderLineItem.objects
            .filter(
                order__in=purchase_orders,
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
            missing_target_date = target is None
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
                "missing_target_date": missing_target_date,
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


    @staticmethod
    def _matrix_months_for_headers(context):
        """Return matrix month keys prepared by export_data().

        InvenTree calls export_data() before update_headers(). The same export
        context dictionary is then passed to update_headers(), so it is the safe
        place to carry the dynamic month schema for this specific export.
        """
        return list(context.get("_po_cashflow_months") or [])

    def update_headers(self, headers, context, **kwargs):
        """Define headers for the selected cashflow report."""
        report_type = context.get("export_report_type", "matrix")

        headers.clear()

        if report_type == "detail":
            detail_headers = [
                ("po_reference", "PO"),
                ("supplier", "Supplier"),
                ("project_code", "Project Code"),
                ("currency", "Currency"),
                ("line_number", "Line"),
                ("ipn", "IPN"),
                ("part_name", "Part"),
                ("ordered_qty", "Ordered Qty"),
                ("received_qty", "Received Qty"),
                ("outstanding_qty", "Outstanding Qty"),
                ("unit_price", "Unit Price"),
                ("discount", "Discount %"),
                ("outstanding_value", "Outstanding Value"),
                ("target_date", "Target Date"),
                ("forecast_month", "Forecast Month"),
                ("missing_target_date", "Missing Target Date"),
                ("missing_price", "Missing Price"),
            ]
            for key, label in detail_headers:
                headers[key] = label
            return headers

        headers["project_code"] = "Project Code"
        headers["currency"] = "Currency"

        # InvenTree fixes the export schema before export_data() is called.
        # Discover month columns now so they are present in the generated CSV/XLSX.
        for month in self._matrix_months_for_headers(context):
            headers[month] = month_label(month)

        return headers

    def export_data(
        self,
        queryset,
        serializer_class,
        headers,
        context,
        output,
        serializer_context=None,
        **kwargs,
    ):
        """Generate either the monthly matrix or the auditable line detail."""
        report_type = context.get("export_report_type", "matrix")
        rows = self._rows(queryset)

        # This export is computed from PO lines, so progress can be completed in one pass.
        try:
            output.refresh_from_db()
            output.progress = queryset.count()
            output.save()
        except Exception:
            pass

        if report_type == "detail":
            detail = []
            for row in rows:
                detail.append({
                    "po_reference": row["po_reference"],
                    "supplier": row["supplier"],
                    "project_code": row["project_code"],
                    "currency": row["currency"],
                    "line_number": row["line_number"] or str(row["line_id"]),
                    "ipn": row["ipn"],
                    "part_name": row["part_name"],
                    "ordered_qty": self._fmt_qty(row["ordered_qty"]),
                    "received_qty": self._fmt_qty(row["received_qty"]),
                    "outstanding_qty": self._fmt_qty(row["outstanding_qty"]),
                    "unit_price": (
                        "" if row["unit_price"] is None
                        else f"{row['unit_price']:.2f}"
                    ),
                    "discount": f"{row['discount']:.2f}",
                    "outstanding_value": (
                        "" if row["outstanding_value"] is None
                        else f"{row['outstanding_value']:.2f}"
                    ),
                    "target_date": (
                        row["target_date"].isoformat() if row["target_date"] else ""
                    ),
                    "forecast_month": month_label(row["month_key"]),
                    "missing_target_date": "YES" if row["missing_target_date"] else "",
                    "missing_price": "YES" if row["missing_price"] else "",
                })
            return detail

        matrix = aggregate_matrix(rows)
        months = sorted_months(rows)

        # InvenTree invokes export_data() before update_headers(). Populate the
        # dynamic month values now, and carry the exact filtered month list forward
        # in the per-export context so update_headers() can declare matching columns.
        context["_po_cashflow_months"] = months

        result = []
        for (project, currency), values in matrix.items():
            row = {
                "project_code": project,
                "currency": currency,
            }
            for month in months:
                row[month] = (
                    f"{values[month]:.2f}"
                    if month in values
                    else ""
                )
            result.append(row)

        return result
