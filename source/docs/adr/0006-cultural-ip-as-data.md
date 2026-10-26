# ADR 0006 - Cultural IP is data, and the sample reel is an HTML animatic

Status: accepted (milestone 4).

## Context

The brief asks for dual guardian characters, a character design manual and visual
asset library, one short-drama workflow with a sample clip, licensing templates and
merchandise specifications, with content review and authenticity labelling. The
delivery must stay reproducible on a clean machine with the Python standard library
and no binary assets in the repository.

## Decision

1. **Canon as data.** `config/ip/characters.json` holds the two guardians, the world
   rules, motifs, palettes, taboos, props, voice, arcs and heritage references. The
   `character_bible` contract validates it and an invariant refuses two guardians
   sharing an element or a review, and refuses any exclusive heritage claim.
2. **Visual assets as vector recipes.** `config/ip/visuals.json` declares the
   variants; the builder emits layered vector recipes with palette tokens resolved
   per character. Each `visual_asset` record carries a SHA-256 checksum over its
   identity and recipe, so verification can prove a build is unchanged without
   storing an image.
3. **Drama as computed time.** Durations live in the beats. Scene durations, frames,
   edit decision list timecodes and subtitle windows are all derived from them, and
   `INV-DRAMA-01` refuses a script, storyboard and cut that disagree.
4. **The sample reel is generated HTML.** `out/sample_reel.html` embeds the frame
   SVGs, a CSS timeline computed from the EDL and the subtitle band. It opens on any
   machine with no codec, no external request and no binary file, and two builds are
   byte identical. A real video export, if the client wants one, would be an
   additional renderer over the same package, not a replacement.
5. **Licensing as a document set.** The `ip_license` contract carries the signed
   documents, their signatories, their checksums and the merchandise specification
   references. `INV-IP-02` refuses a derivative category without a signed document;
   `INV-MERCH-01` refuses a specification without the authenticity label.
6. **Review before ship.** Every artefact cites a `content_review` record with a
   checklist, the reviewer role, the AIGC authenticity block and the heritage check;
   `INV-CONTENT-01` refuses an approval that hides a failed item.

## Consequences

- No binary assets, no codec dependency, no hidden state: the whole IP pipeline is
  reviewable as data and rebuildable by one command.
- The authenticity label is part of the record, not a promise in prose, so the
  labelling requirement is machine-checked.
- The reel is an animatic, not a final film; the workflow, the cut and the review
  record are complete, and a production renderer can consume the same package.
