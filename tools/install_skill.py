#!/usr/bin/env python3
"""Install the portable skill into an explicitly selected project."""
import argparse
from pathlib import Path
import shutil


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',choices=['codex','claude','both'],required=True)
    p.add_argument('--project',type=Path,required=True)
    args=p.parse_args()
    source=Path(__file__).resolve().parents[1]/'skills/jev-gtw'
    root=args.project.resolve(strict=True)
    targets=['codex','claude'] if args.target=='both' else [args.target]
    destinations=[root/('.agents' if t=='codex' else '.claude')/'skills/jev-gtw' for t in targets]
    for dest in destinations:
        if dest.exists() or dest.is_symlink():
            raise SystemExit('Skill destination already exists; review it before replacing it.')
    for dest in destinations:
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(source,dest)
        print(dest)


if __name__=='__main__':main()
