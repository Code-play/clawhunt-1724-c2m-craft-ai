# Manufacturability matrix

Ten concept inputs against two workshops each. The auto verdict comes from the deterministic engine; the final verdict folds in the craftsperson's decision where a review was requested.

Agreement with the hand-written expectation table: 20/20

| Concept | Workshop | Auto | Final | Blockers | Fixes |
|---|---|---|---|---|---|
| DC-0001 | WS-JW-A | manufacturable | manufacturable | - | 0 |
| DC-0001 | WS-JW-B | manufacturable | manufacturable | - | 0 |
| DC-0002 | WS-JW-A | not_manufacturable | not_manufacturable | CAP-JW-A-01, JW-CAST-001, JW-SET-001 | 3 |
| DC-0002 | WS-JW-B | not_manufacturable | not_manufacturable | CAP-JW-B-01, CAP-JW-B-02, JW-CAST-001, JW-SET-001 | 4 |
| DC-0003 | WS-JW-A | conditionally_manufacturable | conditionally_manufacturable | - | 2 |
| DC-0003 | WS-JW-B | not_manufacturable | conditionally_manufacturable | CAP-JW-B-01, CAP-JW-B-02 | 4 |
| DC-0004 | WS-JW-A | conditionally_manufacturable | conditionally_manufacturable | - | 2 |
| DC-0004 | WS-JW-B | not_manufacturable | not_manufacturable | CAP-JW-B-02, CAP-JW-B-06 | 4 |
| DC-0005 | WS-HW-A | manufacturable | manufacturable | - | 0 |
| DC-0005 | WS-HW-B | manufacturable | manufacturable | - | 0 |
| DC-0006 | WS-HW-A | not_manufacturable | not_manufacturable | CAP-HW-A-02, HW-FORM-001, HW-JOIN-003 | 4 |
| DC-0006 | WS-HW-B | not_manufacturable | not_manufacturable | CAP-HW-B-02, HW-FORM-001, HW-JOIN-003 | 4 |
| DC-0007 | WS-HW-A | conditionally_manufacturable | conditionally_manufacturable | - | 2 |
| DC-0007 | WS-HW-B | not_manufacturable | not_manufacturable | CAP-HW-B-01 | 3 |
| DC-0008 | WS-HW-A | not_manufacturable | not_manufacturable | HW-JOIN-002, HW-SURF-002 | 5 |
| DC-0008 | WS-HW-B | not_manufacturable | not_manufacturable | CAP-HW-B-03, HW-JOIN-002, HW-SURF-002 | 6 |
| DC-0009 | WS-HW-A | manufacturable | manufacturable | - | 0 |
| DC-0009 | WS-HW-B | manufacturable | manufacturable | - | 0 |
| DC-0010 | WS-JW-A | conditionally_manufacturable | conditionally_manufacturable | - | 1 |
| DC-0010 | WS-JW-B | not_manufacturable | not_manufacturable | CAP-JW-B-01 | 2 |

## Counterexamples

- DC-0002 at WS-JW-A: not_manufacturable, blockers CAP-JW-A-01, JW-CAST-001, JW-SET-001, 3 fix suggestion(s)
- DC-0002 at WS-JW-B: not_manufacturable, blockers CAP-JW-B-01, CAP-JW-B-02, JW-CAST-001, JW-SET-001, 4 fix suggestion(s)
- DC-0006 at WS-HW-A: not_manufacturable, blockers CAP-HW-A-02, HW-FORM-001, HW-JOIN-003, 4 fix suggestion(s)
- DC-0006 at WS-HW-B: not_manufacturable, blockers CAP-HW-B-02, HW-FORM-001, HW-JOIN-003, 4 fix suggestion(s)
- DC-0008 at WS-HW-A: not_manufacturable, blockers HW-JOIN-002, HW-SURF-002, 5 fix suggestion(s)
- DC-0008 at WS-HW-B: not_manufacturable, blockers CAP-HW-B-03, HW-JOIN-002, HW-SURF-002, 6 fix suggestion(s)

## Artisan review decisions

- AR-0001 (DC-0002 at WS-JW-A): confirmed by ART-JW-01 -> not_manufacturable
- AR-0004 (DC-0003 at WS-JW-B): overridden by ART-JW-01 -> conditionally_manufacturable
