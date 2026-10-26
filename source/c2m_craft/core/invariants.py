"""Cross-field invariants that JSON Schema cannot express.

Each invariant is a pure function ``(instance, ctx) -> list[str]``.  Schemas
reference them through ``x-invariants``; the validator runs them only when the
structural pass is clean, so the messages can rely on the required fields being
present.  Context (``as_of``, allowed status set, settlement policy) is supplied
by the caller.
"""

from __future__ import annotations

from typing import Any, Callable

from .canonical import content_hash
from .clock import parse_ts

MAX_REASON_MIN = 8


def _tc_seconds(text: Any) -> int:
    """Parse a zero padded HH:MM:SS timecode into seconds."""
    parts = str(text).split(":")
    if len(parts) != 3:
        raise ValueError(f"bad timecode {text!r}")
    hours, minutes, seconds = (int(part) for part in parts)
    if minutes > 59 or seconds > 59 or min(hours, minutes, seconds) < 0:
        raise ValueError(f"bad timecode {text!r}")
    return hours * 3600 + minutes * 60 + seconds


def visual_asset_checksum(asset: dict) -> str:
    """Canonical checksum over the identity and the drawing recipe of an asset."""
    return content_hash(
        {
            "asset_id": asset.get("asset_id"),
            "character_id": asset.get("character_id"),
            "kind": asset.get("kind"),
            "view_or_name": asset.get("view_or_name"),
            "recipe": asset.get("recipe"),
            "resolution": asset.get("resolution"),
        }
    )



