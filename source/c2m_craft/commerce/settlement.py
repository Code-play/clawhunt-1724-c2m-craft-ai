"""Revenue-sharing settlement.

Rates are basis points that must sum to 10000, and the payout lines must add up
to the settled total exactly.  The largest-remainder rule decides which parties
receive the leftover cents and the count is recorded, so a finance reviewer can
reproduce the split by hand.
"""

from __future__ import annotations

from ..core import money
from ..core.contracts import SchemaStore


def build(
    store: SchemaStore,
    order: dict,
    policy: dict,
    *,
    settlement_id: str,
    created_at: str,
    net_total_cents: int | None = None,
    refunds: list[dict] | None = None,
    royalty_assets: list[dict] | None = None,
) -> dict:
    total = int(order["amounts"]["total_cents"] if net_total_cents is None else net_total_cents)
    lines = policy["lines"]
    payout_lines = money.shares_by_party(total, lines)
    floor_sum = sum(money.apply_rate(total, int(line["rate_bp"])) for line in lines)
    ip_share = sum(
        int(line["amount_cents"]) for line in payout_lines if line["party"] == "ip_licensor"
    )
    settlement = {
        "settlement_id": settlement_id,
        "order_id": order["order_id"],
        "split_policy": {
            "policy_id": policy["policy_id"],
            "lines": [
                {
                    "party": line["party"],
                    "party_id": line.get("party_id", line["party"]),
                    "rate_bp": int(line["rate_bp"]),
                }
                for line in lines
            ],
        },
        "total_cents": total,
        "currency": "USD",
        "payout_lines": payout_lines,
        "remainder_cents": max(total - floor_sum, 0),
        "status": "draft",
        "created_at": created_at,
        "posted_at": created_at,
        "reversals": [],
        "refunds": list(refunds or []),
        "reconciliation": {
            "sum_payouts_cents": sum(line["amount_cents"] for line in payout_lines),
            "delta_cents": total - sum(line["amount_cents"] for line in payout_lines),
        },
    }
    if royalty_assets:
        settlement["royalty_lines"] = allocate_royalties(
            royalty_assets, ip_share_cents=ip_share, basis_cents=total
        )
    store.assert_valid("settlement", settlement)
    return settlement


def allocate_royalties(assets: list[dict], *, ip_share_cents: int, basis_cents: int) -> list[dict]:
    """Split the IP share across the licensed assets, weighted by their rates."""
    assets = [asset for asset in assets if asset.get("asset_id")]
    if not assets:
        return []
    weights = [max(int(asset.get("rate_bp", 0)), 1) for asset in assets]
    total_weight = sum(weights)
    lines = []
    allocated = 0
    for index, asset in enumerate(assets):
        if index == len(assets) - 1:
            amount = max(int(ip_share_cents) - allocated, 0)
        else:
            amount = int(ip_share_cents) * weights[index] // total_weight
            allocated += amount
        lines.append(
            {
                "asset_id": str(asset["asset_id"]),
                "licensor": str(asset.get("licensor") or "unknown licensor"),
                "rate_bp": int(asset.get("rate_bp", 0)),
                "basis_cents": int(max(basis_cents, amount)),
                "amount_cents": int(amount),
            }
        )
    return lines


def post(settlement: dict) -> dict:
    settlement["status"] = "posted"
    return settlement


def refund_entry(amount_cents: int, kind: str, milestone: str, at: str) -> dict:
    return {
        "amount_cents": int(amount_cents),
        "kind": kind,
        "milestone": milestone,
        "at": at,
    }


def describe(settlement: dict) -> str:
    rows = [f"{settlement['settlement_id']} total {money.fmt_amount(settlement['total_cents'])}"]
    for line in settlement["payout_lines"]:
        share = line["amount_cents"] / max(settlement["total_cents"], 1)
        rows.append(
            f"  {line['party']:<11} {line['rate_bp'] / 100:>5.2f}%  "
            f"{money.fmt_amount(line['amount_cents'])}  ({share:.4f})"
        )
    for line in settlement.get("royalty_lines") or []:
        rows.append(
            f"  royalty {line['asset_id']:<12} {line['rate_bp'] / 100:>5.2f}% "
            f"{money.fmt_amount(line['amount_cents'])} -> {line['licensor']}"
        )
    rows.append(f"  remainder distributed: {settlement['remainder_cents']} cent(s)")
    return "\n".join(rows)
