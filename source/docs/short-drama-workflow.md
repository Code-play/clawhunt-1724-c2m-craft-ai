# Short Drama Workflow: Waking the Kiln
Production reference for SDR-0001, the sample short drama built from bible
IPB-0001. Source data lives in `config/ip/drama.json`; the generated package is
`out/short_drama_package.json`; the playable sample is `out/sample_reel.html`,
served at `/reel`.

Runtime: 67 seconds. Format: vertical 3:4 in the reel, 768 by 1024 viewBox. Genre:
mythic_short. Subtitle language: en, WebVTT style cue list.

Logline: When the kiln guardian lets the fire die, the wood guardian must carry a
half-carved panel across a silent village, and the two learn that their crafts were
always one bench.

Pipeline: script (bible IPB-0001) produces 5 scenes, 10 beats and bilingual
dialogue; storyboard produces SB-001 to SB-010 with shot and camera; the edit
decision list produces 10 rows in continuous HH:MM:SS; subtitles produce 12 English
lines that never overlap; the reel renders the frames and the review CRV-0003
approves the package. All stages are data. `python -m c2m_craft demo` rebuilds the
package and the reel; nothing is edited in a video editor.
## Script: 5 Scenes
| Scene | Int/ext | Location | Time | Cast | Beats | Seconds |
|---|---|---|---|---|---|---|
| SC-01 | EXT | Craft village lane | dawn | CHR-MU | BT-01, BT-02 | 13 |
| SC-02 | INT | Kiln workshop | night | CHR-HUO | BT-03, BT-04 | 14 |
| SC-03 | INT | Woodworking bench | night | CHR-MU | BT-05, BT-06 | 12 |
| SC-04 | INT | Shared bench | dawn | CHR-MU, CHR-HUO | BT-07, BT-08 | 13 |
| SC-05 | EXT | Village courtyard | dusk | CHR-MU, CHR-HUO | BT-09, BT-10 | 15 |

Scene total: 13 + 14 + 12 + 13 + 15 = 67 seconds.
## Script: 10 Beats
| Beat | Scene | Seconds | Action | Dialogue (en) |
|---|---|---|---|---|
| BT-01 | SC-01 | 6 | A-Mu walks the lane and finds the workshop street still dark at first light. | "The street is quieter than it should be." |
| BT-02 | SC-01 | 7 | The kiln door stands cold and open, and A-Mu reads the silence as a refusal. | "A-Huo did not light the kiln. That is not forgetfulness." |
| BT-03 | SC-02 | 8 | A-Huo sits with a cold kiln and a single surviving test tile. | "If the fire rests, the trees on the mountain live one more season." |
| BT-04 | SC-02 | 6 | A-Huo turns the test tile and sees a crackle no one has fired before. | "The kiln does not argue; it answers in colour." |
| BT-05 | SC-03 | 7 | A-Mu sets down a commissioned panel that needs fire to finish the inlay. | "Without fire this panel is only wood." |
| BT-06 | SC-03 | 5 | The buyer leaves without the commission; A-Mu lets the grain stay unfinished. | "Measure twice, and let the wood keep the second measure." |
| BT-07 | SC-04 | 6 | A-Huo carries the kiln fire to the wood bench instead of asking for permission. | "I brought the fire. I will not argue." |
| BT-08 | SC-04 | 7 | The two guardians set one bench where carving and glazing share the same surface. | "Then one bench, two pairs of hands." / "The fire waits for the wood, the wood waits for the fire." |
| BT-09 | SC-05 | 8 | The first fired panel comes out of the kiln with the wood grain still visible. | "The grain survived, and the colour stayed." |
| BT-10 | SC-05 | 7 | The two guardians teach the finishing step to the village apprentices together. | "Keep the student, keep the craft." / "Two streets, one village." |

Every dialogue line exists in both languages in the script record. The English
track is the one rendered in the reel subtitles.
## Storyboard: SB-001 to SB-010
| Frame | Scene | Shot | Camera | Seconds | Visual cue |
|---|---|---|---|---|---|
| SB-001 | SC-01 | wide | static | 6 | Empty lane at first light, workshop doors still closed |
| SB-002 | SC-01 | medium | pan | 7 | Cold kiln door, hooded guardian in the doorway |
| SB-003 | SC-02 | close | static | 8 | Crackled test tile in a gloved hand beside the cold kiln |
| SB-004 | SC-02 | insert | push_in | 6 | The crackle pattern catching the last ember light |
| SB-005 | SC-03 | medium | static | 7 | Half-carved panel on the bench, chisel set down |
| SB-006 | SC-03 | close | handheld | 5 | Guardian's hand flat on the unfinished grain, buyer out of frame |
| SB-007 | SC-04 | wide | pan | 6 | Fire guardian crossing the empty street carrying a bellows pipe |
| SB-008 | SC-04 | medium | static | 7 | Two silhouettes at one bench, tools on the shared surface |
| SB-009 | SC-05 | insert | push_in | 8 | Fired panel lifted from the kiln, grain visible under the glaze |
| SB-010 | SC-05 | wide | orbit | 7 | Apprentices around the bench, two guardians teaching the finishing step |

Frame durations sum to 67 seconds, and each scene's frames sum to the scene
duration: SC-01 13, SC-02 14, SC-03 12, SC-04 13, SC-05 15. Camera vocabulary is
deliberately small: static, pan, push_in, handheld, orbit. A static frame carries
the silence; a push_in carries a decision.
## Edit Decision List
Timecode format is HH:MM:SS. Every row starts where the previous one ended, and the
last row ends at 00:01:07.

