# Evaluation

How good are repo-digest's release notes? This harness runs it on real releases and compares the
output with the release notes the maintainers wrote by hand.

```sh
uv run python -m evals.run --label my-change --repeat 3      # all cases, 3 runs each
uv run python -m evals.run --label quick --only uv,flask     # a subset, one run
```

It reads `LLM_API_KEY` from `.env`, and a `GITHUB_TOKEN` avoids GitHub's anonymous rate limit
(`GITHUB_TOKEN=$(gh auth token) uv run python -m evals.run ...`). Results go to
`results/<label>.json` (every output and every judgement) and `results/<label>.md` (the table).
A full run with `--repeat 3` uses about 210k DeepSeek tokens, a few cents.

## What it measures

For each case in [`cases.json`](cases.json) (a tag range plus that release's GitHub release notes):

| Metric | How |
|---|---|
| **Recall** | An LLM judge lists the changes in the human-written notes and grades each as covered fully, partly (half credit), or missed. Changes that aren't in the commits at all don't count. |
| **Accuracy** | The judge checks each generated entry against its commits: does it describe what they actually do? |
| Duplicate SHAs, long entries | Counted directly: commits cited by more than one entry, and entries over 200 characters. |
| Attempts, tokens, seconds | From the summariser. |

The judge is the code in [`judge.py`](judge.py); the counted checks are in
[`metrics.py`](metrics.py).

## Results

Seven releases: uv, ruff, FastAPI, HTTPX, Flask, Requests, Rich (8 to 163 commits each),
3 runs per case, `deepseek-flash` as both summariser and judge.

| Version | Recall | Accuracy | Duplicate SHAs | Long entries | Tokens per run |
|---|--:|--:|--:|--:|--:|
| [baseline](results/baseline.md) | 70% | 88% | 3 | 2 | 4,260 |
| [prompt-v2](results/prompt-v2.md) | 70% | **97%** | 3 | 2 | 4,410 |

### 1. The errors were embellishment, and the prompt fixed most of them

In the baseline, about one entry in eight was wrong. The mistakes followed a pattern: a terse
commit message was turned into a confident, specific claim.

- Rich's `proxy isatty` became "Added `isatty` proxy for Console, FileIO, and other stream
  wrappers". The commit only touches `FileProxy`.
- Rich's `fix inline code in table cells` became a new feature, "Added support for inline code in
  table cells".
- Flask's `SECRET_KEY_FALLBACKS` became "`SECRET_KEY` can now be a list", and the `-e` flag's
  precedence over `.env` files came out reversed.
- HTTPX's string `verify` argument, which still works with a deprecation warning, was reported as
  removed.

Prompt v2 adds three rules:

- Name only the options, parameters and classes that the commit messages name, and stay terse
  when they're terse.
- Keep the change's own framing: a fix stays a fix, and a deprecation is not a removal.
- Cite each commit in at most one entry.

Accuracy rose from 88% to 97% with no loss of recall, for about 4% more tokens. In an earlier
version of the judge it rose from 90% to 95%, so the improvement survived a change to the
judge.

### 2. Recall is limited by the input, not the prompt

The prompt changes didn't move recall. Most of the remaining misses are changes that the commit
messages don't describe:

- **uv and ruff:** performance pull requests are titled by how they work ("Deserialize cache keys
  and Git patterns directly"), not by what users get.
- **HTTPX:** the removal of the `proxies` and `app` arguments arrived in a commit titled
  "Graceful upgrade path for 0.28".
- **FastAPI:** the maintainers listed a `certifi` bump, which the prompt deliberately leaves out
  as noise.

The next lever is richer input, such as pull request descriptions, rather than more prompt rules.

### 3. The evaluator needed evaluating too

- **Single runs are noise.** On identical inputs, Rich's accuracy was 50% in one run and 83% in
  the next. Every comparison here averages 3 runs per case, and a change worth keeping should
  survive a re-run.
- **The judge has to show its work.** At first the judge could call a reference change "not in
  the commits", and it gave HTTPX's `proxies` removal that grade in one run and "missed" in the
  next. A "missed" grade now has to name the commit that makes the change, and a grade that names
  no real commit is discarded (`Verdict.ground`). This catches invented SHAs. It can't tell
  whether a real SHA is the right one: the judge tied the `proxies` removal to "Graceful upgrade
  path for 0.28", which is plausible but can't be checked from the message alone.
- **The judge sometimes grades against the reference instead of the commits.** HTTPX's commit is
  titled "Error on verify as str", but the shipped release only deprecated it. Entries that said
  "raises an error" were marked inaccurate even though they matched their commit.
- **The judge is the same model as the summariser,** so it may go easy on its own style. Using a
  different model as judge (`--judge-model`) would be a better check.

### 4. The problems I expected turned out to be rare

Before building this, I'd seen duplicate SHAs and overlong bullets by hand. Measured across
21 runs, each happened only 2 or 3 times. That's too rare to justify a hard validation check,
which would trigger paid retries, so the prompt rule is enough. Without measuring, I would have
built that check.
