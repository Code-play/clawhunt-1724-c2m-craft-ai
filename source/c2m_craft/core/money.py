"""Integer-cent money helpers.

All amounts are integers in cents.  Splitting a total across revenue-sharing
parties uses the largest-remainder method so that the shares always add up to
the total exactly; no cent is created or lost by rounding, and the rounding
decision is reproducible.
"""

from __future__ import annotations

from typing import Sequence

BASIS_POINTS = 10000


def fmt_amount(cents: int, currency: str = "USD") -> str:
    sign = "-" if cents < 0 else ""
    value = abs(int(cents))
    whole, rest = divmod(value, 100)
    return f"{sign}{currency} {whole:,}.{rest:02d}"


def fmt_compact(cents: int) -> str:
    return f"${int(cents) / 100:.2f}"


def apply_rate(amount_cents: int, rate_bp: int) -> int:
    """Floor an amount by a basis-point rate (0..10000)."""
    if not 0 <= rate_bp <= BASIS_POINTS:
        raise ValueError(f"rate_bp out of range: {rate_bp}")
    return int(amount_cents) * int(rate_bp) // BASIS_POINTS


def split_amounts(total_cents: int, rates_bp: Sequence[int]) -> list[int]:
    """Split ``total_cents`` by ``rates_bp`` with largest-remainder rounding."""
    rates = [int(rate) for rate in rates_bp]
    if not rates:
        raise ValueError("at least one rate is required")
    if any(rate < 0 or rate > BASIS_POINTS for rate in rates):
        raise ValueError("each rate must be within 0..10000 basis points")
    if sum(rates) != BASIS_POINTS:
        raise ValueError(f"rates must sum to {BASIS_POINTS}, got {sum(rates)}")
    total = int(total_cents)
    if total < 0:
        raise ValueError("total_cents must be non-negative")

    shares = [total * rate // BASIS_POINTS for rate in rates]
    remainder = total - sum(shares)
    order = sorted(
        range(len(rates)),
        key=lambda index: (-(total * rates[index] % BASIS_POINTS), index),
    )
    for index in order[:remainder]:
        shares[index] += 1
    return shares


def shares_by_party(
    total_cents: int, policy_lines: Sequence[dict]
) -> list[dict]:
    """Apply a settlement policy (``party`` + ``rate_bp``) to a total."""
    rates = [int(line["rate_bp"]) for line in policy_lines]
    amounts = split_amounts(total_cents, rates)
    out = []
    for line, amount in zip(policy_lines, amounts):
        out.append(
            {
                "party": str(line["party"]),
                "party_id": str(line.get("party_id") or _default_party_id(line["party"])),
                "rate_bp": int(line["rate_bp"]),
                "amount_cents": int(amount),
            }
        )
    return out


def _default_party_id(party: str) -> str:
    return {
        "designer": "designer-01",
        "factory": "workshop-01",
        "platform": "platform",
        "ip_licensor": "licensor-01",
    }.get(party, party)
