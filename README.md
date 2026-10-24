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

Cache savings can be simulated for free (no LLM calls):

```bash
python -m entity_resolver simulate-cache --skew 1.0 --cache-sizes 0,100000,1000000,10000000
```

It replays a synthetic request stream whose repetition follows a Zipf distribution (`--skew`)
and reports the cache hit rate, LLM calls, and daily cost per cache size. The skew is an
assumption, so the output is a scenario, not a forecast. Results are in [evaluate.md](evaluate.md).

## Layout

The package follows the resolution flow in [design.md](design.md):

```
src/entity_resolver/
  resolver.py        the pipeline: normalize -> exact alias -> cache -> candidates -> LLM -> threshold
  setup.py           build_resolver(): wires the components and computes pipeline_version
  config.py          settings (K, threshold, cache limits, model)
  domain.py          Entity, Candidate, Selection, ResolverResult
  steps/
    normalize.py     step 1: casefold and collapse whitespace
    cache.py         step 3: byte-bounded LRU cache with expiry
    candidates/      step 4: exact / substring / subsequence matchers and ranking
    llm/             step 5: CandidateSelector interface, Claude adapter, prompt
  knowledge_base/    SQLite schema, transactional seed import, in-memory snapshot
  tools/
    cli.py           the command line (import, resolve, evaluate, simulate-cache)
    evaluation/      dataset loading, uncached runs, metrics
    cache_simulation.py
data/                seed catalog (25 cloud, EDR, SIEM, SaaS products) and dev/test sets
```

## Production stubs

Marked with `PRODUCTION:` comments:

- per-stage metrics and token/stop-reason monitoring (`resolver.py`, `steps/llm/claude.py`);
- human review of unknown and low-score results, with alias promotion only after review (`resolver.py`);
- scheduled offline evaluation against a frozen test set (`tools/evaluation/runner.py`);
- a shared cache instead of the in-process one (`steps/cache.py`);
- benchmarking the linear name scan at catalog scale (`steps/candidates/retriever.py`);
- entity deprecation instead of rejecting removed IDs (`knowledge_base/importer.py`);
- replaying real traffic instead of a synthetic stream (`tools/cache_simulation.py`).
