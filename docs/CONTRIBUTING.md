# Contributing

Keep the core generic. Domain banks and cues go under `examples/`.

## License

| You contribute | License |
|----------------|---------|
| Code | **AGPL-3.0-or-later** |
| Docs / fixtures / profiles | **CC-BY-SA-4.0** (call out third-party terms in the PR) |

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

No hard-coded one-game cue list in the library. Use `profile.toml`.

## Honesty

Training or “better English from the wiring” PRs:

1. Report fly vs scramble vs no-fly (or say why a control does not apply).
2. Do not bury a losing fly condition.
3. Update `examples/.../docs/RESULTS.md` (or your example’s results) — numbers beat slogans.

## PR bar

Small diffs. Tests for new branches. No secrets. No “we taught a fly English” without a table. No insect-cosplay lexicon in the flagship profile.

Issues: [actuallyrizzn/fly-cast](https://github.com/actuallyrizzn/fly-cast).
