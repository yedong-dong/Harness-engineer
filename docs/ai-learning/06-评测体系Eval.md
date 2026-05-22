# 评测体系 Eval 详解：用数据驱动 Prompt/Skill 的持续优化

## 1. 这是什么

Eval（Evaluation，评测）回答一个核心问题：**你怎么知道你的 Prompt/Skill 改好了还是改坏了？**

没有 Eval 之前：
- 「我觉得这个 Prompt 效果还行」
- 靠感觉 → 无法量化 → 无法系统化改进 → 容易回退

有了 Eval 之后：
- 「这个 Prompt 在 50 个测试 case 上得分从 72 提升到 84」
- 靠数据 → 可量化 → 可系统化改进 → 不会回退

## 2. 你的 Generator/Evaluator 分离 = 在线 Eval

你已经在做的事——Generator 生成 + Evaluator 独立评分——就是**在线 Eval**（生产环境中的实时质量评估）。

```
在线 Eval（你的方式）：
  每次执行都评估 → 不通过就回修

离线 Eval（评测体系）：
  不是针对单次执行，而是针对 Prompt/Skill 的版本
  跑一批固定的测试 case → 看分数变化
```

两者互补：在线 Eval 保证单次执行质量，离线 Eval 保证持续改进方向正确。

## 3. 离线 Eval 的四步法

### 3.1 构建测试集（Eval Set）

```
测试集 = 一批输入 + 对应的人工标注输出（Ground Truth）

好的测试集特征：
- 覆盖典型场景（常见 PRD 类型）
- 覆盖边界（极短/极长/纯表/矛盾 PRD）
- 覆盖失败历史（之前出过错的 case 留存）
- 10-20 条起步，逐步积累
```

示例——为你的 prd-testcase-xmind 构建的 Eval Set：

```python
eval_set = [
    {
        "id": "eval_001",
        "input": "用户可以通过支付宝充值，单笔金额 1-100000 元",
        "expected_functions": ["充值-支付宝渠道", "金额校验"],
        "expected_dimensions": ["正常路径", "边界值", "异常路径", "状态流转", "数据一致性"],
        "min_case_count": 8,
        "golden": "人工标注的基准用例（重要 case 才标）"
    },
    {
        "id": "eval_002",
        "input": "VIP 等级系统重构：...（完整的复杂 PRD）",
        "expected_functions": ["等级计算", "权益变更", "历史数据迁移"],
        "expected_dimensions": ["正常路径", "边界值", "异常路径", "状态流转", "数据一致性"],
        "min_case_count": 25
    },
    # ... 更多
]
```

### 3.2 定义评估维度

你已经有 5 个评估维度了，让我们系统化它们：

```python
evaluation_dimensions = {
    "覆盖率（Coverage）": {
        "weight": 0.30,  # 权重
        "description": "是否覆盖了所有功能点 × 所有适用维度",
        "scoring": """
        每个功能点的维度覆盖：
        - 5 个维度全覆盖：满分
        - 缺 1 个：扣 20%
        - 缺 2 个以上：扣 50%
        """
    },
    "准确性（Accuracy）": {
        "weight": 0.30,
        "description": "步骤和预期的描述是否和需求一致",
        "scoring": """
        每条用例：
        - 完全正确：1 分
        - 有偏差但不影响测试：0.5 分
        - 逻辑错误（如调用的接口不存在）：0 分
        总分 = 正确用例数 / 总用例数
        """
    },
    "清晰度（Clarity）": {
        "weight": 0.15,
        "description": "另一名测试工程师能否直接执行",
        "scoring": """
        三级评分：
        - 可直接执行（步骤具体、预期明确）：2 分
        - 基本可执行（需要少量推理）：1 分
        - 无法执行（步骤模糊、预期不明确）：0 分
        """
    },
    "冗余度（Redundancy）": {
        "weight": 0.10,
        "description": "是否存在重复或等效的用例",
        "scoring": """
        重复用例占比：
        - < 5%：满分
        - 5-15%：扣 20%
        - > 15%：扣 50%
        """
    },
    "可追溯性（Traceability）": {
        "weight": 0.15,
        "description": "每条用例是否可以追溯到需求中的功能点",
        "scoring": """
        可追溯的用例占比：
        - 100%：满分
        - 90-99%：扣 10%
        - < 90%：扣 30%（有凭空生成的用例）
        """
    }
}

# 总分计算
def calculate_score(scores):
    return sum(
        dim["weight"] * scores[dim_name]
        for dim_name, dim in evaluation_dimensions.items()
    )
```

### 3.3 跑评测

