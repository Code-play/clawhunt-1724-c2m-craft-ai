"""Environment and invariant self-test, runnable without any fixture state.

Checks the guarantees the delivery claims: standard library only, no wall clock,
no network client, contracts load, rule files lint clean, fixtures validate, the
workstation is deterministic, the ledger verifies and the static prototype is
present.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_NET = {"socket", "requests", "httpx", "aiohttp", "ftplib", "smtplib", "telnetlib"}
FORBIDDEN_CLOCK_ATTRS = {"now", "utcnow", "today"}


def _module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def run(service) -> dict:
    root = service.root
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    add(
        "python version",
        sys.version_info >= (3, 11),
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    package_files = sorted((root / "c2m_craft").rglob("*.py"))
    stdlib = set(sys.stdlib_module_names)
    offenders: list[str] = []
    for path in package_files:
        for name in _module_names(path):
            top = name.split(".")[0]
            if top in ("c2m_craft", ""):
                continue
            if top not in stdlib:
                offenders.append(f"{path.relative_to(root)}: {name}")
    add("standard library only", not offenders, "; ".join(offenders[:5]))

    wall_clock: list[str] = []
    for path in package_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CLOCK_ATTRS:
                    owner = getattr(func.value, "id", "")
                    if owner in ("datetime", "date"):
                        wall_clock.append(f"{path.name}:{node.lineno}")
                if isinstance(func, ast.Attribute) and func.attr == "time":
                    owner = getattr(func.value, "id", "")
                    if owner == "time":
                        wall_clock.append(f"{path.name}:{node.lineno}")
    add("no wall clock", not wall_clock, ", ".join(sorted(set(wall_clock))[:5]))

    network: list[str] = []
    for path in package_files:
        for name in _module_names(path):
            top = name.split(".")[0]
            if top in FORBIDDEN_NET:
                network.append(f"{path.name}: {name}")
            if name.startswith("http.client") or name.startswith("urllib.request"):
                network.append(f"{path.name}: {name}")
    add("no network client", not network, "; ".join(network[:5]))

    registry_problems = []
    for entry in service.store.registry["contracts"]:
        if entry["urn"] not in service.store.schemas:
            registry_problems.append(f"{entry['id']} is not loaded")
        for dep in entry.get("deps", []):
            if dep not in service.store.contract_ids:
                registry_problems.append(f"{entry['id']} depends on unknown {dep}")
    add("contract registry", not registry_problems, "; ".join(registry_problems[:5]))

    from .craft import lint as lint_mod

    lint_result = lint_mod.lint_all(service.store, service.settings)
    add("rule lint", lint_result["ok"], f"{lint_result['totals']}")

    bad_fixtures = []
    for concept in service.concepts.values():
        issues = service.store.validate("design_concept", concept)
        if issues:
            bad_fixtures.append(f"{concept['concept_id']}: {issues[0].message}")
    for asset in service.library.assets:
        issues = service.store.validate(
            "pattern_asset",
            asset,
            ctx={"as_of": service.settings.as_of, "require_active_window": False},
        )
        if issues:
            bad_fixtures.append(f"{asset['asset_id']}: {issues[0].message}")
    add("fixtures validate", not bad_fixtures, "; ".join(bad_fixtures[:5]))

    first = service.generate("self test brief", "jewelry", count=2, style_id="coastal_minimal")
    second = service.generate("self test brief", "jewelry", count=2, style_id="coastal_minimal")
    strip = lambda rows: [  # noqa: E731
        {key: value for key, value in row.items() if key != "concept_id"} for row in rows
    ]
    add("workstation determinism", strip(first) == strip(second), "two identical briefs agree")

    ledger = service.ledger.verify()
    add("ledger chain", ledger["ok"], f"{ledger['events']} events, head {ledger['head'][:12]}")

    static_dir = root / "static"
    missing = [name for name in ("index.html", "app.js", "app.css") if not (static_dir / name).is_file()]
    add("static prototype", not missing, ", ".join(missing) or "index.html, app.js, app.css")

    from .core.contracts import format_issues
    from .enterprise.growth import GrowthStack
    from .enterprise.registry import ComponentRegistry
    from .enterprise.runtime import Profiles

    layer_problems: list[str] = []
    registry = ComponentRegistry(service.store, service.settings)
    if len(registry.components) < 10:
        layer_problems.append(f"{len(registry.components)} components")
    profiles = Profiles(service.store, service.settings)
    if len(profiles.ids()) < 2:
        layer_problems.append("fewer than two enterprise profiles")
    add("enterprise service layer", not layer_problems, "; ".join(layer_problems[:3]))

    growth = GrowthStack(service.store, service.settings)
    site = growth.build("SITE-JW-01", at=service.settings.as_of)
    site_issues = service.store.validate("growth_site", site)
    add("growth site contract", not site_issues, format_issues(site_issues)[:120])

    ip_problems: list[str] = []
    for contract_id, payload in (
        ("character_bible", service.ip.bible),
        ("short_drama", service.ip.drama),
        ("ip_license", service.ip.license),
    ):
        issues = service.store.validate(contract_id, payload)
        if issues:
            ip_problems.append(f"{contract_id}: {issues[0].message}")
    add("cultural IP pipeline", not ip_problems, "; ".join(ip_problems[:3]))

    return {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "counts": {"checks": len(checks), "failed": sum(1 for item in checks if not item["ok"])},
    }
