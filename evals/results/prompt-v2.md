# Eval: prompt-v2

Model: `deepseek-flash`, 3 run(s) per case; figures are per-run means, and the duplicate-SHA and long-entry columns are totals across runs. Recall and accuracy are judged by an LLM; the rest is counted.

| Case | Commits | Recall | Accuracy | Entries | Dup SHAs | Long entries | Attempts | Tokens | Seconds |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| uv | 42 | 74% | 100% | 14.3 | 0 | 0 | 1.0 | 4,939 | 4.2 |
| ruff | 114 | 72% | 100% | 33.3 | 0 | 2 | 1.0 | 13,458 | 8.3 |
| fastapi | 8 | 39% | 100% | 2.0 | 0 | 0 | 1.0 | 846 | 1.4 |
| httpx | 34 | 47% | 90% | 9.7 | 0 | 0 | 1.0 | 1,860 | 2.8 |
| flask | 163 | 77% | 95% | 16.7 | 2 | 0 | 1.0 | 6,621 | 3.7 |
| requests | 34 | 81% | 100% | 9.3 | 0 | 0 | 1.0 | 1,994 | 2.4 |
| rich | 28 | 100% | 95% | 6.7 | 1 | 0 | 1.0 | 1,154 | 2.2 |
| **All** | | **70%** | **97%** |||||||

## Inaccurate entries

- **httpx** run 1, #1: Misstates the change: it deprecates the verify-as-string and cert arguments, not the SSLContext API itself.
- **httpx** run 2, #1: The reference deprecates string verify and cert (with warnings), not errors; the generated entry says verifying with a string is now an error and frames it as a breaking replacement.
- **httpx** run 3, #4: The commit deprecates string verify with a warning, not raising an error.
- **flask** run 1, #3: The commit changes precedence of -e path vs default .env/.flaskenv files, not environment variables vs environment files.
- **flask** run 3, #6: MAX_CONTENT_LENGTH already existed; the commits add MAX_FORM_MEMORY_SIZE and MAX_FORM_PARTS and per-request max_content_length, not a new MAX_CONTENT_LENGTH config.
- **rich** run 1, #4: Commits 7ef2d05 and 77f0edb fix inline code in table cells, not HTML export inline code support; a9c4aab is the HTML inline support commit and is not listed here.

## Missed reference changes

- **uv** run 1: Reduce uv's binary size by keeping additional error formatters out of line
- **uv** run 1: Reduce overhead when parsing custom build cache keys
- **uv** run 1: Reject invalid custom build cache keys instead of silently falling back to defaults
- **uv** run 2: Reduce uv's binary size by keeping additional error formatters out of line
- **uv** run 2: Reduce overhead when parsing custom build cache keys
- **uv** run 2: Reject invalid custom build cache keys instead of silently falling back to defaults
- **uv** run 2: Reject certificate chains containing compromised eMudhra intermediate keys via rustls-webpki 0.103.16
- **uv** run 3: Reduce uv's binary size by keeping additional error formatters out of line
- **ruff** run 1: Avoid intermediate names in lint name resolution
- **ruff** run 1: Prefilter bidirectional Unicode checks by UTF-8 leading bytes
- **ruff** run 1: Share postfix parsing and reduce expression copies
- **ruff** run 2: Avoid intermediate names in lint name resolution
- **ruff** run 2: Prefilter bidirectional Unicode checks by UTF-8 leading bytes
- **ruff** run 2: Share postfix parsing and reduce expression copies
- **ruff** run 2: Clarify documentation and correct stale guidance
- **ruff** run 3: Avoid intermediate names in lint name resolution (performance)
- **ruff** run 3: Prefilter bidirectional Unicode checks by UTF-8 leading bytes (performance)
- **ruff** run 3: Share postfix parsing and reduce expression copies (performance)
- **fastapi** run 1: Bump certifi from 2026.1.4 to 2026.10.19.
- **fastapi** run 2: With extra="forbid", fields outside the model are rejected even if another parameter declares them; with extra="allow" they become model extras; with default extra="ignore" they are ignored
- **fastapi** run 2: Bump certifi from 2026.1.4 to 2026.10.19
- **fastapi** run 3: Bump certifi from 2026.1.4 to 2026.10.19
- **httpx** run 1: cert argument is deprecated and raises warnings
- **httpx** run 1: deprecated proxies argument removed
- **httpx** run 1: deprecated app argument removed
- **httpx** run 1: Cleanup Request() method signature
- **httpx** run 1: Bugfix: params={} strictly updates rather than merges querystring
- **httpx** run 2: deprecated proxies argument removed
- **httpx** run 2: deprecated app argument removed
- **httpx** run 2: Cleanup Request() method signature
- **httpx** run 2: Bugfix: params={} strictly updates rather than merges with existing querystring
- **httpx** run 3: cert argument is deprecated and raises warnings
- **httpx** run 3: deprecated proxies argument removed
- **httpx** run 3: deprecated app argument removed
- **httpx** run 3: Cleanup Request() method signature
- **httpx** run 3: Bugfix: params={} strictly updates rather than merges querystring
- **flask** run 1: Request.max_content_length customizable per-request; add MAX_FORM_MEMORY_SIZE and MAX_FORM_PARTS config; document resource limits
- **flask** run 1: -e path takes precedence over default .env and .flaskenv; load_dotenv loads defaults unless load_defaults=False
- **requests** run 1: no_proxy greedy matching fixed via bpo-39057
- **requests** run 2: Support for Python 3.14t
- **requests** run 2: No greedy matching on no_proxy domains (bpo-39057)
- **requests** run 3: No greedy matching on no_proxy domains (bpo-39057)
