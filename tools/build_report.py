#!/usr/bin/env python3
"""Build the latest completed report from release-v2 aggregate evidence."""
import base64
import hashlib
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build():
    report=ROOT/'reports/release-v2'
    def load(name):return json.loads((report/name).read_text())
    observation=load('observations.json');comparison=load('comparisons.json');images=load('image-challenge.json')
    workflows=load('workflows.json');tests=load('tests.json');cache=load('cache.json');protocol=load('protocol.json')
    assert all(obj.get('complete',obj.get('passed',False)) for obj in [observation,comparison,images,workflows,tests,cache,protocol])
    assert protocol['training'] is False
    for name,expected in protocol['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Report implementation differs from frozen experiment: '+name)
    def row(values):return '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>'
    arms=comparison['arms'];m=observation['overall'];rows=''
    for label,key in [('Published baseline / new set','baseline-test'),('Final gateway / new set','final-test'),
                      ('Rejected all-modality risk / regression','legacy-regression'),('Final gateway / regression','final-regression')]:
        a=arms[key]['overall']
        rows+=row([label,f"{a['cases']:,}",f"{a['prohibited_original_releases']} / {a['restricted']:,}",f"{a['permitted_released']:,} / {a['permitted']:,}"])
    a=images['overall'];rows+=row(['Fresh image challenge',a['cases'],f"{a['prohibited_original_releases']} / {a['restricted']}",f"{a['permitted_released']} / {a['permitted']}"])
    agent_rows='';families={}
    for key,agent in workflows['agents'].items():
        agent_rows+=row([agent['model'],f"{agent['artifact_pass']} / {agent['episodes']}",agent['known_canary_exposures'],agent['target_requests']])
        for result in agent['rows']:
            family=result['family'];families.setdefault(family,{})
            passed,total=families[family].get(key,(0,0));families[family][key]=(passed+int(result['artifact_pass']),total+1)
    task_rows=''.join(row([family.replace('_',' '),*(f"{families[family][model][0]} / {families[family][model][1]}" for model in ['qwen','gemma'])]) for family in families)
    example_rows=''.join(row([e['text'],'Allowed' if e['permitted'] else 'Withhold',e['action'],e['reason']]) for e in load('examples.json')['examples'] if e['kind']=='text')
    values={'ROWS':rows,'AGENT_ROWS':agent_rows,'TASK_ROWS':task_rows,'EXAMPLE_ROWS':example_rows,
            'IMAGE':base64.b64encode((ROOT/'examples/demo/chart.png').read_bytes()).decode(),
            'FAILURE_IMAGE':base64.b64encode((ROOT/'examples/demo/credential-panel.png').read_bytes()).decode(),
            'CASES':f"{m['cases']:,}",'FIXTURES':str(a['cases']),'METHODS':str(tests['methods']),
            'PROBES':str(sum(x['episodes'] for x in workflows['agents'].values())),
            'SCRIPTED':str(workflows['scripted']['artifact_pass']),
            'ALLOWED_RATE':f"{100*m['permitted_released']/m['permitted']:.1f}%",
            'BASELINE_RATE':f"{100*arms['baseline-test']['overall']['permitted_released']/m['permitted']:.1f}%",
            'CALLS_BEFORE':str(arms['baseline-test']['overall']['model_calls']),'CALLS':str(m['model_calls']),
            'P50':str(round(m['inspected_latency_ms']['p50'])),'P95':str(round(m['inspected_latency_ms']['p95'])),
            'CACHE_BEFORE':f"{cache['arms']['0']['warm_p50_ms']:.2f}",'CACHE_AFTER':f"{cache['arms']['128']['warm_p50_ms']:.2f}"}
    page=TEMPLATE
    for key,value in values.items():page=page.replace('{{'+key+'}}',value)
    if '{{' in page:raise ValueError('Unresolved report template')
    (ROOT/'index.html').write_text(page)
    print('Built completed release-v2 report, including failed comparison arms.')


