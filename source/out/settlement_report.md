# Settlement and coordination report

## Order cases

| Case | Order | Final status | Events | Amount (cents) |
|---|---|---|---|---|
| designer pre-sale settled | ORD-0001 | settled | 9 | 30000 |
| full refund after payment | ORD-0002 | refunded | 6 | 65000 |
| dispute resolved by split settlement | ORD-0003 | settled | 7 | 9375 |
| order refused for a non-manufacturable concept | None | blocked | 0 | 0 |
| participatory customisation settled | ORD-0005 | settled | 9 | 35100 |
| licensed asset order with royalty split | ORD-0006 | settled | 9 | 22500 |
| limited edition settled and archived | ORD-0007 | settled | 9 | 110000 |
| quality inspection failed and returned for rework | ORD-0008 | in_production | 8 | 0 |

## Payout lines

### ST-0001 (order ORD-0001, total 30000 cents)

| Party | Party id | Rate (bp) | Amount (cents) |
|---|---|---|---|
| designer | designer-01 | 1500 | 4500 |
| factory | workshop-01 | 6000 | 18000 |
| ip_licensor | licensor-01 | 1000 | 3000 |
| platform | platform | 1500 | 4500 |

Remainder distributed by largest-remainder rounding: 0 cent(s). Reconciliation: payouts 30000 cents, delta 0.

### ST-0002 (order ORD-0003, total 9375 cents)

| Party | Party id | Rate (bp) | Amount (cents) |
|---|---|---|---|
| designer | designer-01 | 1500 | 1406 |
| factory | workshop-01 | 6000 | 5625 |
| ip_licensor | licensor-01 | 1000 | 938 |
| platform | platform | 1500 | 1406 |

Remainder distributed by largest-remainder rounding: 1 cent(s). Reconciliation: payouts 9375 cents, delta 0.

- Refund recorded before posting: 9375 cents (partial, milestone pre-settlement)

### ST-0003 (order ORD-0005, total 35100 cents)

| Party | Party id | Rate (bp) | Amount (cents) |
|---|---|---|---|
| designer | designer-01 | 1500 | 5265 |
| factory | workshop-01 | 6000 | 21060 |
| ip_licensor | licensor-01 | 1000 | 3510 |
| platform | platform | 1500 | 5265 |

Remainder distributed by largest-remainder rounding: 0 cent(s). Reconciliation: payouts 35100 cents, delta 0.

### ST-0004 (order ORD-0006, total 22500 cents)

| Party | Party id | Rate (bp) | Amount (cents) |
|---|---|---|---|
| designer | designer-01 | 1500 | 3375 |
| factory | workshop-01 | 6000 | 13500 |
| ip_licensor | licensor-01 | 1000 | 2250 |
| platform | platform | 1500 | 3375 |

Remainder distributed by largest-remainder rounding: 0 cent(s). Reconciliation: payouts 22500 cents, delta 0.

Royalty allocation inside the IP share:

| Asset | Licensor | Rate (bp) | Amount (cents) |
|---|---|---|---|
| PA-JW-0001 | Regional Crafts Archive (synthetic) | 300 | 2250 |

### ST-0005 (order ORD-0007, total 110000 cents)

| Party | Party id | Rate (bp) | Amount (cents) |
|---|---|---|---|
| designer | designer-01 | 1500 | 16500 |
| factory | workshop-01 | 6000 | 66000 |
| ip_licensor | licensor-01 | 1000 | 11000 |
| platform | platform | 1500 | 16500 |

Remainder distributed by largest-remainder rounding: 0 cent(s). Reconciliation: payouts 110000 cents, delta 0.

## Delivery promises

| Order | Workshop | Promised | Working minutes | Alternatives |
|---|---|---|---|---|
| ORD-0001 | WS-JW-A | 2026-11-02T18:00:00Z | 184 | 1 |
| ORD-0002 | WS-HW-A | 2026-11-02T18:00:00Z | 446 | 1 |
| ORD-0003 | WS-JW-A | 2026-11-02T18:00:00Z | 286 | 0 |
| ORD-0005 | WS-JW-A | 2026-11-03T18:00:00Z | 189 | 0 |
| ORD-0006 | WS-JW-A | 2026-11-02T18:00:00Z | 219 | 0 |
| ORD-0007 | WS-HW-A | 2026-11-02T18:00:00Z | 383 | 0 |
| ORD-0008 | WS-JW-A | 2026-11-02T18:00:00Z | 286 | 0 |

## Ledger

- Events: 57, orders: 7, verified: True
- Head: 3f252e590681ffe2d9c16d641e98d7059b36e15e7f586f89e7afbc0e3818c853
