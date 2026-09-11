# Dual licensing — Fly Cast

| Material | License | Typical paths |
|----------|---------|----------------|
| **Software / source code** | **AGPL-3.0-or-later** ([full text](licenses/AGPL-3.0.txt)) | `src/flycast/**/*.py`, `tests/**/*.py`, `tools/**/*.py`, overlay HTML/JS/CSS that ships with the app, entry points |
| **Documentation and other non-code** | **CC-BY-SA-4.0** ([full text](licenses/CC-BY-SA-4.0.txt)) | `README.md`, `docs/**`, `examples/**/*.md`, `examples/**/profile.toml`, banks / lexicons / event fixtures, authored `fixtures/*.txt`, this file |

Root [`LICENSE`](LICENSE) is a pointer. Full texts sit in [`licenses/`](licenses/).

SPDX: code `AGPL-3.0-or-later`; docs `CC-BY-SA-4.0`.

## Why AGPL on the code

This mouth can sit on a live path (overlay now, chat adapters later). AGPL means a modified network service still owes users corresponding source.

## Why CC-BY-SA on docs and fixtures

Prose and profiles should remix with attribution and share-alike without dragging documentation under AGPL.

## Mixed packages

Executable / library source → AGPL. Narrative, TSV banks, TOML profiles, markdown → CC-BY-SA. When in doubt, split by portion.

## Third-party material

| Artifact | Upstream | Notes |
|----------|----------|--------|
| `src/flycast/data/` larva CSVs | **CC-BY** (Winding et al. 2023 via Netzschleuder) | [data README](src/flycast/data/README.md) — keep attribution |
| `fixtures/tinystories_subset.txt` | **CDLA-Sharing-1.0** (TinyStories) | Honesty-gate excerpt |

## Copyright

Copyright (c) 2026 Mark Hopkins / Decision Science Corp and contributors, unless a file says otherwise.