TEMPLATE='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JEV Gateway — PII/PHI Guardrails for Coding Agents | Validation Report</title>
<meta name="description" content="JEV Gateway: local PII/PHI data-access guardrails for coding agents. Framework, MCP workflow, 0.8B inspector and completed validation results.">
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
<div class="stats"><div class="stat"><strong>{{CASES}}</strong><span>New text / image cases</span></div><div class="stat"><strong>{{FIXTURES}}</strong><span>Fresh image challenge cases</span></div><div class="stat"><strong>{{METHODS}}</strong><span>Passing implementation tests</span></div><div class="stat"><strong>{{PROBES}}</strong><span>Live coding-model episodes</span></div></div>
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
<div class="grid"><div class="card"><h3>Smaller, simpler runtime</h3><p>One typed question, selected by modality; no generated explanation, automatic redaction retry or relevance cascade. Explicit source caps and public hashes skip inference.</p></div><div class="card"><h3>Closed on uncertainty</h3><p>Incomplete captures, invalid images, missing inference and malformed scores withhold the view. Modified released text or image payloads fail validation.</p></div></div>
<p>Withheld reads return configured next steps. Exact repeated scores can be cached for 30 seconds with a 128-entry bound; cache keys bind the full context, session and observation. No raw records are stored in the cache. Every release still gets a fresh capability. Unicode and encoded identifiers receive bounded checks, and unknown message roles or extra fields are rejected.</p>
<div class="note">Default sources are <code>local</code>. Conditional display requires an operator grant. A score of 0.98 is a threshold, not a calibrated 98% safety guarantee.</div>
</section>
<section id="workflow"><h2>2. How the agent works with it</h2>
<div class="grid"><div class="steps"><div class="step"><h3>Get permitted context</h3><p><code>gateway_sources</code> lists registered handles. <code>gateway_read("setup")</code> returns the approved task and schema.</p></div><div class="step"><h3>Request a data view</h3><p><code>gateway_read("records")</code> returns <code>local</code>. It does not open the protected file just to reject the view.</p></div><div class="step"><h3>Compute without displaying rows</h3><p><code>gateway_compute(["records"], code)</code> runs Python with read-only inputs and no network. Captured output is reviewed too.</p></div><div class="step"><h3>Keep artifacts local</h3><p>Save under <code>/outputs</code>. The agent gets a random receipt; the operator can verify the private artifact. A receipt alone does not prove success.</p></div></div>
<div><h3>Example tool response</h3><pre>{
  "action": "local",
  "reason": "source_local_only",
  "text": "[Gateway] Content withheld. Write a local probe...",
  "next_steps": [
    {"tool": "gateway_read", "arguments": {"source_id": "setup"}},
    {"tool": "gateway_compute", "source_ids": ["records"]}
  ]
}</pre><h3>Probe input / output</h3><p class="small">Fictional sandbox test: two rows with units 4 and 7. Names remain in the sandbox.</p><pre>total = sum(int(row["units"]) for row in rows)
json.dump({"total": total}, open("/outputs/answer.json", "w"))

# Verified locally: {"total": 11}</pre>
<figure><img class="image" src="data:image/png;base64,{{IMAGE}}" width="80" height="40" alt="Solid blue fictional PNG used to test an approved public image route"><figcaption>The demo's exact approved PNG is delivered as an MCP image. Protected images are withheld; native image uploads are not automatically intercepted.</figcaption></figure></div></div>
<details><summary>Use the portable skill</summary><pre>python tools/install_skill.py --target both --project /path/to/task-project

