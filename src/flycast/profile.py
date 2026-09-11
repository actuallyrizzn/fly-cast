"""Product profile — cues, banks, and paths for a domain mouth.

The core library has no Clone Hero / Fly Hero hard-wiring. A profile (TOML)
points at reply banks, lexicons, and cue lists. The flagship profile ships
under ``examples/fly_hero/``.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PROFILE_DIR = _REPO_ROOT / "examples" / "fly_hero"


@dataclass(frozen=True)
class Profile:
    name: str
    root: Path
    bank_path: Path
    lexicon_path: Path
    events_demo_path: Path | None = None
    known_cues: frozenset[str] = field(default_factory=frozenset)
    interesting_cues: frozenset[str] = field(default_factory=frozenset)
    bank_required_cues: frozenset[str] = field(default_factory=frozenset)
    hit_react_detail: str = "STRUM"
    lexicon_scale: float = 0.85
    description: str = ""

    def should_react(self, cue: str, detail: str = "") -> bool:
        cue_u = cue.strip().upper()
        if cue_u in self.interesting_cues:
            return True
        if cue_u == "HIT" and self.hit_react_detail:
            return detail.strip().upper() == self.hit_react_detail.upper()
        return False


def _resolve(root: Path, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else (root / p).resolve()


def load_profile(path: Path | str | None = None) -> Profile:
    """Load a profile directory or ``profile.toml`` path.

    Resolution order when ``path`` is None:
    1. ``FLYCAST_PROFILE`` env (directory or toml file)
    2. ``examples/fly_hero`` in the repo (flagship)
    """
    if path is None:
        env = os.environ.get("FLYCAST_PROFILE", "").strip()
        path = Path(env) if env else _DEFAULT_PROFILE_DIR
    else:
        path = Path(path)

    if path.is_dir():
        root = path.resolve()
        toml_path = root / "profile.toml"
    else:
        toml_path = path.resolve()
        root = toml_path.parent

    if not toml_path.is_file():
        raise FileNotFoundError(f"profile.toml not found at {toml_path}")

    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    paths = data.get("paths", {})
    cues = data.get("cues", {})
    picker = data.get("picker", {})

    bank = paths.get("bank", "fixtures/reply_bank.tsv")
    lexicon = paths.get("lexicon", "fixtures/fly_lexicon.tsv")
    events_demo = paths.get("events_demo")

    known = frozenset(str(c).upper() for c in cues.get("known", []))
    interesting = frozenset(str(c).upper() for c in cues.get("interesting", []))
    bank_req_raw = cues.get("bank_required")
    if bank_req_raw is None:
        # Default: every known cue except optional lane markers must have bank lines.
        bank_required = frozenset(c for c in known if not c.startswith("LANE_"))
    else:
        bank_required = frozenset(str(c).upper() for c in bank_req_raw)

    return Profile(
        name=str(data.get("name", root.name)),
        root=root,
        bank_path=_resolve(root, bank),
        lexicon_path=_resolve(root, lexicon),
        events_demo_path=_resolve(root, events_demo) if events_demo else None,
        known_cues=known,
        interesting_cues=interesting,
        bank_required_cues=bank_required,
        hit_react_detail=str(cues.get("hit_react_detail", "STRUM") or ""),
        lexicon_scale=float(picker.get("lexicon_scale", 0.85)),
        description=str(data.get("description", "")),
    )


def default_profile() -> Profile:
    return load_profile(None)
