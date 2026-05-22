"""Hook: 检查 Evaluator 评估输出，展示各维度分数，不通过告警。

用法:
  python3 check_evaluator.py <evaluation.json | cases_dir>

当传入目录时，自动寻找最新的 eval_*.json 或 evaluation_*.json。
"""
import sys, json, os, glob

THRESHOLDS = {
    "feature_coverage": 80,
    "rule_coverage": 80,
    "boundary_abnormal": 60,
    "priority_distribution": 70,
    "executability": 80,
}

LABELS = {
    "feature_coverage": "功能覆盖",
    "rule_coverage": "规则覆盖",
    "boundary_abnormal": "边界/异常",
    "priority_distribution": "优先级分布",
    "executability": "可执行性",
}

def find_eval_file(path):
    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        for pat in ["eval_*.json", "evaluation_*.json", "evaluator_*.json"]:
            files = sorted(glob.glob(os.path.join(path, pat)))
            if files:
                return files[-1]
    return None

def extract_json(text):
    """Extract JSON from evaluator output (may have ```json fences or surrounding text)."""
    # Try direct parse first
    try:
        return json.loads(text)
    except:
        pass
    # Try ```json fence
    if "```json" in text:
        block = text.split("```json", 1)[1].split("```", 1)[0]
        try:
            return json.loads(block)
        except:
            pass
    # Try to find { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
    return None

def main():
    if len(sys.argv) < 2:
        print("[prd-testcase-xmind] check_evaluator: 缺少文件参数")
        sys.exit(1)

    path = sys.argv[1]
    eval_file = find_eval_file(path)
    if not eval_file:
        sys.exit(0)  # 还没生成评估文件，静默退出

    with open(eval_file) as f:
        data = extract_json(f.read())

    if data is None:
        print(f"[prd-testcase-xmind] 无法解析评估文件: {eval_file}")
        sys.exit(1)

    scores = data.get("scores", {})
    overall_pass = data.get("pass", False)
    attempt = data.get("attempt", 1)

    # 输出各维度分数表
    lines = []
    lines.append("")
    lines.append("┌──────────────────────┬────────┬────────┬──────────┐")
    lines.append("│ 维度                 │ 得分   │ 阈值   │ 状态     │")
    lines.append("├──────────────────────┼────────┼────────┼──────────┤")
    all_pass = True
    for key, label in LABELS.items():
        dim = scores.get(key, {})
        score = dim.get("score", "N/A")
        threshold = THRESHOLDS.get(key, "N/A")
        passed = dim.get("pass", False)
        if not passed:
            all_pass = False
        status = "✓ 通过" if passed else "✗ 不通过"

        if isinstance(score, (int, float)):
            lines.append(f"│ {label:<20} │ {score:>5.0f}% │ {threshold:>5.0f}% │ {status:<8} │")
        else:
            lines.append(f"│ {label:<20} │ {'N/A':>5} │ {'N/A':>5} │ {status:<8} │")
    lines.append("└──────────────────────┴────────┴────────┴──────────┘")

    # gaps 汇总
    all_gaps = []
    for key, label in LABELS.items():
        dim = scores.get(key, {})
        gaps = dim.get("gaps", [])
        for g in gaps:
            all_gaps.append(f"  [{label}] {g}")

    if all_gaps:
        lines.append("")
        lines.append("⚠ 缺失覆盖项：")
        lines.extend(all_gaps[:15])
        if len(all_gaps) > 15:
            lines.append(f"  ... 共 {len(all_gaps)} 条")

    # 底部状态
    lines.append("")
    if all_pass:
        lines.append("✓ 全部维度通过，可以进入导出阶段")
    else:
        lines.append(f"✗ 存在不通过维度 (attempt {attempt}/3)，请根据 regenerate_hint 回修")

    # 输出 verdict
    verdict = data.get("verdict", "")
    if verdict:
        lines.append(f"  评估意见: {verdict}")

    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