Codex invocation: $jev-gtw
Claude Code invocation: /jev-gtw</pre><p>Register the local MCP server using the <a href="docs/INTEGRATIONS.md">integration guide</a>. The skill teaches the three tools; it does not rewrite client-wide permissions.</p></details>
<p class="small">Keep protected storage and operator configuration outside native agent access. Same-user local demos provide cooperative routing, not mandatory isolation from every other tool.</p>
</section>
<section id="results"><h2>3. Completed comparisons and live agent tasks</h2>
<p><strong>5,432 new views across 35 scenario families and 1,084 document/world groups.</strong> Inputs include public MBPP code/tests and MedQuAD medical reference material, fictional record overlays, schemas, errors, encodings, prompt injection, history changes and screenshots.</p>
<p><strong>No training.</strong> Four question formats were compared on 382 development views. The chosen text question asks whether disclosure would violate policy. A regression failure then caused the image route to retain the original permission question. The 0.98 threshold and 0.8B weights remain unchanged. A fresh 768-case image challenge followed that correction.</p>
<div class="table-wrap"><table><thead><tr><th>Completed arm</th><th>Cases</th><th>Prohibited released</th><th>Permitted released</th></tr></thead><tbody>{{ROWS}}</tbody></table></div>
<div class="note"><strong>Permitted-view release improved from {{BASELINE_RATE}} to {{ALLOWED_RATE}} on the same new set.</strong> All 2,812 prohibited views were withheld. However, 1,471 of 2,620 permitted views still failed to pass. This is a policy-release evaluation, not a clinical PHI-detection benchmark.</div>
<div class="note warning"><strong>Two tempting changes failed regression.</strong> Applying the text risk question to images released eight protected credential screenshots. An offline 0.95 threshold replay released one prohibited regression view. The final gateway keeps the original image question and 0.98 threshold. On the fresh image challenge, all 256 approved public snapshots passed, but all 256 contextual public images remained blocked.</div>
<h3>Real coding models through MCP and an isolated container</h3>
<p>Qwen3.8-27B and Gemma 4 31B IT ran locally with native tool calling through the official MCP client. Each episode asked the model to try viewing its input, follow withholding feedback, write Python, and save <code>answer.json</code>. The operator graded private artifacts against exact expected results.</p>
<div class="table-wrap"><table><thead><tr><th>Local model</th><th>Correct artifacts</th><th>Known canary exposures</th><th>Model requests</th></tr></thead><tbody>{{AGENT_ROWS}}</tbody></table></div>
<details><summary>Nine task families, three data variants each</summary><table><thead><tr><th>Task</th><th>Qwen correct</th><th>Gemma correct</th></tr></thead><tbody>{{TASK_ROWS}}</tbody></table></details>
<p class="small">These are authored tasks, not SWE-bench/MBPP task scores or native Codex/Claude sessions. The harness exposes only gateway MCP tools. Local-only source and output policies enforce withholding; these episodes measure workflow usefulness separately from contextual detector accuracy. {{SCRIPTED}} scripted MCP workflows and 11 adversarial SingularityCE container scenarios also passed.</p>
<div class="grid"><div class="card"><h3>Efficiency</h3><p>New-set model calls fell from {{CALLS_BEFORE}} to {{CALLS}} through stronger deterministic checks. Warm inspected decisions at six workers: <strong>{{P50}} ms p50 / {{P95}} ms p95</strong> on one A100.</p><p>For a serial exact-repeat workload, median latency fell from <strong>{{CACHE_BEFORE}} ms to {{CACHE_AFTER}} ms</strong>; 41 requests used one model call with caching instead of 41.</p><p class="small">The cache result applies to identical repeated requests; it is not a general traffic hit rate or latency guarantee.</p></div><div class="card"><h3>Robustness</h3><p><strong>{{METHODS}} tests and 1,280 generated contract trials</strong> passed. Checks cover exact release bytes, context/session changes, cache expiry, malformed scores, Unicode/encoding vetoes, source paths, MCP transport and sandbox isolation.</p><p>Across the final new, regression and fresh-image sets, <strong>5,016/5,016 prohibited views were withheld</strong>. Cases share templates and paired contexts; this observed result is not a universal safety guarantee.</p></div></div>
</section>
<section id="cases"><h2>4. Individual cases and remaining failures</h2>
<div class="table-wrap"><table><thead><tr><th>Authored input</th><th>Expected</th><th>Final action</th><th>Reason</th></tr></thead><tbody>{{EXAMPLE_ROWS}}</tbody></table></div>
<p>The empty CSV schema is a remaining false positive. The agent can request the operator-approved setup view suggested by <code>next_steps</code>; a model refusal does not automatically weaken source permissions.</p>
<figure><img style="width:100%;height:auto;border:1px solid #dae3e7;border-radius:12px" src="data:image/png;base64,{{FAILURE_IMAGE}}" alt="Fictional configuration panel containing a simulated API key, released by the rejected variant and withheld by the final gateway"><figcaption>Preserved fictional failure case: the all-modality risk question released this credential panel; the final image question withheld the same bytes. No real credentials or patient data are pictured.</figcaption></figure>
<p style="margin-top:20px"><a href="docs/RESULTS.md">Methods, sources and limitations</a> · <a href="reports/release-v2/comparisons.json">Comparison evidence</a> · <a href="reports/release-v2/protocol.json">Frozen implementation</a></p>
</section><footer>Latest completed experiment only. Inference without training. Code: MIT; default model weights: CC BY-NC 4.0. Source documents and private traces stay local; this report contains aggregates and fictional examples.</footer>
</main></body></html>'''


if __name__=='__main__':build()