```python
def evaluate_skill_version(skill_prompt, eval_set):
    """对某个版本的 Skill Prompt 跑完整评测"""
    results = []
    for test_case in eval_set:
        # ① 用当前 Prompt 生成结果
        output = run_skill(skill_prompt, test_case["input"])

        # ② 对每个维度打分
        scores = {}
        for dim_name, dim_config in evaluation_dimensions.items():
            scores[dim_name] = evaluate_dimension(output, test_case, dim_name)

        # ③ 记录
        results.append({
            "case_id": test_case["id"],
            "scores": scores,
            "total": calculate_score(scores),
            "output": output
        })

    # ④ 汇总
    avg_score = sum(r["total"] for r in results) / len(results)
    worst_cases = sorted(results, key=lambda r: r["total"])[:3]

    return {
        "average_score": avg_score,
        "per_case": results,
        "worst_cases": worst_cases,
        "score_distribution": {
            "excellent (>85)": len([r for r in results if r["total"] > 85]),
            "good (70-85)": len([r for r in results if 70 <= r["total"] <= 85]),
            "poor (<70)": len([r for r in results if r["total"] < 70])
        }
    }
```

### 3.4 根据结果迭代

```
跑完评测 → 看 worst_cases → 找失败 pattern → 改 Prompt → 再跑评测 → 对比

关键动作：做 diff
  不是「新 Prompt 好不好」
  而是「哪些 case 从差变好了」和「哪些 case 从好变差了」

例：
  case_003：72 → 88（+16）✅ 这个改对了
  case_012：85 → 79（-6） ⚠️  这个 regress 了，需要分析为什么
  case_007：65 → 65（0）  📝  这个没影响，可能需要单独处理
```

## 4. Eval 的三个层次

```
Level 1: 人工抽检（你现在的 Evaluator Agent）
  - 每次执行后自动评估
  - 评分 + 给出 regenerate_hint
  - 优点：实时、自动化
  - 缺点：Evaluator 自身也可能有偏差

Level 2: 固定 Eval Set 自动化
  - 积累一批 Ground Truth case
  - 每次改 Prompt 后跑一次
  - 优点：可对比、可追踪
  - 缺点：Eval Set 需要持续维护

Level 3: 生产环境反馈闭环
  - 从人工修改中自动学习
  - 用户改了什么 → 那个地方就是 Eval Set 的新 case
  - 优点：自动进化
  - 缺点：需要产品化 level
```

你的项目当前在 Level 1，正在向 Level 2 迈进（你有 coverage_manifest.json 和 review-rules）。

## 5. Eval 的常见陷阱

### 5.1 用 LLM 评估 LLM

你的 Evaluator 是一个独立的 LLM 调用。好处是自动化，问题是「用一个 LLM 判断另一个 LLM 的输出」——这本身就需要 Eval。

```
应对：
  ① 定期人工抽查 Evaluator 的判断是否合理（如每周抽查 10 条）
  ② 如果人频繁推翻 Evaluator 的判断 → 说明 Evaluator 的 Prompt 需要改进
  ③ 重要的 case 人工标注 Ground Truth，用人与 LLM 的一致性作为 Evaluator 的指标
```

### 5.2 Eval Set 的退化

Eval Set 长期不更新 → 你一直在老的 case 上优化 → Prompt 慢慢过拟合到这些 case → 实际使用效果下降。

```
应对：
  ① 每次发现新的失败 case，加入 Eval Set
  ② 定期清理：已废弃的业务场景的 case 要移除
  ③ Eval Set 保持 20-50 个，太多则评测太慢，太少则覆盖不足
```

### 5.3 只看平均分

平均分从 75 提升到 80 看起来很美好——但可能实际情况是：
- 5 个简单 case 从 90 提升到 95
- 5 个困难 case 从 50 降到了 45

平均分 ↑ 但关键场景质量 ↓。

```
应对：
  ① 必须看 per-case 的分数变化，特别是最差的 3 个
  ② 困难 case 可以单独设更高的权重
```

## 6. 与你已有知识的连接

### 你的评估维度可以直接映射到 Eval 框架

```
你的 Evaluator Prompt              → Eval 框架
─────────────────────────────────────────────
检查内容覆盖是否完整                → 覆盖率维度
检查测试场景是否不重复              → 冗余度维度
检查是否和需求冲突                  → 准确性维度
检查步骤是否可执行                  → 清晰度维度
检查用例是否可追溯                  → 可追溯性维度
```

你已经做对了结构，现在只需要加「固定 Eval Set + 版本间对比」就能到 Level 2。

### 你的 regenerate_hint = Eval 的纠正输出

```
Evaluator 输出 regenerate_hint → 告诉 Generator 具体哪里要改
这就是 Eval 的「可操作反馈」——

不要只说「不好」，要说「哪里不好 + 为什么 + 怎么改」
```

## 7. 练习题

### 题目 1：为 Evaluator 做 Eval

