# Contributing

Domain banks and cues live under `examples/`. Shared mouth code lives under `src/flycast/`.

## License

| You contribute | License |
|----------------|---------|
| Code | **AGPL-3.0-or-later** |
| Docs / fixtures / profiles | **CC-BY-SA-4.0** (name third-party terms in the PR when they apply) |

[LICENSING.md](../LICENSING.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Coverage gate: **≥90%**.

## Where it goes

| Change | Path |
|--------|------|
| Shared mouth / connectome / guard / CLI | `src/flycast/` + `tests/` |
| Clone Hero / Fly Hero | `examples/fly_hero/` |
| Your domain | `examples/<name>/` (copy fly_hero) |
| Docs | `docs/` |

Cue vocabulary for a product belongs in that product’s `profile.toml`.

## Honesty

PRs that change training or report English quality include fly vs scramble vs no-fly (or state which control applies), with numbers in `examples/.../docs/RESULTS.md` or the matching example results file.

## PR bar

Small diffs. Tests for new branches. Credentials belong in local vaults, not the repo.

Issues: [actuallyrizzn/fly-cast](https://github.com/actuallyrizzn/fly-cast).
