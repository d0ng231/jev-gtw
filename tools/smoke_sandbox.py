#!/usr/bin/env python3
"""Exercise a real configured sandbox with fictional inputs, never host execution."""
import argparse
import json
import os
from pathlib import Path

from jev_gtw import Access, Context, Gateway
from jev_gtw.service import Service, Source
from jev_gtw.sandbox import ProbeRunner


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=['docker','apptainer'],required=True)
    p.add_argument('--image',required=True)
    p.add_argument('--image-sha256')
    p.add_argument('--executable')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();os.umask(0o077);args.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    root=args.out/'inputs';root.mkdir(mode=0o700)
    (root/'records.csv').write_text('name,units\nFictional Canary Person,4\nFictional Example,7\n')
    canary='Fictional Canary Person'
    runner=ProbeRunner(backend=args.backend,image=args.image,image_sha256=args.image_sha256,
                       artifact_root=args.out/'artifacts',executable=args.executable,timeout=5)
    service=Service(root,Context('Save aggregate units.','All individual records and probe outputs stay local.'),
                    {'records':Source('records.csv','text',Access())},Gateway(),runner)
    scenarios={
        'aggregate_saved':"import csv,json; total=sum(int(r['units']) for r in csv.DictReader(open('/inputs/records')));json.dump({'total':total},open('/outputs/answer.json','w'))",
        'stdout_canary':"print(open('/inputs/records').read())",
        'stderr_canary':"import sys; print(open('/inputs/records').read(),file=sys.stderr)",
        'exception_canary':"raise RuntimeError(open('/inputs/records').read())",
        'nonzero_status':"raise SystemExit(37)",
        'readonly_inputs':"import json\ntry:\n open('/inputs/records','w').write('changed')\n ok=False\nexcept OSError:\n ok=True\njson.dump({'readonly':ok},open('/outputs/check.json','w'))",
        'network_disabled':"import socket,json\ns=socket.socket();s.settimeout(1)\ntry:\n s.connect(('1.1.1.1',443));blocked=False\nexcept OSError:\n blocked=True\nfinally:\n s.close()\njson.dump({'blocked':blocked},open('/outputs/check.json','w'))",
        'environment_clean':"import os,json;json.dump({'credential_absent':'JEV_GTW_TEST_SECRET' not in os.environ},open('/outputs/check.json','w'))",
        'host_unmounted':f"import os,json;json.dump({{'host_absent':not os.path.exists({str((root/'records.csv').resolve())!r})}},open('/outputs/check.json','w'))",
        'output_bound':"print('x'*200000)",
        'time_bound':"import time;time.sleep(10)",
    }
    os.environ['JEV_GTW_TEST_SECRET']='fixture-credential-not-forwarded'
    rows=[]
    for name,code in scenarios.items():
        result=service.compute(['records'],code)
        assert result['action']=='local' and canary not in json.dumps(result),name
        assert 'artifact_id' in result,name
        artifact=args.out/'artifacts'/result['artifact_id']
        capture=(artifact/'capture.bin').read_bytes()
        if name=='aggregate_saved':assert json.loads((artifact/'outputs/answer.json').read_text())=={'total':11}
        if name in ('stdout_canary','stderr_canary','exception_canary'):assert canary.encode() in capture
        expected={'readonly_inputs':{'readonly':True},'network_disabled':{'blocked':True},
                  'environment_clean':{'credential_absent':True},'host_unmounted':{'host_absent':True}}
        if name in expected:assert json.loads((artifact/'outputs/check.json').read_text())==expected[name]
        assert len(capture)<=96000
        rows.append({'scenario':name,'passed':True,'action':result['action']})
        print(json.dumps(rows[-1]),flush=True)
    (args.out/'summary.json').write_text(json.dumps({'passed':True,'backend':args.backend,'scenarios':rows},indent=2)+'\n')


if __name__=='__main__':main()
