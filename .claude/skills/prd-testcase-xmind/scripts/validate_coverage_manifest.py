#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


GROUP_KEYS = ("features", "rules", "states", "risks")
REQUIREMENT_TAG_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)+)(?!\d)")
PLATFORM_TAG_RE = re.compile(r"^\s*(?:【(?:客户端|服务端|Web)】|\[(?:客户端|服务端|Web)\])\s*")

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

VALID_CAPABILITY_STATUSES = {"common", "explicit", "unsupported", "blocking"}
ACTIVE_CAPABILITY_STATUSES = {"common", "explicit"}

PURCHASE_RELATED_RISKS = (
    "资金/资产一致性",
    "幂等",
    "并发/重复提交",
    "失败回滚",
    "超时重试",
    "部分成功后状态一致性",
)
REWARD_RELATED_RISKS = ("资产一致性", "重复下发幂等")
SERVER_DEFAULT_RISKS = ("幂等", "并发/重复提交", "失败回滚", "超时重试", "部分成功后状态一致性", "重复下发幂等")

FINANCIAL_KEYWORDS = ("余额", "扣费", "订单", "库存", "券")
ASSET_KEYWORDS = ("资产",)
PURCHASE_KEYWORDS = ("商城购买", "购买")
GIFT_KEYWORDS = ("商城赠送", "赠送")
REWARD_KEYWORDS = ("奖励包下发", "奖励包", "下发")


def clean_text(text: str | None) -> str:
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
    return None


def strip_platform_tag(title: str) -> str:
    return PLATFORM_TAG_RE.sub("", clean_text(title), count=1)


def format_case_title(item: dict[str, object]) -> str:
    title = strip_platform_tag(str(item.get("title", ""))) or clean_text(str(item.get("title", "")))
    return f"tc-{normalize_priority(str(item.get('priority', 'P2')))}: {title}"


def extract_cases(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, dict):
        cases_data = payload.get("cases", [])
    elif isinstance(payload, list):
        cases_data = payload
    else:
        raise ValueError("Payload must be a list or an object with `cases`.")

    if not isinstance(cases_data, list):
        raise ValueError("`cases` must be a list.")

    cases: list[dict[str, object]] = []
    for item in cases_data:
        if not isinstance(item, dict):
            raise ValueError("Each case in payload must be an object.")
        cases.append(
            {
                "formatted_title": format_case_title(item),
                "platform": normalize_platform(item.get("platform") if isinstance(item, dict) else None),
                "raw": item,
            }
        )
    return cases


def payload_to_text(payload: object) -> str:
    parts: list[str] = []
    if isinstance(payload, dict):
        parts.append(clean_text(str(payload.get("root_title", ""))))
        cases_data = payload.get("cases", [])
    else:
        cases_data = payload

    if isinstance(cases_data, list):
        for item in cases_data:
            if not isinstance(item, dict):
                continue
            parts.extend(clean_text(str(group)) for group in item.get("groups", []) or [])
            parts.append(clean_text(str(item.get("title", ""))))
            parts.extend(clean_text(str(precondition)) for precondition in item.get("preconditions", []) or [])
            for step in item.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                parts.append(clean_text(str(step.get("action", ""))))
                parts.extend(clean_text(str(expectation)) for expectation in step.get("expected", []) or [])

    return "\n".join(part for part in parts if part)


def normalize_capability_status(status: str | None) -> str:
    cleaned = clean_text(status or "").lower()
    if cleaned not in VALID_CAPABILITY_STATUSES:
        raise ValueError(
            "`product_capabilities` values must be one of common, explicit, unsupported, blocking."
        )
    return cleaned


def parse_product_capabilities(entries: list[str] | None) -> dict[str, str]:
    capabilities: dict[str, str] = {}
    for entry in entries or []:
        raw_entry = clean_text(entry)
        if not raw_entry:
            continue
        if "=" not in raw_entry:
            raise ValueError("Each `--product-capability` must use the format <能力名>=<状态>.")
        name, status = raw_entry.split("=", 1)
        capability_name = clean_text(name)
        if not capability_name:
            raise ValueError("Product capability names cannot be empty.")
        capabilities[capability_name] = normalize_capability_status(status)
    return capabilities


