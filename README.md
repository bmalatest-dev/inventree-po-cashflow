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
