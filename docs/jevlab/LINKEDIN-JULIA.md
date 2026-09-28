# LinkedIn Article — Julia-1 sequel (native paste pack)

**Voice:** Doc #729 / kit v2.2 — Mark, business crowd, non-lab. Same receipts as the DSC blog; less jargon.
**Tables:** LinkedIn Articles don’t render markdown tables — insert the PNGs where marked. Charts are already PNGs.

**Full DSC post (for you, not for LinkedIn):**  
https://www.decisionsciencecorp.com/blog/post.php?slug=julia-1-mood-tagger-with-a-marketing-department

---

## Suggested LinkedIn post (promotes the article)

My feed spent last week telling me a tiny new AI model beats the giants at “decision” work — pick from a menu, not write an essay.

We put it on the same scoreboard as three other systems. It lost badly. Then we checked its own published score sheet, full size.

One real win. The rest of the card didn’t hold up.

Article ↓

[link your LinkedIn Article here]

— Mark Hopkins

---

## Article title (LinkedIn)

**Julia-1 is a mood tagger with a marketing department**

## Dek / subtitle

We checked the tiny model your feed was hyping. Here’s what held up — and what didn’t.

---

My feed spent last week telling me Julia-1 was the tiny AI that changes everything. Small enough to run on a normal computer. Beats the big hosted models at “decision” work — the kind where you give the machine a situation and a fixed menu, and it picks: approve or flag, which department, how urgent.

So I put it on the same scoreboard where we’d just lined up three other systems:

1. **Jev** — Venice’s hosted decision model. Cloud. Pay as you go.
2. **Laya** — an open model from ConvAI, running on our machine.
3. **Flybrain** — ours. A readout on a published fruit-fly brain map. Running on a **$350 laptop with no fancy graphics card**.

Julia lost. Badly. Then we went looking for anything it was actually good at, using the company’s own published score sheet as the map. We had to dig hard to find one thing. Along the way we found out why that score sheet reads so much better than the model runs.

**Insert image:** `illustrations/julia/julia-card-vs-full-set.png`

### Round one: the jobs everybody else already played

Same four public tests as last week. Same laptop. Julia ran cold — no special training from us — same as Jev and Laya. (Flybrain gets a small practice pass on labeled examples. That’s how it works, and we said so last week.)

Julia can only handle menus up to about twenty options, so it sat out the 150-option job.

**Insert image:** `illustrations/julia/tables/table-julia-round-one.png`

**Insert image:** `illustrations/julia/julia-round-one.png`

Movie-review sentiment is a two-option question. Positive or negative. A coin gets 50%. Julia got 57%. On ten everyday phone intents — alarm, timer, weather — it got 56%, while Jev hit 99%. Bug severity from the title alone is a three-option question, so random guessing gets 33%. Julia got 28%. That’s worse than guessing.

That’s the model everybody was losing their minds over.

### Round two: we played on its home field

A model can be bad at general work and great at a specialty. That’s allowed. So I went to Supersonic’s own published results, pulled every job they claim as a win, and ran those. Their turf. Their datasets. All four systems.

Here’s the first thing we noticed. Two of their headline numbers come from **100-example samples**. The full public tests are 7,600 and 2,000 examples. So we ran the full tests.

**Insert image:** `illustrations/julia/tables/table-julia-card-vs-ours.png`

**Insert image:** `illustrations/julia/julia-round-two.png`

Go down that board one row at a time.

**News headlines.** Their sheet says 94%. On the full set, Julia comes in at 85% — last of the four. Our fruit fly beat it. The 94% only exists on the hundred examples they chose to publish.

**Mood tags.** This one’s real. Julia scored 80% where everybody else sat around 59%. Short first-person posts (“I feel so…”) tagged with one of six moods. Credit where it’s due. It still came in under their published number, and the huge gap they showed over Jev shrinks once you score all 2,000 examples instead of a hundred.

**Insert image:** `illustrations/julia/julia-emotion-gap.png`

**Voice commands.** Their sheet claims about 87%. Same 2,974 examples, same model: we got 50%. We tried everything we could think of to close that gap and couldn’t. And here’s the kicker — they never published the exact menu wording they fed the model. On a decision system, the menu wording *is* the test. You can’t check their number, because they kept the part that produces it.

**Typed decisions.** We matched their number to the hundredth: 72.55%. So the model is real and our harness works. I want to be fair about that. When they publish the full recipe, their number holds up. Where they don’t, it doesn’t. And even here, hosted Jev beat it.

So that’s the pattern. The benchmark we can fully reproduce checks out. The two headline wins come from hundred-example samples that fall apart at full size. The biggest number on the sheet can’t be reproduced at all, because the setup that produced it was never released. Call it whatever you want. I call that stacking the deck.

**Insert image:** `illustrations/julia/julia-card-check-flow.png`

The whole Jev bill for all of this came to about **25 cents**. Checking a published score sheet is cheap. As far as I can tell, nobody hyping this one on my feed bothered.

### Where Julia actually belongs

One slot. If you need to tag short messages by mood — angry, happy, scared — from a small menu, on a normal computer, Julia is legitimately good at that. Better than every other system on our board. Its soft spot even there is sadness, where the others beat it.

**Insert image:** `illustrations/julia/julia-emotion-by-mood.png`

For everything else we tested, pick something else:

**Insert image:** `illustrations/julia/tables/table-julia-pick.png`

**Insert image:** `illustrations/julia/julia-which-model-flow.png`

### The bottom line

The launch told us Julia beats the big models. The full tests told us it’s a mood tagger with a marketing department. It’s a useful mood tagger, and I’ll route that exact job to it. The rest of the score sheet needs to come with the full test sets and the menus — or it doesn’t belong on the sheet.

If you want the lab writeup with every number, it’s on our site: [Julia-1 is a mood tagger with a marketing department](https://www.decisionsciencecorp.com/blog/post.php?slug=julia-1-mood-tagger-with-a-marketing-department). Last week’s setup post is here: [Same questions, three decision systems](https://www.decisionsciencecorp.com/blog/post.php?slug=same-questions-three-decision-systems).

**Insert image:** `illustrations/julia/tables/table-julia-arms.png`

Not a religion. A pick list.

— Mark Hopkins

---

## Image files (upload into the LinkedIn Article)

Upload in this order (or rename as you paste). Paths relative to `docs/jevlab/`.

| # | File | What it is |
|---|---|---|
| 1 | `illustrations/julia/julia-card-vs-full-set.png` | Opening chart: published claim vs full test |
| 2 | `illustrations/julia/tables/table-julia-round-one.png` | **Table** — round one scoreboard |
| 3 | `illustrations/julia/julia-round-one.png` | Round one bar chart |
| 4 | `illustrations/julia/tables/table-julia-card-vs-ours.png` | **Table** — their score vs ours |
| 5 | `illustrations/julia/julia-round-two.png` | Round two bar chart |
| 6 | `illustrations/julia/julia-emotion-gap.png` | Mood-tag lead: 100 examples vs full set |
| 7 | `illustrations/julia/julia-card-check-flow.png` | Flowchart: what held up / what didn’t |
| 8 | `illustrations/julia/julia-emotion-by-mood.png` | Mood by mood |
| 9 | `illustrations/julia/tables/table-julia-pick.png` | **Table** — which system for which job |
| 10 | `illustrations/julia/julia-which-model-flow.png` | Routing flowchart |
| 11 | `illustrations/julia/tables/table-julia-arms.png` | **Table** — what we actually ran |

**Hard rule for LinkedIn:** anything that was a markdown table must be one of the `tables/table-julia-*.png` files. Do not paste pipes.
