Julia-1 owns one cell on our decision-model scoreboard: emotion tagging. It won that cell by twenty points. Everywhere else, somebody else took the win.

Last week I put three decision models on the same public tests: Venice’s hosted **Jev**, ConvAI’s open-weight **Laya**, and our **Flybrain**, which runs a readout on the published fruit-fly larva connectome. Everything local ran on a $350 Lenovo with no GPU. Then Supersonic Labs released **Julia-1**, a 144-million-parameter decision model built for CPU, Apache 2.0 licensed. It works like the others: you hand it a situation and a menu of options, and it hands back a pick with a probability on every option. Their model card claims strength on AG News, Emotion, typed-decisions, and MASSIVE, and flags long menus as a weak spot.

I ran Julia twice. First on last week’s tests, the ones built to stress everybody. Then on the tests its own card names as strengths, using the full test sets.

## Who trained on what

Jev, Laya, and Julia ran exactly as published, with no tuning on any of these tests.

Flybrain keeps the connectome wiring fixed and fits a small readout layer on each test’s practice split. That practice step is part of how Flybrain works. Typed-decisions ships with no practice split, so Flybrain ran that one cold, matching question text to option text directly.

## Round one: last week’s tests

Julia’s menus top out around twenty options. Three of last week’s four tests fit that limit. The fourth has 151 options, so Julia sat that one out.

| Test | Rows | Julia | Jev | Laya | Flybrain |
|---|---:|---:|---:|---:|---:|
| Movie-review sentiment | 872 | 57.0% | **94.6%** | 90.6% | 76.5% |
| Ten phone intents | 300 | 56.3% | **99.3%** | 97.3% | 94.7% |
| Eclipse bug severity (titles only) | 2,000 | 27.7% | 49.1% | 29.5% | **78.4%** |
| 150 intents + “none of these” | 5,500 | — | 91.7%† | 60.6% | 64.6% |

† Jev’s 150-intent score covers the 4,060 rows it finished before the API stopped answering.

Julia landed in the 50s on sentiment and intents and at 28% on bug severity. Jev and Laya cleared 90% on the short menus, and Flybrain took the bug titles. On this set, Julia is the wrong tool.

## Round two: Julia’s home turf

A stress test shows you where a model breaks. To see what it’s built for, you test it on its own claims. So we pulled the four public sets from Julia’s card:

1. **AG News**: news headlines sorted into 4 topics. 7,600 rows.
2. **DAIR Emotion**: short posts tagged with one of 6 emotions. 2,000 rows.
3. **MASSIVE (English)**: voice-assistant commands sorted into 18 scenarios. 2,974 rows.
4. **Typed-decisions**: 400 cases, 2,000 questions, each with its own menu.

Julia’s published pilots used 100 rows each on AG News and Emotion. We ran the full sets.

| Test | Rows | Julia | Jev | Laya | Flybrain |
|---|---:|---:|---:|---:|---:|
| AG News | 7,600 | 85.1% | 88.4% | **92.9%** | 88.3% |
| Emotion | 2,000 | **79.9%** | 59.0% | 59.3% | 57.7% |
| MASSIVE (English) | 2,974 | 50.4% | 79.1% | 57.5% | **81.9%** |
| Typed-decisions | 2,000 Qs | 72.6% | **74.1%** | 36.2% | 29.1%‡ |

‡ Flybrain ran typed-decisions cold (no practice split).

**Emotion is Julia’s.** Julia scored 80% where the other three sat at 59%. The rows are short first-person lines (“I feel so…”) with six emotion labels. That is exactly the job Julia was trained for, and it shows.

**AG News went to Laya** at 93%. Julia came third at 85%. Sorting headlines by topic is a different skill from reading emotion.

**Typed-decisions went to Jev** by a point and a half. Julia scored 72.55%, which matches its published CPU number to the decimal. The weights are what Supersonic says they are.

**MASSIVE went to Flybrain** at 82%. Julia scored 50%, while its card claims 87% on English. The gap comes from the menu wording. Supersonic never published the option descriptions it used for MASSIVE, so we wrote our own over the real Amazon utterances and labels. The 87% figure can’t be reproduced from what they’ve released. Emotion and typed-decisions reproduce cleanly.

The whole Jev bill for round two came to about 25 cents.

## Where Julia earns a spot

The Emotion set is Twitter-style posts labeled sadness, joy, love, anger, fear, or surprise. Julia hit very high scores on anger, joy, love, fear, and surprise. Sadness was its soft spot, and Jev beat it there.

If you’re tagging short user messages by mood or tone from a small menu, on a CPU, Julia belongs in your lineup. For topic sorting, big intent catalogs, or multi-question agent work, last week’s picks still apply.

## Same $350 laptop

Julia, Laya, and Flybrain all ran on the same Lenovo IdeaPad Slim 3: Intel i3-N305, 8 GB of RAM, no GPU, Ubuntu. Jev ran on Venice’s servers.

## How I’d pick now

| If you need… | Reach for… | Because… |
|---|---|---|
| Top accuracy on a short, clean menu, and a cloud call is fine | **Jev** | Won typed-decisions here; won short intents and sentiment last week |
| Near-top accuracy on your own hardware, sorting by topic | **Laya** | Won AG News at 93% |
| Labels hidden in thin text, and you have labeled examples | **Flybrain** | 78% on bug titles last week, against 49% and 30% |
| Answers in milliseconds on hardware you own | **Flybrain** | 2–5 ms a row last week, against ~435 ms hosted |
| Mood or tone tags on short text, small menu, CPU | **Julia** | 80% on Emotion, against 59% for the field |
| Menus with 100+ options | **Jev** while it stays up, or long-window **Laya** | Julia’s menus top out around twenty |

Flybrain’s wins depend on having labeled examples for your menu, so it can fit that small readout layer before it goes to work. Jev and Julia take a fresh menu on every call.

## Bottom line

Last week taught me that finishing the job and reading thin signals matter as much as raw accuracy. This week taught me specialty. Four models, and each one owns different turf.

Route the call to whoever owns the turf.

Last week’s post: [Same questions, three decision systems — fly connectome on a $350 laptop vs Jev vs Laya](https://www.decisionsciencecorp.com/blog/post.php?slug=same-questions-three-decision-systems)

## Appendix: the models and the tests

| Model | How we called it | Where it ran |
|---|---|---|
| Jev | `POST https://api.venice.ai/api/v1/decisions`, model `jev-latest` | Venice |
| Laya | published `convaiinnovations/laya` checkpoints | The laptop |
| Julia-1 | `SupersonicLabs/Julia-1` | The laptop |
| Flybrain | larva connectome + small readout layer | The laptop |

Each model saw only the row’s text plus the menu.

- **AG News**: World / Sports / Business / Sci-Tech.
- **Emotion**: sadness / joy / love / anger / fear / surprise.
- **MASSIVE (English)**: 18 scenario labels. We wrote the option descriptions.
- **Typed-decisions**: pinned LocalLLaMA set, 400 cases and 2,000 questions across choice, score, and yes/no formats.
