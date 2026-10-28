# Completed evaluation: inference-only gateway improvements

The final gateway released more permitted text while preserving the 0.98
threshold and the frozen 0.8B checkpoint. It withheld all 5,016 prohibited views
across the completed final cohorts. **Over-blocking remains substantial**:
1,471/2,620 permitted views in the new set were withheld, including every
contextual public image. These are constructed permission labels, not clinical
PHI-detection annotations or a population-level safety estimate.

## Matched decision comparisons

| Workload and arm | Cases | Prohibited released | Permitted released |
|---|---:|---:|---:|
| Published baseline, new set | 5,432 | 0 / 2,812 | 132 / 2,620 (5.0%) |
| Final hybrid profile, new set | 5,432 | 0 / 2,812 | 1,149 / 2,620 (43.9%) |
| Rejected all-modality risk profile, reused regression | 4,528 | **8 / 1,948** | 359 / 2,580 |
| Final hybrid profile, reused regression | 4,528 | 0 / 1,948 | 294 / 2,580 |
| Final profile, fresh image challenge | 768 | 0 / 256 | 256 / 512 |

The new-set release/withhold classification accuracy increased from 54.2% to
72.9%. This combines source-policy controls and model review; it must not be
reported as a PHI recognizer's accuracy. The 768 image cases comprise 256
protected contextual views, 256 permitted contextual views and 256 exact
approved public snapshots. Only the approved snapshots were released.

The rejected image variant missed small fictional credentials in configuration
screenshots. The same pixels were withheld by the final image question. An
offline threshold replay at 0.95 released 1,955/2,620 permitted new-set views with
zero prohibited new-set releases, but released **one prohibited regression
view**. The shipping threshold therefore remains 0.98. The retained image route
is conservative, not demonstrated to be a useful automatic visual detector.

## What changed, and how it was selected

No model weights were updated. The default checkpoint remains
`startlux-models/StartLux-Decision-v1.1-0.8B-Instant`, revision
`6496ae641cc71b149ce9dad69bd97f2a44e7bf11`, with its required bidirectional prompt
attention through vLLM 0.31.0. The complete checkpoint fingerprint is recorded
in the [protocol](../reports/release-v2/protocol.json).

1. We compared four typed question formulations on **382 development views**
   from 38 source-document or synthetic-world groups. At the unchanged 0.98
   cutoff, the disclosure-risk question released 75/182 permitted views versus
   12/182 for the original permission question. Both withheld all 200 prohibited
   development views. No gold label was sent to the inspector.
2. We froze that text question and tested **5,432 new views** from 1,084 groups,
   disjoint from development at the source-document/world level. Templates are
   shared across splits. The new cohort includes 5,176 text and 256 image views.
3. The reused 4,528-case regression suite exposed eight screenshot releases.
   We rejected the all-modality change. The final `hybrid` profile uses the risk
   question for text and the original permission question whenever an image is
   present. **Image routing was revised after regression inspection**; the old
   and new cohorts are not pristine held-out evidence for that final decision.
4. We froze the hybrid route and then generated and evaluated a separate
   **768-case image challenge**, with 64 new worlds and 512 unique rendered
   images. No further prompt or threshold change was selected on those results.

The public baseline is commit `7a95a93b933cdb7b92c0e7f4268a686c490a76c6`.
Baseline and final new-set arms use identical case hashes and six inference
workers. The baseline was preserved and executed separately. Failed candidate
results remain in [comparison evidence](../reports/release-v2/comparisons.json).
The original release evidence remains under `reports/release-v1/`.

Implementation changes also include bounded Unicode/encoding checks, a
session/context-bound score cache, explicit navigation suggestions, and stricter
message validation. The validator now rejects unsupported roles, including
legacy `function`, and extra message fields that previously escaped the receipt
check. Plain trusted harness text and arbitrary top-level provider API arguments
remain outside its observation guarantee.

## Data and scenarios

