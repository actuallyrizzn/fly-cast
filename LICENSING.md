# Dual licensing — Fly Cast

This project uses **two licenses**, same pattern as Broca, SMCP, and the rest of Mark’s public stack:

| Material | License | Typical paths |
|----------|---------|----------------|
| **Software / source code** | **GNU Affero General Public License v3.0 or later** ([AGPL-3.0-or-later](licenses/AGPL-3.0.txt)) | `src/flycast/**/*.py`, `tests/**/*.py`, `tools/**/*.py`, overlay HTML/JS/CSS that ships as part of the running app, `pyproject.toml` entry points |
| **Documentation and other non-code** | **Creative Commons Attribution-ShareAlike 4.0 International** ([CC-BY-SA-4.0](licenses/CC-BY-SA-4.0.txt)) | `README.md`, `docs/**`, `examples/**/*.md`, `examples/**/profile.toml`, reply banks / lexicons / event fixtures under `examples/`, generic `fixtures/*.txt` we authored, design notes, this file |

Full legal texts live under [`licenses/`](licenses/). The root [`LICENSE`](LICENSE) file is a short pointer.

SPDX for code files may say `AGPL-3.0-or-later`. SPDX for docs may say `CC-BY-SA-4.0`.

## Why AGPL for the code

Fly Cast is a mouth that can sit on a live path (overlay server, later chat adapters). AGPL keeps modified network services obliged to offer corresponding source to their users.

## Why CC-BY-SA for docs and fixtures

Prose, architecture notes, and product profiles should be easy to fork and remix with attribution and share-alike, without dragging documentation derivatives under AGPL.

## Combined works

If you distribute a package that mixes code and docs, apply each license to its portion. When in doubt: executable / library source → AGPL; narrative, TSV banks, TOML profiles, markdown → CC-BY-SA.

## Third-party material (not our dual license)

| Artifact | Upstream license | Notes |
|----------|------------------|--------|
| Larva connectome CSVs under `src/flycast/data/` | **CC-BY** (Winding et al. 2023 via Netzschleuder) | See [`src/flycast/data/README.md`](src/flycast/data/README.md). Not CC-BY-SA; keep attribution. |
| `fixtures/tinystories_subset.txt` | **CDLA-Sharing-1.0** (TinyStories) | Training corpus excerpt for honesty gates; not our authorship. |

## Copyright

Copyright (c) 2026 Mark Hopkins / Decision Science Corp and contributors, unless a file says otherwise.
