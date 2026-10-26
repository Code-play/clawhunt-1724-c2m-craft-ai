"""SEO auditor for the generated growth site.

The auditor reads the same record the generator produced and scores it against the
bounds declared in the site contract: title and description length, a single H1,
canonical path, reciprocal hreflang alternates, parseable structured data and the
keyword set.  It returns a new record with the audit written into ``seo`` so the
score is part of the committed evidence rather than a log line.
"""

from __future__ import annotations

PENALTY = {"major": 1500, "minor": 500, "info": 100}


def _issue(rows: list[dict], code: str, page_id: str, severity: str, detail: str) -> None:
    rows.append({"code": code, "page_id": page_id, "severity": severity, "detail": detail})


def audit(record: dict, *, at: str) -> dict:
    """Score the site record and return it with the audit block filled in."""
    rules = record["seo"]["rules"]
    pages = record["pages"]
    issues: list[dict] = []
    index = {(page["language"], page["path"]): page for page in pages}

    for page in pages:
        page_id = page["page_id"]
        title = str(page["title"])
        description = str(page["meta_description"])
        if not rules["title_min"] <= len(title) <= rules["title_max"]:
            _issue(
                issues,
                "title_length",
                page_id,
                "major",
                f"title length {len(title)} outside {rules['title_min']}..{rules['title_max']}",
            )
        if not rules["description_min"] <= len(description) <= rules["description_max"]:
            _issue(
                issues,
                "description_length",
                page_id,
                "major",
                f"description length {len(description)} outside "
                f"{rules['description_min']}..{rules['description_max']}",
            )
        if not 4 <= len(str(page["h1"])) <= 120:
            _issue(issues, "h1_length", page_id, "minor", "the H1 is outside 4..120 characters")
        if page["canonical_path"] != page["path"]:
            _issue(
                issues,
                "canonical_mismatch",
                page_id,
                "major",
                "the canonical path differs from the page path",
            )
        if len(page["keywords"]) < 3:
            _issue(issues, "keywords_thin", page_id, "minor", "fewer than three keywords")
        structured = page.get("json_ld") or {}
        if "@type" not in structured or "@context" not in structured:
            _issue(issues, "structured_data_incomplete", page_id, "minor", "JSON-LD lacks @context or @type")
        if structured.get("inLanguage") != page["language"]:
            _issue(
                issues,
                "structured_data_language",
                page_id,
                "info",
                "JSON-LD inLanguage does not match the page language",
            )
        for alternate in page["hreflang"]:
            target = index.get((alternate["lang"], alternate["path"]))
            if target is None:
                _issue(
                    issues,
                    "hreflang_target_missing",
                    page_id,
                    "major",
                    f"alternate {alternate['lang']} {alternate['path']} has no page",
                )
                continue
            back = {(row["lang"], row["path"]) for row in target["hreflang"]}
            if (page["language"], page["path"]) not in back:
                _issue(
                    issues,
                    "hreflang_not_reciprocal",
                    page_id,
                    "minor",
                    f"page {alternate['lang']} does not link back to {page['language']}",
                )

    primary = record["primary_language"]
    if not any(page["language"] == primary and page["page_id"] == "home" for page in pages):
        _issue(issues, "primary_home_missing", "home", "major", "the primary language has no home page")
    languages = set(record["languages"])
    if {page["language"] for page in pages} != languages:
        _issue(
            issues,
            "language_coverage",
            "home",
            "major",
            "a declared language has no page",
        )

    penalty = sum(PENALTY[issue["severity"]] for issue in issues)
    score = max(0, 10000 - penalty)
    reviewed = score >= 8000 and not any(issue["severity"] == "major" for issue in issues)
    result = dict(record)
    result["pages"] = [
        {**page, "status": "reviewed" if reviewed else page["status"]} for page in pages
    ]
    result["seo"] = {
        "audited": True,
        "score_bp": score,
        "issues": issues,
        "checked_at": at,
        "rules": dict(rules),
    }
    return result
