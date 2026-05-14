#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import uuid
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from validate_coverage_manifest import parse_product_capabilities, validate_coverage_manifest


DEFAULT_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "assets" / "testcase_import_template.xmind"
)

PLATFORM_ALIASES = {
    "client": "客户端",
    "server": "服务端",
    "web": "Web",
    "客户端": "客户端",
    "服务端": "服务端",
    "后台": "Web",
    "管理端": "Web",
    "后台管理端": "Web",
}
PLATFORM_TAG_RE = re.compile(r"^\s*(?:【(?:客户端|服务端|Web)】|\[(?:客户端|服务端|Web)\])\s*")
REQUIREMENT_TAG_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)+)(?!\d)")
ILLEGAL_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class Step:
    action: str
    expected: list[str]


@dataclass
class Case:
    groups: list[str]
    title: str
    priority: str = "P2"
    platform: str | None = None
    labels: list[str] | None = None
    preconditions: list[str] | None = None
    steps: list[Step] | None = None


def clean_text(text: str) -> str:
    return (text or "").replace("\r\n", "\n").strip()


def normalize_priority(priority: str | None) -> str:
    cleaned = clean_text(priority or "").upper()
    if cleaned in {"P0", "P1", "P2"}:
        return cleaned
    return "P2"


def normalize_platform(platform: str | None) -> str | None:
    cleaned = clean_text(platform or "")
    if not cleaned:
        return None

    normalized = PLATFORM_ALIASES.get(cleaned.lower())
    if normalized:
        return normalized

    raise ValueError("`platform` must be one of 客户端, 服务端, Web (or client/server/web aliases).")


def strip_label_wrapper(label: str | None) -> str:
    cleaned = clean_text(label or "")
    if not cleaned:
        return ""
    if (cleaned.startswith("【") and cleaned.endswith("】")) or (
        cleaned.startswith("[") and cleaned.endswith("]")
    ):
        return clean_text(cleaned[1:-1])
    return cleaned


def normalize_label(label: str | None) -> str:
    inner = strip_label_wrapper(label)
    if not inner:
        return ""
    return f"【{inner}】"


def normalize_labels(labels: object) -> list[str]:
    if labels is None:
        return []
    if not isinstance(labels, list):
        raise ValueError("`labels` must be a list of strings.")

    normalized: list[str] = []
    for item in labels:
        if not isinstance(item, str):
            raise ValueError("`labels` must be a list of strings.")
        label = normalize_label(item)
        if label:
            normalized.append(label)
    return normalized


def normalize_requirement_tag(requirement_tag: str | None) -> str | None:
    normalized = strip_label_wrapper(requirement_tag)
    return normalized or None


def extract_requirement_tag(text: str | None) -> str | None:
    match = REQUIREMENT_TAG_RE.search(clean_text(text or ""))
    if not match:
        return None
    return match.group(1)