你的 Evaluator Agent 评估了一条用例，给出了以下分数。请判断 Evaluator 的评估是否合理，如果不合理，哪里有问题。

```
【用例】
标题：充值金额为负数时提示错误
前置：用户已登录
步骤：1.进入充值页 2.输入-100元 3.提交
预期：系统报错

【Evaluator 评分】
覆盖率：4/5（缺数据一致性维度检查）
准确性：1/1（逻辑正确）
清晰度：2/2（可直接执行）

【问题】
这条用例真的「清晰度 2/2」吗？
```

---

### 题目 2：设计 Eval Set

为你的 prd-testcase-xmind Skill 设计 8 个测试 case。要求覆盖：
- 2 个典型 PRD
- 2 个边界 PRD
- 2 个错误/异常 PRD
- 2 个从历史失败中提取的 case

---

### 题目 3：分析 Eval 结果

下面是一次评测的前后对比。分析哪些改对了、哪些需要关注：

```
Case    v1.0    v1.1    变化
case_01 88      90      +2   (正常 PRD)
case_02 82      86      +4   (正常 PRD)
case_03 72      83      +11  (复杂 PRD) 
case_04 90      91      +1   (简单 PRD)
case_05 60      62      +2   (纯表格 PRD)
case_06 45      78      +33  (长 PRD)
case_07 80      76      -4   (简单 PRD)
case_08 70      70       0   (包含矛盾的 PRD)
```

---

### 题目 4：设计「从人工修改中学习」的机制

当用户审核 Agent 生成的用例并做修改时，如何自动从修改中提取信息，反哺到 Eval 体系和 Prompt 中？

---

## 8. 答案

### 答案 1

Evaluator 没有发现清晰度的真实问题：

1. **步骤不完整**：「2.输入-100元 3.提交」——这不是正常操作流程。正常流程应该是「输入金额 → 确认 → 支付」。输入负数后，是在哪个环节被拦截的？是在输入框失焦时校验，还是在点击确认时校验？这直接决定测试能否执行。

2. **预期结果模糊**：「系统报错」——什么形式的报错？Toast 提示？弹窗？输入框下方红字？文案是什么？只有「系统报错」四个字，另一名测试无法判断执行结果是否正确。

3. **前置条件不完整**：充值方式是什么（支付宝/微信/银行卡）？这条用例的「无法输入负数」可能和充值方式有关吗？如果有关就要标注。

**修正后的用例**：
```
标题：充值金额输入负数时前端拦截
前置：用户已登录，账户余额充足，选择支付宝充值
步骤：
  1. 进入充值页面
  2. 在金额输入框中输入"-100"
  3. 点击输入框外部区域（触发失焦校验）
预期：
  - 金额输入框下方显示红色提示文字"充值金额需大于0"
  - "确认充值"按钮保持不可点击状态
  - 不发起任何网络请求
```

清晰度 2/2 应该是上面这种——换任何一个人都能执行。

### 答案 2

```python
eval_set = [
    # === 典型 PRD ===
    {
        "id": "typical_1",
        "category": "典型",
        "input": """
        功能：用户积分兑换
        规则：用户可使用积分兑换优惠券。100积分=1元优惠券，500积分=10元优惠券。
        限制：每日最多兑换3次，优惠券有效期30天。
        """,
        "min_case_count": 10,
        "key_scenarios": ["积分不足", "超每日限额", "优惠券过期"]
    },
    {
        "id": "typical_2",
        "category": "典型",
        "input": """
        功能：App 启动闪屏页改版
        需求：支持展示静态图和短视频两种格式，支持点击跳转，根据用户标签个性化展示。
        灰度：先对 10% 用户开放
        """,
        "min_case_count": 8,
        "key_scenarios": ["图片格式", "视频格式", "跳转", "灰度", "个性化"]
    },

    # === 边界 PRD ===
    {
        "id": "edge_1",
        "category": "边界-极短",
        "input": "支持微信支付充值",  # 只有一句话
        "min_case_count": 6,
        "expectation": "Agent 应该把一句话扩展出完整的测试场景，包括金额、状态、异常"
    },
    {
        "id": "edge_2",
        "category": "边界-纯表格",
        "input": """
        | 等级 | 所需积分 | 权益 |
        |------|---------|------|
        | Lv1  | 0       | 基础功能 |
        | Lv2  | 100     | 专属客服 |
        | Lv3  | 500     | 优先退款 |
        | Lv4  | 2000    | 定制服务 |
        """,
        "min_case_count": 8,
        "expectation": "Agent 应该正确解析表格，生成等级相关测试用例"
    },

    # === 错误/异常 PRD ===
    {
        "id": "error_1",
        "category": "矛盾PRD",
        "input": "充值金额限制：第2章说单笔上限100000元，第5章说单笔上限50000元",
        "expectation": "Agent 应该标注矛盾并请求澄清，而不是随便选一个"
    },
    {
        "id": "error_2",
        "category": "信息缺失",
        "input": "优化支付流程，提升支付成功率",
        "expectation": "Agent 应该指出信息不足（不知道具体改了什么），生成有限的通用用例并建议补充信息"
    },

    # === 历史失败 case ===
    {
        "id": "history_1",
        "category": "历史失败-漏了并发",
        "input": "用户站内转账功能，从A账户转账到B账户",
        "min_case_count": 8,
        "regression_check": "必须包含并发转账的用例（两人同时向同一账户转账）"
    },
    {
        "id": "history_2",
        "category": "历史失败-状态不全",
        "input": "优惠券发放和核销功能",
        "min_case_count": 8,
        "regression_check": "必须覆盖优惠券的所有状态：未使用/已使用/已过期/已退回"
    }
]
```