def derive_required_risks(
    *,
    payload: object,
    is_product_module: bool,
    product_capabilities: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    capabilities = product_capabilities or {}
    capability_inputs_provided = bool(capabilities)
    active_capabilities = {
        capability_name
        for capability_name, status in capabilities.items()
        if normalize_capability_status(status) in ACTIVE_CAPABILITY_STATUSES
    }
    payload_text = payload_to_text(payload)

    purchase_hit = "商城购买" in active_capabilities or (
        not capability_inputs_provided
        and is_product_module
        and any(keyword in payload_text for keyword in PURCHASE_KEYWORDS)
    )
    gift_hit = "商城赠送" in active_capabilities or (
        not capability_inputs_provided
        and is_product_module
        and any(keyword in payload_text for keyword in GIFT_KEYWORDS)
    )
    reward_hit = "奖励包下发" in active_capabilities or (
        not capability_inputs_provided
        and is_product_module
        and any(keyword in payload_text for keyword in REWARD_KEYWORDS)
    )
    financial_semantic_hit = any(keyword in payload_text for keyword in FINANCIAL_KEYWORDS)
    asset_semantic_hit = any(keyword in payload_text for keyword in ASSET_KEYWORDS)

    derived: list[dict[str, str]] = []

    def append_risks(risk_names: tuple[str, ...], reason: str) -> None:
        existing_names = {item["name"] for item in derived}
        for risk_name in risk_names:
            if risk_name in existing_names:
                continue
            derived.append({"name": risk_name, "reason": reason})
            existing_names.add(risk_name)

    if purchase_hit or gift_hit or financial_semantic_hit:
        append_risks(
            PURCHASE_RELATED_RISKS,
            "命中商城购买/商城赠送能力，或命中余额/扣费/订单/库存/券类等高风险语义。",
        )

    if reward_hit:
        append_risks(
            REWARD_RELATED_RISKS,
            "命中奖励包下发能力，必须补资产一致性与重复下发幂等风险。",
        )
    elif is_product_module and asset_semantic_hit and not (purchase_hit or gift_hit):
        append_risks(
            ("资产一致性",),
            "命中商品资产语义，至少补资产一致性风险。",
        )

    return derived


def normalize_manifest_item(group_name: str, item: object, item_index: int) -> tuple[dict[str, object] | None, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    if not isinstance(item, dict):
        issues.append(
            {
                "type": "invalid_item",
                "group": group_name,
                "name": f"{group_name}[{item_index}]",
                "detail": "Each coverage manifest item must be an object.",
            }
        )
        return None, issues

    name = clean_text(str(item.get("name", "")))
    reason = clean_text(str(item.get("reason", "")))
    applicable = item.get("applicable")
    mapped_cases = item.get("mapped_cases")

    if not name:
        issues.append(
            {
                "type": "invalid_item",
                "group": group_name,
                "name": f"{group_name}[{item_index}]",
                "detail": "`name` must be a non-empty string.",
            }
        )
    if not isinstance(applicable, bool):
        issues.append(
            {
                "type": "invalid_item",
                "group": group_name,
                "name": name or f"{group_name}[{item_index}]",
                "detail": "`applicable` must be a boolean.",
            }
        )
    if not reason:
        issues.append(
            {
                "type": "invalid_item",
                "group": group_name,
                "name": name or f"{group_name}[{item_index}]",
                "detail": "`reason` must be a non-empty string.",
            }
        )
    if not isinstance(mapped_cases, list) or any(not isinstance(case_title, str) for case_title in mapped_cases):
        issues.append(
            {
                "type": "invalid_item",
                "group": group_name,
                "name": name or f"{group_name}[{item_index}]",
                "detail": "`mapped_cases` must be a list of strings.",
            }
        )

    if issues:
        return None, issues

    normalized_item = {
        "name": name,
        "applicable": applicable,
        "reason": reason,
        "mapped_cases": [clean_text(case_title) for case_title in mapped_cases if clean_text(case_title)],
    }
    return normalized_item, issues


def normalize_manifest(manifest: object) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, str]]]:
    normalized = {group_name: [] for group_name in GROUP_KEYS}
    issues: list[dict[str, str]] = []

    if not isinstance(manifest, dict):
        issues.append(
            {
                "type": "invalid_manifest",
                "group": "manifest",
                "name": "manifest",
                "detail": "Coverage manifest must be a JSON object.",
            }
        )
        return normalized, issues

    for group_name in GROUP_KEYS:
        group_items = manifest.get(group_name)
        if group_items is None:
            issues.append(
                {
                    "type": "missing_group",
                    "group": group_name,
                    "name": group_name,
                    "detail": f"Coverage manifest is missing `{group_name}`.",
                }
            )
            continue
        if not isinstance(group_items, list):
            issues.append(
                {
                    "type": "invalid_group",
                    "group": group_name,
                    "name": group_name,
                    "detail": f"`{group_name}` must be a list.",
                }
            )
            continue
        for index, item in enumerate(group_items):
            normalized_item, item_issues = normalize_manifest_item(group_name, item, index)
            issues.extend(item_issues)
            if normalized_item is not None:
                normalized[group_name].append(normalized_item)

    return normalized, issues


