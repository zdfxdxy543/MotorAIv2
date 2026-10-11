# MotorAI 修改交接文档

整理日期：2026-10-11。项目根目录：`D:/Code/MotorAI/MotorAIv2`。

本文交接当前工作区中已经实施的修改，以及本地留存的验证结果。项目原理和使用方法见 [PROJECT_OVERVIEW.md](D:/Code/MotorAI/MotorAIv2/PROJECT_OVERVIEW.md)。

## 1. 接手时的状态

- 当前工作区包含 GMP 适配、任务控制、历史工程管理、F280049C 工程生成和 CCS/SysConfig 修复；这些修改尚未提交。
- 整理时 Git 最近一次提交为 `6aac463`（`Update README with latest version information`）。这只是工作区基线，不代表当前修改已经包含在该提交中。
- 当前目标平台为 `D:/Code/gmp_pro`；`D:/Code/gmp_pro_old` 用于迁移前后对照。本次工作没有重新证明所有功能仍同时兼容旧平台。
- `Output/`、`.venv/`、`motorai_settings.json` 被忽略；复制代码仓库不会自动带走用户工程、验证产物、运行环境和本机配置。
- `Generate/ui/history.json` 是有修改的已跟踪文件，包含本机历史工程状态。提交前需要单独判断是否保留，不能把它当成通用默认配置。

接手前先保存 `git status` 和差异。不要对整个仓库执行恢复操作来撤回某一项修复，也不要用工作区重新初始化覆盖现有调优结果。

## 2. 已确定的工程方案

每个 candidate 同时包含 `project/simulate` 和 `project/f280049c`，两者引用该 candidate 的同一份 `src/`，包括 `paras.generated.h`。优化更新参数头文件后，CCS 下次构建会读取更新后的参数，不需要另外维护一套硬件参数副本。

F280049C 模板直接来自现有的 `Generate/Example/mcs_pmsm_nt/project/f280049c`。保留此方案，不再增加独立的顶层硬件导出目录、第二份 F280049C 模板或额外的构建包装层。此前尝试的更复杂导出方案已按用户要求撤回。

候选方案自身的控制代码、板级头文件、启动汇编、链接命令文件和 SysConfig 文件保存在工程内；GMP 与 C2000Ware 通过 CCS 的外部路径/产品配置引用。项目移交时应保留整个 candidate 的目录结构，只移动 `f280049c` 文件夹会破坏指向 `../../src` 的链接。

## 3. 修改清单与维护入口

### 3.1 新版 GMP、源管理器与接口适配

| 修改 | 主要入口 | 后续维护要点 |
| --- | --- | --- |
| GMP 根目录校验、候选方案配置传播 | [config_project.py](D:/Code/MotorAI/MotorAIv2/Optimize/config_project.py)、[competition_workspace.py](D:/Code/MotorAI/MotorAIv2/Competition/competition_workspace.py) | 使用实际 GMP 根目录及新版注册表/生成器，不再依赖旧示例目录中的 BAT。 |
| 编译前生成 GMP 源文件，动态收集编译项 | [build_sln.bat](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/Example/build_sln.bat)、[simulate 模板](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/DigialPower_simulink.vcxproj)、模板 `gmp_src_mgr/` | GMP 源生成必须在 MSBuild 评估项目之前完成，避免首次编译出现零源文件或使用旧缓存列表。 |
| 新版头文件路径、数值转换、运行时接口 | [控制模板](D:/Code/MotorAI/MotorAIv2/Generate/Example/ctl_main.c)、[代码合并器](D:/Code/MotorAI/MotorAIv2/Generate/merge_loop_ids_into_ctl_main.py)、[完整示例控制代码](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/src/ctl_main.c) | 更新 scheduler/datalink 引用及 `real2ctrl` 等 API。根目录生成模板和完整示例都要保持兼容，不能用测试控制器覆盖完整示例算法。 |
| 仿真编译依赖与本地板级配置 | [MotorAISILDependencies.props](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/MotorAISILDependencies.props)、[Driver_Board.h](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/xplt/Driver_Board.h) | 复用已存在的依赖，可通过 `GMP_SIL_DEPENDENCY_ROOT` 指定路径；保留板级缩放、方向及 ADC/PWM/编码器语义。 |

目前已迁移到 GMP 新的源管理和 SIL 设施。修改范围不限于某个 include：构建顺序、编译源清单、接口 ABI、模型契约和网络设置必须保持一致。

