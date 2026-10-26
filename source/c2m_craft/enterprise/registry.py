"""Component registry of the enterprise service layer.

The registry is the single list of reusable components: each entry declares the
industries it serves, the capabilities it contributes, the contracts it reads,
the components it depends on and the data it touches.  Everything the runtime
does afterwards is a selection over this list, which is why adding an industry is
a configuration change rather than a code change.
"""

from __future__ import annotations

from ..core.errors import ValidationFailed


class ComponentRegistry:
    def __init__(self, store, settings) -> None:
        self.store = store
        self.settings = settings
        data = settings.json("config/enterprise/components.json")
        self.version = str(data["version"])
        self.components: list[dict] = list(data["components"])
        self.by_id: dict[str, dict] = {}
        for component in self.components:
            component_id = str(component["component_id"])
            if component_id in self.by_id:
                raise ValidationFailed(f"component {component_id} is registered twice")
            self.by_id[component_id] = component
            store.assert_valid("service_component", component)

    # -- lookups ---------------------------------------------------------
    def ids(self) -> list[str]:
        return [str(component["component_id"]) for component in self.components]

    def get(self, component_id: str) -> dict:
        try:
            return self.by_id[component_id]
        except KeyError as exc:
            raise KeyError(f"unknown component {component_id}") from exc

    def for_industry(self, industry: str) -> list[dict]:
        return [
            component for component in self.components if industry in component["industries"]
        ]

    def for_kind(self, kind: str) -> list[dict]:
        return [component for component in self.components if component["kind"] == kind]

    # -- dependency resolution ------------------------------------------
    def dependency_closure(self, component_id: str) -> list[str]:
        """Return the component ids a component needs, dependencies first."""
        ordered: list[str] = []
        visiting: set[str] = set()

        def visit(current: str) -> None:
            if current in ordered:
                return
            if current in visiting:
                raise ValidationFailed(f"component dependency cycle at {current}")
            visiting.add(current)
            component = self.get(current)
            for dependency in component.get("depends_on") or []:
                visit(str(dependency))
            visiting.discard(current)
            ordered.append(current)

        visit(component_id)
        ordered.remove(component_id)
        return ordered

    # -- aggregate views -------------------------------------------------
    def kind_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for component in self.components:
            counts[component["kind"]] = counts.get(component["kind"], 0) + 1
        return dict(sorted(counts.items()))

    def industry_coverage(self, industries: list[str]) -> dict:
        coverage = {}
        for industry in industries:
            applicable = self.for_industry(industry)
            coverage[industry] = {
                "components": [str(component["component_id"]) for component in applicable],
                "capabilities": sorted(
                    {capability for component in applicable for capability in component["capabilities"]}
                ),
            }
        return coverage

    def contract_ids(self) -> list[str]:
        return sorted(
            {
                str(contract)
                for component in self.components
                for contract in component.get("contracts") or []
            }
        )

    def config_paths(self) -> list[str]:
        return sorted({str(component["config_ref"]) for component in self.components})

    def describe(self) -> dict:
        return {
            "version": self.version,
            "counts": {"components": len(self.components), "by_kind": self.kind_counts()},
            "components": [
                {
                    "component_id": component["component_id"],
                    "name": component["name"],
                    "kind": component["kind"],
                    "industries": component["industries"],
                    "capabilities": component["capabilities"],
                    "contracts": component["contracts"],
                    "depends_on": component["depends_on"],
                    "config_ref": component["config_ref"],
                    "maturity": component["maturity"],
                    "enabled_by_default": component["enabled_by_default"],
                    "data_boundary": component["data_boundary"],
                    "summary": component["summary"],
                }
                for component in self.components
            ],
        }