def sanitize_filename_segment(text: str | None) -> str:
    cleaned = clean_text(text or "")
    if not cleaned:
        return ""
    cleaned = ILLEGAL_FILENAME_CHARS_RE.sub("_", cleaned)
    cleaned = WHITESPACE_RE.sub("_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip(" ._")


def derive_xmind_filename(root_title: str, requirement_tag: str | None = None) -> str:
    normalized_requirement_tag = normalize_requirement_tag(requirement_tag) or extract_requirement_tag(root_title)
    normalized_root_title = clean_text(root_title) or "测试用例"
    title_without_tag = normalized_root_title
    if normalized_requirement_tag:
        title_without_tag = re.sub(
            rf"^\s*{re.escape(normalized_requirement_tag)}(?:[\s_-]+)?",
            "",
            normalized_root_title,
            count=1,
        ).strip()

    requirement_part = sanitize_filename_segment(normalized_requirement_tag)
    title_part = sanitize_filename_segment(title_without_tag or normalized_root_title)

    if requirement_part and title_part:
        filename_stem = f"{requirement_part}_{title_part}"
    else:
        filename_stem = title_part or requirement_part or "测试用例"

    return f"{filename_stem}.xmind"


def resolve_output_path(
    output: str | Path,
    *,
    root_title: str,
    requirement_tag: str | None,
) -> Path:
    output_path = Path(output).expanduser()
    if output_path.suffix.lower() == ".xmind":
        return output_path.resolve()
    return (output_path / derive_xmind_filename(root_title, requirement_tag)).resolve()


def dedupe_preserving_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def new_id() -> str:
    return uuid.uuid4().hex[:26]


def format_preconditions(preconditions: list[str]) -> str:
    cleaned = [clean_text(item) for item in preconditions if clean_text(item)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return "\n".join(f"{index}、{item}" for index, item in enumerate(cleaned, start=1))


def make_topic(
    title: str,
    children: list[dict] | None = None,
    labels: list[str] | None = None,
) -> dict:
    topic = {
        "id": new_id(),
        "class": "topic",
        "title": clean_text(title),
    }
    if labels:
        topic["labels"] = labels
    if children:
        topic["structureClass"] = "org.xmind.ui.logic.right"
        topic["children"] = {"attached": children}
    return topic


def strip_platform_tag(title: str) -> str:
    return PLATFORM_TAG_RE.sub("", clean_text(title), count=1)


def format_case_title(case: Case) -> str:
    title = strip_platform_tag(case.title) or clean_text(case.title)
    return f"tc-{case.priority}: {title}"


def build_case_labels(case: Case, requirement_tag: str | None) -> list[str]:
    labels: list[str] = []
    if case.platform:
        labels.append(normalize_label(case.platform))
    return dedupe_preserving_order([label for label in labels if label])


def parse_payload(payload: object) -> tuple[str, str | None, list[Case]]:
    if isinstance(payload, list):
        root_title = "测试用例"
        requirement_tag = extract_requirement_tag(root_title)
        cases_data = payload
    elif isinstance(payload, dict):
        root_title = clean_text(payload.get("root_title", "测试用例"))
        requirement_tag = normalize_requirement_tag(payload.get("requirement_tag")) or extract_requirement_tag(root_title)
        cases_data = payload.get("cases", [])
    else:
        raise ValueError("Input JSON must be a list of cases or an object with `cases`.")

    if not isinstance(cases_data, list):
        raise ValueError("`cases` must be a list.")

    cases: list[Case] = []
    for item in cases_data:
        if not isinstance(item, dict):
            raise ValueError("Each case must be an object.")

        groups = [clean_text(group) for group in item.get("groups", []) if clean_text(group)]
        preconditions = [
            clean_text(precondition)
            for precondition in item.get("preconditions", []) or []
            if clean_text(precondition)
        ]

        steps: list[Step] = []
        for raw_step in item.get("steps", []) or []:
            if not isinstance(raw_step, dict):
                raise ValueError("Each step must be an object.")
            action = clean_text(raw_step.get("action", ""))
            expected = [
                clean_text(expectation)
                for expectation in raw_step.get("expected", []) or []
                if clean_text(expectation)
            ]
            if action:
                steps.append(Step(action=action, expected=expected))

        title = clean_text(item.get("title", ""))
        if not title:
            raise ValueError("Each case must include a non-empty `title`.")

        cases.append(
            Case(
                groups=groups,
                title=title,
                priority=normalize_priority(item.get("priority")),
                platform=normalize_platform(item.get("platform")),
                labels=normalize_labels(item.get("labels")),
                preconditions=preconditions,
                steps=steps,
            )
        )
    return root_title or "测试用例", requirement_tag, cases


def case_to_topic(case: Case, requirement_tag: str | None) -> dict:
    child_topics: list[dict] = []
    preconditions_title = format_preconditions(case.preconditions or [])
    if preconditions_title:
        child_topics.append(make_topic(f"pc：{preconditions_title}"))
    for item in case.steps or []:
        expected_topics = [make_topic(expect) for expect in item.expected if clean_text(expect)]
        child_topics.append(make_topic(item.action, expected_topics))
    return make_topic(
        format_case_title(case),
        child_topics or None,
        labels=build_case_labels(case, requirement_tag),
    )


def build_group_tree(cases: list[Case]) -> OrderedDict[str, dict]:
    tree: OrderedDict[str, dict] = OrderedDict()
    ungrouped_key = "未分组的用例"

    sorted_cases = sorted(cases, key=lambda case: tuple(case.groups or [ungrouped_key]))
    for case in sorted_cases:
        groups = case.groups or [ungrouped_key]
        cursor = tree
        for group in groups:
            if group not in cursor:
                cursor[group] = {"groups": OrderedDict(), "cases": []}
            cursor = cursor[group]["groups"]

        parent = tree
        for group in groups[:-1]:
            parent = parent[group]["groups"]
        parent[groups[-1]]["cases"].append(case)
    return tree


def group_tree_to_topics(tree: OrderedDict[str, dict], requirement_tag: str | None) -> list[dict]:
    topics: list[dict] = []
    for title, payload in tree.items():
        children = group_tree_to_topics(payload["groups"], requirement_tag)
        children.extend(case_to_topic(case, requirement_tag) for case in payload["cases"])
        topics.append(make_topic(title, children or None))
    return topics


def load_template_files(template_path: Path) -> tuple[list[dict], bytes, bytes, bytes]:
    with zipfile.ZipFile(template_path, "r") as archive:
        content = json.loads(archive.read("content.json"))
        metadata = archive.read("metadata.json")
        manifest = archive.read("manifest.json")
        thumbnail = archive.read("Thumbnails/thumbnail.png")
    return content, metadata, manifest, thumbnail


def build_content(
    *,
    root_title: str,
    requirement_tag: str | None,
    cases: list[Case],
    template_path: Path,
    sheet_title: str = "画布 1",
) -> list[dict]:
    content, _, _, _ = load_template_files(template_path)
    sheet = content[0]
    root = sheet["rootTopic"]
    attached = group_tree_to_topics(build_group_tree(cases), requirement_tag)

    root["title"] = clean_text(root_title) or "测试用例"
    root["children"] = {"attached": attached}

    for extension in root.get("extensions", []):
        if extension.get("provider") != "org.xmind.ui.map.unbalanced":
            continue
        for item in extension.get("content", []):
            if item.get("name") == "right-number":
                item["content"] = str(len(attached))

    sheet["title"] = clean_text(sheet_title) or "画布 1"
    sheet["topicPositioning"] = "fixed"
    return content


def write_xmind(
    *,
    content: list[dict],
    output_path: Path,
    template_path: Path,
) -> None:
    _, metadata, manifest, thumbnail = load_template_files(template_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "content.json",
            json.dumps(content, ensure_ascii=False, separators=(",", ":")),
        )
        archive.writestr("metadata.json", metadata)
        archive.writestr("manifest.json", manifest)
        archive.writestr("Thumbnails/thumbnail.png", thumbnail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export structured testcase payloads to an XMind file.")
    parser.add_argument("--input-json", required=True, help="Path to JSON payload with testcase groups and steps.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output .xmind file, or a directory to auto-generate <版本号>_<需求主题测试用例>.xmind.",
    )
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to the XMind template file.")
    parser.add_argument("--root-title", help="Optional root topic title override.")
    parser.add_argument("--sheet-title", default="画布 1", help="Optional sheet title.")
    parser.add_argument("--coverage-manifest", help="Optional path to coverage_manifest.json for pre-export validation.")
    parser.add_argument(
        "--product-module",
        action="store_true",
        help="Whether the current stage-B scope is a product module or productized capability.",
    )
    parser.add_argument(
        "--product-capability",
        action="append",
        default=[],
        help="Product capability in the form <能力名>=<状态>; repeat as needed.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input_json).resolve()
    template_path = Path(args.template).resolve()

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    root_title, requirement_tag, cases = parse_payload(payload)
    if args.root_title:
        root_title = clean_text(args.root_title)
    if not requirement_tag:
        requirement_tag = extract_requirement_tag(root_title)
    output_path = resolve_output_path(
        args.output,
        root_title=root_title,
        requirement_tag=requirement_tag,
    )

    if args.coverage_manifest:
        manifest = json.loads(Path(args.coverage_manifest).resolve().read_text(encoding="utf-8"))
        validation = validate_coverage_manifest(
            payload=payload,
            manifest=manifest,
            is_product_module=args.product_module,
            product_capabilities=parse_product_capabilities(args.product_capability),
        )
        if not validation["ok"]:
            details = "; ".join(
                f"{issue['type']}[{issue['group']}:{issue['name']}] {issue['detail']}"
                for issue in validation["issues"]
            )
            raise ValueError(f"coverage manifest validation failed: {details}")

    content = build_content(
        root_title=root_title,
        requirement_tag=requirement_tag,
        cases=cases,
        template_path=template_path,
        sheet_title=args.sheet_title,
    )
    write_xmind(content=content, output_path=output_path, template_path=template_path)

    print(f"output={output_path}")
    print(f"case_count={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