### 3.2 SIL 模型准备、连接与数据采集

- [sil_session.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/sil_session.py) 和 [motorai_sil_job.m](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/motorai_sil_job.m) 使用选定 GMP 的统一 SIL helper/MEX 源，准备模型掩码、通信契约和 MEX 缓存。
- 当前契约中，控制器接收 264 字节、发送 200 字节。UDP/TCP 使用两个数据端口；不要恢复旧版四端口配置。
- Connection ID 由最终模型路径及通信块确定。复制模型或切换远程模型路径后不能沿用另一模型的 ID；改变通信配置会使原契约失效。
- [scope_sources.json](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/scope_sources.json) 明确测量 Scope 来源，补齐日志变量；缺失或歧义必须在准备阶段报错。模型物理连接及板级参数保持原有含义。
- [automation.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/tools/automation.py) 检查准备、构建、控制器启动和仿真结果；控制器就绪后才进入仿真。
- 远程端增加 `/prepare_simulation`，以远程实际模型生成契约，不匹配的 ID 返回 HTTP 409。
- 主项目与 [silworker](D:/Code/MotorAI/MotorAIv2/silworker/remote_sil_worker.py) 内 helper 的副本需要同步部署；远程机器还需配置自己的 GMP 和模型路径。

旧的 `silworker/README.md` 和 `Optimize/agent_silhelper/README.md` 仍含早期共享 Engine、旧路径或四端口示例。它们不能作为当前自动调优协议的完整依据；部署以当前代码及迁移/暂停文档为准，后续应同步整理这两份旧说明。

### 3.3 调优进度、轮次控制与失败诊断

入口：[competition_runner.py](D:/Code/MotorAI/MotorAIv2/Competition/competition_runner.py)、[ui_main.py](D:/Code/MotorAI/MotorAIv2/Generate/ui/ui_main.py)、[app.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/app.py)、[process_runner.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/process_runner.py)。

- 子进程使用无缓冲输出，stdout/stderr 逐行落盘并向 UI 反馈；UI 增量解码跨分块的 UTF-8。
- 显示迭代、编译、模型准备、仿真、评分和模型调用等待等阶段，避免长期只有“第 1 轮已启动”。
- UI 用 `--single-round` 启动 runner，由 UI 决定是否进入下一轮；独立 CLI 可自行推进外层轮次，避免两层重复递归。
- 根据达标条件和轮次上限结束任务，不默认强制下一轮。总体得分达标不等于全部指标达标，还需检查最低指标分和评价错误。
- 失败通过退出码、阶段信息和具体日志暴露，不继续使用旧反馈伪装成功。

此前“卡住”的 `test3` 任务实际在完成多次耗时迭代，主要问题是日志输出和 UI 可见性不足。历史诊断中的耗时/分数只对应当时工程，不是当前运行结果。

### 3.4 停止、恢复与等待动画

入口：[task_control.py](D:/Code/MotorAI/MotorAIv2/Generate/ui/workflow/task_control.py)、[agent_flow.py](D:/Code/MotorAI/MotorAIv2/Generate/ui/workflow/agent_flow.py)、[chat.py](D:/Code/MotorAI/MotorAIv2/Generate/ui/widgets/chat.py)、[checkpoint.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/checkpoint.py)。

- 发送按钮在任务运行时变为停止按钮；停止期间显示停止状态，完成清理后恢复发送，保留输入草稿。
- 对话、路由、生成、指标配置及调优任务使用统一取消入口；取消定时推进并忽略已失效任务的迟到回调。
- 后台调优状态复用已有 `ThinkingIndicatorWidget` / `Generate/旋转.gif`，停止或完成后清理动画。
- 停止会保存检查点并结束本任务拥有的进程树。它不是操作系统级进程挂起：中断的 MATLAB 仿真恢复时重新执行；生成/指标环节也可能重新请求。
- 输入“继续运行”“继续调优”“继续优化”等指令可恢复。复用检查点前检查工程路径、run ID 和需求指纹；需求改变后不能直接复用旧评价。
- 已完成的候选方案可跳过重复优化；当前/最佳参数和已完成迭代可恢复，随后重新建立必要的运行证据。
- 调优 MATLAB 使用自有 batch 进程，避免停止任务时结束用户其他 MATLAB 会话。
- 远程取消依赖 `/cancel_simulation` 及任务 ID、取消令牌。`remote_active.json` 保留到确认清理完成；旧远程 worker 未升级时不能保证停止完成。

