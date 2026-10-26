# Eval: baseline

Model: `deepseek-flash`, 3 run(s) per case; figures are per-run means, and the duplicate-SHA and long-entry columns are totals across runs. Recall and accuracy are judged by an LLM; the rest is counted.

| Case | Commits | Recall | Accuracy | Entries | Dup SHAs | Long entries | Attempts | Tokens | Seconds |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| uv | 42 | 68% | 96% | 8.0 | 0 | 2 | 1.0 | 4,554 | 3.3 |
| ruff | 114 | 78% | 100% | 26.7 | 0 | 0 | 1.0 | 13,003 | 7.1 |
| fastapi | 8 | 33% | 83% | 2.0 | 0 | 0 | 1.0 | 738 | 1.4 |
| httpx | 34 | 45% | 80% | 10.0 | 2 | 0 | 1.0 | 1,765 | 2.9 |
| flask | 163 | 78% | 87% | 10.3 | 0 | 0 | 1.0 | 6,352 | 3.2 |
| requests | 34 | 88% | 82% | 10.0 | 0 | 0 | 1.0 | 1,883 | 2.8 |
| rich | 28 | 100% | 83% | 6.0 | 1 | 0 | 1.3 | 1,501 | 2.8 |
| **All** | | **70%** | **88%** |||||||

## Inaccurate entries

- **uv** run 3, #9: 4053abe updates rustls-webpki to reject compromised eMudhra chains, and 5477928 updates release-signing actions; neither updates uv's bundled trust store (that was 0.13.4).
- **fastapi** run 2, #2: The commit applies each parameter model's `extra` configuration to sibling fields; the generated entry states the opposite (applied only to its own fields, not sibling fields).
- **httpx** run 1, #1: String verify is deprecated with warnings, not removed; it still accepts strings.
- **httpx** run 1, #2: cert argument is deprecated, not removed.
- **httpx** run 1, #3: SSLContext is not required; verify parameter is not deprecated (only string verify and cert are).
- **httpx** run 2, #1: Overstates: string verify is deprecated with warnings, not removed; also omits cert deprecation.
- **httpx** run 3, #1: The commit deprecates string verify with warnings; it does not remove string support.
- **httpx** run 3, #7: The change makes JSON request bodies compact, not JSON responses.
- **flask** run 1, #8: Vague; does not specify that -e path takes precedence over default .env and .flaskenv, or that load_dotenv loads defaults unless load_defaults=False.
- **flask** run 2, #3: Claims SECRET_KEY can be a list; the change adds SECRET_KEY_FALLBACKS, not list support for SECRET_KEY.
- **flask** run 2, #10: Describes precedence as 'correct' but omits the actual change: -e path takes precedence over defaults, and load_dotenv loads defaults unless load_defaults=False.
- **flask** run 3, #10: Vague; does not describe the actual change that -e path takes precedence over default .env/.flaskenv files and load_dotenv loads defaults unless load_defaults=False.
- **requests** run 1, #9: Vague: doesn't mention no_proxy greedy matching, which is the user-facing change.
- **requests** run 2, #2: Claims Python 3.14 support, but commits only add 3.15 and 3.14t (free-threaded) support; 3.14t is not the same as 3.14.
- **requests** run 3, #6: Describes it as a memory leak; the change prevents a self-reference in redirect history, not a memory leak.
- **requests** run 3, #7: Commit b294b08 is about considering urllib3 version numbers having at most 3 components, not misparsing URLs with more than three components.
- **requests** run 3, #8: Commit a4f9a59 ports bpo-39057 to fix no_proxy greedy matching, not general URL parsing portability.
- **rich** run 2, #2: The reference only mentions inline code in Markdown table cells; the HTML export change (a9c4aab) is a separate change not described in the reference, and the entry conflates the two.
- **rich** run 2, #3: The change is to FileProxy.isatty proxying to the underlying file, not Console.isatty.
- **rich** run 3, #3: The change is to FileProxy.isatty proxying to the underlying file, not Console.isatty.

## Missed reference changes

- **uv** run 1: Reduce binary size by keeping additional error formatters out of line
- **uv** run 1: Reduce overhead when parsing custom build cache keys
- **uv** run 1: Reject invalid custom build cache keys instead of silently falling back to defaults
- **uv** run 2: Reduce uv's binary size by keeping additional error formatters out of line
- **uv** run 2: Reduce overhead when parsing custom build cache keys
- **uv** run 2: Reject invalid custom build cache keys instead of silently falling back to the defaults
- **uv** run 2: Reject certificate chains containing compromised eMudhra intermediate keys via rustls-webpki 0.103.16
- **uv** run 3: Reduce uv's binary size by keeping additional error formatters out of line
- **uv** run 3: Reduce overhead when parsing custom build cache keys
- **uv** run 3: Reject invalid custom build cache keys instead of silently falling back to the defaults
- **ruff** run 1: Avoid intermediate names in lint name resolution
- **ruff** run 1: Prefilter bidirectional Unicode checks by UTF-8 leading bytes
- **ruff** run 1: Share postfix parsing and reduce expression copies
- **ruff** run 2: Avoid intermediate names in lint name resolution (performance)
- **ruff** run 2: Share postfix parsing and reduce expression copies (performance)
- **ruff** run 3: Avoid intermediate names in lint name resolution (performance)
- **ruff** run 3: Prefilter bidirectional Unicode checks by UTF-8 leading bytes (performance)
- **ruff** run 3: Share postfix parsing and reduce expression copies (performance)
- **fastapi** run 1: Bump certifi from 2026.1.4 to 2026.10.19
- **fastapi** run 2: Bump certifi from 2026.1.4 to 2026.10.19 (internal).
- **fastapi** run 3: Bump certifi from 2026.1.4 to 2026.10.19
- **httpx** run 1: deprecated proxies argument removed
- **httpx** run 1: deprecated app argument removed
- **httpx** run 1: Cleanup Request() method signature
- **httpx** run 1: Bugfix: params={} strictly updates rather than merges with existing querystring
- **httpx** run 2: cert argument deprecated
- **httpx** run 2: deprecated proxies argument removed
- **httpx** run 2: deprecated app argument removed
- **httpx** run 2: Cleanup Request() method signature
- **httpx** run 2: Bugfix: params={} strictly updates querystring
- **httpx** run 3: cert argument is deprecated and raises warnings
- **httpx** run 3: deprecated proxies argument removed
- **httpx** run 3: deprecated app argument removed
- **httpx** run 3: Cleanup Request() method signature
- **httpx** run 3: Bugfix: params={} strictly updates rather than merges with existing querystring
- **flask** run 1: Update minimum dependency versions (Werkzeug >= 3.1, ItsDangerous >= 2.2, Blinker >= 1.9)
- **flask** run 1: Request.max_content_length can be customized per-request; add MAX_FORM_MEMORY_SIZE and MAX_FORM_PARTS config; document resource limits
- **requests** run 2: No greedy matching on no_proxy domains (bpo-39057)
