# Use JEV Gateway with Codex, Claude Code and custom harnesses

For a first run, start with the [no-GPU demo](../README.md#quick-start-no-gpu-required)
and its copyable client registration commands. This guide covers custom source
configuration, inference, local computation and harness integration.

The repository ships one portable skill and one stdio MCP server. No global
settings are changed by installation. Native client tool interception is not
claimed; the default integration covers these three gateway tools:

| Tool | Input | Result |
|---|---|---|
| `gateway_sources` | none | Operator-provided source IDs, kinds and coarse permissions. |
| `gateway_read` | `source_id` | Reviewed text/image or fixed withholding feedback. |
| `gateway_compute` | `source_ids`, `code` | Reviewed capture and a private-artifact receipt. Requires a sandbox. |

## Install and connect

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[mcp]'
python tools/install_skill.py --target both --project /path/to/task-project
jev-gtw check --config /absolute/path/to/gateway.json
```

Register the server in each client that you use:

```bash
codex mcp add jev_gtw -- /absolute/path/to/jev-gtw serve --config /absolute/path/to/gateway.json
claude mcp add --transport stdio --scope user jev_gtw -- /absolute/path/to/jev-gtw serve --config /absolute/path/to/gateway.json
```

Invoke `$jev-gtw` in Codex or `/jev-gtw` in Claude Code. The skill also works in
other clients supporting the Agent Skills format and MCP tools. The installer
copies only the skill and refuses to overwrite an existing installation.

The package's real stdio test uses the official MCP Python client to discover
and call the tools, including a reviewed image. The skill is validated and its
installation is tested for both client directory conventions. A full native
Codex/Claude model conversation was not executed in this release study.

## Start the smaller inspector

Install the official [StartLux runtime](https://github.com/StartLuxLabs/StartLux-Decision)
in its own GPU environment, following its supported vLLM dependencies. Then:

```bash
bash tools/serve_inspector.sh
```

This downloads the pinned 0.8B Instant checkpoint and starts the API on loopback
port 8090. Set `TMPDIR` to private scratch first. `JEV_GTW_GPUS`, `JEV_GTW_PORT`
and `JEV_GTW_MODEL_DIR` are optional deployment overrides. The default
[model weights](https://huggingface.co/startlux-models/StartLux-Decision-v1.1-0.8B-Instant)
are CC BY-NC 4.0, separately from this repository's MIT code.

The demonstration in `examples/gateway.json` needs no live model: its setup
and image have exact public grants, and records stay local. A contextual source
requires a ready inspector; unavailable inference withholds the view.

## Configure local computation

Add a `sandbox` object to the trusted config. Use an existing image digest and
an absolute owner-only artifact root. Set `TMPDIR` outside `/tmp`.

```json
{
  "sandbox": {
    "backend": "docker",
    "image": "python@sha256:<operator-selected-image-digest>",
    "artifact_root": "/private/gateway-artifacts",
    "timeout": 30
  }
}
```

For a cluster, use `backend: "apptainer"`, `image: "/private/python.sif"`,
`image_sha256: "<verified-sha256>"`, and optionally `executable`.
Run `tools/smoke_sandbox.py --help` for an executable fictional-data smoke test.
The release tested an actual Apptainer sandbox. Docker command construction
is unit-tested; a Docker daemon was unavailable for a live run.

Protected files and the configuration belong outside the coding agent's
filesystem access. For separated hosts, a stdio launcher can use an operator-
configured SSH connection to the gateway command. Constrain that connection
and OS account; do not give the agent unrestricted shell access to protected
storage. Merely copying a skill into the same-user workspace is cooperative
routing, not mandatory enforcement.

## Custom harness

```python
from jev_gtw import Access, Context, Gateway, Observation, StartLuxJudge

context = Context(task="Compute team totals.", policy="Individual rows stay local.")
gate = Gateway(StartLuxJudge())
observation = Observation(text=captured_stdout_and_stderr, complete=not_truncated)
decision = gate.inspect(context, observation, Access())  # local-only default
messages.extend(gate.messages(context, decision, tool_call_id=call_id))
gate.validate_request(context, messages)  # after final formatting
response = coding_model(messages)
```

The host supplies `Access("contextual")` only when the source permits conditional
display. Register an operator-reviewed immutable public view with
`Access("approved", approved_sha256=observation.fingerprint())`; do not compute
that grant automatically from an arbitrary tool result. For images, pass PNG
bytes to `Observation(image=...)` before the coding model sees them.

Official client references: [Codex MCP](https://developers.openai.com/codex/mcp/),
[Codex skills](https://developers.openai.com/codex/skills/),
[Claude Code MCP](https://code.claude.com/docs/en/mcp),
[Claude Code skills](https://code.claude.com/docs/en/skills).
