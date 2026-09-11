# Product profiles

A **profile** is a directory with a `profile.toml` plus fixtures. The core library loads it and stays domain-agnostic.

Resolution order for `load_profile(None)` / CLI defaults:

1. `--profile PATH` (sets `FLYCAST_PROFILE`)
2. Environment `FLYCAST_PROFILE` (directory or `profile.toml`)
3. Repo flagship: `examples/fly_hero/`

## `profile.toml` shape

```toml
name = "your_thing"
description = "One line for humans."

[paths]
# Relative to the profile directory.
bank = "fixtures/reply_bank.tsv"
lexicon = "fixtures/fly_lexicon.tsv"
events_demo = "fixtures/events_demo.jsonl"   # optional

[cues]
known = ["EVENT", "CHAT", "HIT"]             # prompt / bank vocabulary
interesting = ["EVENT", "CHAT"]            # live/replay triggers
# hit_react_detail = "STRUM"                 # also react when cue=HIT and detail matches
# bank_required = ["EVENT", "CHAT"]          # optional; default = known minus LANE_*

[picker]
lexicon_scale = 0.85
```

### Reply bank (`cue <TAB> text`)

At least a few lines per cue you care about. Lines may start with `[synth]` (stripped on load).

### Lexicon (`phrase <TAB> weight`)

Lowercase phrases; higher weight → soft bonus when that phrase appears in a candidate. Prefer mouth taste over insect cosplay.

## Fork checklist

1. Copy `examples/fly_hero/` → `examples/your_thing/`.
2. Edit `profile.toml` (name, cues, paths).
3. Replace bank / lexicon / demo events.
4. Run:

```bash
export FLYCAST_PROFILE=examples/your_thing
flycast replay "$FLYCAST_PROFILE/fixtures/events_demo.jsonl"
pytest   # still uses fly_hero fixtures unless you add your own tests
```

Or one-shot: `flycast --profile examples/your_thing replay path/to/events.jsonl`.

Leave `src/flycast/` alone unless you are changing shared mouth behavior for everyone.

## License note

Profile TOML, banks, lexicons, and example markdown are **CC-BY-SA-4.0**. Library code that loads them is **AGPL-3.0-or-later**. See [LICENSING.md](../LICENSING.md).
