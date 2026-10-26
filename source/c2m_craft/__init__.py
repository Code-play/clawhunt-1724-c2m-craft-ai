"""C2M craft co-creation platform - M1 reference implementation.

The package is deliberately standard-library only, offline and deterministic:
every timestamp comes from a logical clock, every generated artifact is a pure
function of the inputs, and nothing here opens a network connection.

Module map (see ARCHITECTURE.md):

    core/       contracts, invariants, logical clock, money, hash-chained ledger
    craft/      facts model, rule engine, rule lint, manufacturability assessment
    creative/   deterministic creative workstation and series expansion
    library/    licensed pattern assets, ingestion gate, search
    commerce/   order state machines, dispatch, quality control, settlement
    web/        stdlib HTTP server and JSON API
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
