#!/usr/bin/env python3
"""Build the latest completed English report from published aggregate evidence."""
import base64
import hashlib
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build():
    report=ROOT/'reports/release-v1'
    observation=json.loads((report/'observations.json').read_text())
    fixtures=json.loads((report/'public-fixtures.json').read_text())
    protocol=json.loads((report/'protocol.json').read_text())
    tests=json.loads((report/'tests.json').read_text())
    sandbox=json.loads((report/'sandbox.json').read_text())
    assert observation['complete'] and fixtures['complete'] and tests['passed'] and sandbox['passed']
    assert protocol['training'] is False
    for name,value in protocol['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value:
            raise ValueError('Report source differs from frozen inference implementation: '+name)
    m=observation['overall'];f=fixtures['overall']
    rows=''
    for kind in ['text','image']:
        x=observation['slices']['kind'][kind]
        rows+=f'<tr><td>{kind.title()}</td><td>{x["cases"]:,}</td><td>{x["restricted_withheld"]:,} / {x["restricted"]:,}</td><td>{x["permitted_released"]:,} / {x["permitted"]:,}</td></tr>'
    policy_rows=''
    labels={'protected':'Protected default','public_snapshot':'Approved public snapshot','contextual_private':'Contextual private','contextual_public':'Contextual public'}
    for key,label in labels.items():
        x=fixtures['slices']['family'][key]
        policy_rows+=f'<tr><td>{label}</td><td>{x["cases"]}</td><td>{x["actions"].get("show",0)} released</td><td>{x["model_calls"]}</td></tr>'
    pixels=base64.b64encode((ROOT/'examples/demo/chart.png').read_bytes()).decode()
    page=TEMPLATE.replace('{{ROWS}}',rows).replace('{{POLICY_ROWS}}',policy_rows).replace('{{IMAGE}}',pixels)
    replacements={'CASES':f'{m["cases"]:,}','FIXTURES':str(f['cases']),'METHODS':str(tests['methods']),
                  'TRIALS':f'{tests["generated_contract_trials"]:,}','PROBES':str(len(sandbox['scenarios'])),
                  'CALLS':f'{m["model_calls"]:,}','P50':str(round(m['inspected_latency_ms']['p50'])),
                  'P95':str(round(m['inspected_latency_ms']['p95']))}
    for key,value in replacements.items():page=page.replace('{{'+key+'}}',html.escape(value))
    if '{{' in page:raise ValueError('Unresolved report template')
    (ROOT/'index.html').write_text(page)
    print('Built index.html from completed release evidence.')


TEMPLATE='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JEV Gateway — Framework and completed validation</title>
<style>
:root{--ink:#142d3c;--muted:#536675;--line:#dae3e7;--green:#087c75;--pale:#edf7f5;--amber:#7a4b13}
*{box-sizing:border-box}body{margin:0;background:#f4f7f9;color:var(--ink);font:16px/1.6 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:48px 24px 70px}a{color:var(--green)}h1{font-size:clamp(32px,6vw,56px);line-height:1.08;letter-spacing:-2px;margin:12px 0 18px}h2{font-size:27px;letter-spacing:-.6px;margin:0 0 12px}h3{font-size:18px;margin:0 0 8px}
p{margin:0 0 16px}.eyebrow{color:var(--green);font-size:12px;font-weight:750;letter-spacing:2px;text-transform:uppercase}.lead{max-width:800px;font-size:20px;color:var(--muted)}nav{display:flex;gap:22px;flex-wrap:wrap;margin:24px 0 32px}nav a{text-decoration:none;font-weight:600}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0 40px}.stat{padding:18px;border:1px solid var(--line);background:white;border-radius:12px}.stat strong{font-size:28px;display:block}.stat span{font-size:13px;color:var(--muted)}
section{background:white;border:1px solid var(--line);border-radius:16px;padding:30px;margin:22px 0}.sub{color:var(--muted)}.diagram{overflow-x:auto;margin:24px 0}.diagram svg{width:100%;min-width:700px;height:auto;display:block}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.card{border:1px solid var(--line);border-radius:12px;padding:20px}.note{background:var(--pale);padding:18px 20px;border-left:4px solid var(--green);border-radius:4px;margin:20px 0}.warning{background:#fff7e9;border-left-color:#b47526;color:var(--amber)}
table{border-collapse:collapse;width:100%;margin:16px 0 22px;font-size:15px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:12px 9px}th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.4px}.table-wrap{overflow-x:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:16px;border-radius:8px;line-height:1.5;font-size:13px}code{font-family:ui-monospace,monospace;font-size:.9em}.steps{counter-reset:step}.step{position:relative;padding:2px 0 20px 44px}.step:before{counter-increment:step;content:counter(step);position:absolute;left:0;top:0;background:var(--pale);color:var(--green);width:28px;height:28px;border-radius:50%;text-align:center;font-weight:bold}.step p{margin-bottom:5px}.small{font-size:13px;color:var(--muted)}figure{margin:0}figcaption{font-size:13px;color:var(--muted);margin-top:12px}.image{width:100%;height:130px;object-fit:contain;border:1px solid var(--line);background:#eef4f7;border-radius:8px}summary{cursor:pointer;font-weight:650;color:var(--green)}details{margin-top:20px}footer{font-size:13px;color:var(--muted);margin-top:25px}
@media(max-width:700px){main{padding:25px 14px}.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}section{padding:21px 16px}.stat strong{font-size:24px}h1{letter-spacing:-1px}}
@media print{body{background:white}main{padding:0}section{break-inside:avoid}nav{display:none}a{color:inherit}.diagram svg{min-width:0}details{display:block}}
</style></head><body><main>
<div class="eyebrow">Inference only · Portable agent skill · Local MCP server</div>
<h1>JEV Gateway</h1>
<p class="lead">Keep protected data local. Give coding agents a permitted way to inspect public context and compute over private inputs.</p>
<p>Default inspector: <strong>StartLux-Decision-v1.1-0.8B-Instant</strong>. No training or weight updates.</p>
<nav aria-label="Report navigation"><a href="#setup">Framework</a><a href="#workflow">Agent workflow</a><a href="#results">Completed results</a><a href="skills/jev-gtw/SKILL.md">Agent skill</a><a href="docs/INTEGRATIONS.md">Install</a></nav>
<div class="stats"><div class="stat"><strong>{{CASES}}</strong><span>Text / image decision contexts</span></div><div class="stat"><strong>{{FIXTURES}}</strong><span>Reproducible policy fixtures</span></div><div class="stat"><strong>{{METHODS}}</strong><span>Passing implementation tests</span></div><div class="stat"><strong>{{PROBES}}</strong><span>Real sandbox scenarios</span></div></div>
<section id="setup"><h2>1. One observation boundary</h2>
<p class="sub">The operator owns the task, recipient, source permissions and approved public snapshots. The coding agent requests a source handle or submits probe code.</p>
<div class="diagram"><svg viewBox="0 0 1000 320" role="img" aria-labelledby="flow-title flow-desc" xmlns="http://www.w3.org/2000/svg">
<title id="flow-title">Coding agent, trusted gateway and private computation</title><desc id="flow-desc">The agent uses MCP tools. Protected views are withheld. Exact approved public views pass immediately. Contextual views require one model check. Sandbox output is reviewed before any return to the agent, while artifacts stay local.</desc>
<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#6e8792"/></marker></defs>
<g fill="none" stroke="#6e8792" stroke-width="2" marker-end="url(#arrow)"><path d="M190 85 H245"/><path d="M420 85 H465"/><path d="M655 65 H720"/><path d="M655 95 H690 V157 H720"/><path d="M655 115 H670 V242 H720"/><path d="M190 242 H245"/><path d="M420 242 H560 V135"/></g>
<g font-family="system-ui,sans-serif" fill="#142d3c"><rect x="10" y="45" width="180" height="80" rx="12" fill="#edf7f5" stroke="#087c75"/><text x="100" y="77" text-anchor="middle" font-weight="700" font-size="17">Coding agent</text><text x="100" y="100" text-anchor="middle" font-size="13">Codex / Claude Code</text>
<rect x="245" y="45" width="175" height="80" rx="12" fill="#f3f6f8" stroke="#dae3e7"/><text x="332" y="77" text-anchor="middle" font-weight="700" font-size="17">Guarded MCP tools</text><text x="332" y="100" text-anchor="middle" font-size="13">Read / local compute</text>
<rect x="465" y="35" width="190" height="100" rx="12" fill="#edf7f5" stroke="#087c75"/><text x="560" y="66" text-anchor="middle" font-weight="700" font-size="18">Trusted policy</text><text x="560" y="91" text-anchor="middle" font-size="13">Task · recipient · source</text><text x="560" y="112" text-anchor="middle" font-size="13">Bound exact release bytes</text>
<rect x="720" y="35" width="265" height="60" rx="10" fill="#edf7f5" stroke="#087c75"/><text x="852" y="60" text-anchor="middle" font-weight="700" font-size="15">Exact public view → show</text><text x="852" y="81" text-anchor="middle" font-size="12">No model call</text>
<rect x="720" y="125" width="265" height="65" rx="10" fill="#fff7e9" stroke="#d8b785"/><text x="852" y="151" text-anchor="middle" font-weight="700" font-size="15">Protected source → withhold</text><text x="852" y="173" text-anchor="middle" font-size="12">Fixed feedback; records stay local</text>
<rect x="720" y="215" width="265" height="65" rx="10" fill="#f3f6f8" stroke="#dae3e7"/><text x="852" y="240" text-anchor="middle" font-weight="700" font-size="15">Contextual → one 0.8B check</text><text x="852" y="263" text-anchor="middle" font-size="12">Score ≥ 0.98 required to show</text>
<rect x="10" y="205" width="180" height="75" rx="12" fill="#f3f6f8" stroke="#dae3e7"/><text x="100" y="234" text-anchor="middle" font-weight="700" font-size="16">Registered inputs</text><text x="100" y="257" text-anchor="middle" font-size="12">Private text / PNG / tables</text>
<rect x="245" y="205" width="175" height="75" rx="12" fill="#f3f6f8" stroke="#dae3e7"/><text x="332" y="234" text-anchor="middle" font-weight="700" font-size="16">Isolated sandbox</text><text x="332" y="257" text-anchor="middle" font-size="12">Outputs saved privately</text>
<text x="467" y="262" font-size="12">Capture → review again</text><text x="10" y="310" font-size="13" fill="#536675">Only admitted content or fixed feedback returns to the agent. A skill guides routing; host isolation enforces access.</text></g></svg></div>
<div class="grid"><div class="card"><h3>Smaller, simpler runtime</h3><p>One typed permission question; no generated explanation, automatic redaction retry or relevance cascade. Explicit source caps and public hashes skip inference.</p></div><div class="card"><h3>Closed on uncertainty</h3><p>Incomplete captures, invalid images, missing inference and malformed scores withhold the view. Modified released text or image payloads fail validation.</p></div></div>
<div class="note">Default sources are <code>local</code>. Conditional display requires an operator grant. A score of 0.98 is a threshold, not a calibrated 98% safety guarantee.</div>
</section>
<section id="workflow"><h2>2. How the agent works with it</h2>
<div class="grid"><div class="steps"><div class="step"><h3>Get permitted context</h3><p><code>gateway_sources</code> lists registered handles. <code>gateway_read("setup")</code> returns the approved task and schema.</p></div><div class="step"><h3>Request a data view</h3><p><code>gateway_read("records")</code> returns <code>local</code>. It does not open the protected file just to reject the view.</p></div><div class="step"><h3>Compute without displaying rows</h3><p><code>gateway_compute(["records"], code)</code> runs Python with read-only inputs and no network. Captured output is reviewed too.</p></div><div class="step"><h3>Keep artifacts local</h3><p>Save under <code>/outputs</code>. The agent gets a random receipt; the operator can verify the private artifact. A receipt alone does not prove success.</p></div></div>
<div><h3>Example tool response</h3><pre>{
  "action": "local",
  "reason": "source_local_only",
  "text": "[Gateway] Content withheld. Write a local probe..."
}</pre><h3>Probe input / output</h3><p class="small">Fictional sandbox test: two rows with units 4 and 7. Names remain in the sandbox.</p><pre>total = sum(int(row["units"]) for row in rows)
json.dump({"total": total}, open("/outputs/answer.json", "w"))

# Verified locally: {"total": 11}</pre>
<figure><img class="image" src="data:image/png;base64,{{IMAGE}}" width="80" height="40" alt="Solid blue fictional PNG used to test an approved public image route"><figcaption>The demo's exact approved PNG is delivered as an MCP image. Protected images are withheld; native image uploads are not automatically intercepted.</figcaption></figure></div></div>
<details><summary>Use the portable skill</summary><pre>python tools/install_skill.py --target both --project /path/to/task-project

Codex invocation: $jev-gtw
Claude Code invocation: /jev-gtw</pre><p>Register the local MCP server using the <a href="docs/INTEGRATIONS.md">integration guide</a>. The skill teaches the three tools; it does not rewrite client-wide permissions.</p></details>
<p class="small">Keep protected storage and operator configuration outside native agent access. Same-user local demos provide cooperative routing, not mandatory isolation from every other tool.</p>
</section>
<section id="results"><h2>3. Completed validation</h2>
<p><strong>{{CASES}} existing text/image cases</strong> cover medical and general formats: documents, table previews, logs, code, schemas, clinical narratives, charts and synthetic identity images. Sources include OpenPII, Gretel, BigCodeBench, ChartQA and IDSpace, with constructed task/permission contexts.</p>
<div class="table-wrap"><table><thead><tr><th>Input</th><th>Cases</th><th>Prohibited withheld</th><th>Permitted released</th></tr></thead><tbody>{{ROWS}}</tbody></table></div>
<div class="note warning"><strong>High withholding, substantial over-blocking.</strong> All 1,948 prohibited views were withheld, and all 2,580 permitted views were also withheld. The model path has not demonstrated useful automatic release judgment at this threshold. These are not clinical PHI-detection accuracy results.</div>
<h3>{{FIXTURES}} reproducible policy fixtures</h3><div class="table-wrap"><table><thead><tr><th>Route</th><th>Cases</th><th>Outcome</th><th>Model calls</th></tr></thead><tbody>{{POLICY_ROWS}}</tbody></table></div>
<p>Approved public navigation remains usable: 128/128 exact public snapshots passed, with no model calls. The protected default withheld 128/128 views. These controls validate policy enforcement separately from the learned reviewer.</p>
<div class="grid"><div class="card"><h3>Inference cost</h3><p><strong>{{CALLS}} requests</strong> on the large cohort; at most one model question per observation. Warm inspected decisions: <strong>{{P50}} ms p50 / {{P95}} ms p95</strong>, six workers on one A100. No inspector errors.</p></div><div class="card"><h3>Boundary and sandbox checks</h3><p><strong>{{METHODS}} tests + {{TRIALS}} generated trials</strong> passed, including real MCP stdio and skill installation. <strong>{{PROBES}} real Apptainer scenarios</strong> passed, including private output withholding and a saved aggregate.</p></div></div>
<p class="small" style="margin-top:18px">The large cohort is reused research data with dependent matched contexts, not an independent population sample. The public fixtures are synthetic policy controls. Docker argument checks passed; live Docker and full native Codex/Claude conversations were not run. No training or new coding-agent completion study is claimed.</p>
<p><a href="docs/RESULTS.md">Full methods, source attribution and limitations</a> · <a href="reports/release-v1/observations.json">Aggregate metrics</a> · <a href="reports/release-v1/protocol.json">Frozen protocol</a></p>
</section><footer>Latest completed release validation only. Gateway code: MIT. Default model weights: CC BY-NC 4.0. Experimental records stay local; this report contains aggregates and fictional examples.</footer>
</main></body></html>'''


if __name__=='__main__':build()
