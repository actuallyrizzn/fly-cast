"""React to cues using the reply bank + picker."""

from __future__ import annotations

from pathlib import Path

from flycast.bank import load_bank
from flycast.brain import FlyBrain, build_fly_brain
from flycast.picker import PickResult, pick
from flycast.prompt import Event, build_prompt
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a

DEFAULT_BANK = Path(__file__).resolve().parent.parent.parent / "fixtures" / "reply_bank.tsv"


def react(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    events: list[Event],
    *,
    bank: dict[str, list[str]] | None = None,
    message: str = "",
    lexicon: dict[str, float] | None = None,
    use_lexicon: bool = True,
) -> PickResult:
    bank = bank or load_bank(DEFAULT_BANK)
    prompt, cue = build_prompt(events, message=message)
    candidates = bank.get(cue) or bank.get("HIT") or ["…"]
    return pick(
        brain,
        tokenizer,
        prompt,
        candidates,
        lexicon=lexicon,
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
