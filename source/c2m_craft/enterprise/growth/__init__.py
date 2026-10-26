"""Growth stack: multilingual site generation, SEO audit and the inquiry to CRM loop."""

from __future__ import annotations

from . import crm as crm_mod
from . import seo as seo_mod
from . import site as site_mod


class GrowthStack:
    def __init__(self, store, settings) -> None:
        self.store = store
        self.settings = settings
        self.sites = {spec["site_id"]: spec for spec in site_mod.load_sites(settings)}
        self.crm = crm_mod.CrmLoop(store, settings)

    # -- site ------------------------------------------------------------
    def site_ids(self) -> list[str]:
        return sorted(self.sites)

    def spec(self, site_id: str) -> dict:
        return site_mod.site_spec(self.settings, site_id)

    def copy(self, site_id: str) -> dict:
        return site_mod.copy_pack(self.settings, site_id)

    def build(self, site_id: str, *, at: str) -> dict:
        record = site_mod.build(self.settings, site_id, created_at=at)
        self.store.assert_valid("growth_site", record)
        return record

    def audit(self, record: dict, *, at: str) -> dict:
        audited = seo_mod.audit(record, at=at)
        self.store.assert_valid("growth_site", audited)
        return audited

    def write(self, record: dict, directory) -> list[str]:
        spec = self.spec(record["site_id"])
        packs = self.copy(record["site_id"])
        return site_mod.write_site(record, spec, packs, directory)

    def page_paths(self, record: dict) -> list[str]:
        spec = self.spec(record["site_id"])
        return [site_mod.page_path(page["language"], "") for page in record["pages"] if page["page_id"] == "home"]

    def negative_audit(self, record: dict) -> dict:
        """Audit a copy with one page stripped of its description (the detection proof)."""
        damaged = dict(record)
        pages = [dict(page) for page in record["pages"]]
        pages[0]["meta_description"] = ""
        damaged["pages"] = pages
        damaged_seo = dict(record["seo"])
        damaged_seo["audited"] = False
        damaged_seo["score_bp"] = 0
        damaged_seo["issues"] = []
        damaged["seo"] = damaged_seo
        return seo_mod.audit(damaged, at=record["seo"]["checked_at"])

    # -- inquiry to CRM --------------------------------------------------
    def intake(self, payload: dict, *, at: str) -> dict:
        return self.crm.intake(payload, at=at)

    def advance(self, inquiry_id: str, stage: str, *, at: str, note: str) -> dict:
        return self.crm.advance(inquiry_id, stage, at=at, note=note)

    def report(self, *, now: str, site_record: dict | None = None) -> dict:
        crm_report = self.crm.report(now=now)
        payload = {
            "version": "1.0.0",
            "sites_configured": [
                {
                    "site_id": spec["site_id"],
                    "profile_id": spec["profile_id"],
                    "languages": spec["languages"],
                    "pages": len(spec["pages"]) * len(spec["languages"]),
                }
                for spec in (self.sites[key] for key in sorted(self.sites))
            ],
            "crm": crm_report,
        }
        if site_record is not None:
            payload["site"] = dict(site_record)
            payload["site_seo_summary"] = {
                "score_bp": site_record["seo"]["score_bp"],
                "issues": len(site_record["seo"]["issues"]),
                "pages": len(site_record["pages"]),
                "languages": len(site_record["languages"]),
                "reviewed_pages": sum(
                    1 for page in site_record["pages"] if page["status"] == "reviewed"
                ),
            }
        return payload
