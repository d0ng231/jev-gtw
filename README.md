# jev-gtw

A small, local observation gateway for coding agents. Keep protected text and
images out of model context, give the agent useful next-step feedback, and run
its data-processing probes inside an isolated local sandbox. **No training.**

The default inspector is **StartLux-Decision-v1.1-0.8B-Instant**. Trusted source
policy comes first; the model gets one typed permission question only for
explicitly contextual sources. Public setup/schema views use exact approved
fingerprints and need no model call.

[Visual report](index.html) · [Architecture](docs/ARCHITECTURE.md) ·
[Codex / Claude setup](docs/INTEGRATIONS.md) · [Portable skill](skills/jev-gtw/SKILL.md)

```text
Coding agent -> guarded MCP tools -> trusted source policy
                                      | protected -> withhold / local probe
                                      | approved exact view -> release
                                      | contextual -> 0.8B JEV -> release or withhold
Local sandbox -> captured stdout/stderr -> same gateway
              -> private artifacts remain local
```

## Quick start

Python 3.10+ on POSIX; the MCP extra provides the server. The core has no external
Python dependencies. Run from a repository checkout:

```bash
python -m pip install -e '.[mcp]'
jev-gtw check --config examples/gateway.json
jev-gtw read --config examples/gateway.json setup
jev-gtw read --config examples/gateway.json records
```

The fictional demo works without a GPU: public setup is shown, records are
withheld. Probe execution is disabled until an operator configures a sandbox.
For contextual model review, install the official StartLux runtime in a GPU
environment and run `bash tools/serve_inspector.sh`; it downloads the pinned
0.8B model. Set `TMPDIR` to private scratch first.

## Use as an agent skill

```bash
python tools/install_skill.py --target both --project /path/to/task-project
codex mcp add jev_gtw -- /absolute/path/to/jev-gtw serve --config /absolute/path/to/gateway.json
claude mcp add --transport stdio --scope user jev_gtw -- /absolute/path/to/jev-gtw serve --config /absolute/path/to/gateway.json
```

Invoke `$jev-gtw` in Codex or `/jev-gtw` in Claude Code. The same skill describes
`gateway_sources`, `gateway_read` and `gateway_compute`. Installation does not
modify global client configuration; the registration commands above do.

**A skill is guidance, not the security boundary.** Put protected storage and
operator configuration outside native agent access. The MCP tools enforce their
own routes; native shell/read/image tools, other servers and direct chat uploads
are not automatically intercepted. See the [deployment boundary](docs/ARCHITECTURE.md#deployment-boundary).

## Completed validation

- **4,528 existing text/image cases:** 1,948/1,948 prohibited originals withheld.
  All 2,580 permitted views were also withheld. Contextual release is therefore
  highly conservative and not validated as useful automatic permission judgment.
- **512 reproducible synthetic policy fixtures:** all 256 prohibited views withheld;
  all 128 exact approved public snapshots released. The 128 contextual public
  views were withheld. Policy enforcement and model accuracy are separate results.
- **57 tests plus 1,280 generated contract trials**, real MCP stdio tool calls,
  and **11 actual Apptainer probe scenarios** passed. A local aggregate was saved
  without exposing the input records.

The large cohort made 2,572 model calls, at most one per observation. Warm
six-worker decision latency for inspected cases was approximately **106 ms p50 /
265 ms p95** on one A100. This is not a cold-start or isolated hardware benchmark.
No weights were updated. Full counts, limitations and provenance are in
[RESULTS.md](docs/RESULTS.md).

## Reproduce

```bash
python -m pip install -e '.[dev]'
python -B -m unittest discover -s tests -v
python tools/make_cases.py --out /path/to/new-fixtures
python tools/evaluate.py --cases /path/to/new-fixtures/cases.json \
  --out /path/to/new-results --url http://127.0.0.1:8090
```

Use a new directory for every evaluation. These synthetic fixtures are policy
controls; they are not a clinical PHI benchmark. External source rows, research
traces, local credentials and model weights are excluded from this repository.
`tools/smoke_sandbox.py` exercises an operator-configured container with fictional
inputs. No training scripts are included.

Gateway code: MIT. The default [StartLux model](https://huggingface.co/startlux-models/StartLux-Decision-v1.1-0.8B-Instant)
weights: **CC BY-NC 4.0**, separately licensed; the model is not an unrestricted
commercial dependency. See [NOTICE](NOTICE).
