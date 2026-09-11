# Contributing

Thanks for looking. Fly Cast is meant to be forked: keep the **core** generic and put domain stuff under **`examples/`**.

## License

By contributing you agree that:

- **Code** contributions are licensed under **AGPL-3.0-or-later**.
- **Docs / fixtures / profiles** you add are licensed under **CC-BY-SA-4.0**, unless they are clearly third-party material with their own terms (call that out in the PR).

See [LICENSING.md](../LICENSING.md).

## Dev setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Coverage gate is **≥90%** (`pyproject.toml`).

## Where to put changes

| Change | Put it here |
|--------|-------------|
| Shared mouth / connectome / guard / CLI | `src/flycast/` + `tests/` |
| Clone Hero / Fly Hero banks, cues, demos | `examples/fly_hero/` |
| Your new domain | new `examples/<name>/` (copy fly_hero) |
| Architecture / how-to prose | `docs/` |

Do **not** hard-code a single game’s cue list into the library. Use `profile.toml`.

## Honesty bar

If you change training or claim better English from the wiring:

1. Report fly vs scramble vs no-fly (or say why a control does not apply).
2. Do not bury a losing fly condition.
3. Prefer updating `examples/.../docs/RESULTS.md` (or a new example’s results) over marketing copy alone.

## PR hygiene

- Small, focused diffs.
- Tests for new branches.
- No secrets, no platform credentials, no “we taught a fly English” without numbers.
- Keep insect-cosplay lexicons out of the flagship profile.

## Questions

Open an issue on [actuallyrizzn/fly-cast](https://github.com/actuallyrizzn/fly-cast) with the profile or module you care about.
