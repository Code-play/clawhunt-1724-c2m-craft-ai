"""Enterprise runtime: assemble a service layer from a profile and prove the switch.

An enterprise profile selects components from the registry.  Assembly resolves
each selection back to its registry entry, checks that the component serves the
enterprise industry, that its configuration path exists, that every contract it
reads is registered and that its dependencies are enabled too.  The result is the
capability envelope the enterprise actually gets, plus the list of problems that
would block go-live.  Comparing two profiles on the same registry is the proof
that switching industry is configuration, not duplicated code.
"""

from __future__ import annotations

from ..core import canonical
from ..core.errors import NotFound


class Profiles:
    def __init__(self, store, settings) -> None:
        self.store = store
        self.settings = settings
        directory = settings.path("config/enterprise/profiles")
        self.records: dict[str, dict] = {}
        for path in sorted(directory.glob("*.json")):
            profile = canonical.read_json(path)
            store.assert_valid("enterprise_profile", profile)
            self.records[str(profile["profile_id"])] = profile

    def ids(self) -> list[str]:
        return sorted(self.records)

    def get(self, profile_id: str) -> dict:
        try:
            return self.records[profile_id]
        except KeyError as exc:
            raise NotFound(f"enterprise profile {profile_id} not found") from exc

    def for_industry(self, industry: str) -> list[dict]:
        return [
            profile
            for profile in (self.records[key] for key in sorted(self.records))
            if profile["enterprise"]["industry"] == industry
        ]


