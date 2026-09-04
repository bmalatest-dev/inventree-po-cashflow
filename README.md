## v0.1.3

- Fixes Monthly Matrix exports which previously omitted all month columns.
- Discovers the required target-month columns before InvenTree finalizes the export schema.
- Keeps Project Code and currency rows unchanged.
- Formats exported monetary values to two decimal places.
- Cashflow calculation logic is unchanged.

## v0.1.2

- Registers PO Cashflow using InvenTree's `DataExportMixin`.
- `PO Cashflow` is selectable from the Download button on the main Purchase Orders table.
- Export options:
  - Monthly Matrix
  - Outstanding PO Line Detail
- The export respects the Purchase Order table queryset / filters, then limits cashflow to open POs.
- Removes the standalone navigation / URL report entry.
- Cashflow calculation assumptions are unchanged.

## v0.1.1

- Moves the PO Cashflow report entry into the `Downloads` navigation group.
- Cashflow calculation logic is unchanged from v0.1.0.
- The report page still provides the monthly matrix, detailed outstanding PO lines,
  Matrix CSV export and Detail CSV export.

# InvenTree PO Cashflow

Initial Per Vices cashflow reporting plugin for InvenTree.

## v0.1.0

The report uses the following working assumptions:

- Open Purchase Orders are InvenTree Purchase Orders in an OPEN state.
- Received quantity is treated as paid.
- Unreceived quantity is treated as financially outstanding.
- Outstanding value is calculated from each individual PO line, not the PO header total.
- The line-item target date is used for cashflow timing; if blank, the PO target date is used.
- Project Code is taken from the line item when present, otherwise from the Purchase Order.
- Currencies are kept separate and are not converted.
- Fully received lines are excluded.
- Missing target dates are grouped under `No Target Date`.
- Missing-price lines remain visible in the detail table but are excluded from matrix totals and called out as warnings.

### Outstanding value

`Outstanding Qty = Ordered Qty - Received Qty`

`Outstanding Value = Outstanding Qty × Unit Price × (1 - Discount %)`

Regular Purchase Order lines are included in v0.1.0. Extra PO line items are not included because
they do not have the same receipt / outstanding-quantity semantics.
