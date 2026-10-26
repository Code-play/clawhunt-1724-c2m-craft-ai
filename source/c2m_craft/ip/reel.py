"""Sample reel: a self-contained HTML animatic rendered from the drama package.

The reel is not a video file.  It is one HTML document with the vector drawing
recipes of the frames, a CSS timeline derived from the edit decision list and the
subtitle windows, so it opens on any machine without a codec, no binary asset is
committed, and two builds are byte identical.
"""

from __future__ import annotations

import html


def _number(value) -> str:
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _layer_svg(layer: dict) -> str:
    shape = layer["shape"]
    geometry = [_number(value) for value in layer["geometry"]]
    fill = layer["fill"]
    stroke = layer["stroke"]
    width = _number(layer["stroke_width"])
    opacity = _number(float(layer["opacity_bp"]) / 10000.0)
    common = f'fill="{fill}" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"'
    if shape == "rect":
        return f'<rect x="{geometry[0]}" y="{geometry[1]}" width="{geometry[2]}" height="{geometry[3]}" {common}/>'
    if shape == "circle":
        return f'<circle cx="{geometry[0]}" cy="{geometry[1]}" r="{geometry[2]}" {common}/>'
    if shape == "ellipse":
        return f'<ellipse cx="{geometry[0]}" cy="{geometry[1]}" rx="{geometry[2]}" ry="{geometry[3]}" {common}/>'
    if shape == "line":
        return f'<line x1="{geometry[0]}" y1="{geometry[1]}" x2="{geometry[2]}" y2="{geometry[3]}" {common}/>'
    points = " ".join(f"{geometry[index]},{geometry[index + 1]}" for index in range(0, len(geometry) - 1, 2))
    if shape == "polygon":
        return f'<polygon points="{points}" {common}/>'
    path = "M " + " L ".join(f"{geometry[index]} {geometry[index + 1]}" for index in range(0, len(geometry) - 1, 2))
    if layer.get("closed"):
        path += " Z"
    return f'<path d="{path}" {common}/>'


def asset_svg(asset: dict, *, label: str = "") -> str:
    recipe = asset["recipe"]
    resolution = asset["resolution"]
    width = int(resolution["width"])
    height = int(resolution["height"])
    layers = "".join(_layer_svg(layer) for layer in recipe["layers"])
    title = f"<title>{html.escape(label or asset['asset_id'])}</title>"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="xMidYMid slice" role="img">{title}{layers}</svg>'
    )


def _keyframes(index: int, start: float, end: float, total: float) -> str:
    start_pct = max(0.0, min(100.0, start / total * 100.0))
    end_pct = max(0.0, min(100.0, end / total * 100.0))
    frames = []
    if start_pct > 0:
        frames.append("0%{opacity:0}")
    else:
        frames.append("0%{opacity:1}")
    frames.append(f"{start_pct:.4f}%{{opacity:1}}")
    frames.append(f"{end_pct:.4f}%{{opacity:0}}")
    frames.append("100%{opacity:0}")
    return f"@keyframes f{index:03d}{{" + "".join(frames) + "}"


