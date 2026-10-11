# “第 1 轮调优已启动”长时间不变化：诊断与修改

检查对象：`D:/Code/MotorAI/MotorAIv2/Output/test3`，2026-10-09 晚间实际运行。

## 实际运行结论

检查期间任务正在推进，未发现本轮 GMP 编译、SIL 握手或闭环仿真失败。

- 后台于 21:42:47 启动，配置为 2 个候选方案、每个最多 4 次参数迭代、最多 2 轮；候选串行执行。
- `candidate_01` 于 22:01:13 完成 4 次迭代，耗时约 18 分 26 秒。得分依次为 58.160740、74.499226、83.040659、87.110844，`errors` 为空。
- 控制器日志出现 `GMP SIL session established` 和 `Simulink session ended explicitly at major step 40000`，说明新平台握手及仿真正常完成。
- 随后 `candidate_02` 启动；22:03:47 启动该方案的控制器与 MATLAB 仿真，检查时日志已确认建立 SIL 会话。
- `candidate_01` 最后一次调节时间为 0.565 秒，单项分 69.6。停止条件要求综合分至少 85、最低单项分至少 80、指标错误数为 0，因此综合分 87.11 仍不足以满足全部条件。

这些是检查时的状态快照，后续分数和进度以实际输出文件为准。

## 界面看起来卡住的原因

1. `run_optimize_for_candidate()` 原来用 `subprocess.run(capture_output=True)`，子进程结束后才保存标准输出和错误输出。因此正在仿真时，Optimize 日志可能为空或不存在。
2. `run_agent_optimization()` 原来只在启动和 QProcess 退出时更新界面，没有运行阶段回报。
3. `run_competition()` 原来在后台进程内部递归运行下一轮，界面也实现了一套逐轮启动逻辑。界面的“第 1 轮”提示实际可能覆盖后台的多轮运行。
4. 后台递归原来没有根据 `requirement_satisfied` 停止，界面还默认传入 `--force-next-round`。这是另外发现的停止逻辑缺陷，并非当前第一轮继续仿真的原因。

## 修改清单

| 文件 | 修改 |
| --- | --- |
| `D:/Code/MotorAI/MotorAIv2/Competition/competition_runner.py` | 子进程采用 UTF-8 无缓冲输出，逐行实时保存日志，错误输出直接落盘；把阶段提示转发给界面；新增 `--single-round`；CLI 根据停止条件与轮数限制继续，UI 模式每轮返回；本轮结果先保存再继续；候选失败返回非零，反馈/策略异常不再被静默吞掉。 |
| `D:/Code/MotorAI/MotorAIv2/Generate/ui/ui_main.py` | 使用 QProcess 实时输出信号保存完整日志并显示阶段提示；支持 UTF-8 字符跨数据包边界；通过 `--single-round` 由界面统一管理轮次，移除默认强制下一轮；失败时显示错误摘要与日志位置，避免把失败显示为完成或读到上一轮反馈。 |
| `D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/app.py` | 输出每次参数迭代开始、模型请求等待、迭代评分完成的阶段提示。 |
| `D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/tools/automation.py` | 输出编译、模型准备、控制器启动、闭环仿真和输出验证的阶段提示。 |
| `D:/Code/MotorAI/MotorAIv2/tests/test_optimization_progress.py` | 新增 8 项离线回归测试，涵盖运行中日志可读、错误透传、轮次边界、满足条件停止、轮数限制、失败传播、Qt 实时输出及界面启动参数。 |

## 验证范围

8 项新增测试与原有 5 项 GMP SIL 兼容测试通过。Qt 输出测试使用真实 QProcess 和无界面 QApplication；轮次测试模拟优化/生成/模型服务，未调用真实 LLM、MATLAB 或控制器。语法检查与 `git diff --check` 通过。

测试汇总：`C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/optimization_progress_test_summary.json`。

本次检查保留了正在运行的真实任务，没有重新启动调优。新界面代码需在本次任务结束后重启 MotorAI 才生效；尚未在重启后的完整真实两轮调优中验证新提示。

## 运行日志

- 迭代状态与评分：`D:/Code/MotorAI/MotorAIv2/Output/test3/candidates/candidate_01/log/optimize/tuning_result.json`（第二方案位于 `candidate_02`）。
- 实际控制器握手与结束事件：各方案 `log/optimize/build/run_exe.log`。
- Optimize 工具调用与异常：各方案 `log/optimize/run_optimize_stdout.txt`、`run_optimize_stderr.txt`。
- 界面启动的后台进程日志：`D:/Code/MotorAI/MotorAIv2/Output/test3/log/ui/competition_runner_stdout.txt`、`competition_runner_stderr.txt`。