class EnterpriseRuntime:
    def __init__(self, store, settings, registry, profiles) -> None:
        self.store = store
        self.settings = settings
        self.registry = registry
        self.profiles = profiles
        self.checklist = settings.json("config/enterprise/fde-checklist.json")
        self.industries = settings.industry_ids()

    # -- assembly --------------------------------------------------------
    def assemble(self, profile_id: str) -> dict:
        profile = self.profiles.get(profile_id)
        industry = str(profile["enterprise"]["industry"])
        declarations = {str(item["component_id"]): item for item in profile["components"]}
        enabled_ids = {key for key, item in declarations.items() if item.get("enabled")}
        issues: list[dict] = []
        detail: list[dict] = []
        capabilities: set[str] = set()
        contracts: set[str] = set()

        for component_id in sorted(declarations):
            declaration = declarations[component_id]
            entry = self.registry.by_id.get(component_id)
            problems: list[str] = []
            if entry is None:
                problems.append("the component is not in the registry")
                issues.append(
                    {
                        "component_id": component_id,
                        "code": "unknown_component",
                        "detail": "the profile selects a component that the registry does not declare",
                    }
                )
                detail.append(
                    {
                        "component_id": component_id,
                        "enabled": bool(declaration.get("enabled")),
                        "status": "blocked",
                        "problems": problems,
                    }
                )
                continue
            if declaration.get("kind") != entry["kind"]:
                problems.append(
                    f"profile kind {declaration.get('kind')} differs from registry kind {entry['kind']}"
                )
            if industry not in entry["industries"]:
                problems.append(f"the component does not serve the {industry} industry")
            if not self.settings.path(str(entry["config_ref"])).exists():
                problems.append(f"configuration path {entry['config_ref']} is missing")
            for contract in entry.get("contracts") or []:
                if contract not in self.store.contract_ids:
                    problems.append(f"the component reads an unregistered contract {contract}")
            if declaration.get("enabled"):
                capabilities.update(str(item) for item in entry["capabilities"])
                contracts.update(str(item) for item in entry.get("contracts") or [])
                for dependency in entry.get("depends_on") or []:
                    if str(dependency) not in enabled_ids:
                        problems.append(f"dependency {dependency} is not enabled in the profile")
            for problem in problems:
                issues.append(
                    {
                        "component_id": component_id,
                        "code": "component_not_assembled",
                        "detail": problem,
                    }
                )
            detail.append(
                {
                    "component_id": component_id,
                    "kind": entry["kind"],
                    "enabled": bool(declaration.get("enabled")),
                    "status": "ok" if not problems else "blocked",
                    "maturity": entry["maturity"],
                    "capabilities": list(entry["capabilities"]),
                    "config_ref": entry["config_ref"],
                    "problems": problems,
                }
            )

        available = [str(item["component_id"]) for item in self.registry.for_industry(industry)]
        assembly = {
            "status": "ready" if not issues else "blocked",
            "industry": industry,
            "components_enabled": len(enabled_ids),
            "components_available": len(available),
            "components_declined": sorted(set(available) - enabled_ids),
            "capabilities": sorted(capabilities),
            "contracts": sorted(contracts),
            "issues": issues,
            "component_detail": detail,
        }
        return {
            "profile_id": profile_id,
            "enterprise": profile["enterprise"],
            "industry": industry,
            "assembly": assembly,
            "channels": profile["channels"],
            "locale": profile["locale"],
            "sla": profile["sla"],
            "deployment": profile.get("deployment"),
            "growth": profile.get("growth"),
            "data_boundaries": profile.get("data_boundaries"),
            "fde": {
                "fde_id": profile["fde"]["fde_id"],
                "handbook_ref": profile["fde"]["handbook_ref"],
                "go_live_checklist": profile["fde"]["go_live_checklist"],
                "readiness": self.fde_readiness(profile_id),
            },
        }

    # -- FDE readiness ---------------------------------------------------
    def checklist_items(self) -> list[dict]:
        rows: list[dict] = []
        for phase in self.checklist["phases"]:
            for item in phase["items"]:
                row = dict(item)
                row["phase_id"] = phase["phase_id"]
                rows.append(row)
        return rows

    def fde_readiness(self, profile_id: str | None = None) -> dict:
        items = self.checklist_items()
        done = [item for item in items if item["status"] == "done"]
        open_items = [item for item in items if item["status"] != "done"]
        blocking = [item for item in open_items if item["blocking"]]
        readiness_bp = len(done) * 10000 // max(len(items), 1)
        profile = self.profiles.get(profile_id) if profile_id else None
        return {
            "phases": [
                {
                    "phase_id": phase["phase_id"],
                    "title": phase["title"],
                    "done": sum(1 for item in phase["items"] if item["status"] == "done"),
                    "total": len(phase["items"]),
                }
                for phase in self.checklist["phases"]
            ],
            "items_total": len(items),
            "items_done": len(done),
            "items_open": len(open_items),
            "blocking_open": [
                {"item_id": item["item_id"], "title": item["title"], "owner": item["owner"]}
                for item in blocking
            ],
            "readiness_bp": readiness_bp,
            "status": "go_live_ready" if not blocking else "pilot",
            "open_items": [
                {
                    "item_id": item["item_id"],
                    "phase_id": item["phase_id"],
                    "title": item["title"],
                    "owner": item["owner"],
                    "evidence": item["evidence"],
                    "blocking": item["blocking"],
                }
                for item in open_items
            ],
            "client_checklist": list(profile["fde"]["go_live_checklist"]) if profile else [],
        }

    # -- industry switch -------------------------------------------------
    def switch_matrix(self) -> dict:
        rows = []
        for industry in self.industries:
            for profile in self.profiles.for_industry(industry):
                assembly = self.assemble(profile["profile_id"])
                rows.append(
                    {
                        "industry": industry,
                        "profile_id": profile["profile_id"],
                        "enterprise": profile["enterprise"]["name"],
                        "components_enabled": assembly["assembly"]["components_enabled"],
                        "capabilities": len(assembly["assembly"]["capabilities"]),
                        "contracts": len(assembly["assembly"]["contracts"]),
                        "languages": (profile.get("growth") or {}).get("languages", []),
                        "deployment": (profile.get("deployment") or {}).get("mode"),
                        "status": assembly["assembly"]["status"],
                    }
                )
        capability_sets = {
            industry: set(
                capability
                for profile in self.profiles.for_industry(industry)
                for capability in self.assemble(profile["profile_id"])["assembly"]["capabilities"]
            )
            for industry in self.industries
        }
        shared = (
            sorted(set.intersection(*capability_sets.values())) if capability_sets else []
        )
        only = {
            industry: sorted(capabilities - set(shared))
            for industry, capabilities in capability_sets.items()
        }
        return {
            "industries": self.industries,
            "rows": rows,
            "capabilities_shared": shared,
            "capabilities_industry_specific": only,
            "proof": {
                "registry_version": self.registry.version,
                "profiles": len(self.profiles.ids()),
                "code_changes_between_industries": 0,
                "note": "Both rows are assembled by the same code from the same registry; only the profile and the industry configuration differ.",
            },
        }

    # -- report ----------------------------------------------------------
    def report(self) -> dict:
        assemblies = [self.assemble(profile_id) for profile_id in self.profiles.ids()]
        readiness = {profile_id: self.fde_readiness(profile_id) for profile_id in self.profiles.ids()}
        blocking = sorted(
            {
                item["item_id"]
                for readiness_row in readiness.values()
                for item in readiness_row["blocking_open"]
            }
        )
        return {
            "version": "1.0.0",
            "registry": self.registry.describe(),
            "profiles": assemblies,
            "switch": self.switch_matrix(),
            "fde": {
                "checklist_version": self.checklist["version"],
                "readiness": readiness,
                "blocking_open": blocking,
            },
            "summary": {
                "components": len(self.registry.components),
                "profiles": len(assemblies),
                "industries": len(self.industries),
                "capabilities": len(
                    {
                        capability
                        for assembly in assemblies
                        for capability in assembly["assembly"]["capabilities"]
                    }
                ),
                "contracts": len(self.registry.contract_ids()),
                "assemblies_ready": sum(
                    1 for assembly in assemblies if assembly["assembly"]["status"] == "ready"
                ),
                "fde_readiness_bp": readiness[self.profiles.ids()[0]]["readiness_bp"],
            },
        }

    def describe(self) -> dict:
        return {
            "registry": {
                "version": self.registry.version,
                "components": [
                    {
                        "component_id": component["component_id"],
                        "name": component["name"],
                        "kind": component["kind"],
                        "industries": component["industries"],
                        "capabilities": component["capabilities"],
                        "maturity": component["maturity"],
                        "enabled_by_default": component["enabled_by_default"],
                    }
                    for component in self.registry.components
                ],
            },
            "profiles": [self.assemble(profile_id) for profile_id in self.profiles.ids()],
            "switch": self.switch_matrix(),
            "fde": self.fde_readiness(self.profiles.ids()[0]) if self.profiles.ids() else None,
        }
