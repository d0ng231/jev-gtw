"""CLI entry point. Configuration and source fingerprints are operator inputs."""
import argparse
import json
from pathlib import Path
import sys

from .core import Observation
from .service import Service


def main():
    parser = argparse.ArgumentParser(prog="jev-gtw")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "check", "read"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        if name == "read":
            p.add_argument("source_id")
    p = sub.add_parser("fingerprint", help="Operator-only: fingerprint a reviewed public snapshot")
    p.add_argument("path")
    p.add_argument("--image", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "fingerprint":
            raw = Path(args.path).read_bytes()
            view = Observation(image=raw) if args.image else Observation(text=raw.decode("utf-8"))
            print(view.fingerprint())
            return
        service = Service.from_config(args.config)
        if args.command == "check":
            print(json.dumps({"valid": True, **service.catalog()}))
        elif args.command == "read":
            print(json.dumps(service.read(args.source_id)))
        else:
            from .mcp_server import create_server
            create_server(service).run(transport="stdio")
    except Exception:
        # A traceback can expose source paths or contents to an MCP caller.
        print("jev-gtw: configuration or service unavailable; no raw content released.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
