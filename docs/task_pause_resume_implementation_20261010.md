# MotorAI 对话停止与调优恢复

日期：2026-10-10。

## 使用方式

1. 重新启动 MotorAI UI，打开优化工程。
2. 发送对话、生成控制程序、生成需求指标或启动调优后，输入框右边的按钮变为“停止”。输入框中尚未发送的文字会保留。
3. 点击“停止”，按钮显示“正在停止…”。清理结束后恢复为“发送”，可以继续输入新指令。
4. 发送“继续运行”可以恢复暂停的操作。“继续”“恢复运行”“继续调优”“继续优化”“继续生成”也可以识别。
5. 调优恢复会读取本轮检查点，跳过本次任务已经完成的候选方案及迭代。被中断的模型调用、编译或仿真会重新执行。

暂停采用保存检查点并结束当前执行进程的方式。已完成的迭代记录、模型对话、当前参数、最佳参数和最佳分数会保留；正在执行的仿真不保留 MATLAB 内存状态。程序生成和指标生成暂停后，继续运行会重新执行相应生成流程。

修改需求或启动另一轮调优时，检查点必须同时匹配任务标识、工程路径和需求指纹。旧结果仍保留在原有产物中，但不会被当成本次任务已经完成的迭代。

新版 UI 管理由它启动的后台任务。已经由旧版 UI 启动的进程没有这套暂停状态，更新代码不会自动接管它们；请在结束旧任务后重启 UI。

## 修改清单

下表路径均相对于 MotorAIv2 根目录。

| 文件 | 修改内容 |
| --- | --- |
| `Generate/ui/panels/main_program.py` | 发送/停止/正在停止三种按钮状态；取消对话、意图识别、程序生成、指标生成；保留输入草稿；识别继续指令；屏蔽取消任务迟到的回调。 |
| `Generate/ui/widgets/chat.py` | 使用已有 PyQt5 的网络组件执行可中止的模型请求；检查线程取消标记；增加共用的可取消线程基类。无需新增 Python 依赖。 |
| `Generate/ui/workflow/agent_flow.py` | 意图识别可以取消，停止后不执行迟到的路由结果。 |
| `Generate/ui/panels/requirement.py` | 将多阶段指标生成移到后台线程；界面更新通过 Qt 信号返回主线程；停止后不进入后续阶段；目标表刷新不会重复绑定编辑事件或触发并发写入。 |
| `Generate/ui/ui_main.py` | 跟踪调优进程；暂停时保存工程和轮次；取消下一轮自动启动定时器；停止完成后允许继续输入；阻止运行期间切换工程；关闭窗口时先清理任务；处理进程启动失败。 |
| `Generate/ui/workflow/task_control.py` | 在后台清理 UI 所拥有的 Windows 进程树；本地调用进程停止后再次查找远端任务标记，并请求精确停止远端任务。 |
| `Generate/ui/run_agent.py` | 旧模式调优启动器等待批处理结束，使 UI 能持续跟踪完整子进程树；转发恢复参数；使用当前 Python 解释器。 |
| `Optimize/agent_optimize/run_tuning_agent.bat` | 支持可选的 `--resume` 参数和启动器指定的 Python 解释器。 |
| `Competition/competition_runner.py` | 恢复本轮阶段；保留已生成的程序及已完成方案；补齐完成方案的汇总证据；为每次调优分配独立任务标识；下一轮策略生成放在可停止的后台进程中。 |
| `Optimize/agent_optimize/agent_core/checkpoint.py` | 校验工程路径、任务标识、需求指纹及完成迭代数，决定检查点是否有效。 |
| `Optimize/agent_optimize/agent_core/app.py` | 增加 `--resume`；从最后完成的迭代继续；保存模型对话及最佳参数状态；用临时文件原子替换检查点。 |
| `Optimize/agent_optimize/agent_core/tools/optimization.py` | 恢复最佳分数和最佳参数，继续使用已有的参数回退逻辑。 |
| `Optimize/agent_optimize/agent_core/parameters/parameter_header_editor.py` | 原子替换参数头文件，停止时不会留下写到一半的正式头文件。 |
| `Optimize/agent_silhelper/local_sil_runner.py`、`run_local_job.py`、`run_local_quick.bat` | 支持 `--batch`，调优使用本次任务创建的 MATLAB 进程，便于停止完整任务树。 |
| `Competition/competition_workspace.py` | 生成的本地仿真批处理脚本传入 `--batch`。 |
| `Optimize/agent_silhelper/sil_session.py` | MATLAB 批处理启动时回传进程对象，供远端 worker 跟踪和清理。 |
| `Optimize/agent_silhelper/remote_sil_client.py` | 每次请求保存任务 ID、随机取消令牌和 worker 地址；通信异常时保留标记，便于确认远端任务是否停止。 |
| `silworker/remote_sil_worker.py` | 增加 `/cancel_simulation`；同时匹配任务 ID 和取消令牌；停止被跟踪的进程树并释放 worker；处理取消请求先于任务登记到达的情况。 |
| `silworker/agent_silhelper/local_sil_runner.py`、`run_local_job.py`、`sil_session.py` | 同步独立 worker 所需的辅助代码。 |
| `tests/test_task_pause_resume.py` | 添加停止、恢复、进程清理和远端任务身份校验回归测试。 |

