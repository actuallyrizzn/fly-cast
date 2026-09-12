"""Additive free-write path — Level A checkpoint generate (picker stays default)."""

from __future__ import annotations

from pathlib import Path

from flycast.brain import FlyBrain
from flycast.checkpoint import default_checkpoint_path, load_level_a
from flycast.generate import generate
from flycast.picker import PickResult
from flycast.profile import Profile, default_profile
from flycast.prompt import Event, build_prompt
from flycast.tokenizer import Tokenizer


def resolve_checkpoint(path: Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    import os

    env = os.environ.get("FLYCAST_WRITE_CKPT", "").strip()
    if env:
        return Path(env)
    return default_checkpoint_path()


def load_writer(checkpoint: Path | None = None) -> tuple[FlyBrain, Tokenizer, Path]:
    ckpt = resolve_checkpoint(checkpoint)
    if not ckpt.is_file():
        raise FileNotFoundError(
            f"free-write checkpoint missing: {ckpt} "
            "(run: python tools/climb_reaction_freewrite.py)"
        )
    brain, tok = load_level_a(ckpt)
    return brain, tok, ckpt


def freewrite(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    events: list[Event],
    *,
    profile: Profile | None = None,
    max_tokens: int = 16,
    min_tokens: int = 3,
    temperature: float = 0.7,
    seed: int = 0,
) -> PickResult:
    """Generate a continuation under the cue prompt (mode=wrote)."""
    profile = profile or default_profile()
    prompt, _cue = build_prompt(events, known_cues=profile.known_cues)
    text = generate(
        brain,
        tokenizer,
        prompt,
        max_tokens=max_tokens,
        min_tokens=min_tokens,
        temperature=temperature,
        seed=seed,
    ).strip()
    if not text:
        text = "…"
    return PickResult(text=text, score=0.0, mode="wrote", index=0)
