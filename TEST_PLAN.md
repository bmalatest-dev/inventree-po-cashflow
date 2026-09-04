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
