#!/usr/bin/env python3
"""Serial real-model cache microbenchmark, separate from concurrent accuracy runs."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import statistics
import time

from jev_gtw import Access, Context, Gateway, Observation, StartLuxJudge


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--endpoint',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();os.umask(0o077);args.out.mkdir(parents=True,mode=0o700,exist_ok=False)
    endpoint=json.loads(args.endpoint.read_text());token=Path(endpoint['api_key_file']).read_text().strip()
    rows=[]
    for cache_size in [0,128]:
        judge=StartLuxJudge(endpoint['base_url'],token=token,trusted_hosts=[endpoint['node']],cache_size=cache_size)
        gate=Gateway(judge)
        ctx=Context('Implement a public numeric helper.','Public code may be shown; personal records and credentials stay local.',session='cache-benchmark')
        obs=Observation(text='def total(values):\n    return sum(values)\n')
        for index in range(41):
            start=time.perf_counter();decision=gate.inspect(ctx,obs,Access('contextual'))
            messages=gate.messages(ctx,decision,tool_call_id=f'cache-{cache_size}-{index}')
            gate.validate_request(ctx,messages)
            rows.append({'cache_size':cache_size,'index':index,'action':decision.action,'model_calls':gate.events[-1]['model_calls'],
                         'cache_hit':gate.events[-1].get('cache_hit',False),'elapsed_ms':(time.perf_counter()-start)*1000})
    summary={'complete':True,'training':False,'checkpoint_sha256':endpoint['checkpoint_sha256'],'arms':{}}
    for cache_size in [0,128]:
        selected=[r for r in rows if r['cache_size']==cache_size];warm=selected[1:];latencies=sorted(r['elapsed_ms'] for r in warm)
        summary['arms'][str(cache_size)]={'requests':len(selected),'warm_requests':len(warm),'model_calls':sum(r['model_calls'] for r in selected),
            'cache_hits':sum(r['cache_hit'] for r in selected),'actions':dict(Counter(r['action'] for r in selected)),
            'warm_p50_ms':statistics.median(latencies),'warm_p95_ms':latencies[math.ceil(len(latencies)*.95)-1]}
    summary['limitations']='Single repeated text observation, unchanged session/history, serial requests, warm local model. Not general workload latency or cache hit rate.'
    (args.out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n');(args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
