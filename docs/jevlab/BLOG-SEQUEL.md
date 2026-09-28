My feed spent last week telling me Julia-1 was the tiny decision model that changes everything. A 144-million-parameter model from Supersonic Labs, runs on a CPU, Apache licensed, beats the hosted giants on their own benchmarks. So I put it on the same scoreboard where Venice’s Jev, ConvAI’s Laya, and our fruit-fly connectome model had just gone head to head.

It lost. Badly. Then we went looking for anything it was actually good at, using its own model card as the map, and we had to dig hard to find one thing. Along the way we found out why the card reads so much better than the model runs.

## Round one: the scoreboard everybody else already played on

Same four public tests as last week, same laptop — a $350 Lenovo with no GPU. Julia ran cold, exactly as published, same as Jev and Laya. (Flybrain fits a small readout layer on each test’s practice examples. That’s how it works, and we said so last week.)

Julia can only handle menus up to about twenty options, so it sat out the 151-option intent test.

| Test | Rows | Julia | Jev | Laya | Flybrain |
|---|---:|---:|---:|---:|---:|
| Movie-review sentiment | 872 | 57.0% | **94.6%** | 90.6% | 76.5% |
| Ten phone intents | 300 | 56.3% | **99.3%** | 97.3% | 94.7% |
| Eclipse bug severity (titles only) | 2,000 | 27.7% | 49.1% | 29.5% | **78.4%** |
| 150 intents + “none of these” | 5,500 | — | 91.7%† | 60.6% | 64.6% |

† Jev’s 150-intent score covers the 4,060 rows it finished before the API stopped answering.

Movie-review sentiment is a two-option question. Positive or negative. A coin gets 50%. Julia got 57%. On ten phone intents — alarm, timer, weather, the stuff every voice assistant has handled for a decade — it got 56%, while Jev hit 99%.

That’s the model everybody was losing their minds over.

## Round two: we played on its home field

Don’t get me wrong — a model can be bad at general work and great at a specialty. That’s allowed. So I went to Supersonic’s own model card, pulled every benchmark they claim as a win, and ran those. Their turf, their datasets, all four models.

Here’s the first thing we noticed. Their AG News and Emotion headline numbers come from **100-row pilots**. The full test sets are 7,600 and 2,000 rows. So we ran the full sets.

| Test | Their card | Our run (full set) | Jev | Laya | Flybrain |
|---|---:|---:|---:|---:|---:|
| AG News (news topics) | 94% on 100 rows | 85.1% on 7,600 | 88.4% | **92.9%** | 88.3% |
| Emotion | 86% on 100 rows | **79.9%** on 2,000 | 59.0% | 59.3% | 57.7% |
| MASSIVE (English voice commands) | 86.75% | 50.4% | 79.1% | 57.5% | **81.9%** |
| Typed-decisions | 72.55% | 72.55% | **74.1%** | 36.2% | 29.1%‡ |

‡ Typed-decisions has no practice split, so Flybrain ran it cold.

Go down that table one row at a time.

**AG News.** Their card says 94%. On the full set, Julia comes in at 85% — dead last of the four. Our fruit fly beat it. The 94% only exists on the hundred rows they chose to publish.

**Emotion.** This one’s real. Julia scored 80% where everybody else sat around 59%. It’s the one job it does well: short first-person posts (“I feel so…”) tagged with one of six emotions. Credit where it’s due. It still came in six points under the card, and the card’s 86%-vs-48% gap over Jev shrinks to 80-vs-59 once you stop scoring a hundred hand-picked rows.

**MASSIVE.** Their card claims 86.75% on English. Same 2,974 rows, same weights: we got 50%. We tried everything we could think of to close that gap and couldn’t. And here’s the kicker — Supersonic never published the option wording they fed the model for this test. On a decision model, the menu wording *is* the test. You can’t check their number, because they kept the part that produces it.

**Typed-decisions.** We matched their number to the hundredth: 72.55%. So the weights are real and the harness works. I want to be fair about that, because it matters. When they publish the full recipe, their number holds up. Where they don’t, it doesn’t. And even on typed, hosted Jev beat it.

So that’s the pattern. The benchmark we can fully reproduce checks out. The two headline wins come from hundred-row samples that fall apart at full size. The biggest number on the card can’t be reproduced at all, because the setup that produced it was never released. Call it whatever you want. I call that stacking the deck.

The whole Jev bill for all of this came to about 25 cents. Checking a model card is cheap. As far as I can tell, nobody hyping this one on my feed bothered.

## Where Julia actually belongs

One slot. If you need to tag short messages by mood — angry, happy, scared — from a small menu, on a CPU, Julia is legitimately good at that. Better than every other model on our board. Its soft spot even there is sadness, where Jev beats it.

For everything else we tested, pick something else:

| If you need… | Reach for… | Because… |
|---|---|---|
| Top accuracy on a short menu, cloud is fine | **Jev** | 94–99% on sentiment and intents; won typed-decisions |
| Near-top accuracy on your own hardware | **Laya** | Won AG News at 93% |
| Labels hidden in thin text, and you have labeled examples | **Flybrain** | 78% on bug titles vs 49% and 30%; won MASSIVE |
| Answers in milliseconds on hardware you own | **Flybrain** | 2–5 ms a row vs ~435 ms hosted |
| Mood tags on short text, CPU only | **Julia** | 80% on Emotion vs 59% for the field |
| Menus with 100+ options | **Jev**, or long-window **Laya** | Julia tops out around twenty |

## The bottom line

The launch told us Julia beats the big models. The full test sets told us it’s a mood tagger with a marketing department. It’s a useful mood tagger, and I’ll route that exact job to it. The rest of the card needs to come with the full test sets and the prompts, or it doesn’t belong on the card.

Want to check us? The test files are frozen, the scoring is public, and last week’s post has the whole setup: [Same questions, three decision systems — fly connectome on a $350 laptop vs Jev vs Laya](https://www.decisionsciencecorp.com/blog/post.php?slug=same-questions-three-decision-systems).

## Appendix: how we ran it

| Model | How we called it | Where it ran |
|---|---|---|
| Jev | `POST https://api.venice.ai/api/v1/decisions`, model `jev-latest` | Venice |
| Laya | published `convaiinnovations/laya` checkpoints | The laptop |
| Julia-1 | `SupersonicLabs/Julia-1`, as published | The laptop |
| Flybrain | larva connectome + small readout layer | The laptop |

Each model saw the row’s text plus the menu, nothing else.

- **AG News**: 7,600 headlines, 4 topics (World / Sports / Business / Sci-Tech).
- **Emotion**: 2,000 posts, 6 labels (sadness / joy / love / anger / fear / surprise).
- **MASSIVE (English)**: 2,974 voice-assistant commands, 18 scenarios. Supersonic didn’t publish their option wording, so we wrote ours over the real Amazon utterances and labels.
- **Typed-decisions**: the pinned LocalLLaMA set Supersonic uses — 400 cases, 2,000 questions.