重要状态文件：工程 `log/ui/paused_task.json`、`rounds/round_NN/run_state.json`、candidate `log/optimize/tuning_result.json`、candidate `log/optimize/simulation/remote_active.json`。

### 3.5 历史工程右键菜单

入口：[history.py](D:/Code/MotorAI/MotorAIv2/Generate/ui/panels/history.py)。

右键选中鼠标所在工程，提供“查看详情”“打开工程”“从历史移除”“删除工程…”。“从历史移除”仅删除历史记录；“删除工程”经确认后使用 `QFile.moveToTrash` 将工程目录送入回收站，成功后才移除历史并清理当前加载状态。

删除前校验工程身份和目录，拒绝根目录、代码仓库、链接/reparse point 及无法识别的工作区；运行中的工程不能删除。用户取消或回收失败时保留记录和文件。不要用真实用户工程做自动删除测试。

### 3.6 Windows `tuning_result.json` 拒绝访问

此前错误发生在固定 `.tmp` 替换正式文件时。共用写入函数 `write_result_json` 改为同目录唯一临时文件、关闭句柄后 `os.replace`；遇到 `PermissionError` 最多尝试 21 次，每次间隔 0.1 秒，总等待约 2 秒。

永久失败时仍抛出错误，保留原正式文件并清理本次临时文件；UI 暂停标记也使用该写入函数。参数头文件另有原子替换保护。不能把此修复解释成所有 JSON 写入路径均已完成同等加固。

### 3.7 F280049C 生成及 CCS 元数据修复

入口：[f280049c_project.py](D:/Code/MotorAI/MotorAIv2/Competition/f280049c_project.py)、[硬件模板中文说明](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/f280049c/README_CN.md)。

- 初始化 candidate 时复制现有模板，链接该 candidate 的 `src`，添加本地板级支持文件及 GMP 必需源链接；缺失源或扁平化文件名冲突直接报错。
- CCS 工程名包含 candidate 路径摘要，减少多工程导入重名。
- `.cproject` XML 序列化后补回 `<?fileVersion 4.0.0?>`。丢失此处理指令是先前 CCS “meta-data cannot be interpreted” 的原因，不能只验证 XML 语法是否正确。
- GMP CCS 产品版本读取所选根目录的 `.metadata/.tirex/package.tirex.json`；当前本机注册标签为 `1.00.00.05`。产品标签不能凭源码版本推测为 `2.10.00.00`。
- 新建目录采用临时目录再重命名，短暂 Windows 目录锁可重试；已有工程保留用户修改，只做必要兼容修复，避免每次初始化覆盖板级配置。

## 4. 最近的 SysConfig 修复：当前工程与新工程

报错工程：[test4/candidate_02/f280049c](D:/Code/MotorAI/MotorAIv2/Output/test4/candidates/candidate_02/project/f280049c/.cproject)。原错误指向 `Debug/null`：CCS 的 SysConfig 工具缺失有效输入脚本配置。

Debug/Release 已补齐明确的输入和 SDK 配置：

| 项目 | 值 |
| --- | --- |
| 输入脚本 | `${PROJECT_LOC}/280049C_LaunchPad.syscfg` |
| 设备 / 封装 / context | `TMS320F280049C` / `100PZ` / `system` |
| SDK | `${COM_TI_C2000WARE_INSTALL_DIR}/.metadata/sdk.json` |

同时移除脚本元信息中旧的 `gmp_pro@1.00.00.05` 产品要求；脚本主体保持原样。当前工程 Release 中不一致的 GMP 产品版本也已纠正。

| 工程 | 当前处理 | 原因 |
| --- | --- | --- |
| 已有 `test4/candidate_02` | 修复编辑器参数，继续编译工程内已有 `syscfg/` 代码；保持冻结的板级生成文件 | 用户脚本采用 LAUNCHXL/BOOSTXL 资源名，而现有接口引用 IRIS 名称。直接重新生成会产生 37 个未定义宏错误。 |
| 后续新建 candidate | Debug/Release 自动执行 SysConfig，优先包含 `${PROJECT_LOC}/${ConfigName}/syscfg`；排除复制的根目录 `syscfg/` | 模板脚本和接口的 IRIS 命名一致，可生成对应板级代码，且避免重复编译。 |
| 已存在的其他硬件工程 | 按旧工程兼容路径补缺失项，保留有效输入配置和用户工具参数 | 已有用户工程不能按新模板无条件重建。 |

