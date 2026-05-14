#!/usr/bin/env python3
"""Convert an XMind testcase file to MCP ConvertAndSaveLibraryCaseDataset input.

Usage:
  python3 xmind_to_mcp.py <xmind_path> --requirement-name "需求名" [--dry-run] [--batch-size 15]

Output: JSON array of case_data objects to stdout (or /tmp/xmind_import.json).
         --dry-run prints summary only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

PLATFORM_MAP = {
    "客户端": "client",
    "服务端": "server",
    "Web": "web",
    "client": "client",
    "server": "server",
    "web": "web",
}


def extract_cases(root_topic: dict) -> list[dict]:
    """Recursively walk XMind topic tree, extract case nodes (tc-Px: prefix)."""

    def walk(topics: list[dict], path: list[str], cases: list[dict]):
        for t in topics:
            title = (t.get("title") or "").strip()
            children = t.get("children", {}).get("attached", [])
            labels = t.get("labels", [])

            if title.startswith("tc-"):
                # Parse priority and title
                priority = "P2"
                case_title = title
                if title.startswith("tc-P0:"):
                    priority = "P0"
                    case_title = title[6:].strip()
                elif title.startswith("tc-P1:"):
                    priority = "P1"
                    case_title = title[6:].strip()
                elif title.startswith("tc-P2:"):
                    priority = "P2"
                    case_title = title[6:].strip()

                # Parse children: pc： → preconditions, others → steps
                preconditions = []
                steps = []
                for child in children:
                    ct = (child.get("title") or "").strip()
                    gc = child.get("children", {}).get("attached", [])

                    if ct.startswith("pc："):
                        preconditions.append(ct[3:])
                    else:
                        expected = [(g.get("title") or "").strip() for g in gc if (g.get("title") or "").strip()]
                        steps.append({"action": ct, "expected": expected})

                # Platform from labels
                platform = "client"
                tags = []
                for label in labels:
                    stripped = _strip_brackets(label)
                    if stripped in PLATFORM_MAP:
                        platform = PLATFORM_MAP[stripped]
                    elif stripped:
                        tags.append(stripped)

                cases.append({
                    "node_path": list(path),
                    "title": case_title,
                    "priority": priority,
                    "platform": platform,
                    "preconditions": preconditions,
                    "steps": steps,
                    "tags": tags,
                })
            else:
                # Group node — recurse
                walk(children, path + [title], cases)

    result = []
    root_children = root_topic.get("children", {}).get("attached", [])
    walk(root_children, [], result)
    return result


def _strip_brackets(label: str) -> str:
    s = label.strip()
    if (s.startswith("【") and s.endswith("】")) or (s.startswith("[") and s.endswith("]")):
        s = s[1:-1].strip()
    return s


def cases_to_mcp_data(cases: list[dict], requirement_name: str) -> list[dict]:
    """Convert extracted cases to MCP case_data format."""
    result = []
    for c in cases:
        # Prepend requirement name to node_path
        full_path = [requirement_name] + c["node_path"]

        # Generate deterministic case_id (MD5 of path + title)
        case_id = hashlib.md5(
            ("/".join(full_path) + c["title"]).encode()
        ).hexdigest()[:32]

        # Convert steps to JSON string
        steps_json = json.dumps(
            [{"step": s["action"], "result": "\n".join(s["expected"])} for s in c["steps"]],
            ensure_ascii=False,
        )

        # Join preconditions with newlines
        premise = "\n".join(
            f"{i+1}、{p}" for i, p in enumerate(c["preconditions"])
        ) if c["preconditions"] else ""

        # Tags: comma-separated, add platform label back
        tags = c["tags"] + [c["platform"]]
        tags_str = ",".join(tags)

        result.append({
            "case_id": case_id,
            "node_path": full_path,
            "title": c["title"],
            "type": "MANUAL",
            "platform": c["platform"],
            "priority": c["priority"],
            "premise": premise,
            "step_type": "STEP",
            "steps": steps_json,
            "tags": tags_str,
        })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert XMind testcase file to MCP import format."
    )
    parser.add_argument("xmind", type=Path, help="Path to .xmind file.")
    parser.add_argument(
        "--requirement-name", required=True,
        help="Top-level directory name in the target library (e.g. 'Achat3.22-女性权益聚合')."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print summary only, no output file.")
    parser.add_argument("--batch-size", type=int, default=15, help="Batch size hint (default: 15).")
    args = parser.parse_args(argv)

    if not args.xmind.exists():
        print(f"Error: file not found: {args.xmind}", file=sys.stderr)
        return 1

    # Parse XMind
    with zipfile.ZipFile(args.xmind) as z:
        content = json.loads(z.read("content.json"))
    root_topic = content[0]["rootTopic"]
    root_title = root_topic.get("title", "").strip()

    cases = extract_cases(root_topic)
    if not cases:
        print("Warning: No test cases found (no tc-Px: prefix nodes).", file=sys.stderr)
        return 1

    mcp_data = cases_to_mcp_data(cases, args.requirement_name)

    # Stats
    p0 = sum(1 for c in mcp_data if c["priority"] == "P0")
    p1 = sum(1 for c in mcp_data if c["priority"] == "P1")
    p2 = sum(1 for c in mcp_data if c["priority"] == "P2")
    modules = set(c["node_path"][1] for c in mcp_data if len(c["node_path"]) > 1)

    if args.dry_run:
        print(f"XMind root: {root_title}")
        print(f"Cases: {len(mcp_data)} (P0={p0}, P1={p1}, P2={p2})")
        print(f"Modules: {len(modules)} → {sorted(modules)}")
        print(f"Will mount under: '{args.requirement_name}'")
        print(f"Estimated batches: {(len(mcp_data) + args.batch_size - 1) // args.batch_size}")
        return 0

    # Output
    output_path = Path("/tmp/xmind_import.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mcp_data, f, ensure_ascii=False, indent=2)

    print(f"Written {len(mcp_data)} cases to {output_path}")
    print(f"  P0={p0}, P1={p1}, P2={p2}")
    print(f"  Will mount under: '{args.requirement_name}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
