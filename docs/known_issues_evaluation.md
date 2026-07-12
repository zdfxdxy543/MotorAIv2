# 评价指标体系 —— 已知问题 & 暂缓修复清单

审查时间: 2026-07-12
涉及文件: requirement.py, parameter_seeder.py, scoring.py, evaluator.py


## 1. _generate_targets_from_metrics 只取第一个 metric 的 target_value

位置: Generate/ui/panels/requirement.py  第 957-961 行

```python
for metric in metrics:
    if metric.get('signal') == signal:
        target_value = metric.get('target_value', 0.0)
        break  # ← 只取第一个匹配的
```

问题: 同一信号的多个 metric 理论上 target_value 应该一致，但如果 LLM 约束覆盖只更新了部分
metric（比如 signal_target_overrides 的更新逻辑），就会出现不一致。当前代码静默取第一个，出
了问题没有 warning。

风险: 低。目前信号级 target_value 同步逻辑（_collect_signal_targets → signal_target_overrides
→ 覆盖所有同信号 metric）已经保证了同信号一致，但缺乏防御性检查。

建议: 遍历所有同信号 metric，检查 target_value 是否一致，不一致时取多数或报 warning。


## 2. _generate_metrics LLM 失败时可能写回空 metrics 列表

位置: Generate/ui/panels/requirement.py  第 754-927 行

问题: LLM 调用有重试机制（最多 2 次），兜底方案是硬编码的 speed 三个 combo：
```python
parsed = [
    {"combo": "speed_overshoot", "constraints": []},
    {"combo": "speed_settling_time", "constraints": []},
    {"combo": "speed_steady_state_error", "constraints": []},
]
```
如果项目是 torque 控制或纯电流控制场景，available_signals 里没有 rotor_speed_rad_s，
这三个 combo 在 metric 构建阶段会被全部跳过（第 882 行 continue），最终写入空的
data['metrics'] = []，白白覆盖了之前可能有效的旧 metrics。

风险: 低~中。需要同时满足三个条件才会触发：(a) LLM 连续失败 3 次, (b) 项目不是速度控制,
(c) 用户之前手动配置过 metrics。但一旦触发就是数据丢失。

建议: 在 LLM 全部失败且构建出来的 metrics 为空时，不覆盖 project JSON 中的旧 metrics；
或者兜底时根据 available_signals 动态生成合理的默认 combo。


## 3. _get_reference_target 的 val != 0 检查跳过合法零值

位置: Generate/ui/panels/requirement.py  第 592-610 行

```python
if isinstance(val, (int, float)) and val != 0:  # ← 跳过了零值
    return float(val)
```

问题: 对于 id 电流控制，目标值合法为 0。如果 existing_targets 中 rotor_id_a 的 target_value=0，
这个检查会跳过它，层层回退到 PHYSICAL_QUANTITIES 的默认值。当前恰好默认值也是 0 所以没问题，
但逻辑本身是脆弱的——如果哪天有人把 id 默认值改成非零，或者某个信号目标值设为 0 是合法的，
就会出错。

风险: 低。当前所有合法零值恰好都与默认值一致。但如果未来要加新型号/新信号，需要注意。

建议: 把检查从 val != 0 改为 val is not None，允许零值通过。


## 4. parameter_seeder.py round-to-zero 回退方案不合理

位置: Competition/parameter_seeder.py  第 319-321 行

```python
new_value = round(new_value_raw, 6)
if new_value == 0.0:
    new_value = round(float(param.value) * 0.5, 6)
```

问题: 乘性扰动结果太小被 round 到 0 时，回退方案是把原值直接乘 0.5，完全跳出 profile 定义
的乘数范围。更糟的是，如果原值本身就极小（如 1e-7），乘 0.5 后依然会被 round 到 0，死循环。
虽然实际中很少遇到（模板默认值通常不会小到被 round 掉），但防御性代码形同虚设。

风险: 极低。模板默认值都在合理范围内，乘性扰动后几乎不可能出现 round-to-zero 的情况。

建议: 回退到一个有物理意义的最小值（如 max(param.value * 0.01, 1e-6)），或直接跳过该参数
并在 report 里记录 warning。


## 5. _compact_evaluation_summary 的 scoring_summary 字段同步

位置: Optimize/agent_optimize/agent_core/app.py  第 422-435 行
      Optimize/agent_optimize/agent_core/evaluation/evaluator.py  第 379-389 行

问题: _compact_evaluation_summary 现在透传了 scoring_summary（包含 min_metric_score），
evaluator.py 的 _add_scores_safely 错误路径也已经同步了这些字段。但如果未来有人修改
scoring.py 的 score_metric_results 输出结构（比如新增一个字段），需要同时更新至少 3 处：
(scoring.py 返回, evaluator.py 错误路径, app.py compact 函数)。目前没有自动化测试覆盖
这个结构一致性。

风险: 低。当前结构稳定，但缺乏测试覆盖，未来改动容易遗漏。

建议: 给 scoring.py 的输出结构写一个 schema/snapshot 测试，或者至少加个 dataclass 来
统一结构定义，让三处引用同一个来源。
