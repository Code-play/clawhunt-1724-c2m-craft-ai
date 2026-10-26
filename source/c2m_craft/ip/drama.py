"""Short drama pipeline: script, storyboard, edit decision list, subtitles, review.

Durations live in the beats; the scene duration, the frame duration, the edit
decision list timecodes and the subtitle windows are all computed from them.  The
cut therefore cannot disagree with the script, which is the whole point of shipping
the workflow as data instead of a folder of files.
"""

from __future__ import annotations

from ..core.errors import ValidationFailed


def timecode(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _scene_record(scene: dict) -> dict:
    beats = [
        {
            "beat_id": beat["beat_id"],
            "summary": beat["summary"],
            "duration_seconds": int(beat["duration_seconds"]),
            "dialogue": list(beat.get("dialogue") or []),
        }
        for beat in scene["beats"]
    ]
    assets = set(scene.get("assets") or [])
    for beat in scene["beats"]:
        for asset in beat.get("assets") or []:
            assets.add(asset)
    return {
        "scene_id": scene["scene_id"],
        "heading": dict(scene["heading"]),
        "duration_seconds": sum(beat["duration_seconds"] for beat in beats),
        "characters": list(scene["characters"]),
        "beats": beats,
        "assets": sorted(assets),
    }


def _frames(config: dict) -> list[dict]:
    frames: list[dict] = []
    for scene in config["scenes"]:
        for beat in scene["beats"]:
            plan = config["shots"].get(beat["beat_id"])
            if plan is None:
                raise ValidationFailed(f"beat {beat['beat_id']} has no shot plan")
            dialogue = beat.get("dialogue") or []
            subtitle = (
                str(dialogue[0]["line"][config["subtitle_language"]])
                if dialogue
                else str(beat["summary"])[:120]
            )
            frames.append(
                {
                    "frame_id": f"SB-{len(frames) + 1:03d}",
                    "scene_id": scene["scene_id"],
                    "shot": plan["shot"],
                    "camera": plan["camera"],
                    "duration_seconds": int(beat["duration_seconds"]),
                    "visual_cue": plan["visual_cue"],
                    "asset_ids": list(beat.get("assets") or []),
                    "subtitle": subtitle,
                }
            )
    return frames


def _subtitles(config: dict, scenes: list[dict], total: int) -> list[dict]:
    language = config["subtitle_language"]
    rows: list[dict] = []
    cursor = 0
    for scene in scenes:
        for beat in scene["beats"]:
            duration = int(beat["duration_seconds"])
            lines = beat.get("dialogue") or []
            if lines:
                remaining = duration
                for index, line in enumerate(lines):
                    share = remaining if index == len(lines) - 1 else max(1, duration // len(lines))
                    share = min(share, remaining)
                    if share <= 0:
                        break
                    rows.append(
                        {
                            "in_tc": timecode(cursor),
                            "out_tc": timecode(cursor + share),
                            "text": str(line["line"][language]),
                        }
                    )
                    cursor += share
                    remaining -= share
            cursor += remaining
    if cursor != total:
        raise ValidationFailed(f"subtitle windows end at {cursor}s but the cut is {total}s")
    return rows


def build(store, settings, reviews: dict[str, dict]) -> dict:
    config = settings.json("config/ip/drama.json")
    scenes = [_scene_record(scene) for scene in config["scenes"]]
    frames = _frames(config)
    total = sum(frame["duration_seconds"] for frame in frames)
    edl = []
    clock = 0
    for index, frame in enumerate(frames):
        edl.append(
            {
                "order": index + 1,
                "frame_id": frame["frame_id"],
                "in_tc": timecode(clock),
                "out_tc": timecode(clock + frame["duration_seconds"]),
                "transition": "fade" if index == len(frames) - 1 else "cut",
            }
        )
        clock += frame["duration_seconds"]
    review = dict(config["review"])
    if review["content_review_ref"] not in reviews:
        raise ValidationFailed("the drama review cites an unknown content review")
    record = {
        "drama_id": config["drama_id"],
        "title": config["title"],
        "bible_ref": config["bible_ref"],
        "logline": config["logline"],
        "genre": config["genre"],
        "script": {"scenes": scenes},
        "storyboard": {"frames": frames},
        "cut": {
            "total_seconds": total,
            "timecode_format": "HH:MM:SS",
            "edl": edl,
            "tracks": [
                {
                    "kind": "video",
                    "source": "out/sample_reel.html (vector frame compilation)",
                    "gain_db": 0,
                },
                {
                    "kind": "voice",
                    "source": "bilingual voice take, synthetic placeholder",
                    "gain_db": -3,
                },
                {
                    "kind": "music",
                    "source": "original motif score, synthetic placeholder",
                    "gain_db": -18,
                },
                {
                    "kind": "subtitle",
                    "source": f"subtitle track {config['subtitle_language']}",
                    "gain_db": 0,
                },
            ],
        },
        "subtitles": {
            "language": config["subtitle_language"],
            "lines": _subtitles(config, scenes, total),
            "format": "vtt",
        },
        "review": {
            "status": review["status"],
            "reviewer": review["reviewer"],
            "content_review_ref": review["content_review_ref"],
            "authenticity_label": review["authenticity_label"],
            "issues": list(review.get("issues") or []),
        },
        "created_at": config["created_at"],
    }
    store.assert_valid("short_drama", record)
    return record


def dialogue_cues(drama: dict, language: str = "en") -> list[dict]:
    """Flatten the script into timed dialogue cues for the reel."""
    cues: list[dict] = []
    cursor = 0
    for scene in drama["script"]["scenes"]:
        for beat in scene["beats"]:
            lines = beat.get("dialogue") or []
            duration = int(beat["duration_seconds"])
            if lines:
                remaining = duration
                for index, line in enumerate(lines):
                    share = remaining if index == len(lines) - 1 else max(1, duration // len(lines))
                    share = min(share, remaining)
                    if share <= 0:
                        break
                    cues.append(
                        {
                            "at": cursor,
                            "duration": share,
                            "character_id": line["character_id"],
                            "text": str(line["line"][language]),
                        }
                    )
                    cursor += share
                    remaining -= share
            cursor += remaining
    return cues


def summary(drama: dict) -> dict:
    frames = drama["storyboard"]["frames"]
    return {
        "drama_id": drama["drama_id"],
        "scenes": len(drama["script"]["scenes"]),
        "beats": sum(len(scene["beats"]) for scene in drama["script"]["scenes"]),
        "frames": len(frames),
        "total_seconds": drama["cut"]["total_seconds"],
        "subtitle_lines": len(drama["subtitles"]["lines"]),
        "status": drama["review"]["status"],
        "shots": sorted({frame["shot"] for frame in frames}),
    }
