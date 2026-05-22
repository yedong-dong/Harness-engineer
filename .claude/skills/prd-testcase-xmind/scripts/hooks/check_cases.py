"""Hook: 校验 cases.json 的 priority/platform/steps 字段合法性。

用法:
  python3 check_cases.py <cases.json 路径>
"""
import sys, json, os

VALID_PRIORITY = {"P0", "P1", "P2"}
PLATFORM_MAP = {
    "客户端": "客户端", "client": "客户端",
    "服务端": "服务器", "server": "服务端",
    "web": "Web", "Web": "Web",
    "后台": "Web", "管理端": "Web", "后台管理端": "Web",
}

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        sys.exit(0)

    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"")
            print(f"✗ cases.json JSON 语法错误: {e}")
            return

    cases = data.get("cases", [])
    if not isinstance(cases, list):
        print(f"")
        print(f"✗ cases 字段不是数组")
        return

    errors = []
    summary = {"total": 0, "invalid_priority": 0, "invalid_platform": 0, "empty_steps": 0}

    for i, case in enumerate(cases):
        summary["total"] += 1
        title = case.get("title", f"#{i}")

        # priority 校验
        p = case.get("priority", "")
        if p not in VALID_PRIORITY:
            summary["invalid_priority"] += 1
            errors.append(f"  #{i+1} [{title}]: priority='{p}' 无效，须为 P0/P1/P2")

        # platform 校验
        plat = case.get("platform", "")
        if plat and plat not in PLATFORM_MAP:
            summary["invalid_platform"] += 1
            allowed = "客户端/服务端/Web"
            errors.append(f"  #{i+1} [{title}]: platform='{plat}' 无效，须为 {allowed}")

        # steps 校验
        steps = case.get("steps", [])
        if not steps or len(steps) == 0:
            summary["empty_steps"] += 1
            errors.append(f"  #{i+1} [{title}]: steps 为空")
        else:
            for j, step in enumerate(steps):
                if not step.get("action", "").strip():
                    summary["empty_steps"] += 1
                    errors.append(f"  #{i+1} [{title}]: step {j+1} action 为空")

    # 输出
    print("")
    print("┌──────────────────────┬──────┐")
    print(f"│ 用例总数              │ {summary['total']:>4} │")
    print(f"│ priority 非法         │ {summary['invalid_priority']:>4} │")
    print(f"│ platform  非法        │ {summary['invalid_platform']:>4} │")
    print(f"│ steps 为空            │ {summary['empty_steps']:>4} │")
    print("└──────────────────────┴──────┘")

    if errors:
        print("")
        print(f"✗ 发现 {len(errors)} 个字段问题：")
        for e in errors[:20]:
            print(e)
        if len(errors) > 20:
            print(f"  ... 共 {len(errors)} 条")
    else:
        print("✓ 所有用例字段校验通过")


if __name__ == "__main__":
    main()
