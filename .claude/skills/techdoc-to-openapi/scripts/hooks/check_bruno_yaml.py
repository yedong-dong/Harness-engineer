"""Hook: 校验 Bruno 请求文件格式，检测缩进问题、JSON 合法性、必填字段。

用法:
  python3 check_bruno_yaml.py <file_or_dir>
"""
import sys, os, json, yaml

REQUIRED_TOP_FIELDS = ["info", "http"]
REQUIRED_INFO_FIELDS = ["name", "type"]
REQUIRED_HTTP_FIELDS = ["method", "url", "headers"]

def check_file(filepath):
    """Return list of errors found, empty = good."""
    errors = []
    basename = os.path.basename(filepath)

    # Skip non-request files
    if basename in ("folder.yml", "opencollection.yml"):
        return []
    if "environments" in filepath:
        return []

    # 1. Parse YAML
    with open(filepath) as f:
        content = f.read()
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        errors.append(f"YAML 解析失败: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append("文件内容不是有效的 YAML 字典")
        return errors

    # 2. Check top-level required fields
    for field in REQUIRED_TOP_FIELDS:
        if field not in data:
            errors.append(f"缺少顶层必填字段: {field}")

    info = data.get("info", {})
    for field in REQUIRED_INFO_FIELDS:
        if field not in info:
            errors.append(f"info 缺少必填字段: {field}")

    http = data.get("http", {})
    for field in REQUIRED_HTTP_FIELDS:
        if field not in http:
            errors.append(f"http 缺少必填字段: {field}")

    # 3. Check URL format
    url = http.get("url", "")
    if url and not url.startswith("{{baseUrl}}"):
        errors.append(f"URL 不以 {{{{baseUrl}}}} 开头: {url}")

    # 4. Check x-reqcontrol-bin for PB requests (if URL is {{baseUrl}}/)
    if url == "{{baseUrl}}/":
        has_reqcontrol = False
        for h in http.get("headers", []):
            if h.get("name") == "x-reqcontrol-bin":
                has_reqcontrol = True
                value = h.get("value", "")
                if '"service"' not in value or '"method"' not in value:
                    errors.append("x-reqcontrol-bin 缺少 service/method 字段")
                break
        if not has_reqcontrol:
            errors.append("PB 请求缺少 x-reqcontrol-bin header")

    # 5. Check body.data JSON validity and indentation
    body = http.get("body", {})
    if body and "data" in body:
        raw = body["data"]
        if raw and raw.strip():
            # Check JSON validity
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"body.data JSON 解析失败: {e}")

            # Check indentation: body data lines should be indented >= 6 spaces
            # Find the data block in raw content
            in_data = False
            for line in content.split("\n"):
                stripped = line.strip()
                if "data: |-" in line or "data: |" in line:
                    in_data = True
                    continue
                if in_data and stripped:
                    # End of data: YAML key at parent indent (2 spaces, starts with letter)
                    if line.startswith("  ") and len(line) > 3 and line[2].isalpha() and ":" in line:
                        in_data = False
                        continue
                    # JSON lines must be indented >= 6 spaces or be closing braces
                    if stripped in ("}", "{}"):
                        continue
                    if not line.startswith("      "):
                        errors.append(f"body.data JSON 缩进不足（需至少6空格）: {stripped[:40]}")
                        break

    # 6. Check settings exist
    if "settings" not in data:
        errors.append("缺少 settings 字段")

    return errors


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    path = sys.argv[1]
    errors_found = []

    if os.path.isfile(path):
        errors_found = check_file(path)
        if errors_found:
            print(f"")
            print(f"✗ {os.path.basename(path)} 格式问题:")
            for e in errors_found:
                print(f"  - {e}")
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith(".yml"):
                    fp = os.path.join(root, f)
                    errs = check_file(fp)
                    if errs:
                        name = os.path.relpath(fp, path)
                        print(f"")
                        print(f"✗ {name}:")
                        for e in errs:
                            print(f"  - {e}")
                        errors_found.extend(errs)

    if errors_found:
        print(f"")
        print(f"共发现 {len(errors_found)} 个格式问题，请修复后重新生成")
    else:
        # Only print success if we actually checked files
        pass  # Silent success


if __name__ == "__main__":
    main()