def _licensing(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    license_block = instance.get("license") or {}
    source = license_block.get("source_type")
    if source in ("licensed", "traditional_heritage"):
        for field in ("licensor", "license_id"):
            if not license_block.get(field):
                problems.append(f"license.source_type={source} requires license.{field}")
    if license_block.get("attribution_required") is True:
        review = instance.get("review") or {}
        if review.get("status") != "content_reviewed":
            problems.append("attribution_required=true requires review.status=content_reviewed")
    return problems


def _usage_scope(instance: dict, ctx: dict) -> list[str]:
    license_block = instance.get("license") or {}
    scopes = license_block.get("usage_scope")
    if not isinstance(scopes, list) or not scopes:
        return ["license.usage_scope must list at least one permitted scope"]
    if len(set(scopes)) != len(scopes):
        return ["license.usage_scope contains duplicate entries"]
    return []


def _traditional_prototype(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    license_block = instance.get("license") or {}
    exclusive = bool(license_block.get("exclusive"))
    if instance.get("traditional_prototype") is True and exclusive:
        problems.append(
            "a traditional cultural prototype cannot be claimed as an exclusive right"
        )
    if instance.get("religious_site_names") and exclusive:
        problems.append("assets referencing religious sites cannot be licensed exclusively")
    return problems


def _license_window(instance: dict, ctx: dict) -> list[str]:
    license_block = instance.get("license") or {}
    start = license_block.get("valid_from")
    end = license_block.get("valid_to")
    if not start or not end:
        return ["license.valid_from and license.valid_to are required"]
    try:
        start_dt = parse_ts(str(start))
        end_dt = parse_ts(str(end))
    except ValueError as exc:
        return [f"license window is not a valid timestamp: {exc}"]
    if start_dt >= end_dt:
        return ["license.valid_from must be earlier than license.valid_to"]
    problems: list[str] = []
    as_of = ctx.get("as_of")
    if ctx.get("require_active_window") and as_of:
        moment = parse_ts(str(as_of))
        if not (start_dt <= moment <= end_dt):
            problems.append(f"license window {start}..{end} does not cover as_of {as_of}")
    return problems


def _settlement_totals(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    lines = instance.get("payout_lines") or []
    total = instance.get("total_cents")
    policy = instance.get("split_policy") or {}
    policy_lines = policy.get("lines") or []
    if policy_lines:
        policy_rates = sum(int(line.get("rate_bp", 0)) for line in policy_lines)
        if policy_rates != 10000:
            problems.append(f"split policy rates sum to {policy_rates} bp, expected 10000")
        declared = {str(line.get("party")): int(line.get("rate_bp", 0)) for line in policy_lines}
        for line in lines:
            party = str(line.get("party"))
            if party in declared and int(line.get("rate_bp", 0)) != declared[party]:
                problems.append(
                    f"payout rate for {party} ({line.get('rate_bp')}) differs from the policy "
                    f"({declared[party]})"
                )
    if isinstance(total, int) and lines:
        allocated = sum(int(line.get("amount_cents", 0)) for line in lines)
        if allocated != total:
            problems.append(f"payout lines sum to {allocated} cents, total is {total}")
        rates = sum(int(line.get("rate_bp", 0)) for line in lines)
        if rates != 10000:
            problems.append(f"payout rates sum to {rates} bp, expected 10000")
    reconciliation = instance.get("reconciliation") or {}
    if reconciliation:
        if int(reconciliation.get("sum_payouts_cents", 0)) != int(total or 0):
            problems.append("reconciliation.sum_payouts_cents does not match total_cents")
        if int(reconciliation.get("delta_cents", 0)) != 0:
            problems.append("reconciliation.delta_cents must be zero")
    return problems


def _order_amounts(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    amounts = instance.get("amounts") or {}
    try:
        total = int(amounts.get("total_cents", 0))
        subtotal = int(amounts.get("subtotal_cents", 0))
        fee = int(amounts.get("customization_fee_cents", 0))
        shares = (
            int(amounts.get("designer_share_cents", 0))
            + int(amounts.get("factory_share_cents", 0))
            + int(amounts.get("ip_share_cents", 0))
            + int(amounts.get("platform_fee_cents", 0))
        )
    except (TypeError, ValueError):
        return ["amounts must be integers"]
    if total != subtotal + fee:
        problems.append(
            f"amounts.total_cents {total} != subtotal {subtotal} + customization fee {fee}"
        )
    if shares != total:
        problems.append(f"revenue shares sum to {shares} cents, total is {total}")
    allowed = ctx.get("allowed_statuses")
    if allowed and instance.get("status") not in allowed:
        problems.append(f"status {instance.get('status')!r} is not a known order state")
    return problems


def _review_override(instance: dict, ctx: dict) -> list[str]:
    status = instance.get("status")
    decision = instance.get("decision") or {}
    if status == "overridden":
        reason = str(decision.get("reason") or "").strip()
        if len(reason) < MAX_REASON_MIN:
            return [
                f"an override needs a decision.reason of at least {MAX_REASON_MIN} characters"
            ]
        if decision.get("verdict") == instance.get("auto_verdict"):
            return ["an override must change the verdict"]
    if status == "confirmed" and decision.get("verdict") != instance.get("auto_verdict"):
        return ["status=confirmed contradicts a different decision.verdict"]
    return []


def _ip_scope(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    refs = instance.get("traditional_prototype_refs") or []
    for ref in refs:
        if ref.get("exclusive_claimed") is not False:
            problems.append(
                f"traditional prototype {ref.get('name')!r} must keep exclusive_claimed=false"
            )
    usage = instance.get("usage") or {}
    if refs and usage.get("exclusivity"):
        problems.append("exclusivity cannot be granted while traditional prototypes are referenced")
    return problems


def _customization(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    selections = instance.get("selections") or []
    groups = [str(item.get("group_id")) for item in selections]
    if len(set(groups)) != len(groups):
        problems.append("selections must use each option group at most once")
    amounts = instance.get("amounts") or {}
    base = int(amounts.get("base_unit_price_cents", 0))
    delta = int(amounts.get("delta_cents", 0))
    unit = int(amounts.get("unit_price_cents", 0))
    if unit != base + delta:
        problems.append(f"unit price {unit} != base {base} + delta {delta}")
    resolved = sum(int(item.get("price_delta_cents", 0)) for item in selections)
    if resolved != delta:
        problems.append(f"selection deltas sum to {resolved}, amounts declare {delta}")
    if instance.get("status") == "applied" and not instance.get("result_concept_id"):
        problems.append("an applied choice needs a result concept")
    feasibility = instance.get("feasibility") or {}
    if instance.get("status") == "infeasible" and feasibility.get("ok"):
        problems.append("status infeasible contradicts feasibility.ok=true")
    if instance.get("status") == "feasible" and not feasibility.get("ok"):
        problems.append("status feasible contradicts feasibility.ok=false")
    return problems


def _edition(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    size = int(instance.get("size", 0))
    numbering = instance.get("numbering") or {}
    issued = numbering.get("issued") or []
    reserved = [int(value) for value in numbering.get("reserved") or []]
    numbers = [int(row.get("number", 0)) for row in issued]
    if any(number < 1 or number > size for number in numbers):
        problems.append("issued numbers must be within 1..size")
    if len(set(numbers)) != len(numbers):
        problems.append("issued numbers must be unique")
    if any(number < 1 or number > size for number in reserved):
        problems.append("reserved numbers must be within 1..size")
    if set(reserved) & set(numbers):
        problems.append("a number cannot be both reserved and issued")
    if instance.get("status") == "closed" and len(issued) != size:
        problems.append(f"a closed edition must issue all {size} numbers, issued {len(issued)}")
    collectors = [str(row.get("collector_id")) for row in issued]
    if len(set(collectors)) != len(collectors):
        problems.append("each issued number needs a distinct collector record")
    artist = instance.get("artist") or {}
    if int(artist.get("royalty_rate_bp", 0)) > 5000:
        problems.append("artist royalty above 50 percent of the edition revenue is refused")
    return problems


def _collector_provenance(instance: dict, ctx: dict) -> list[str]:
    chain = instance.get("provenance") or []
    if not chain:
        return ["provenance must have at least one entry"]
    problems: list[str] = []
    owner = str((instance.get("owner") or {}).get("owner_id", ""))
    if chain[0].get("from") is not None:
        problems.append("the first provenance entry must have no predecessor")
    for index in range(1, len(chain)):
        if chain[index].get("from") != chain[index - 1].get("to"):
            problems.append(f"provenance entry {index} does not continue the chain")
    if chain[-1].get("to") != owner:
        problems.append("the last provenance entry must point at the current owner")
    kinds = {str(entry.get("kind")) for entry in chain}
    if "issue" not in kinds:
        problems.append("the chain must start from an issue entry")
    return problems


def _quality(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    verdict = str(instance.get("verdict"))
    defects = instance.get("defects") or []
    counted = [item for item in defects if int(item.get("count", 0)) > 0]
    critical = [item for item in counted if item.get("severity") == "critical"]
    major = [item for item in counted if item.get("severity") == "major"]
    if verdict == "pass":
        if critical:
            problems.append("a pass cannot carry a critical defect")
        if major:
            problems.append("a pass cannot carry a major defect")
    elif verdict == "fail":
        if not critical and not major:
            problems.append("a failing inspection needs a major or critical defect")
    elif verdict == "rework":
        if not counted:
            problems.append("an inspection sent back for rework needs at least one defect")
    for item in instance.get("measurements") or []:
        low = float(item.get("limit_min", 0))
        high = float(item.get("limit_max", 0))
        value = float(item.get("value", 0))
        if bool(item.get("ok")) != (low <= value <= high):
            problems.append(f"measurement {item.get('name')} ok flag contradicts its limits")
    return problems


def _promise(instance: dict, ctx: dict) -> list[str]:
    promise = instance.get("promise")
    if not promise:
        return []
    problems: list[str] = []
    created = str(instance.get("created_at", ""))
    promised = str(promise.get("promised_delivery_at", ""))
    if created and promised and promised <= created:
        problems.append("the promised delivery must be after the order was created")
    if int(promise.get("working_minutes", 0)) <= 0:
        problems.append("a promise needs a positive working time")
    for alternative in promise.get("alternatives") or []:
        moment = str(alternative.get("promised_delivery_at", ""))
        if created and moment and moment <= created:
            problems.append("an alternative promise must be after the order was created")
    return problems


def _dispute(instance: dict, ctx: dict) -> list[str]:
    dispute = instance.get("dispute") or {}
    status = str(dispute.get("status"))
    cited = list(dispute.get("qc_record_ids") or [])
    problems: list[str] = []
    if status == "none":
        if dispute.get("reason") or dispute.get("opened_at") or cited:
            problems.append("a dispute that never opened cannot carry a reason, a time or evidence")
    else:
        if not dispute.get("reason"):
            problems.append("an opened dispute needs a reason")
        if not dispute.get("opened_at"):
            problems.append("an opened dispute needs an opening time")
    if status.startswith("resolved"):
        if not dispute.get("resolution_note"):
            problems.append("a resolved dispute needs a resolution note")
        if not dispute.get("resolved_at"):
            problems.append("a resolved dispute needs a resolution time")
    if len(set(cited)) != len(cited):
        problems.append("a quality record can be cited once")
    return problems


def _royalty(instance: dict, ctx: dict) -> list[str]:
    lines = instance.get("royalty_lines") or []
    if not lines:
        return []
    problems: list[str] = []
    ip_share = sum(
        int(line.get("amount_cents", 0))
        for line in instance.get("payout_lines") or []
        if line.get("party") == "ip_licensor"
    )
    allocated = sum(int(line.get("amount_cents", 0)) for line in lines)
    if allocated != ip_share:
        problems.append(f"royalty lines sum to {allocated} but the IP share is {ip_share}")
    for line in lines:
        rate = int(line.get("rate_bp", 0))
        amount = int(line.get("amount_cents", 0))
        basis = int(line.get("basis_cents", 0))
        if not 0 <= rate <= 10000:
            problems.append(f"royalty rate out of range for {line.get('asset_id')}")
        if amount < 0:
            problems.append(f"royalty for {line.get('asset_id')} is negative")
        if amount > basis:
            problems.append(f"royalty for {line.get('asset_id')} exceeds its basis")
        if amount > ip_share:
            problems.append(f"royalty for {line.get('asset_id')} exceeds the whole IP share")
    return problems


def _component(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    component_id = str(instance.get("component_id", ""))
    if component_id in [str(item) for item in instance.get("depends_on") or []]:
        problems.append("a component cannot depend on itself")
    if instance.get("enabled_by_default") and instance.get("maturity") == "prototype":
        problems.append("a prototype component cannot be enabled by default")
    boundary = instance.get("data_boundary") or {}
    if boundary.get("personal_data") and int(boundary.get("retention_days", 0)) <= 0:
        problems.append("a component touching personal data needs a retention policy")
    if "crm" in (boundary.get("stores") or []) and not boundary.get("personal_data"):
        problems.append("a component storing leads must declare personal_data=true")
    capabilities = [str(item) for item in instance.get("capabilities") or []]
    if len(set(capabilities)) != len(capabilities):
        problems.append("capabilities must be unique")
    return problems


def _enterprise_profile(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    components = instance.get("components") or []
    component_ids = [str(item.get("component_id")) for item in components]
    if len(set(component_ids)) != len(component_ids):
        problems.append("profile component ids must be unique")
    enabled_kinds = {str(item.get("kind")) for item in components if item.get("enabled")}
    channels = instance.get("channels") or {}
    required_kinds = {
        "site": {"workflow", "growth", "knowledge_base"},
        "seo": {"growth", "knowledge_base", "agent"},
        "crm": {"crm"},
    }
    for channel, kinds in required_kinds.items():
        if channels.get(channel) and not (enabled_kinds & kinds):
            problems.append(f"channels.{channel}=true needs an enabled {' or '.join(sorted(kinds))} component")
    locale = instance.get("locale") or {}
    if locale.get("primary") in (locale.get("secondary") or []):
        problems.append("the primary locale cannot repeat in the secondary list")
    fde = instance.get("fde") or {}
    if ".md" not in str(fde.get("handbook_ref", "")):
        problems.append("the FDE handbook reference must point at a markdown handbook")
    if len(fde.get("go_live_checklist") or []) < 4:
        problems.append("a go-live checklist needs at least four items")
    growth = instance.get("growth") or {}
    if growth:
        pipeline = [str(item) for item in growth.get("crm_pipeline") or []]
        if len(set(pipeline)) != len(pipeline):
            problems.append("the CRM pipeline stages must be unique")
        if pipeline and pipeline[0] != "new":
            problems.append("the CRM pipeline must start at the new stage")
        if locale.get("primary") not in (growth.get("languages") or []):
            problems.append("the growth stack must serve the primary locale")
    for store in (instance.get("data_boundaries") or {}).get("stores") or []:
        if store.get("personal_data") and not (instance.get("data_boundaries") or {}).get("dpa_ref"):
            problems.append("a personal data store needs a data processing agreement reference")
    return problems


def _growth_site(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    languages = {str(item) for item in instance.get("languages") or []}
    pages = instance.get("pages") or []
    page_languages = {str(page.get("language")) for page in pages}
    if page_languages != languages:
        problems.append(
            f"every site language needs a page: languages {sorted(languages)} vs pages {sorted(page_languages)}"
        )
    rules = (instance.get("seo") or {}).get("rules") or {}
    title_min = int(rules.get("title_min", 0))
    title_max = int(rules.get("title_max", 10**6))
    description_min = int(rules.get("description_min", 0))
    description_max = int(rules.get("description_max", 10**6))
    canonicals: list[str] = []
    for page in pages:
        page_id = page.get("page_id")
        language = str(page.get("language"))
        path = str(page.get("path"))
        if not path.startswith(f"/{language}"):
            problems.append(f"page {page_id} path {path} does not start with /{language}")
        if page.get("canonical_path") != path:
            problems.append(f"page {page_id} canonical path differs from its own path")
        canonicals.append(str(page.get("canonical_path")))
        alternates = {str(row.get("lang")) for row in page.get("hreflang") or []}
        if alternates != languages:
            problems.append(f"page {page_id} hreflang does not cover every site language")
        title = str(page.get("title", ""))
        description = str(page.get("meta_description", ""))
        if not title_min <= len(title) <= title_max:
            problems.append(f"page {page_id} title length {len(title)} outside {title_min}..{title_max}")
        if not description_min <= len(description) <= description_max:
            problems.append(
                f"page {page_id} description length {len(description)} outside "
                f"{description_min}..{description_max}"
            )
    if len(set(canonicals)) != len(canonicals):
        problems.append("canonical paths must be unique")
    seo = instance.get("seo") or {}
    if seo.get("audited") and int(seo.get("score_bp", 0)) <= 0:
        problems.append("an audited site needs a positive SEO score")
    return problems


_LEAD_STAGE_EVENTS = {
    "new": {"received", "scored"},
    "qualified": {"routed"},
    "contacted": {"contacted"},
    "quoted": {"quoted"},
    "won": {"won"},
    "lost": {"lost"},
}


def _inquiry_lead(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    lead = instance.get("lead") or {}
    points = sum(int(row.get("points", 0)) for row in lead.get("score_breakdown") or [])
    expected = max(0, min(100, points))
    if int(lead.get("score", -1)) != expected:
        problems.append(f"lead score {lead.get('score')} != clamped sum of its factors {expected}")
    stage = str(lead.get("stage"))
    submitted = str(instance.get("submitted_at", ""))
    sla_due = str(lead.get("sla_due_at", ""))
    if submitted and sla_due and sla_due <= submitted:
        problems.append("the response SLA must fall after the inquiry was submitted")
    if stage in ("contacted", "quoted", "won") and not lead.get("first_response_at"):
        problems.append(f"stage {stage} needs a first response time")
    quote = instance.get("quote")
    if stage in ("quoted", "won") and not quote:
        problems.append(f"stage {stage} needs a quote")
    if quote:
        if submitted and str(quote.get("valid_until", "")) <= submitted:
            problems.append("a quote must stay valid after the inquiry was submitted")
        if int(quote.get("amount_cents", -1)) < 0:
            problems.append("a quote amount cannot be negative")
    events = instance.get("crm_events") or []
    if events:
        last = str(events[-1].get("type"))
        if last not in _LEAD_STAGE_EVENTS.get(stage, set()):
            problems.append(f"last CRM event {last} does not open stage {stage}")
        moments = [str(row.get("at")) for row in events]
        if moments != sorted(moments):
            problems.append("CRM events must be in time order")
    follow_ups = instance.get("follow_ups") or []
    follow_ids = [str(row.get("follow_up_id")) for row in follow_ups]
    if len(set(follow_ids)) != len(follow_ids):
        problems.append("follow-up ids must be unique")
    dues = [str(row.get("due_at")) for row in follow_ups]
    if dues != sorted(dues):
        problems.append("follow-ups must be scheduled in due order")
    for due in dues:
        if submitted and due < submitted:
            problems.append("a follow-up cannot be due before the inquiry arrived")
    return problems


def _character_bible(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    characters = (instance.get("canon") or {}).get("characters") or []
    ids = [str(item.get("character_id")) for item in characters]
    if len(set(ids)) != len(ids):
        problems.append("character ids must be unique")
    elements = [str(item.get("element")) for item in characters]
    if len(set(elements)) != len(elements):
        problems.append("the two guardians must not share an element")
    lines = [str((item.get("voice") or {}).get("signature_line")) for item in characters]
    if len(set(lines)) != len(lines):
        problems.append("each guardian needs its own signature line")
    reviews = [str(item.get("content_review_ref")) for item in characters]
    if len(set(reviews)) != len(reviews):
        problems.append("each guardian needs its own content review")
    for character in characters:
        character_id = character.get("character_id")
        if len(character.get("motifs") or []) < 3:
            problems.append(f"character {character_id} needs at least three motifs")
        if len(character.get("props") or []) < 2:
            problems.append(f"character {character_id} needs at least two props")
        if len(character.get("palette") or []) < 3:
            problems.append(f"character {character_id} needs a three colour palette")
        if not str(character.get("authenticity_label") or "").strip():
            problems.append(f"character {character_id} needs an authenticity label")
        arc = character.get("story_arc") or []
        if len(arc) < 3:
            problems.append(f"character {character_id} needs at least three arc beats")
        beats = [str(item.get("beat")) for item in arc]
        if len(set(beats)) != len(beats):
            problems.append(f"character {character_id} repeats an arc beat")
    for ref in instance.get("heritage_refs") or []:
        if ref.get("exclusive_claimed") is not False:
            problems.append("heritage references must stay non-exclusive")
    rules = (instance.get("world") or {}).get("rules") or []
    if len(set(rules)) != len(rules):
        problems.append("world rules must be distinct")
    return problems


def _visual_asset(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    if str(instance.get("checksum")) != visual_asset_checksum(instance):
        problems.append("the checksum does not recompute from the recipe")
    source = instance.get("source") or {}
    if source.get("sourcing") == "licensed_cc" and not source.get("licence_ref"):
        problems.append("a licensed asset needs its licence reference")
    if source.get("ai_assisted") and not str(source.get("authenticity_label") or "").strip():
        problems.append("an AI assisted asset needs an authenticity label")
    review = instance.get("review") or {}
    if review.get("status") == "approved" and not review.get("reviewer"):
        problems.append("an approved asset needs a reviewer")
    layers = (instance.get("recipe") or {}).get("layers") or []
    layer_ids = [str(item.get("layer_id")) for item in layers]
    if len(set(layer_ids)) != len(layer_ids):
        problems.append("layer ids must be unique")
    for layer in layers:
        geometry = layer.get("geometry") or []
        shape = layer.get("shape")
        if shape == "circle" and len(geometry) != 3:
            problems.append("a circle layer needs centre x, centre y and a radius")
        if shape == "ellipse" and len(geometry) != 4:
            problems.append("an ellipse layer needs centre x, centre y, rx and ry")
        if shape in ("polygon", "path", "line") and len(geometry) % 2 != 0:
            problems.append("a polygon, path or line layer needs x,y pairs")
    return problems


def _short_drama(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    scenes = (instance.get("script") or {}).get("scenes") or []
    scene_ids = [str(item.get("scene_id")) for item in scenes]
    if len(set(scene_ids)) != len(scene_ids):
        problems.append("scene ids must be unique")
    scene_assets: dict[str, set[str]] = {}
    scene_total = 0
    for scene in scenes:
        scene_id = str(scene.get("scene_id"))
        beats = scene.get("beats") or []
        beat_total = sum(int(beat.get("duration_seconds", 0)) for beat in beats)
        if beat_total != int(scene.get("duration_seconds", 0)):
            problems.append(
                f"scene {scene_id} beats add up to {beat_total}s but the scene declares "
                f"{scene.get('duration_seconds')}s"
            )
        scene_total += int(scene.get("duration_seconds", 0))
        scene_assets[scene_id] = {str(item) for item in scene.get("assets") or []}
        cast = {str(item) for item in scene.get("characters") or []}
        for beat in beats:
            for line in beat.get("dialogue") or []:
                if str(line.get("character_id")) not in cast:
                    problems.append(
                        f"scene {scene_id} has dialogue from a character not listed in the scene"
                    )
    cut = instance.get("cut") or {}
    total = int(cut.get("total_seconds", -1))
    if scene_total != total:
        problems.append(f"scene durations add up to {scene_total}s but the cut is {total}s")
    frames = (instance.get("storyboard") or {}).get("frames") or []
    frame_ids = [str(item.get("frame_id")) for item in frames]
    if len(set(frame_ids)) != len(frame_ids):
        problems.append("storyboard frames must be unique")
    frame_total = sum(int(item.get("duration_seconds", 0)) for item in frames)
    if frame_total != total:
        problems.append(f"storyboard durations add up to {frame_total}s but the cut is {total}s")
    per_scene: dict[str, int] = {}
    for frame in frames:
        scene_id = str(frame.get("scene_id"))
        if scene_id not in scene_ids:
            problems.append(f"frame {frame.get('frame_id')} cites unknown scene {scene_id}")
        per_scene[scene_id] = per_scene.get(scene_id, 0) + int(frame.get("duration_seconds", 0))
        outside = {str(item) for item in frame.get("asset_ids") or []} - scene_assets.get(scene_id, set())
        if outside:
            problems.append(
                f"frame {frame.get('frame_id')} uses assets outside its scene: {sorted(outside)}"
            )
    for scene in scenes:
        scene_id = str(scene.get("scene_id"))
        if per_scene.get(scene_id, 0) != int(scene.get("duration_seconds", 0)):
            problems.append(
                f"scene {scene_id} storyboard adds up to {per_scene.get(scene_id, 0)}s, "
                f"declared {scene.get('duration_seconds')}s"
            )
    edl = cut.get("edl") or []
    if [str(row.get("frame_id")) for row in edl] != frame_ids:
        problems.append("the edit decision list must follow the storyboard order exactly once")
    clock = 0
    for index, row in enumerate(edl):
        if int(row.get("order", 0)) != index + 1:
            problems.append("edit decision list rows must be numbered from one without gaps")
        try:
            start = _tc_seconds(row.get("in_tc"))
            end = _tc_seconds(row.get("out_tc"))
        except ValueError:
            problems.append(f"edit decision list row {index} has an invalid timecode")
            continue
        if start != clock:
            problems.append(f"edit decision list row {index} does not start where the previous one ended")
        if end <= start:
            problems.append(f"edit decision list row {index} has a non-positive duration")
        clock = end
    if clock != total:
        problems.append(f"the edit decision list ends at {clock}s but the cut is {total}s")
    subtitles = (instance.get("subtitles") or {}).get("lines") or []
    previous_end = 0
    for line in subtitles:
        try:
            start = _tc_seconds(line.get("in_tc"))
            end = _tc_seconds(line.get("out_tc"))
        except ValueError:
            problems.append("a subtitle line has an invalid timecode")
            continue
        if end <= start:
            problems.append("a subtitle line has a non-positive duration")
        if end > total:
            problems.append("a subtitle line runs past the end of the cut")
        if start < previous_end:
            problems.append("subtitle lines must not overlap")
        previous_end = end
    review = instance.get("review") or {}
    if review.get("status") == "approved":
        if not review.get("content_review_ref"):
            problems.append("an approved drama needs a content review reference")
        if review.get("issues"):
            problems.append("an approved drama cannot carry open issues")
    return problems


def _content_review(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    checklist = instance.get("checklist") or []
    fails = [row for row in checklist if row.get("verdict") == "fail"]
    verdict = str(instance.get("verdict"))
    authenticity = instance.get("authenticity") or {}
    heritage = instance.get("heritage_check") or {}
    if verdict == "approved":
        if fails:
            problems.append("an approved review cannot carry a failed checklist item")
        if not str(authenticity.get("label") or "").strip():
            problems.append("approved content needs an authenticity label")
        if heritage.get("exclusive_claim"):
            problems.append("approved content cannot claim heritage exclusivity")
    if verdict == "rejected" and not fails and not heritage.get("exclusive_claim"):
        problems.append("a rejection needs a failed checklist item or a heritage conflict")
    if verdict == "changes_requested" and not fails:
        problems.append("a changes-requested verdict needs a failed checklist item")
    item_ids = [str(row.get("item_id")) for row in checklist]
    if len(set(item_ids)) != len(item_ids):
        problems.append("checklist item ids must be unique")
    for row in fails:
        if not str(row.get("note") or "").strip():
            problems.append(f"failed item {row.get('item_id')} needs a note")
    if authenticity.get("ai_generated") and not authenticity.get("disclosure_required"):
        problems.append("AI generated content must require disclosure")
    return problems


def _merch_spec(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    quality = instance.get("quality") or {}
    for row in quality.get("tolerances") or []:
        if float(row.get("tolerance_mm", 0)) <= 0:
            problems.append(f"tolerance {row.get('dimension')} must be positive")
    sampling = quality.get("sampling") or {}
    if float(sampling.get("aql", 0)) > 6.5:
        problems.append("an AQL above 6.5 is not an inspection plan")
    characters = [str(item) for item in instance.get("character_ids") or []]
    if len(set(characters)) != len(characters):
        problems.append("character ids must be unique")
    materials = [str(item.get("name")) for item in instance.get("materials") or []]
    if len(set(materials)) != len(materials):
        problems.append("material names must be unique")
    packaging = instance.get("packaging") or {}
    labels = " ".join(
        [str(item) for item in quality.get("inspection_points") or []]
        + [str(item) for item in packaging.get("label_requirements") or []]
    ).lower()
    if "authenticity" not in labels:
        problems.append("the packaging or inspection plan must carry the authenticity label")
    if int((instance.get("rights") or {}).get("royalty_rate_bp", 0)) > 5000:
        problems.append("a derivative royalty above 50 percent is refused")
    return problems


def _licence_documents(instance: dict, ctx: dict) -> list[str]:
    problems: list[str] = []
    documents = instance.get("documents") or []
    ids = [str(item.get("document_id")) for item in documents]
    if len(set(ids)) != len(ids):
        problems.append("licence document ids must be unique")
    signed = [item for item in documents if item.get("status") == "signed"]
    for document in signed:
        parties = {str(row.get("party")) for row in document.get("signatories") or []}
        if not {"licensor", "licensee"} <= parties:
            problems.append(
                f"document {document.get('document_id')} is signed without both parties"
            )
    categories = [str(item) for item in (instance.get("usage") or {}).get("derivative_categories") or []]
    covered = {
        str(category)
        for document in signed
        for category in document.get("derivative_categories") or []
    }
    missing = [category for category in categories if category not in covered]
    if documents and missing:
        problems.append(f"derivative categories without a signed document: {missing}")
    usage = instance.get("usage") or {}
    if usage.get("exclusivity") and instance.get("traditional_prototype_refs"):
        problems.append("exclusivity cannot be granted while traditional prototypes are referenced")
    return problems


INVARIANTS: dict[str, tuple[str, Callable[[dict, dict], list[str]]]] = {
    "INV-LIC-01": ("licensing source fields", _licensing),
    "INV-LIC-02": ("usage scope present and unique", _usage_scope),
    "INV-LIC-03": ("no exclusive claim on heritage", _traditional_prototype),
    "INV-LIC-04": ("license window", _license_window),
    "INV-MONEY-01": ("settlement totals reconcile", _settlement_totals),
    "INV-ORDER-01": ("order amounts reconcile", _order_amounts),
    "INV-REVIEW-01": ("artisan override needs a reason", _review_override),
    "INV-IP-01": ("IP licensing scope", _ip_scope),
    "INV-CUSTOM-01": ("customisation deltas reconcile", _customization),
    "INV-EDITION-01": ("edition numbering is bounded and unique", _edition),
    "INV-EDITION-02": ("collector provenance chain", _collector_provenance),
    "INV-QC-01": ("quality verdict matches the defects", _quality),
    "INV-PROMISE-01": ("delivery promise is after the order", _promise),
    "INV-DISPUTE-01": ("dispute state, evidence and resolution agree", _dispute),
    "INV-ROYALTY-01": ("royalty lines reconcile with the IP share", _royalty),
    "INV-COMP-01": ("service component boundary and dependencies", _component),
    "INV-ENT-01": ("enterprise profile assembles a coherent service layer", _enterprise_profile),
    "INV-SEO-01": ("growth site language and SEO closure", _growth_site),
    "INV-LEAD-01": ("inquiry to CRM lead consistency", _inquiry_lead),
    "INV-CHAR-01": ("dual guardian canon is distinct and licence safe", _character_bible),
    "INV-ASSET-01": ("visual asset provenance and recipe integrity", _visual_asset),
    "INV-DRAMA-01": ("short drama cut, storyboard and script agree", _short_drama),
    "INV-CONTENT-01": ("content review verdict matches its checklist", _content_review),
    "INV-MERCH-01": ("merchandise specification is manufacturable and labelled", _merch_spec),
    "INV-IP-02": ("licence document set covers every derivative category", _licence_documents),
}


def run(invariant_id: str, instance: Any, ctx: dict | None = None) -> list[str]:
    if invariant_id not in INVARIANTS:
        return [f"unknown invariant {invariant_id}"]
    if not isinstance(instance, dict):
        return []
    _, func = INVARIANTS[invariant_id]
    return func(instance, ctx or {})


def known_ids() -> list[str]:
    return sorted(INVARIANTS)
