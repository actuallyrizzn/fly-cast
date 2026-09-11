"""React to cues using the reply bank + picker."""

from __future__ import annotations

from flycast.bank import load_bank
from flycast.brain import FlyBrain, build_fly_brain
from flycast.picker import PickResult, pick
from flycast.profile import Profile, default_profile
from flycast.prompt import Event, build_prompt
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a


def react(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    events: list[Event],
    *,
    bank: dict[str, list[str]] | None = None,
    message: str = "",
    lexicon: dict[str, float] | None = None,
    use_lexicon: bool = True,
    profile: Profile | None = None,
) -> PickResult:
    profile = profile or default_profile()
    bank = bank or load_bank(profile.bank_path)
    prompt, cue = build_prompt(events, message=message, known_cues=profile.known_cues)
    candidates = bank.get(cue) or bank.get("HIT") or bank.get("EVENT") or ["…"]
    return pick(
        brain,
        tokenizer,
        prompt,
        candidates,
        lexicon=lexicon,
        lexicon_scale=profile.lexicon_scale,
        use_lexicon=use_lexicon,
    )


def demo_brain() -> tuple[FlyBrain, Tokenizer]:
    lines = [
        "missed a note on green.",
        "nice catch on the hit.",
        "streak going strong.",
        "song over that is a wrap.",
    ]
    tok = Tokenizer.build(lines, max_vocab=200)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=32)
    train_fly_level_a(brain, tok, lines, max_pairs=200)
    return brain, tok
