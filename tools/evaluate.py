#!/usr/bin/env python3
"""Score complete-view release on labeled JSON cases, without training.

Use new output directories. Input format is illustrated by make_cases.py.
Permission labels are evaluation-only; they are never supplied to the judge.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

from jev_gtw import Access, Context, Gateway, Observation, StartLuxJudge, DEFAULT_MODEL, DEFAULT_REVISION


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(rows):
    restricted = [r for r in rows if not r['permitted']]
    permitted = [r for r in rows if r['permitted']]
    latencies = sorted(r['elapsed_ms'] for r in rows if r['model_calls'])
    return {
        'cases': len(rows), 'restricted': len(restricted),
        'restricted_withheld': sum(r['action'] != 'show' for r in restricted),
        'prohibited_original_releases': sum(r['action'] == 'show' for r in restricted),
        'permitted': len(permitted), 'permitted_released': sum(r['action'] == 'show' for r in permitted),
        'unnecessary_withholds': sum(r['action'] != 'show' for r in permitted),
        'model_calls': sum(r['model_calls'] for r in rows),
        'inspection_failures': sum(r['reason'] == 'inspection_failed' for r in rows),
        'actions': dict(Counter(r['action'] for r in rows)),
        'reasons': dict(Counter(r['reason'] for r in rows)),
        'inspected_latency_ms': {'n': len(latencies), 'p50': statistics.median(latencies) if latencies else None,
                                 'p95': latencies[math.ceil(len(latencies)*.95)-1] if latencies else None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8090')
    parser.add_argument('--trusted-host', action='append', default=[])
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--threshold', type=float, default=.98)
    parser.add_argument('--question-profile', choices=['hybrid','risk','permission'], default='hybrid')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--revision', default=DEFAULT_REVISION)
    parser.add_argument('--checkpoint-sha256')
    parser.add_argument('--token-file', type=Path)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error('workers must be between 1 and 16')
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False, mode=0o700)
    cases = json.loads(args.cases.read_text())
    token = args.token_file.read_text().strip() if args.token_file else os.environ.get('JEV_GTW_INSPECTOR_TOKEN','')
    root = Path(__file__).resolve().parents[1]
    files = [root/'jev_gtw'/name for name in ['__init__.py','core.py','judge.py','images.py','signals.py']] + [Path(__file__).resolve()]
    hashes = {str(p.relative_to(root)): sha(p) for p in files}
    protocol = {'training':False, 'model':args.model,'revision':args.revision,
                'checkpoint_sha256':args.checkpoint_sha256,'threshold':args.threshold,'workers':args.workers,
                'question_profile':args.question_profile,
                'case_sha256':sha(args.cases),'source_sha256':hashes,'cases':len(cases),
                'posthoc_tuning':False,'automatic_redaction':False,
                'legacy_redacted_policy':'Map redacted-only sources to local-only: no automatic candidate release.',
                'scoring':'Complete original view release vs constructed permission labels; not semantic leak detection.'}
    (args.out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    for p in files:
        target=args.out/'source'/p.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())

    def run(row):
        context = {k:v for k,v in row['context'].items() if k in Context.__dataclass_fields__}
        context['history']=tuple(context.get('history',()))
        item=dict(row['observation']);image_path=item.pop('image_path',None);image_hash=item.pop('image_sha256',None)
        if image_path:
            path=Path(image_path)
            if not path.is_absolute():path=args.cases.parent/path
            item['image']=path.read_bytes()
            if not image_hash or hashlib.sha256(item['image']).hexdigest()!=image_hash:
                raise ValueError('Image hash mismatch')
        policy=dict(row.get('access',{}))
        if policy.get('view')=='redacted':policy['view']='local'
        gate=Gateway(StartLuxJudge(args.url,token=token,trusted_hosts=args.trusted_host,
                                  question_profile=args.question_profile,cache_size=0),show_threshold=args.threshold)
        ctx=Context(**context);obs=Observation(**item)
        start=time.perf_counter();decision=gate.inspect(ctx,obs,Access(**policy))
        messages=gate.messages(ctx,decision,tool_call_id='evaluation')
        gate.validate_request(ctx,messages)
        event=gate.events[-1]
        # Audit the complete released view against the original captured bytes.
        if decision.action=='show':
            if messages[0]['content']!=obs.text or (len(messages)==2)!=(obs.image is not None):
                raise ValueError('Released payload audit failed')
        return {'id':row['id'],'kind':row.get('kind','image' if obs.image is not None else 'text'),
                'family':row.get('family','unspecified'),'group_id':row.get('group_id',row['id']),
                'domain':row.get('domain','unspecified'),'source_key':row.get('source_key','unspecified'),
                'permitted':row['gold']['original_permitted'],'action':decision.action,'reason':decision.reason,
                'model_calls':event['model_calls'],'event':event,'elapsed_ms':(time.perf_counter()-start)*1000}

    records=[];started=time.perf_counter()
    with (args.out/'results.jsonl').open('w') as stream, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run,row) for row in cases]
        for future in as_completed(futures):
            row=future.result();records.append(row);stream.write(json.dumps(row)+'\n')
            if len(records)%200==0:
                stream.flush();print(json.dumps({'completed':len(records),'total':len(cases)}),flush=True)
    for relative,expected in hashes.items():
        if sha(root/relative)!=expected:raise ValueError('Implementation changed during evaluation')
    if sha(args.cases)!=protocol['case_sha256']:raise ValueError('Cases changed during evaluation')
    metrics={'complete':True,'training':False,'overall':summarize(records),'elapsed_seconds':time.perf_counter()-started,
             'slices':{key:{v:summarize([r for r in records if r[key]==v]) for v in sorted({r[key] for r in records})}
                       for key in ['kind','domain','family','source_key']}}
    (args.out/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics['overall']),flush=True)


if __name__=='__main__':main()
