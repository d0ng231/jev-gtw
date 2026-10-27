#!/usr/bin/env python3
"""Check the explicit public file set; never traverse excluded research data."""
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TOP={'README.md','LICENSE','NOTICE','pyproject.toml','index.html','.gitignore'}
DIRECTORIES={'jev_gtw','tests','tools','examples','skills','reports','.github'}
DOCS={'docs/ARCHITECTURE.md','docs/INTEGRATIONS.md','docs/RESULTS.md',
      'docs/assets/architecture.svg','docs/assets/workflow.svg'}
PATTERNS=[re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),
          re.compile(r'hf_[A-Za-z0-9]{25,}'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
          re.compile('/'+'midtier/'),re.compile('/'+'cdata/'),re.compile(r'\bai-(?:gpu|cpu)\d+\b')]


def public_path(name):
    p=Path(name)
    return name in TOP or name in DOCS or (len(p.parts)>1 and p.parts[0] in DIRECTORIES)


def main():
    command=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True)
    if command.returncode:
        raise SystemExit('Initialize and explicitly stage the public file set first.')
    names=[n for n in command.stdout.decode().split('\0') if n]
    if not names:raise SystemExit('No staged public files.')
    errors=[];size=0
    for name in names:
        path=ROOT/name
        if not public_path(name) or path.is_symlink() or path.suffix in {'.safetensors','.sif','.bin','.log','.pyc'}:
            errors.append((name,'excluded path or type'));continue
        raw=path.read_bytes();size+=len(raw)
        if len(raw)>512_000:errors.append((name,'unexpected large file'))
        if path.suffix=='.png':
            if not name.startswith('examples/demo/'):errors.append((name,'unexpected binary asset'))
            continue
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:errors.append((name,'unexpected binary'));continue
        if any(pattern.search(text) for pattern in PATTERNS):errors.append((name,'credential or private environment pattern'))
    # Check that the packaged default and all copied skill references are consistent.
    skill=ROOT/'skills/jev-gtw'
    import yaml
    text=(skill/'SKILL.md').read_text();front=text.split('---',2)[1];metadata=yaml.safe_load(front)
    if metadata.get('name')!='jev-gtw' or not metadata.get('description'):errors.append(('SKILL.md','metadata'))
    for reference in re.findall(r'\]\((references/[^)]+)\)',text):
        if not (skill/reference).is_file():errors.append((reference,'missing skill reference'))
    if errors:
        for name,reason in errors:print(f'{name}: {reason}',file=sys.stderr)
        raise SystemExit(1)
    print(f'Public release check passed: {len(names)} files, {size:,} bytes. No research data or weights tracked.')


if __name__=='__main__':main()