模板还关闭 SysConfig 自动生成 code-start branch，保留现有启动汇编，避免重复定义。

当前工程修复前的备份在 [current_backup](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/current_backup)。已有控制/板级文件 48 个经过哈希比对保持不变。后续如果要让该工程也启用自动生成，应先显式统一脚本与板级接口的资源命名，再重新构建验证。

## 5. 验证证据与结论边界

以下是此前实施过程中留存的结果；本次文档整理没有重新运行付费模型调用、MATLAB 仿真或全量测试。

| 范围 | 已留存的验证 | 证据与边界 |
| --- | --- | --- |
| GMP 迁移 | PID、SMC、LADRC 速度/位置分支；原生 Release/x64 与 Debug/x64 编译；首次源生成及旧缓存更新 | [迁移实施记录](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_migration_implementation_20261009.md)，包括 96 个 GMP 库源文件的构建记录。 |
| SIL 闭环 | MATLAB R2025b 模型准备、MEX、真实 PID 电机模型 2 秒仿真、40,000 控制步、3 个 Scope 数据；TCP 20 帧握手 | 同上。TCP 验证为通信握手，未单独跑 TCP 电机模型闭环。 |
| 日志/轮次 | 流式日志、UTF-8 分块、单轮 UI、达标和轮次停止、失败传播等测试 | [进度诊断及修复记录](D:/Code/MotorAI/MotorAIv2/docs/optimization_progress_diagnosis_20261009.md)。真实新 UI 连续多轮仍需验收。 |
| 停止/恢复 | Qt offscreen、HTTP 请求取消、Windows 自有进程树、检查点及远程取消竞态等测试 | [暂停恢复实施记录](D:/Code/MotorAI/MotorAIv2/docs/task_pause_resume_implementation_20261010.md)。该文档的 32 项计数对应当时版本。 |
| Windows 文件锁 | 真实读句柄释放后写入、唯一临时文件、永久拒绝访问及 UI 共用写入测试 | [test_task_pause_resume.py](D:/Code/MotorAI/MotorAIv2/tests/test_task_pause_resume.py)。 |
| CCS 导入 | 缺失 fileVersion 的对照导入失败；仅补回处理指令后 CCS 12.8.1 导入成功 | [before_import.log](D:/Code/MotorAI/MotorAIv2/Output/ccs_import_validation/before_import.log)、[after_import.log](D:/Code/MotorAI/MotorAIv2/Output/ccs_import_validation/after_import.log)。 |
| 最新 SysConfig / F280049C | 当前工程副本与新生成工程均导入并完成 Debug、Release 构建，产生 4 个 `.out`；硬件生成回归 8 项通过 | [verification.json](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/verification.json)、[验证说明](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/verification.md)。CCS 12.8.1、SysConfig CLI 1.26.2。 |

最新 CCS 验证是在隔离副本上完成：当前工程最终成功的 Debug 日志为 [current_debug_build_frozen.log](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/current_debug_build_frozen.log)。同目录 `current_debug_build.log` 是最初尝试自动生成时的失败记录，不应当作最终结果。其余最终构建日志为 [current_release_build.log](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/current_release_build.log)、[generated_debug_build.log](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/generated_debug_build.log)、[generated_release_build.log](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/generated_release_build.log)。

当前 `tests/test_*.py` 共定义 50 项测试：F280049C 8、SIL 5、历史工程 6、优化进度 8、任务控制/检查点 23。此数字是当前测试清单，不等于本次重新执行了 50 项。

需要复验时，在项目根目录运行：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

这些测试大部分采用本地桩、Qt offscreen 或隔离工作区；不能替代真实 MATLAB 停止/恢复、远程部署、完整 LLM 流程和硬件验证。

## 6. 后续验收与待办