| # | Frame | In | Out | Transition |
|---|---|---|---|---|
| 1 | SB-001 | 00:00:00 | 00:00:06 | cut |
| 2 | SB-002 | 00:00:06 | 00:00:13 | cut |
| 3 | SB-003 | 00:00:13 | 00:00:21 | cut |
| 4 | SB-004 | 00:00:21 | 00:00:27 | cut |
| 5 | SB-005 | 00:00:27 | 00:00:34 | cut |
| 6 | SB-006 | 00:00:34 | 00:00:39 | cut |
| 7 | SB-007 | 00:00:39 | 00:00:45 | cut |
| 8 | SB-008 | 00:00:45 | 00:00:52 | cut |
| 9 | SB-009 | 00:00:52 | 00:01:00 | cut |
| 10 | SB-010 | 00:01:00 | 00:01:07 | fade |

Nine cuts and one fade. The fade is the only transition: the story earns a soft
exit, not a montage.
## Subtitle Track
Language en, 12 lines. Times are within the 67 second cut and never overlap.

| # | In | Out | Text |
|---|---|---|---|
| 1 | 00:00:00 | 00:00:06 | The street is quieter than it should be. |
| 2 | 00:00:06 | 00:00:13 | A-Huo did not light the kiln. That is not forgetfulness. |
| 3 | 00:00:13 | 00:00:21 | If the fire rests, the trees on the mountain live one more season. |
| 4 | 00:00:21 | 00:00:27 | The kiln does not argue; it answers in colour. |
| 5 | 00:00:27 | 00:00:34 | Without fire this panel is only wood. |
| 6 | 00:00:34 | 00:00:39 | Measure twice, and let the wood keep the second measure. |
| 7 | 00:00:39 | 00:00:45 | I brought the fire. I will not argue. |
| 8 | 00:00:45 | 00:00:48 | Then one bench, two pairs of hands. |
| 9 | 00:00:48 | 00:00:52 | The fire waits for the wood, the wood waits for the fire. |
| 10 | 00:00:52 | 00:01:00 | The grain survived, and the colour stayed. |
| 11 | 00:01:00 | 00:01:03 | Keep the student, keep the craft. |
| 12 | 00:01:03 | 00:01:07 | Two streets, one village. |

Lines 8 and 9 split one frame because two characters speak in BT-08. Lines 11 and
12 split the final frame for the same reason. Splitting inside a shot is allowed;
overlapping is not.
## INV-DRAMA-01
This invariant is what makes the script, the storyboard and the cut agree. It
refuses a package when any of the following is true:

- Scene ids are not unique.
- A scene's beat durations do not sum to its declared duration.
- The scene durations do not sum to `cut.total_seconds`.
- A dialogue line names a character not listed in that scene.
- Storyboard frame ids are not unique, or frame durations do not sum to the cut.
- A frame cites an unknown scene, or uses an asset outside that scene's asset set.
- A scene's frames do not sum to the scene duration.
- The edit decision list does not follow the storyboard order exactly once.
- EDL rows are not numbered from one without gaps.
- An EDL timecode is invalid, does not start where the previous row ended, or has a
  non-positive duration.
- The EDL does not end at the cut total.
- A subtitle has an invalid or non-positive span, runs past the cut, or overlaps
  the previous line.
- An approved drama has no content review reference, or carries open issues.

A single changed beat duration therefore forces a new frame duration, a new EDL row
and possibly a new subtitle span. That is the point: the three documents cannot
drift apart silently. Negative coverage exists as
`samples/contracts/negative/short-drama-timecode-gap.json`, a documented mutation of
SDR-0001 with a deliberate timecode gap that must be rejected.
## Review, Authenticity and Reel
Review CRV-0003, subject SDR-0001, template drama, verdict approved, no open
issues. Reviewer: Content review desk. Heritage note: the drama references regional
joinery and glaze techniques as setting, not as an origin claim. Authenticity label:
"AI-assisted script and storyboard draft, human reviewed; synthetic characters."
The label appears in the package and in the reel header. The review checklist covers
script structure, bilingual dialogue, heritage non-exclusivity, subtitle sync, the
authenticity label and the no-ritual-object rule.

`out/sample_reel.html` is the self-contained reel, served at `/reel`. It has ten
inline SVG figures, one per storyboard frame, drawn from the vector recipes in
`out/ip_asset_library.json`; a 67 second CSS keyframe cycle with one opacity track
per frame and the same in and out points as the EDL; a per-frame caption with frame
id, shot, camera, scene and seconds, plus the English subtitle line; a visible EDL
table; and a header authenticity label naming CRV-0003. There is no image file, no
font, no external stylesheet, no video element, no audio element, no codec and no
network request. The page opens from disk or from the local server. This is a
reviewable animatic, not a rendered film: a client can see timing, framing and
subtitle load without a media pipeline, and the repository stays free of binary
assets.
## Change Procedure
1. Edit `config/ip/drama.json`.
2. Run `python -m c2m_craft demo`.
3. If INV-DRAMA-01 rejects the package, fix durations, frames, EDL or subtitles
   until the totals agree at 67 seconds.
4. Re-run `python tests/test_runner.py`.
5. Re-run `python verify/run_verification.py` before delivery.
6. Update this document if a public value changed.