def render(drama: dict, assets: list[dict], bible: dict, *, generated_note: str) -> str:
    by_id = {asset["asset_id"]: asset for asset in assets}
    frames = drama["storyboard"]["frames"]
    total = int(drama["cut"]["total_seconds"]) or 1
    cursor = 0
    rules: list[str] = []
    blocks: list[str] = []
    for index, frame in enumerate(frames):
        start = cursor
        end = cursor + int(frame["duration_seconds"])
        cursor = end
        rules.append(_keyframes(index, start, end, total))
        asset = by_id.get(frame["asset_ids"][0]) if frame["asset_ids"] else None
        picture = asset_svg(asset, label=frame["frame_id"]) if asset else ""
        blocks.append(
            f'<figure class="frame f{index:03d}">'
            f"{picture}"
            f'<figcaption><strong>{html.escape(frame["frame_id"])}</strong> '
            f'{html.escape(frame["shot"])} / {html.escape(frame["camera"])} '
            f'<span class="tc">{html.escape(frame["scene_id"])} '
            f'{start:02d}s-{end:02d}s</span>'
            f'<span class="cue">{html.escape(frame["visual_cue"])}</span></figcaption>'
            f'<p class="subtitle">{html.escape(frame.get("subtitle", ""))}</p>'
            "</figure>"
        )
        cursor = end
    style_rules = []
    for index in range(len(frames)):
        style_rules.append(
            f".f{index:03d}{{animation-name:f{index:03d};animation-duration:{total}s;"
            "animation-iteration-count:infinite;animation-timing-function:linear}"
        )
    title_zh = html.escape(drama["title"]["zh"])
    title_en = html.escape(drama["title"]["en"])
    label = html.escape(drama["review"]["authenticity_label"])
    status = html.escape(drama["review"]["status"])
    review_ref = html.escape(drama["review"]["content_review_ref"])
    bible_title = html.escape(bible["title"]["en"])
    note = html.escape(generated_note)
    edl_rows = "".join(
        f'<tr><td>{row["order"]}</td><td>{html.escape(row["frame_id"])}</td>'
        f'<td>{html.escape(row["in_tc"])}</td><td>{html.escape(row["out_tc"])}</td>'
        f'<td>{html.escape(row["transition"])}</td></tr>'
        for row in drama["cut"]["edl"]
    )
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Sample reel - {title_en}</title>",
            "<style>",
            "body{margin:0;background:#12151c;color:#f2ead8;font-family:Georgia,serif}",
            "header{padding:20px 24px;border-bottom:1px solid #39404f}",
            "header h1{margin:0 0 4px;font-size:1.35rem;letter-spacing:.02em}",
            "header p{margin:2px 0;color:#b9c0cf;font-size:.9rem}",
            ".stage{max-width:900px;margin:0 auto;padding:18px}",
            ".reel{position:relative;width:100%;aspect-ratio:3/4;background:#000;overflow:hidden;border:1px solid #39404f}",
            ".frame{position:absolute;inset:0;margin:0;opacity:0}",
            ".frame svg{width:100%;height:100%;display:block}",
            ".frame figcaption{position:absolute;left:12px;top:10px;right:12px;font-size:.78rem;color:#f2ead8;background:rgba(18,21,28,.72);padding:4px 8px}",
            ".frame .tc{float:right;color:#c9a227}",
            ".frame .cue{display:block;color:#b9c0cf;margin-top:2px}",
            ".frame .subtitle{position:absolute;left:8%;right:8%;bottom:6%;margin:0;text-align:center;font-size:1.05rem;line-height:1.35;background:rgba(0,0,0,.62);padding:8px 10px}",
            ".meta{display:flex;flex-wrap:wrap;gap:16px;margin:16px 0;font-size:.85rem;color:#b9c0cf}",
            "table{width:100%;border-collapse:collapse;font-size:.82rem}",
            "th,td{text-align:left;border-bottom:1px solid #2a3040;padding:4px 6px}",
            "th{color:#c9a227;font-weight:normal}",
            "footer{padding:18px 24px;color:#8f97a8;font-size:.78rem;border-top:1px solid #39404f}",
            ".label{display:inline-block;border:1px solid #c9a227;color:#c9a227;padding:2px 8px;border-radius:999px;font-size:.72rem}",
            ".frame{animation-iteration-count:infinite;animation-timing-function:linear}",
            "".join(style_rules),
            "".join(rules),
            "</style>",
            "</head>",
            "<body>",
            "<header>",
            f"<h1>{title_zh} / {title_en}</h1>",
            f"<p>{html.escape(drama['logline'])}</p>",
            f'<p><span class="label">AI-assisted</span> authenticity label, review {status}, '
            f"reference {review_ref}.</p>",
            "</header>",
            '<main class="stage">',
            '<div class="reel">',
            "".join(blocks),
            "</div>",
            '<div class="meta">',
            f"<span>duration {total}s</span>",
            f"<span>{len(frames)} frames</span>",
            f"<span>bible {html.escape(drama['bible_ref'])} - {bible_title}</span>",
            f"<span>{label}</span>",
            "</div>",
            "<h2>Edit decision list</h2>",
            "<table><thead><tr><th>#</th><th>frame</th><th>in</th><th>out</th><th>transition</th></tr></thead>",
            f"<tbody>{edl_rows}</tbody></table>",
            "</main>",
            f"<footer>{note} Frames are vector recipes from out/ip_asset_library.json; no image files are committed.</footer>",
            "</body>",
            "</html>",
            "",
        ]
    )