1. 重启 MotorAI，确保载入最新 Python 代码；刷新/重新载入 CCS 工程元数据，实际打开当前 `.syscfg`。已有记录证明 CLI 解析和原生构建通过，尚未证明 CCS 图形编辑器双击打开成功。
2. 用一个新建 candidate 验收真实 UI 的生成 → 调优 → 日志与动画 → 停止 → 继续流程，尤其检查 MATLAB 仿真中断后的重启、最佳参数恢复和外层轮次停止。
3. 更新并重启实际远程 worker，确认 `/prepare_simulation`、`/cancel_simulation`、两端口契约及主端/worker helper 一致，再做跨机器取消和恢复验收。
4. 如需让已有 `test4/candidate_02` 改为自动 SysConfig 构建，先完成资源命名/引脚映射协调。保持冻结模式也可继续使用当前控制代码构建。
5. 在实际开发板上检查电机/板级配置、控制级别、采样/缩放及引脚，然后验证烧写和运行。当前没有真实烧写或电机运行结果，仿真优化结果不构成硬件性能验证。
6. 后续整理旧 helper/worker README。仓库已有 [评价体系暂缓清单](D:/Code/MotorAI/MotorAIv2/docs/known_issues_evaluation.md) 是 2026-07-12 的历史记录，本轮未逐项重新审查，不能直接宣称仍存在或已经修复。

完整 LLM 端到端、多候选并行压力、跨机器完整闭环及真实硬件仍是验证缺口；不要依据单个本地编译或通信测试扩大结论。

## 7. 排障与交付资料

| 现象 | 优先查看 | 排查方向 |
| --- | --- | --- |
| 长时间停在“后台运行中” | 工程 `log/ui/competition_runner_stdout.txt`；candidate `log/optimize/run_optimize_stdout.txt` | 看最后阶段、子进程是否输出、MATLAB/模型调用耗时；先区分仍在计算和实际失败。 |
| 调优失败、返回码 1 | 对应 stderr；candidate `log/optimize/build/`、`simulation/` | 定位具体失败阶段，避免只看外层摘要。 |
| Connection ID / 帧长度错误 | 模型准备输出、网络配置、远程 worker 日志 | 确认所选 GMP、实际模型路径、通信块和两个端口，重新准备契约。 |
| JSON 替换 WinError 5 | `tuning_result.json` 写入异常及文件占用 | 确认共用写入函数已载入；短锁可重试，持续拒绝访问仍需处理文件占用/权限。 |
| CCS 元数据无法解释 | `.cproject` 文件头和导入日志 | 检查 fileVersion 处理指令以及产品标签。 |
| SysConfig 加载 `Debug/null` | Debug/Release 的 SysConfig INPUT_SCRIPT / PRODUCTS | 检查明确脚本与 SDK 配置，并刷新 CCS 元数据。 |
| 自动 SysConfig 后 IRIS 宏缺失 | `.syscfg` 资源名与 `xplt` 接口、最终构建日志 | 先统一资源命名；不要用不同板级脚本覆盖已有冻结生成代码。 |
| 停止后仍显示清理中 | `paused_task.json`、`remote_active.json`、worker `/cancel_simulation` | 确认远端支持取消并已确认清理，不能把未确认取消当成成功停止。 |

交付代码时需同时包含新增模块、模板支持文件和测试，不能只复制已跟踪文件的 diff。需要移交运行证据时另外归档 `Output/sysconfig_bugfix_validation`、`Output/ccs_import_validation` 及所需用户工程；原生迁移的额外记录位置见迁移实施文档。

修改新工程行为应优先更新生成器与模板；只手工修改某个 `Output/` 工程不会修复后续生成。当前工程修复及备份需要单独保留。本文文件链接按当前机器绝对路径记录，迁移到新位置后需相应更新链接和本机配置。

## 8. 相关记录的阅读顺序

1. [项目说明](D:/Code/MotorAI/MotorAIv2/PROJECT_OVERVIEW.md)。
2. [GMP 迁移实施记录](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_migration_implementation_20261009.md)。
3. [调优进度诊断与修复](D:/Code/MotorAI/MotorAIv2/docs/optimization_progress_diagnosis_20261009.md)。
4. [停止/恢复实施记录](D:/Code/MotorAI/MotorAIv2/docs/task_pause_resume_implementation_20261010.md)。
5. [F280049C 模板说明](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/f280049c/README_CN.md) 和 [最新 CCS 验证](D:/Code/MotorAI/MotorAIv2/Output/sysconfig_bugfix_validation/verification.md)。

早期 [兼容性分析](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_compatibility_analysis_20261009.md) 和 [迁移清单](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_migration_checklist_20261009.md) 用于理解问题来源；其中尚待迁移的描述不能覆盖后续实施记录和当前代码。
