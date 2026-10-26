"""Multilingual growth site: generate pages, metadata and crawler files from data.

The site contract (``config/growth/site.json``) declares the pages and the limits;
the copy pack (``config/growth/copy.json``) holds every string in every language.
Generation composes one page record per page and language with its canonical path,
its hreflang alternates and its structured data, renders the HTML, and writes the
sitemap and robots file.  Nothing here reads the clock or the network.
"""

from __future__ import annotations

import html

from ...core import canonical
from ...core.errors import NotFound

SITE = "http://127.0.0.1:8412"


def load_sites(settings) -> list[dict]:
    return list(settings.json("config/growth/site.json")["sites"])


def site_spec(settings, site_id: str) -> dict:
    for spec in load_sites(settings):
        if spec["site_id"] == site_id:
            return spec
    raise NotFound(f"growth site {site_id} not found")


def copy_pack(settings, site_id: str) -> dict:
    packs = settings.json("config/growth/copy.json")["sites"]
    try:
        return packs[site_id]
    except KeyError as exc:
        raise NotFound(f"no copy pack for growth site {site_id}") from exc


def page_path(language: str, slug: str) -> str:
    return f"/{language}" + (f"/{slug}" if slug else "")


def _json_ld(spec: dict, page: dict, language: str, path: str, text: dict) -> dict:
    page_id = str(page["page_id"])
    if page_id == "home":
        kind = "Organization"
    elif page_id == "collection":
        kind = "CollectionPage"
    else:
        kind = "AboutPage"
    node = {
        "@context": "https://schema.org",
        "@type": kind,
        "name": spec["brand"].get(language) or spec["brand"]["en"],
        "url": SITE + path,
        "inLanguage": language,
        "description": text["meta_description"],
    }
    if page_id == "home":
        node["slogan"] = text["h1"]
    if page_id == "collection":
        node["isPartOf"] = SITE + page_path(language, "")
    return node


def build(settings, site_id: str, *, created_at: str) -> dict:
    spec = site_spec(settings, site_id)
    packs = copy_pack(settings, site_id)
    languages = list(spec["languages"])
    pages: list[dict] = []
    for page in spec["pages"]:
        for language in languages:
            text = packs[language]["pages"][page["page_id"]]
            path = page_path(language, page["slug"])
            alternates = [
                {"lang": other, "path": page_path(other, page["slug"])} for other in languages
            ]
            sections = [
                {
                    "section_id": section_id,
                    "heading": text["sections"][section_id]["heading"],
                    "body": text["sections"][section_id]["body"],
                }
                for section_id in page["sections"]
            ]
            pages.append(
                {
                    "page_id": page["page_id"],
                    "path": path,
                    "language": language,
                    "title": text["title"],
                    "meta_description": text["meta_description"],
                    "h1": text["h1"],
                    "canonical_path": path,
                    "hreflang": alternates,
                    "keywords": list(text["keywords"]),
                    "json_ld": _json_ld(spec, page, language, path, text),
                    "sections": sections,
                    "status": "generated",
                }
            )
    form = spec["inquiry_form"]
    fields = []
    for field in form["fields"]:
        key = str(field["label_key"]).split(".")[-1]
        fields.append(
            {
                "name": field["name"],
                "type": field["type"],
                "required": bool(field["required"]),
                "label": {
                    "zh": packs["zh"]["form"][key],
                    "en": packs["en"]["form"][key],
                },
            }
        )
    record = {
        "site_id": site_id,
        "profile_id": spec["profile_id"],
        "brand": {
            "zh": spec["brand"]["zh"],
            "en": spec["brand"]["en"],
        },
        "languages": languages,
        "primary_language": spec["primary_language"],
        "pages": pages,
        "seo": {
            "audited": False,
            "score_bp": 0,
            "issues": [],
            "checked_at": created_at,
            "rules": dict(spec["seo"]),
        },
        "inquiry_form": {"form_id": form["form_id"], "endpoint": form["endpoint"], "fields": fields},
        "created_at": created_at,
    }
    return record


def _escape(value) -> str:
    return html.escape(str(value), quote=True)


def _nav(spec: dict, packs: dict, language: str, current: str) -> str:
    items = []
    for page in spec["pages"]:
        label = packs[language]["nav"][page["page_id"]]
        path = page_path(language, page["slug"])
        active = ' class="active"' if page["page_id"] == current else ""
        items.append(f'<a href="{_escape(path)}"{active}>{_escape(label)}</a>')
    return " ".join(items)


def _language_switch(spec: dict, language: str, slug: str) -> str:
    items = []
    for other in spec["languages"]:
        path = page_path(other, slug)
        active = ' class="active"' if other == language else ""
        items.append(f'<a href="{_escape(path)}"{active}>{_escape(other.upper())}</a>')
    return " ".join(items)


