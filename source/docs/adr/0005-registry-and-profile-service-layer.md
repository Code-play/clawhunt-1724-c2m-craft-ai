# ADR 0005 - The enterprise service layer is a registry plus a profile

Status: accepted (milestone 3).

## Context

The brief asks for reusable components for at least two industries, with industry
switching done by configuration rather than by duplicated code, an FDE delivery
method and one fully populated enterprise profile. The M1 seam already declared an
`enterprise_profile` contract, but there was no runtime behind it.

## Decision

1. A **component registry** (`config/enterprise/components.json`) lists every
   reusable component once: its industries, capabilities, contracts, dependencies,
   configuration path and data boundary. Each entry validates against the
   `service_component` contract.
2. An **enterprise profile** (`config/enterprise/profiles/*.json`) selects
   components and records the enterprise, locale, channels, SLA, growth stack,
   data boundaries, deployment posture and the client go-live list.
3. The **runtime assembles** a profile against the registry: it resolves each
   selection, checks the industry, the configuration path, the registered
   contracts and the dependencies, and reports every blocker. Assembly status is a
   function of those checks, never a typed field.
4. **FDE readiness** is derived from `config/enterprise/fde-checklist.json`: the
   report recomputes done, open and blocking items on every run, so a deployment
   cannot claim go-live while a blocking item is open.
5. The **growth stack** is data too: `config/growth/site.json` declares pages,
   languages and SEO bounds, `config/growth/copy.json` holds the copy, and
   `config/growth/crm.json` holds scoring, routing, follow-up and quote policy. The
   generator, the SEO auditor and the CRM loop are pure functions over those files.

## Consequences

- Adding an industry, a component or a market is a data edit; the verification
  group J proves two industries assemble from one registry with zero code changes.
- A profile that references an unknown component, a missing configuration path, an
  unregistered contract or a disabled dependency is reported as blocked with the
  reason, instead of failing later at request time.
- The same repository can present a jewellery deployment and a hardwood pilot
  side by side, which makes the enterprise conversation concrete early.
- The generated site lives under `out/site/` and is served read-only by the
  prototype server; nothing in the runtime writes to `static/`.
