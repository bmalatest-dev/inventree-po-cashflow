# PO Cashflow v0.1.0 Test Plan

## 1. Install / load

- Install plugin.
- Restart InvenTree so the new plugin is discovered.
- Enable plugin.
- Confirm version 0.1.0.
- Confirm a `Cashflow > PO Cashflow` navigation entry appears.

## 2. Completely open line

Create / identify an OPEN PO line:
- ordered 100
- received 0
- unit price 20 USD
- Project Code TATE
- line target date 2026-11-15

Expected:
- Outstanding Qty = 100
- Outstanding Value = 2,000 USD
- Matrix: TATE / USD / Nov 2026 = 2,000

## 3. Partially received line

Receive 75 of the 100 units.

Expected:
- Outstanding Qty = 25
- Outstanding Value = 500 USD
- Matrix contribution changes from 2,000 to 500

## 4. Fully received line

Receive the remaining 25.

Expected:
- Line disappears from the outstanding detail.
- Matrix contribution becomes zero.
- PO may remain open because of other lines; this line must still contribute zero.

## 5. Mixed line target dates

Use two open lines on the same PO with different target dates.

Expected:
- Each line lands in its own target month.
- PO header target date does not override a populated line target date.

## 6. Blank line target date

Leave a line target date blank but set the PO target date.

Expected:
- The PO target date is used as fallback.

Leave both blank.

Expected:
- The line appears in `No Target Date`.

## 7. Project Code

- Set a PO Project Code.
- Leave line Project Code blank.
Expected: line uses PO Project Code.

- Set a different line Project Code.
Expected: line-level Project Code overrides the PO code.

## 8. Currency

Test two lines in different currencies.

Expected:
- They appear as separate matrix rows.
- No FX conversion is performed.

## 9. Discount

Create a line:
- outstanding qty 6
- unit price 100
- discount 10%

Expected:
- outstanding value = 540.

## 10. Missing price

Create / identify an open line with no purchase price.

Expected:
- Detail line remains visible.
- Missing-price warning appears.
- Matrix does not treat the missing price as zero-value known spend.

## 11. CSV exports

Export Matrix CSV and Detail CSV.

Expected:
- Matrix CSV matches the on-screen monthly matrix.
- Detail CSV contains every included outstanding PO line and the values used for aggregation.

## 12. v0.1.1 navigation

- Enable navigation integration in InvenTree.
- Install / enable v0.1.1.
- Restart InvenTree if required for plugin navigation registration.
- Confirm `Downloads` appears in the main navigation.
- Confirm `Downloads > PO Cashflow` opens the report.
- Confirm both CSV export buttons still work.

## 13. v0.1.2 native PO download integration

1. Go to Purchasing > Purchase Orders.
2. Click the Download icon in the top-right of the Purchase Orders table.
3. Confirm `PO Cashflow` appears as an Export Plugin option.
4. Select `PO Cashflow`.
5. Confirm `Cashflow Report` provides:
   - Monthly Matrix
   - Outstanding PO Line Detail
6. Export Monthly Matrix as CSV.
7. Export Outstanding PO Line Detail as CSV.
8. Confirm table filters/search are respected.
9. Confirm fully received lines are excluded.
10. Confirm only open PO statuses contribute.

## 14. v0.1.3 matrix regression

Using the current PO-0006 / PO-0007 test dataset:

Expected detail lines:
- PO-0006 Crimson USD Sep 2026 = 2,500.00
- PO-0006 Cyan USD Oct 2026 = 750.00
- PO-0006 No Project Code USD Sep 2026 = 2,500.00
- PO-0007 Other CAD Dec 2026 = 350.00
- PO-0007 Other CAD Jan 2027 = missing price / excluded from matrix
- PO-0007 Crimson CAD Sep 2026 = 500.00

Expected matrix columns:
- Sep 2026
- Oct 2026
- Dec 2026
- Jan 2027

Expected matrix:
- Crimson / CAD: Sep 2026 = 500.00
- Crimson / USD: Sep 2026 = 2,500.00
- Cyan / USD: Oct 2026 = 750.00
- No Project Code / USD: Sep 2026 = 2,500.00
- Other / CAD: Dec 2026 = 350.00
- Other / CAD: Jan 2027 blank because that outstanding line has no price
