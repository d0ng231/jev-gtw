#!/usr/bin/env python3
"""Fetch pinned public MBPP code and MedQuAD reference questions for gateway tests.

No source documents are published by this script. Use a new private output
directory. This is an access-control workload, not an MBPP/MedQuAD task score.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "jev-gtw-evaluation"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(32 * 1024 * 1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mbpp-revision")
    parser.add_argument("--medquad-revision")
    args = parser.parse_args()
    os.umask(0o077)
    args.out.mkdir(parents=True, mode=0o700, exist_ok=False)
    mbpp_revision = args.mbpp_revision or json.loads(fetch(
        "https://api.github.com/repos/google-research/google-research/commits?path=mbpp/mbpp.jsonl&per_page=1"))[0]["sha"]
    med_revision = args.medquad_revision or json.loads(fetch(
        "https://api.github.com/repos/abachaa/MedQuAD/commits/master"))["sha"]
    manifest = {"sources": [], "source_files": {}}
    rows = []
    url = f"https://raw.githubusercontent.com/google-research/google-research/{mbpp_revision}/mbpp/mbpp.jsonl"
    raw = fetch(url)
    (args.out / "mbpp.jsonl").write_bytes(raw)
    manifest["source_files"]["mbpp.jsonl"] = hashlib.sha256(raw).hexdigest()
    for line in raw.splitlines():
        row = json.loads(line)
        text = row["text"] + "\n\n" + row["code"] + "\n\n" + "\n".join(row["test_list"])
        if len(text) <= 6000:
            rows.append({"id": "mbpp:" + str(row["task_id"]), "source_key": "mbpp", "domain": "general", "text": text})
    manifest["sources"].append({"key": "mbpp", "repository": "google-research/google-research", "revision": mbpp_revision,
                                "url": url, "license": "CC-BY-4.0 (MBPP data)", "role": "public code and tests; no code-generation score"})
    tree = json.loads(fetch(f"https://api.github.com/repos/abachaa/MedQuAD/git/trees/{med_revision}?recursive=1"))
    assert not tree.get("truncated")
    files = sorted(item["path"] for item in tree["tree"] if item["path"].endswith(".xml") and item["type"] == "blob")
    # Spread a fixed selection across the whole tree instead of only one topic.
    selected = [files[i * len(files) // 160] for i in range(160)]
    def download(path):
        return path, fetch(f"https://raw.githubusercontent.com/abachaa/MedQuAD/{med_revision}/{path}")
    with ThreadPoolExecutor(max_workers=6) as pool:
        for path, raw in pool.map(download, selected):
            target = args.out / "medquad" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            manifest["source_files"]["medquad/" + path] = hashlib.sha256(raw).hexdigest()
            doc = ET.fromstring(raw)
            for number, pair in enumerate(doc.findall(".//QAPair")):
                question = " ".join(pair.findtext("Question", "").split())
                answer = " ".join(pair.findtext("Answer", "").split())
                if question and answer and len(question) + len(answer) <= 6000:
                    rows.append({"id": f"medquad:{path}:{number}", "group_id": f"medquad:{path}",
                                 "source_key": "medquad", "domain": "medical", "text": question + "\n\n" + answer})
    manifest["sources"].append({"key": "medquad", "repository": "abachaa/MedQuAD", "revision": med_revision,
                                "url": "https://github.com/abachaa/MedQuAD", "license": "CC-BY-4.0",
                                "role": "public NIH medical reference text; not patient records or a QA score"})
    # One question per source document prevents train/dev/test document overlap.
    seen = set()
    selected_rows = []
    for row in rows:
        group = row.get("group_id", row["id"])
        if group not in seen:
            seen.add(group)
            selected_rows.append(row)
    payload = json.dumps(selected_rows, ensure_ascii=True, indent=2) + "\n"
    (args.out / "examples.json").write_text(payload)
    manifest.update(examples=len(selected_rows), examples_sha256=hashlib.sha256(payload.encode()).hexdigest(), training=False)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"examples": len(selected_rows), "sources": manifest["sources"]}), flush=True)


if __name__ == "__main__":
    main()
