"""Requirement decomposition: machine-checked matrix plus rendered reports.

The brief is decomposed into stable ids (A/B/C/D/E/F/G/H/I/J).  Every id carries
a milestone, a status, the contracts and artifacts that implement it, the
verification group that proves it, and the acceptance criteria it serves.  The
check command fails the build when an id loses its artifact or the mapping stops
being closed; the render command produces the bilingual matrix a reviewer reads.
"""

from __future__ import annotations

import json
from pathlib import Path

from .core.contracts import SchemaStore

STATUSES = ("covered", "partial", "planned", "excluded")
MILESTONES = ("M1", "M2", "M3", "M4")
MODULES = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")

STATUS_LABEL = {
    "covered": {"en": "covered", "zh": "已覆盖"},
    "partial": {"en": "partial", "zh": "部分"},
    "planned": {"en": "planned", "zh": "计划"},
    "excluded": {"en": "excluded", "zh": "排除"},
}


def load(root: Path | str) -> dict:
    root = Path(root)
    with open(root / "docs" / "requirements.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def item_index(data: dict) -> dict[str, dict]:
    return {str(item["id"]): item for item in data["items"]}


def check(
    root: Path | str,
    store: SchemaStore | None = None,
    later_artifacts: frozenset[str] = frozenset(),
) -> dict:
    """Audit the requirement matrix against the tree.

    ``later_artifacts`` lists artifacts that the current process writes *after*
    the audit runs (the demo writes the reel and the hash manifest last, and the
    manifest hashes this report, so the audit cannot wait for them).  They are
    skipped by the existence check and by nothing else: the demo then proves
    them by listing them in the manifest, and ``verify`` re-checks the tree once
    every artifact exists.
    """
    root = Path(root)
    data = load(root)
    store = store or SchemaStore(root)
    groups = data.get("verify_groups", {})
    acceptance = {str(row["id"]): row for row in data.get("acceptance", [])}
    items = data.get("items", [])
    index = item_index(data)
    problems: list[str] = []

    seen: set[str] = set()
    for item in items:
        item_id = str(item["id"])
        if item_id in seen:
            problems.append(f"{item_id}: duplicate id")
        seen.add(item_id)
        if item_id.split(".")[0][0] != str(item["module"]):
            problems.append(f"{item_id}: module {item['module']} does not match the id prefix")
        if item["module"] not in MODULES:
            problems.append(f"{item_id}: unknown module {item['module']}")
        if item["milestone"] not in MILESTONES:
            problems.append(f"{item_id}: unknown milestone {item['milestone']}")
        if item["status"] not in STATUSES:
            problems.append(f"{item_id}: unknown status {item['status']}")
        if item.get("parent") and not item_id.startswith(str(item["parent"])):
            problems.append(f"{item_id}: parent {item['parent']} is not a prefix of the id")
        if item.get("verify_group") not in groups:
            problems.append(f"{item_id}: verify group {item.get('verify_group')} is not declared")
        for contract_id in item.get("contract_refs", []) or []:
            if contract_id not in store.contract_ids:
                problems.append(f"{item_id}: unknown contract {contract_id}")
        for ac_id in item.get("ac_refs", []) or []:
            if ac_id not in acceptance:
                problems.append(f"{item_id}: unknown acceptance criterion {ac_id}")
        if item["status"] in ("covered", "partial"):
            for relative in item.get("artifact_refs", []) or []:
                if relative in later_artifacts:
                    continue
                if not (root / relative).exists():
                    problems.append(f"{item_id}: artifact missing: {relative}")
            if item["status"] == "covered" and not item.get("artifact_refs"):
                problems.append(f"{item_id}: covered but lists no artifact")

    for ac_id, row in acceptance.items():
        declared = str(row.get("coverage", "planned"))
        claimed = [value for value in row.get("m1_items", []) or []]
        if declared in ("covered", "partial") and not claimed:
            problems.append(f"{ac_id}: declares {declared} coverage but claims no M1 item")
        for item_id in claimed:
            if item_id not in index:
                problems.append(f"{ac_id}: m1_items references unknown {item_id}")

    status_counts = {status: 0 for status in STATUSES}
    milestone_counts = {milestone: {"covered": 0, "partial": 0, "planned": 0, "excluded": 0} for milestone in MILESTONES}
    for item in items:
        status_counts[item["status"]] += 1
        milestone_counts[item["milestone"]][item["status"]] += 1

    ac_coverage = {}
    for ac_id, row in acceptance.items():
        declared = str(row.get("coverage", "planned"))
        computed = _ac_status(row, index)
        ac_coverage[ac_id] = {"declared": declared, "computed": computed, "evidence": row.get("evidence")}

    m1_items = [item for item in items if item["milestone"] == "M1" and item["status"] != "excluded"]
    m1_ok = [item for item in m1_items if item["status"] in ("covered", "partial")]
    return {
        "ok": not problems,
        "problems": problems,
        "stats": {
            "items": len(items),
            "status_counts": status_counts,
            "milestone_counts": milestone_counts,
            "m1_items": len(m1_items),
            "m1_implemented": len(m1_ok),
        },
        "acceptance": ac_coverage,
        "data": data,
    }


def _ac_status(row: dict, index: dict[str, dict]) -> str:
    statuses = [index[item_id]["status"] for item_id in row.get("m1_items", []) if item_id in index]
    if not statuses:
        return "planned"
    if all(status == "covered" for status in statuses):
        return "covered"
    if any(status in ("covered", "partial") for status in statuses):
        return "partial"
    return "planned"


def matrix_rows(data: dict) -> list[dict]:
    rows = []
    for item in data["items"]:
        rows.append(
            {
                "id": item["id"],
                "module": item["module"],
                "milestone": item["milestone"],
                "status": STATUS_LABEL[item["status"]],
                "title_en": item["title_en"],
                "title_zh": item["title_zh"],
                "contracts": ", ".join(item.get("contract_refs", []) or []) or "-",
                "artifacts": ", ".join(item.get("artifact_refs", []) or []) or "-",
                "verify": item.get("verify_group", "-"),
                "ac": ", ".join(item.get("ac_refs", []) or []) or "-",
                "note": item.get("note", ""),
                "quote": "",
            }
        )
    return rows


def render(root: Path | str) -> dict:
    root = Path(root)
    data = load(root)
    report = check(root)
    rows = matrix_rows(data)
    acceptance = data.get("acceptance", [])

    for language in ("en", "zh"):
        lines: list[str] = []
        title = (
            "Requirement decomposition matrix"
            if language == "en"
            else "需求拆解矩阵"
        )
        lines.append(f"# {title}")
        lines.append("")
        lines.append(
            "Generated from `docs/requirements.json` by `python -m c2m_craft requirements render`."
            if language == "en"
            else "由 `docs/requirements.json` 经 `python -m c2m_craft requirements render` 生成。"
        )
        lines.append("")
        stats = report["stats"]
        lines.append(
            f"- Items: {stats['items']} · covered {stats['status_counts']['covered']} · "
            f"partial {stats['status_counts']['partial']} · planned {stats['status_counts']['planned']} · "
            f"excluded {stats['status_counts']['excluded']}"
            if language == "en"
            else f"- 条目 {stats['items']} · 已覆盖 {stats['status_counts']['covered']} · "
            f"部分 {stats['status_counts']['partial']} · 计划 {stats['status_counts']['planned']} · "
            f"排除 {stats['status_counts']['excluded']}"
        )
        lines.append(
            f"- M1 items implemented: {stats['m1_implemented']}/{stats['m1_items']}"
            if language == "en"
            else f"- M1 条目已落地：{stats['m1_implemented']}/{stats['m1_items']}"
        )
        lines.append("")
        header = (
            "| ID | Module | Milestone | Status | Requirement | Contracts | Artifacts | Verify | AC | Quote |"
            if language == "en"
            else "| 编号 | 模块 | 里程碑 | 状态 | 需求 | 契约 | 产物 | 验证组 | 验收 | 报价 |"
        )
        lines.append(header)
        lines.append("|" + "---|" * 10)
        for row in rows:
            title_cell = row["title_en"] if language == "en" else row["title_zh"]
            lines.append(
                f"| {row['id']} | {row['module']} | {row['milestone']} | "
                f"{row['status'][language]} | {title_cell} | {row['contracts']} | "
                f"{row['artifacts']} | {row['verify']} | {row['ac']} |  |"
            )
        lines.append("")
        lines.append("## Acceptance criteria" if language == "en" else "## 验收条目")
        lines.append("")
        lines.append(
            "| AC | Criterion | Coverage | M1 items | Evidence |"
            if language == "en"
            else "| 验收 | 条目 | 覆盖 | M1 条目 | 证据 |"
        )
        lines.append("|" + "---|" * 5)
        for row in acceptance:
            computed = report["acceptance"][row["id"]]["computed"]
            text = row["text_en"] if language == "en" else row["text_zh"]
            m1_items = ", ".join(row.get("m1_items", [])) or "-"
            lines.append(
                f"| {row['id']} | {text} | {STATUS_LABEL.get(computed, {}).get(language, computed)} | "
                f"{m1_items} | {row.get('evidence', '-')} |"
            )
        lines.append("")
        lines.append(
            "Verification groups: " if language == "en" else "验证组："
        )
        lines.append("")
        for key in sorted(data.get("verify_groups", {})):
            lines.append(f"- {key}: {data['verify_groups'][key]}")
        lines.append("")
        name = "requirements-matrix.md" if language == "en" else "requirements-matrix.zh.md"
        path = root / "docs" / name
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        written = name
    return {"ok": report["ok"], "written": written, "stats": report["stats"]}


def coverage_report(root: Path | str, later_artifacts: frozenset[str] = frozenset()) -> str:
    report = check(root, later_artifacts=later_artifacts)
    lines = ["# Requirement coverage", ""]
    stats = report["stats"]
    lines.append(f"- Items: {stats['items']}")
    for status in STATUSES:
        lines.append(f"- {status}: {stats['status_counts'][status]}")
    lines.append("")
    lines.append("## By milestone")
    for milestone in MILESTONES:
        row = stats["milestone_counts"][milestone]
        lines.append(
            f"- {milestone}: covered {row['covered']}, partial {row['partial']}, "
            f"planned {row['planned']}, excluded {row['excluded']}"
        )
    lines.append("")
    lines.append("## Acceptance criteria")
    for ac_id in sorted(report["acceptance"]):
        entry = report["acceptance"][ac_id]
        lines.append(f"- {ac_id}: {entry['computed']} (declared {entry['declared']})")
    lines.append("")
    if report["problems"]:
        lines.append("## Problems")
        for problem in report["problems"]:
            lines.append(f"- {problem}")
    else:
        lines.append("No unmapped or broken requirement items.")
    lines.append("")
    return "\n".join(lines)