| Source | Use in this experiment | Provenance |
|---|---|---|
| [MBPP](https://github.com/google-research/google-research/tree/master/mbpp) | Public Python problem descriptions, implementations and tests; paired with fictional private-record overlays. No code-generation benchmark score. | 974 eligible source documents; CC BY 4.0; revision `f82046ba5aabbbb427dbfd38a254d26bff08b533`. |
| [MedQuAD](https://github.com/abachaa/MedQuAD) | Public NIH medical reference questions/answers; paired with fictional private-record overlays. These are reference texts, not patient records. | 78 selected source documents with eligible answers from a fixed 160-file traversal sample; CC BY 4.0; revision `577bd37b96c02d1833b2c9eed2de9f96964e96cb`. |
| Authored text and screenshots | CSV, JSON, SQL, YAML, traceback, source diff, file listing, FHIR, HL7, XML, clinical prose, business records, Unicode, base64, URL encoding, injection, role spoofing, multilingual text, aggregates, history linkage and trusted scope changes. | Six development worlds and 64 test worlds; all individual records fictional. |
| Fresh authored image challenge | Credential panels, patient footers, contact corners and rotated labels, with 10–22 pixel text; matched public and protected views. | 64 new worlds, 512 unique PNGs, 768 permission contexts. |
| Reused regression sources | OpenPII, Gretel English/multilingual finance, BigCodeBench, ChartQA, IDSpace and earlier authored controls. | [Pinned source manifest](../reports/release-v1/sources.json). Previously inspected research data; not an untouched external test. |

Each public source document belongs to only one new split. The first 16
eligible documents per source are development; the others are test. Source
selection is deterministic, not a random population sample. Shared templates,
matched views and multiple renders are dependent. Reference content is not
executed by the gateway evaluator. No WCM data was read or used in this study.

## Actual coding-model workflows

Both local models used native tool calls through the official MCP Python client,
with the current gateway server and a real SingularityCE 4.3.1 container backend.
The models could call only `gateway_sources`, `gateway_read` and
`gateway_compute`. We asked each to attempt viewing the input and then adapt to
the returned feedback. Some episodes skipped that initial read; it was an
instruction, not a forced controller action.

| Model | Episodes | Created a correct artifact | Also returned a final response | Known canary exposures | Model requests | Tool calls |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.8-27B | 27 | 27 | 23 | 0 | 184 | 161 |
| Gemma 4 31B IT | 27 | 27 | 27 | 0 | 111 | 84 |

Nine task families each had three data variants: CSV thousands-separator repair,
CSV joins, JSONL error counts, read-only SQLite grouping, FHIR and HL7 numeric
aggregation, clinical diagnosis counts, private PNG dimensions, and approved
public PNG dimensions. The models wrote their own Python. The operator graded
`answer.json` inside the private artifact directory against the expected result.
The original artifact metric counts **any correct artifact during an episode**;
it does not require the agent to stop or its last probe to create the answer.

The follow-up audit found four Qwen episodes at the 12-turn limit: one FHIR and
three HL7 tasks. All had created correct artifacts, but none returned a final
response. Six other Qwen episodes ran follow-up verification probes assuming
earlier `/outputs` files persisted. Every call actually creates a fresh workspace.
The earlier correct artifacts remained saved; those six latest probes contained
no `answer.json`. Qwen's latest receipt had a correct answer in 21/27 episodes;
17/27 both returned a final response and had a correct answer in the latest
receipt. Gemma achieved 27/27 on both diagnostics. The latest-receipt diagnostic
is stricter than task artifact creation and does not invalidate earlier artifacts.

Here, a final response means an assistant message without tool calls. The saved
traces did not retain provider finish reasons, and response prose was not graded.
The audit therefore does not establish fully correct conversational completion.

Qwen issued 79 compute calls and Gemma 36. The withholding response deliberately
does not reveal execution success or raw exceptions, which can cause redundant
probes. The tool description now explains fresh workspaces and tells the agent
not to retry solely because output was withheld. This clarification has **not**
been evaluated in a new coding-model run. Approved
images actually reached Qwen in three episodes and Gemma in one; other image
work could be completed by local header inspection. This is not a broad visual
reasoning evaluation.

These are bounded, authored MCP tasks, not SWE-bench, native MBPP task scores,
or complete native Codex/Claude sessions. Local-only input/output rules enforce
protection in these episodes; contextual model accuracy is measured separately.
Known-canary and exact-private-image checks do not establish protection against
every semantic inference or covert channel. The harness omits native shell and
other bypass tools, so a real deployment must enforce equivalent separation.

Another **27 scripted MCP workflows** verified the same nine task families,
and **11 real container scenarios** passed: aggregate saving, stdout/stderr and
exception withholding, nonzero exit status, read-only inputs, network isolation,
clean environment, hidden host paths, capture bounds and timeout.

## Efficiency and robustness

The final new-set run made **3,514 model calls**, compared with 3,771 for the
baseline, after stronger deterministic text checks. At six workers on one A100
80 GB, warm inspected latency was 78 ms p50 / 150 ms p95. The baseline measured
81 ms / 144 ms. These workload-level timings cover different inspected subsets;
they do not show a uniform unique-request speedup.

A separate serial cache test used one unchanged public-code observation and
context for 41 requests per arm. Excluding the first request, median latency
was **30.31 ms without caching versus 0.47 ms with caching**; p95 was 31.13 ms
versus 0.59 ms. Calls fell from 41 to 1. This measures exact repeats, not the hit
rate or latency of general agent traffic.

The cache stores only hashes and scores, is bounded to 128 entries and 30
seconds by default, and binds context, recipient, session, history and
observation identity. Each hit still needs a fresh release capability. Tests
cover changes, eviction, expiry, malformed responses and failure non-caching.
The original suite passed **74 tests and 1,280 generated contract trials**;
the follow-up implementation suite passes **86 tests** with the same 1,280 trials.
Those counts cover implementation behavior, not independent privacy examples.

## Follow-up audit

The [offline audit](../reports/release-v2-audit.json) recomputed every published
comparison-arm total from raw per-case records, checked final-cohort case IDs,
labels, image hashes and frozen source snapshots, and independently regraded
artifacts from the 54 saved agent traces. All published decision totals match.
It replayed **10,728 final decisions** through the updated gateway using their
saved model scores; all actions and reasons remained unchanged. This is a code
compatibility check, not fresh inference or a new accuracy estimate.

A 5,000-message stress check reproduced an unbounded receipt registry in the
experiment version. The current implementation retains at most **4,096 message
hashes** by default. The newest receipt validates and an evicted receipt is
rejected. Tests additionally cover image receipt pairs, session isolation and
reissuance. The workflow grader now distinguishes artifact creation, final
response and latest-artifact correctness, and rejects oversized files and
symlinks in every artifact path component.

Model measurements belong to [commit 7c5cdfd](https://github.com/d0ng231/jev-gtw/tree/7c5cdfdcd48c0d84b29387b990e434fc2ae897d7).
All original `reports/release-v2` records are preserved. The separate audit pins
their hashes and the changed implementation. No training or additional model
inference was performed for this audit.

## Reproduce and inspect

Install `.[dev]`, set `TMPDIR` to private scratch, and use new output directories.
With the original raw records available locally, recheck them with
`python tools/audit_release.py --records eval/release/v2 --out reports/new-audit.json`.
That command publishes aggregates only; the public repository does not contain
the raw traces or source documents.

Fetch the exact source versions:

```bash
python tools/fetch_public_examples.py --out /path/to/public-sources \
  --mbpp-revision f82046ba5aabbbb427dbfd38a254d26bff08b533 \
  --medquad-revision 577bd37b96c02d1833b2c9eed2de9f96964e96cb
python tools/make_scenarios.py --out /path/to/scenarios \
  --public /path/to/public-sources/examples.json
python tools/evaluate.py --cases /path/to/scenarios/test.json \
  --out /path/to/results --url http://127.0.0.1:8090
python tools/make_image_challenge.py --out /path/to/image-challenge
```

`tools/exercise_workflows.py --help` runs scripted or local-model MCP workflows
against an operator-provisioned SIF and executable. A target endpoint manifest
must identify a ready local `/v1/chat/completions` server with native tool calling
and image support. It is a test harness, not an installer for the two large
coding models. `tools/benchmark_cache.py` uses the local inspector endpoint
manifest. The default checkpoint and container image hashes are recorded in the
public evidence; raw public documents, model weights and individual traces are
not redistributed.

Evidence: [decisions](../reports/release-v2/observations.json),
[comparisons](../reports/release-v2/comparisons.json),
[development](../reports/release-v2/development.json),
[image challenge](../reports/release-v2/image-challenge.json),
[agent workflows](../reports/release-v2/workflows.json),
[cache](../reports/release-v2/cache.json),
[tests](../reports/release-v2/tests.json),
[protocol](../reports/release-v2/protocol.json).