def merge_applicable_items_by_name(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for item in items:
        item_name = str(item["name"])
        if item_name not in merged:
            merged[item_name] = {
                "name": item_name,
                "applicable": bool(item["applicable"]),
                "reason": str(item["reason"]),
                "mapped_cases": list(item["mapped_cases"]),
            }
            continue

        merged[item_name]["applicable"] = bool(merged[item_name]["applicable"]) or bool(item["applicable"])
        merged[item_name]["mapped_cases"] = list(
            dict.fromkeys([*merged[item_name]["mapped_cases"], *item["mapped_cases"]]).keys()
        )
        if not merged[item_name]["reason"]:
            merged[item_name]["reason"] = str(item["reason"])
    return merged


def validate_coverage_manifest(
    *,
    payload: object,
    manifest: object,
    is_product_module: bool = False,
    product_capabilities: dict[str, str] | None = None,
) -> dict[str, object]:
    normalized_manifest, issues = normalize_manifest(manifest)
    cases = extract_cases(payload)
    case_titles = {str(case["formatted_title"]) for case in cases}
    case_platforms = {str(case["formatted_title"]): case["platform"] for case in cases}

    for group_name, group_items in normalized_manifest.items():
        for item in group_items:
            if not item["applicable"]:
                continue
            mapped_cases = list(item["mapped_cases"])
            if not mapped_cases:
                issues.append(
                    {
                        "type": "unmapped_item",
                        "group": group_name,
                        "name": str(item["name"]),
                        "detail": "Applicable coverage items must map to at least one case.",
                    }
                )
                continue

            for mapped_case in mapped_cases:
                if mapped_case not in case_titles:
                    issues.append(
                        {
                            "type": "unknown_case_reference",
                            "group": group_name,
                            "name": str(item["name"]),
                            "detail": f"`{mapped_case}` does not exist in the testcase payload.",
                        }
                    )

    derived_risks = derive_required_risks(
        payload=payload,
        is_product_module=is_product_module,
        product_capabilities=product_capabilities or {},
    )
    manifest_risks = merge_applicable_items_by_name(normalized_manifest["risks"])

    for risk_name, manifest_risk in manifest_risks.items():
        if risk_name not in SERVER_DEFAULT_RISKS or "客户端主验" in str(manifest_risk["reason"]):
            continue
        mapped_cases = list(manifest_risk["mapped_cases"])
        if mapped_cases and not any(case_platforms.get(case_title) == "服务端" for case_title in mapped_cases):
            issues.append(
                {
                    "type": "server_platform_violation",
                    "group": "risks",
                    "name": risk_name,
                    "detail": "幂等 / 并发 / 重试 / 回滚类风险默认应由服务端 case 承载；若例外请在 reason 中写明“客户端主验”。",
                }
            )

    for risk in derived_risks:
        risk_name = risk["name"]
        manifest_risk = manifest_risks.get(risk_name)
        if not manifest_risk or not manifest_risk["applicable"]:
            issues.append(
                {
                    "type": "missing_required_risk",
                    "group": "risks",
                    "name": risk_name,
                    "detail": risk["reason"],
                }
            )
            continue

    return {
        "ok": not issues,
        "derived_risks": derived_risks,
        "issues": issues,
        "actual_case_titles": sorted(case_titles),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate coverage_manifest.json against testcase payloads.")
    parser.add_argument("--payload", required=True, help="Path to testcase payload JSON.")
    parser.add_argument("--coverage-manifest", required=True, help="Path to coverage_manifest.json.")
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

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.coverage_manifest).read_text(encoding="utf-8"))
    result = validate_coverage_manifest(
        payload=payload,
        manifest=manifest,
        is_product_module=args.product_module,
        product_capabilities=parse_product_capabilities(args.product_capability),
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