## 暂停状态与检查点

- 工程 `log/ui/paused_task.json`：保存工程路径和当前暂停轮次，重开工程后仍可发送“继续运行”。
- 工程 `rounds/round_NN/run_state.json`：保存本轮的生成/调优阶段及独立任务标识。
- 候选方案 `log/optimize/tuning_result.json`：保存完成迭代、评价结果、模型对话和最佳参数状态。
- 候选方案 `log/optimize/simulation/remote_active.json`：保存尚需确认结束的远端请求，只有确认后才删除。

已经完成的候选方案在恢复时跳过调优，但会重新补齐汇总证据。检查点不完整、需求已变化或来自其他任务时，保留当前参数并重新评价。停止过程失败时界面会显示错误，允许重试；不会直接把未确认停止的远端任务显示为已暂停。

## 远端 worker 更新

使用远端仿真时，需要同步并重启新版 `silworker/remote_sil_worker.py` 及其 `agent_silhelper` 辅助文件。旧 worker 不支持 `/cancel_simulation`，UI 会报告远端停止未确认。先结束旧 worker 正在执行的任务，再更新、重启并重新运行工程。

## 验证结果

在 MotorAIv2 的 `.venv` Python 环境中执行离线测试：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
./.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
```

本次验证使用隔离临时目录和离屏 Qt；最终 **32 项测试全部通过**，包含原有 GMP/SIL 兼容性及实时日志测试。新增检查覆盖：

- 发送按钮变为停止；取消后按钮恢复；草稿保留；迟到回复被忽略；可以发送下一条消息。
- 本地 HTTP 模拟服务收到模型请求后，取消线程能在 1.5 秒内退出。
- 多阶段需求指标生成可停止，后续生成阶段和完成回调不会执行。
- 已完成一次、总计三次的任务恢复时，只执行剩余两次，保留已有结果和最佳参数状态。
- 改变需求或调优任务标识后，不跳过旧检查点对应的工作。
- 暂停发生在两轮之间时，取消下一轮定时启动；停止重试保留原暂停轮次。
- 恢复优化阶段不会重新生成控制程序；已完成方案不会再次启动 Optimize Agent，并补齐证据。
- 参数头文件替换中断时，原正式文件保持完整。
- 真实 Windows 测试进程树及其子进程被清理，另一个无关测试进程保持运行。
- 远端取消必须匹配令牌；完成清理后释放 worker；处理提前取消和本地停止期间新出现的远端标记。
- 旧模式启动器能处理带空格及中文的路径、等待子任务并传入恢复参数。
- 运行期间通过历史列表切换工程会被拦截。

真实 MainWindow 已通过离屏初始化和发送/停止状态切换检查。修改及新增的 Python 文件通过语法检查，`git diff --check` 通过。

本次没有运行完整的真实 MATLAB“中断仿真→继续调优”流程，也没有部署或重启用户正在使用的远端 worker。MATLAB 的停止依赖已验证的任务进程树清理机制，仿真恢复会重新执行本次被中断的仿真。
