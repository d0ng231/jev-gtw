# Completed release validation

**No training.** The gateway uses the frozen StartLux-Decision-v1.1-0.8B-Instant
checkpoint at revision `6496ae641cc71b149ce9dad69bd97f2a44e7bf11`. Its release
threshold is 0.98. The prompt, threshold and inference implementation were frozen
before the scored runs; no threshold was selected from these results.

The implementation achieves high withholding through trusted source policy and
conservative contextual review. **The contextual path over-blocks: all permitted
views in the large cohort were withheld.** Do not interpret its zero prohibited
releases as useful PHI classification or a general zero-leakage guarantee.

## Existing public/synthetic cohort

4,528 decision contexts: 3,600 text and 928 image cases, 996 world/source groups
and 592 unique PNGs. Formats include CSV previews, JSON/JSONL, SQL-like results,
logs, code, schemas, clinical narratives, radiology-style text, FHIR/HL7-shaped
records, document images and charts. Medical and general contexts are both
represented. Matched scenarios change trusted authorization, task relevance,
recipient or source capability.

| Input | Cases | Prohibited originals withheld | Permitted originals released | Inspector failures |
|---|---:|---:|---:|---:|
| Text | 3,600 | 1,612 / 1,612 | 0 / 1,988 | 0 |
| Images | 928 | 336 / 336 | 0 / 592 | 0 |
| Total | 4,528 | **1,948 / 1,948** | **0 / 2,580** | 0 |

Of the 2,580 unnecessary withholds, 945 come from deterministic text vetoes and
1,635 from a model score below the release threshold. Both mechanisms are
conservative. All 928 image views reached the model and were withheld.

There were **2,572 model requests**, at most one per case. Other cases used
source restrictions, completeness checks or text vetoes. Warm decision latency
for inspected cases was 106 ms p50 / 265 ms p95, measured with six concurrent
workers on one A100 using vLLM 0.31.0 and BF16. Text p50/p95 was 95/118 ms;
image p50/p95 was 194/348 ms. Latency includes the HTTP request and gateway work;
it excludes model startup, and repeated image assets may benefit from caches.

Source groups in this cohort:

| Source | Selected material | Decision contexts |
|---|---|---:|
| [AI4Privacy OpenPII](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1.5m) | 300 annotated documents | 600 |
| [Gretel multilingual finance](https://huggingface.co/datasets/gretelai/synthetic_pii_finance_multilingual) | 200 synthetic documents | 400 |
| [Gretel English PII](https://huggingface.co/datasets/gretelai/gretel-pii-masking-en-v1) | 200 synthetic documents | 400 |
| [BigCodeBench](https://huggingface.co/datasets/bigcode/bigcodebench) | 100 public coding prompts | 200 |
| [ChartQA](https://github.com/vis-nlp/ChartQA) | 64 development images, matched permissions and overlays | 192 |
| [IDSpace](https://huggingface.co/datasets/cactuslab/IDSpace) | 80 synthetic identity documents | 160 |
| Authored text/control cases and rendered images | General and medical formats | 2,576 |

This is the existing research cohort reused to test the smaller release. It is
not an unseen independent holdout. Its source documents also appeared in prior
zero-shot research. Source annotations and constructed permission labels are
incomplete privacy ground truth; repeated worlds/renderings are dependent.
A native public image is not declared intrinsically PII-free. Approval is a
specific trusted policy, and image confidentiality may be simulated.

The new implementation never automatically redacts and releases an alternative.
The 20 legacy redacted-only source controls are conservatively mapped to
local-only. The score counts whether the **whole original** may be released,
not whether some transformed extract could be safe. The exact dataset rows and
images remain local; this repository publishes aggregates, source revisions and
file hashes, not a redistributable copy of that cohort.

## Reproducible public policy fixtures

`tools/make_cases.py` generates 512 fictional cases from 64 worlds. Each world
pairs text and images with four permission scenarios. The same chart can be
public or private by explicit policy; these are permission controls, not image
PHI-localization labels.

| Scenario | Cases | Result | Model calls |
|---|---:|---|---:|
| Protected default | 128 | 128 withheld | 0 |
| Exact approved public snapshots | 128 | 128 released | 0 |
| Contextual private | 128 | 128 withheld | 64 |
| Contextual public | 128 | 128 withheld | 128 |

These results demonstrate the usable strict path: approved navigation is
available, while protected sources remain local. They do not establish useful
automatic contextual permission judgment. The model adds no observed release
utility at this threshold in either cohort.

## Implementation checks

**57 test methods and 1,280 generated contract trials passed.** Coverage includes
hard source caps, trusted public hashes, changed text/images, one-use capability
binding, context mutation, malformed scores, timeouts/errors, symlinks and special
files, probe-output policy, transport redirects, actual MCP stdio calls and skill
installation into both Codex and Claude project directories.

**11 actual Apptainer scenarios passed:** an aggregate artifact was saved;
private stdout, stderr and exceptions were withheld; raw exit status was not
returned; inputs were read-only; external networking was blocked; host
credentials were absent; the host source path was unmounted; excessive output
and time were bounded. The aggregate fixture produced `{"total": 11}` locally.
An artifact receipt alone is not proof of successful task completion.

The MCP smoke test uses the official SDK to discover and invoke the actual
server, including a reviewed PNG. A full native Codex/Claude model conversation
was not run. Docker launch arguments are unit-tested, but a Docker daemon was
unavailable for live validation. There are no newly trained models or new live
Qwen/Gemma task-completion scores in this release.

## Interpretation and evidence

The prior frozen 2B research workflow used up to three model questions per
observation. On the same 4,528 contexts, it made 10,587 requests and released
405/2,580 permitted originals with zero tracked prohibited displays. The new
release uses a smaller checkpoint and one question, but it also changes vetoes,
prompt, threshold and redaction behavior. The request count decreases by 75.7%;
this is not an isolated model-size or speed ablation. The complete historical
records remain preserved locally.

The strict source policy is the dependable withholding mechanism. Contextual
model decisions, unrecognized PHI types, semantic/encoded disclosures, adaptive
query composition, full agent bypass resistance and clinical deployment remain
outside the demonstrated guarantees. No identified or de-identified patient data
was used in these release tests. No experimental rows or credentials are shipped.

Machine-readable evidence:

- [Large cohort metrics](../reports/release-v1/observations.json)
- [Synthetic policy fixtures](../reports/release-v1/public-fixtures.json)
- [Sandbox checks](../reports/release-v1/sandbox.json)
- [Test summary](../reports/release-v1/tests.json)
- [Frozen inference protocol](../reports/release-v1/protocol.json)
- [Source provenance](../reports/release-v1/sources.json)
