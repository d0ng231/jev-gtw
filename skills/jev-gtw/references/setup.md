# Operator setup

Install the `jev-gtw` Python package with its MCP extra from the repository:

```bash
python -m pip install -e '.[mcp]'
jev-gtw check --config /absolute/path/to/gateway.json
```

Register the same stdio server in either client. Use the absolute executable
path printed by `command -v jev-gtw` if it is installed in a virtual environment.

```bash
codex mcp add jev_gtw -- /absolute/path/to/jev-gtw serve --config /absolute/path/to/gateway.json
claude mcp add --transport stdio --scope user jev_gtw -- /absolute/path/to/jev-gtw serve --config /absolute/path/to/gateway.json
```

Copy this skill directory to `.agents/skills/jev-gtw` for Codex or
`.claude/skills/jev-gtw` for Claude Code. In a repository checkout,
`python tools/install_skill.py --target both --project /path/to/task-project`
does this without changing global client settings.

Invoke `$jev-gtw` in Codex or `/jev-gtw` in Claude Code. The MCP tool names may
have a client-specific prefix; discover them rather than assuming a prefix.

The default inspector is the pinned **StartLux-Decision-v1.1-0.8B-Instant**.
Use the repository's `tools/serve_inspector.sh` with the official StartLux
inference package installed in a separate GPU environment. It serves only on
loopback. No external model API is used for inspection. The model weights have
their own non-commercial license; the gateway code's license does not cover them.

The configuration is a trusted operator file outside the agent's writable
workspace. Most sources should omit `access`, which means local-only. Grant
`contextual` only for sources eligible for model-reviewed display; use `approved`
with a reviewed exact fingerprint for public setup text and images. Do not run
the fingerprint command on a protected file merely to approve it.

For enforcement, keep protected storage on a server or OS account inaccessible
to native agent tools. A local demo using the same account is cooperative use.
An SSH stdio launcher can place the gateway on a separate host; constrain that
account to the gateway command. Any bypass tool or direct chat upload can put
data into context before this skill runs. This package does not install global
hooks or automatically wrap native shell, file, search and image tools.

Official integration references:

- [Codex skills](https://developers.openai.com/codex/skills/)
- [Codex MCP](https://developers.openai.com/codex/mcp/)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
