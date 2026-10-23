# Technology Entity Disambiguation

Resolves technology names from threat-intelligence reports to a stable canonical product ID.
The approach and trade-offs are in [design.md](design.md).

```python
from pathlib import Path
from entity_resolver import build_resolver

resolver = build_resolver(Path("var/kb.sqlite"))
resolver.resolve("Microsoft sp")
# ResolverResult(status='resolved', canonical_id='ms_sharepoint',
#                canonical_name='Microsoft SharePoint', match_type='llm', score=..., pipeline_version=...)
```

## Run

Requires Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

python -m entity_resolver import data/seed.json      # build var/kb.sqlite
python -m entity_resolver resolve "AWS"              # exact alias: no API key needed
python -m entity_resolver resolve "Microsoft sp"     # LLM path: needs ANTHROPIC_API_KEY or `ant auth login`

pytest                                               # offline; uses a fake LLM
ruff check . && pyright                              # lint and strict type check
```

Evaluation calls the LLM and costs money:

```bash
python -m entity_resolver evaluate data/eval/dev.json --repeats 3 --cache-hit-rate 0.3
```

It prints precision/recall/F1 at the configured threshold, a threshold sweep computed from the
recorded scores, candidate recall@K, repeat agreement across uncached runs, p50/p95 latency,
LLM-call rate, mean cost per call, and projected daily cost with and without cache hits.
Tune `top_k` and `llm_score_threshold` in `config.py` on the dev set, freeze them, then run
`data/eval/test.json` once.

## Layout

| Path | Role |
|---|---|
| `src/entity_resolver/resolver.py` | Pipeline: normalize → exact alias → cache → candidates → LLM → threshold |
| `src/entity_resolver/retrieval/` | Exact / substring / subsequence matchers (strategies) and ranking |
| `src/entity_resolver/selection/` | `CandidateSelector` port, Claude adapter, prompt |
| `src/entity_resolver/store/` | SQLite schema, transactional seed import, in-memory snapshot |
| `src/entity_resolver/cache.py` | Byte-bounded LRU cache with expiry |
| `src/entity_resolver/composition.py` | The single place components are wired; computes `pipeline_version` |
| `src/entity_resolver/evaluation/` | Dataset loading, uncached runs, metrics |
| `data/` | Seed catalog (25 cloud, EDR, SIEM, SaaS products) and dev/test sets |

## Production stubs

Marked with `PRODUCTION:` comments:

- per-stage metrics and token/stop-reason monitoring (`resolver.py`, `anthropic_selector.py`);
- human review of unknown and low-score results, with alias promotion only after review (`resolver.py`);
- scheduled offline evaluation against a frozen test set (`evaluation/runner.py`);
- a shared cache instead of the in-process one (`cache.py`);
- benchmarking the linear name scan at catalog scale (`retrieval/retriever.py`);
- entity deprecation instead of rejecting removed IDs (`store/importer.py`).