### 答案 3

```
case_06 (+33)：改动对长 PRD 非常有效，说明可能是优化了上下文处理或分块策略
  → 保留这个改动

case_03 (+11)：复杂 PRD 也有较大提升
  → 说明改动对复杂场景有帮助

case_07 (-4)：简单 PRD 轻微下降
  → 关注：是不是为了优化长 PRD 加了复杂指令，让简单场景反而困惑了？
  → 需要单独再看 case_07 的输出，看具体哪里变差了

case_08 (0)：矛盾 PRD 没变化
  → 这个 case 可能需要不同的策略（不只是 Prompt 优化，可能要加专门的校验逻辑）

总体：v1.1 的平均分从 73.4 提升到 80.0，提升显著。
但 case_07 的轻微回退需要在合并前确认原因。
```

### 答案 4

```python
# 从人工修改中自动学习的机制

# ① 记录每次人工修改
def track_human_edit(original_case, edited_case, edit_description):
    """
    记录：
    - 哪条用例被改了
    - 改了什么（diff）
    - 为什么改（人备注 / Agent 推断）
    """
    edit_record = {
        "timestamp": now(),
        "original": original_case,
        "edited": edited_case,
        "diff": compute_diff(original_case, edited_case),
        "edit_type": classify_edit(compute_diff(original_case, edited_case)),
        # edit_type 如：add_dimension / fix_expected / add_precondition / split_steps
        "reason": edit_description or infer_reason_from_diff(original_case, edited_case)
    }
    save_to_edit_log(edit_record)

# ② 定期分析修改 pattern
def analyze_edit_patterns(period="monthly"):
    """找出最常被修改的 pattern"""
    edits = load_edit_log(period)
    patterns = group_by(edits, "edit_type")

    # 发现：过去一个月，30% 的修改是「补数据一致性维度」
    # 结论：Generator 容易漏数据一致性 → 强化 Prompt 中数据一致性的要求
    return {
        "top_edit_types": count_by(edits, "edit_type"),
        "top_missing_dimensions": find_missing_dimensions(edits),
        "suggested_prompt_updates": generate_prompt_fixes(patterns)
    }

# ③ 自动生成新的 Eval case
def auto_generate_eval_cases(edit_log):
    """从高价值修改中提取新 Eval case"""
    # 被修改的原始用例 → 加入 Eval Set
    # 下次改 Prompt 后，看新 Prompt 是否能生成更接近「人改后版本」的用例
    new_eval_cases = []
    for edit in edit_log:
        if is_high_value_edit(edit):  # 不只是文案修改，而是逻辑/维度修改
            new_eval_cases.append({
                "id": f"auto_eval_{edit.timestamp}",
                "input": edit.original_prd,
                "regression_check": edit.pattern,  # 确保不再犯同样的错误
                "source": "human_edit"
            })
    return new_eval_cases

# ④ 反哺 Prompt
"""
分析结果示例：
  过去一个月，65 条人工修改中：
  - 18 条（28%）：补充了「数据一致性」维度（原生成遗漏）
  - 12 条（18%）：修改了预期结果（原预期不够具体）
  - 8 条（12%）：调整了优先级（原默认 P1，应改为 P0）

反哺行动：
  1. 在 Generator Prompt 中加强数据一致性检查：「每个涉及多系统/多表的功能点，
     必须生成至少 1 条数据一致性校验用例」
  2. 在预期结果的 Prompt 模板中加示例：「预期结果不是"操作成功"，而是具体的
     可观察现象，如 Toast 文案、页面跳转目标、接口返回字段值」
  3. 更新 review-rules.md，补充「涉及资金/金额的功能点默认 P0」
"""
```

**核心逻辑**：每个人工修改都是一个数据点，告诉你「Agent 哪里不够好」。收集 100 个修改，你就知道改进 Prompt 的准确方向。
