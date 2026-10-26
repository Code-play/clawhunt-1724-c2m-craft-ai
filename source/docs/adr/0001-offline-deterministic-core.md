# ADR 0001 - offline, deterministic core

## Status
Accepted for M1.

## Context
The brief requires that re-running verification yields the same conclusions, and
the delivery must run on a clean machine with a one-command start. The prototype
also has to work before any client cloud account, model key or network access
exists.

## Decision
The whole repository is standard-library Python, offline, and deterministic:

- the logical clock is rooted at `config/site.json -> as_of`, advanced by one
  minute per mutation; no wall-clock call exists anywhere;
- concept generation is seeded by `sha256(prompt|industry|style|palette|index)`;
- JSON is canonicalised (sorted keys, no insignificant whitespace, LF) before
  hashing or writing;
- no HTTP client is imported; the model boundary is a protocol with an offline
  implementation.

## Consequences
Verification can compare two demo runs byte for byte, which is the strongest
reproducibility statement available without a test harness. The prototype cannot
show off a real generative model, so the limitation is stated in the UI, the
README and DELIVERY.md. M2 adds a real adapter on the same boundary; because the
interface is already declared, the call sites do not change.

## Alternatives rejected
- "Use the real model API but cache the responses": the cache would be a secret
  dependency and the first run would still need network access.
- "Pin the clock in tests only": the demo would still produce different files on
  each run, so determinism could not be verified against the shipped artifact.