def _form_html(spec: dict, packs: dict, language: str) -> str:
    form = spec["inquiry_form"]
    copy = packs[language]["form"]
    rows = []
    for field in form["fields"]:
        key = str(field["label_key"]).split(".")[-1]
        label = _escape(copy[key])
        required = " required" if field["required"] else ""
        name = _escape(field["name"])
        if field["type"] == "select":
            options = "".join(
                f'<option value="{_escape(value)}">{_escape(copy["intents"][value])}</option>'
                for value in field["options"]
            )
            control = f'<select name="{name}"{required}>{options}</select>'
        elif field["type"] == "textarea":
            control = f'<textarea name="{name}" rows="4"{required}></textarea>'
        else:
            control = f'<input type="{_escape(field["type"])}" name="{name}"{required}>'
        rows.append(f'<label class="field"><span>{label}</span>{control}</label>')
    return (
        f'<form class="inquiry" method="post" action="{_escape(form["endpoint"])}">'
        + "".join(rows)
        + f'<button type="submit">{_escape(copy["submit"])}</button>'
        + f'<p class="hint">{_escape(copy["success"])}</p></form>'
    )


def page_html(spec: dict, packs: dict, page: dict) -> str:
    language = str(page["language"])
    slug = "" if page["page_id"] == "home" else next(
        item["slug"] for item in spec["pages"] if item["page_id"] == page["page_id"]
    )
    alternates = "".join(
        f'<link rel="alternate" hreflang="{_escape(row["lang"])}" href="{_escape(SITE + row["path"])}">'
        for row in page["hreflang"]
    )
    sections = "".join(
        f'<section id="{_escape(section["section_id"])}"><h2>{_escape(section["heading"])}</h2>'
        f"<p>{_escape(section['body'])}</p></section>"
        for section in page["sections"]
    )
    json_ld = canonical.canonical_json(page["json_ld"])
    headline = _escape(page["h1"])
    inquiry = _form_html(spec, packs, language)
    brand = _escape(spec["brand"][language])
    footer = _escape(packs[language]["footer"])
    return "\n".join(
        [
            "<!DOCTYPE html>",
            f'<html lang="{_escape(language)}">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_escape(page['title'])}</title>",
            f'<meta name="description" content="{_escape(page["meta_description"])}">',
            f'<meta name="keywords" content="{_escape(", ".join(page["keywords"]))}">',
            '<meta name="robots" content="index,follow">',
            f'<link rel="canonical" href="{_escape(SITE + page["canonical_path"])}">',
            alternates,
            f'<meta property="og:title" content="{_escape(page["title"])}">',
            f'<meta property="og:description" content="{_escape(page["meta_description"])}">',
            f'<meta property="og:locale" content="{_escape(language)}">',
            f'<script type="application/ld+json">{json_ld}</script>',
            "<style>",
            ":root{color-scheme:light}body{margin:0;font-family:Georgia,serif;color:#1f2a44;background:#f7f3ea}",
            "header{display:flex;justify-content:space-between;align-items:center;padding:18px 28px;background:#1f2a44;color:#f7f3ea}",
            "header a{color:#f7f3ea;text-decoration:none;margin-left:14px}nav a.active{text-decoration:underline}",
            "main{max-width:880px;margin:0 auto;padding:32px 24px 64px}h1{font-size:2.1rem;line-height:1.2}",
            "h2{font-size:1.2rem;margin-top:28px}section p{line-height:1.65}",
            ".inquiry{display:grid;gap:10px;margin-top:24px}.field{display:grid;gap:4px}",
            "input,select,textarea{font:inherit;padding:8px}button{font:inherit;padding:10px 18px;background:#c9a227;border:0;cursor:pointer}",
            ".hint{font-size:.85rem;color:#5b6478}footer{padding:24px;text-align:center;font-size:.85rem;color:#5b6478}",
            "</style>",
            "</head>",
            "<body>",
            f'<header><strong><a href="{_escape(page_path(language, ""))}">{brand}</a></strong>'
            f'<nav>{_nav(spec, packs, language, page["page_id"])} '
            f'{_language_switch(spec, language, slug)}</nav></header>',
            "<main>",
            f"<h1>{headline}</h1>",
            sections,
            inquiry,
            "</main>",
            f"<footer>{footer}</footer>",
            "</body>",
            "</html>",
            "",
        ]
    )


def sitemap_xml(record: dict) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for page in record["pages"]:
        lines.append("  <url>")
        lines.append(f"    <loc>{_escape(SITE + page['canonical_path'])}</loc>")
        for alternate in page["hreflang"]:
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="{_escape(alternate["lang"])}" '
                f'href="{_escape(SITE + alternate["path"])}"/>'
            )
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def robots_txt(record: dict) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "",
            f"Sitemap: {SITE}/sitemap.xml",
            "",
        ]
    )


def page_filename(page: dict, spec: dict) -> str:
    slug = next(
        (item["slug"] for item in spec["pages"] if item["page_id"] == page["page_id"]), ""
    )
    return f"{page['language']}/{slug}.html" if slug else f"{page['language']}/index.html"


def write_site(record: dict, spec: dict, packs: dict, directory) -> list[str]:
    """Write pages, sitemap and robots; return the relative file names written."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for page in record["pages"]:
        name = page_filename(page, spec)
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(target, page_html(spec, packs, page))
        written.append(f"site/{name}")
    canonical.write_text(directory / "sitemap.xml", sitemap_xml(record))
    canonical.write_text(directory / "robots.txt", robots_txt(record))
    written.extend(["site/sitemap.xml", "site/robots.txt"])
    return written
