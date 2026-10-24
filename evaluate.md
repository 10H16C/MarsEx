# Evaluation Results

First evaluation of the resolver with Claude on the development set.

## Setup

| | |
|---|---|
| Date | 2026-10-24 |
| Dataset | `data/eval/dev.json`: 20 inputs (14 with a correct product, 6 that should be unknown) |
| Repeats | 3 uncached runs, so 60 observations |
| Model | `claude-opus-5-5`, effort `low` |
| Candidates per input (K) | 10 |
| Configured threshold | 0.8 |
| Pipeline version | `a988faa24453` |

Command:

```bash
python -m entity_resolver evaluate data/eval/dev.json --repeats 3
```

## Summary

| Metric | Result |
|---|---|
| Precision at threshold 0.8 | 0.92 |
| Recall at threshold 0.8 | 0.79 |
| F1 at threshold 0.8 | 0.85 |
| Wrongly accepted unknowns | 1 of 6 inputs |
| Same answer in all 3 runs | 100% of inputs |
| Correct product among candidates | 85% of inputs that reached retrieval |
| Requests that needed the LLM | 70% |
| Cost per LLM call | $0.0033 |
| Latency p50 / p95 | 2.0 s / 4.8 s |

## Choosing the threshold

The threshold decides when an LLM answer is accepted. Results by threshold:

| Threshold | Precision | Recall | F1 | Wrongly accepted unknowns |
|---|---|---|---|---|
| 0.00 – 0.70 | 0.92 | 0.86 | 0.89 | 17% |
| 0.75 – 0.80 | 0.92 | 0.79 | 0.85 | 17% |
| **0.85** | **1.00** | **0.74** | **0.85** | **0%** |
| 0.90 – 0.95 | 1.00 | 0.64 | 0.78 | 0% |
| 1.00 | 1.00 | 0.07 | 0.13 | 0% |

The rule set before tuning was: highest recall with precision at least 0.95. That selects **0.85**.

The cost of that choice: one correct answer scored between 0.70 and 0.75 is rejected. This is most likely "Microsoft sp", which Claude scored 0.75 in a separate manual test. A threshold of 0.70 keeps it, but also accepts one input that should be unknown.

With only 20 inputs, one example moves these numbers a lot. The threshold should be confirmed on a larger set before it is frozen.

## Findings

**1. Claude chose correctly whenever the right product was a candidate.**
Below threshold 0.7, recall is 0.86 (12 of 14), which is exactly the retrieval limit. The two missed inputs, "Falcon EDR" and "Elastic EDR", never received candidates.

**2. Retrieval is the main source of misses.**
Name matching fails when the input adds words to a product name, e.g. "Falcon EDR" or "SharePoint Server". The LLM cannot choose a product it never sees.

**3. Answers were fully consistent.**
Every input received the same answer in all three uncached runs. This is a small sample, but it is the measurement asked for.

**4. One unknown input was wrongly accepted.**
It was accepted in all three runs with a score between 0.80 and 0.85. Which input it was is not shown by the current report; that needs to be checked, as the label itself may be debatable.

**5. Cost and latency are high for millions of requests per day.**

| Requests per day | LLM calls (70%) | Daily cost | Monthly cost |
|---|---|---|---|
| 1,000,000 | 700,000 | ~$2,300 | ~$70,000 |

This assumes no cache hits and this dataset's mix of inputs. Real traffic likely has more exact matches, which cost nothing. Latency of 2–5 seconds per LLM call is also slow at this volume.

## Cache simulation

How much the cache saves depends on how often the same names repeat in real traffic, which is unknown. To see how the cache behaves, a synthetic stream was replayed through the real cache with a free stand-in for the LLM:

```bash
python -m entity_resolver simulate-cache --skew 1.0
```

- 50,000 requests drawn from 20,000 unseen name variants. Every request needs the LLM unless it is cached.
- Popularity follows a Zipf distribution: a few names are very common, most are rare. Higher skew means more repetition.
- Cost per LLM call is the $0.0033 measured above. Daily figures assume 1,000,000 requests per day.
- Cache expiry is 24 hours, simulated by advancing a clock per request.

Cache hit rate:

| Cache size | Skew 0.8 (little repetition) | Skew 1.0 | Skew 1.2 (much repetition) |
|---|---|---|---|
| No cache | 0% | 0% | 0% |
| 100 KB | 25% | 52% | 78% |
| 1 MB | 58% | 77% | 90% |
| 10 MB | 73% | 81% | 90% |

Daily LLM cost at 1,000,000 requests:

| Cache size | Skew 0.8 | Skew 1.0 | Skew 1.2 |
|---|---|---|---|
| No cache | $3,300 | $3,300 | $3,300 |
| 100 KB | $2,474 | $1,580 | $737 |
| 1 MB | $1,378 | $747 | $344 |
| 10 MB | $884 | $620 | $342 |

What this shows:

- Most of the saving comes from a small cache. 1 MB, about 4,000–5,500 results at 180–250 bytes each, captures most of the benefit in all three scenarios.
- How repetitive traffic is matters more than cache size. The same 1 MB cache saves 58% or 90% depending on the skew.
- Once the cache holds every distinct name (10 MB here), the hit rate is limited only by how many names are new. Each new name costs one LLM call. This is Matan's point: new variations keep missing the cache.

Limits of the simulation:

- The skew is an assumption. Real hit rates need a replay of real extracted names.
- The stream has 50,000 requests, not a full day. Over 1,000,000 requests, popular names repeat more, so a large cache would likely hit more often.
- Every simulated request needs the LLM. Real traffic also has exact alias matches, which never reach the LLM or the cache.

## Limitations

- 20 inputs is a small sample. Single examples change precision and recall noticeably.
- The 70% LLM-call rate reflects this dataset, not real traffic.
- The test set (`data/eval/test.json`) has not been run. It should be run once, after the threshold is frozen.

## Next steps

1. Add the list of wrong predictions to the evaluation report, so the wrongly accepted input can be identified.
2. Improve retrieval for inputs with extra words, then re-measure candidate recall.
3. Measure a cheaper model (a smaller Claude model, or Jev) on the same set to reduce cost and latency.
4. Freeze the threshold and run the test set once.
5. Replay a sample of real extracted names through `simulate-cache` logic to measure the real cache hit rate.
