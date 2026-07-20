#!/usr/bin/env python
"""Scan CAADoc to auto-generate Framework navigation index."""
import re, sys
from pathlib import Path

def find_caadoc_refman():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from skills.env import CAAEnvironment
    env = CAAEnvironment()
    env.load_config()
    catia = env.config.get("CATIA_INSTALL", "")
    if not catia: return None
    refman = Path(catia) / "CAADoc" / "Doc" / "generated" / "refman"
    return refman if refman.is_dir() else None

def extract_framework_info(html_path):
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    name = html_path.stem
    desc = ""
    m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE)
    if m:
        desc = re.sub(r"^CAA\s*", "", m.group(1).strip())
        desc = re.sub(r"\s*Framework$", "", desc)
    keywords = set()
    for m in re.finditer(r"CATI\w+|CATE\w+", text):
        k = m.group(0)
        if 5 < len(k) < 60:
            keywords.add(k)
        if len(keywords) >= 5: break
    return {"name": name, "description": desc or name, "keywords": sorted(keywords)[:5]}

def scan():
    refman = find_caadoc_refman()
    if not refman:
        print("ERROR: Cannot locate CAADoc refman", file=sys.stderr)
        return []
    fws = []
    for hf in sorted(refman.glob("*.htm")):
        # visidx.txt.htm is CAADoc's global API index page, not a framework
        # manual page. Scanning it produces bogus "framework" entries whose
        # keywords are random API names pulled from across many frameworks.
        if hf.stem.lower() == "visidx.txt":
            continue
        info = extract_framework_info(hf)
        if info:
            fws.append(info)
            print(f"  {info['name']}")
    return fws

def write_files(fws, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for fw in fws:
        name = fw["name"]
        kw = fw["keywords"]
        kw_str = ", ".join(kw) if kw else name
        content = f"""---
id: framework.{name}
title: {name}
category: framework
domain: infrastructure
keywords: {kw[:5]}
apis: {kw[:5]}
requires: []
patterns: []
examples: []
release: [R19, R28]
tags: [framework, caadoc]
---

# {name}

{fw["description"]}

## CAADoc Reference

- API: `<CATIA_INSTALL>/CAADoc/Doc/docs/api/`
- Manual: `<CATIA_INSTALL>/CAADoc/Doc/generated/refman/{name}.htm`
"""
        (out_dir / f"{name}.md").write_text(content, encoding="utf-8")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    print("Scanning CAADoc...")
    fws = scan()
    print(f"\nFound {len(fws)} frameworks")
    if args.write and fws:
        out = Path(__file__).resolve().parent.parent / "knowledge" / "frameworks"
        print(f"Writing to {out}...")
        write_files(fws, out)
        print(f"Done. {len(fws)} files generated.")
