# MotorAI 新版 GMP 迁移实施记录

日期：2026-10-09。修改已应用到 `D:/Code/MotorAI/MotorAIv2`。目标平台为 `D:/Code/gmp_pro`。

## 1. 已实施的修改清单

| 修改位置 | 修改内容与原因 |
| --- | --- |
| [Optimize/config_project.py](D:/Code/MotorAI/MotorAIv2/Optimize/config_project.py) | 使用 `gmp_core.h`、源管理字典/引擎及属性表判断 GMP 根目录，移除对已删除的生成器示例 BAT 的依赖。为优化配置写入 `automation.gmp_root`。 |
| [构建 BAT 模板](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/Example/build_sln.bat)、[启动 BAT 模板](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/Example/start_exe.bat) | 调用当前 GMP 环境入口；在 MSBuild 求值前生成源文件；检查 runtime/interface 输出。启动时以候选 simulate 目录为工作目录。 |
| [源管理配置](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/gmp_src_mgr/gmp_framework_config.json)及同目录三个 BAT | 补选 core 的 `base/port`、`rt`；BAT 从新版 GMP 的规范入口分发，固定到脚本目录运行。 |
| [VS 工程](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/DigialPower_simulink.vcxproj)、同名 `.filters` | 移除固定的旧库源文件列表；生成后重新收集 C/C++ 编译项，覆盖首次 IDE 构建；补本地 src/xplt include、C++17、`/FS`。移除旧 tracer 的 IDE 记录。 |
| [MotorAISILDependencies.props](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/MotorAISILDependencies.props) | 优先使用 GMP 私有依赖目录或候选自带依赖，也接受 `GMP_SIL_DEPENDENCY_ROOT`；链接 fmt/Windows socket 库并复制运行 DLL。已有依赖时不重复启动 vcpkg restore。 |
| 根级 [ctl_main.c](D:/Code/MotorAI/MotorAIv2/Generate/Example/ctl_main.c)/`.h`、[user_main.c](D:/Code/MotorAI/MotorAIv2/Generate/Example/user_main.c)/`.h`及嵌套 `mcs_pmsm_nt/src` 同名文件 | 更新 scheduler/datalink 头文件路径；`float2ctrl` 改为新版 `real2ctrl`；纠正 PIL 宏拼写。嵌套模板保留原控制算法，不用测试生成的 PID 代码覆盖它。 |
| [控制器合并器](D:/Code/MotorAI/MotorAIv2/Generate/merge_loop_ids_into_ctl_main.py) | 同步转换宏，防止后续 SMC/LADRC 生成重新引入已删除的函数。 |
| [Driver_Board.h](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/xplt/Driver_Board.h)、[ctrl_settings.h](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/xplt/ctrl_settings.h) | 将原 MONKEY_BOARD 的标定常量放入 MotorAI 本地模板，消除对旧 GMP 私有板卡文件的依赖。 |
| [xplt.peripheral.cpp](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/xplt/xplt.peripheral.cpp) | 移除新版 GMP 已删除的 rt_trace include、注册和日志调用；保留 ADC/PWM/encoder 的顺序、方向和缩放。 |
| [sil_session.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/sil_session.py)、[motorai_sil_job.m](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/motorai_sil_job.m) | 统一本地/worker 模型准备：升级旧 SIL mask，使用 GMP 原始协议 helper/MEX 源码，配置 UDP/TCP，保存模型并生成路径相关的连接 ID。验证 264/200 字节 ABI。处理 Windows MinGW 的 C++17/socket 链接差异。 |
| [LocalSimulinkRunner](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/local_sil_runner.py)、[run_local_job.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/run_local_job.py)、[本地 BAT](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/run_local_quick.bat) | 没有 Python MATLAB Engine 时自动使用 MATLAB `-batch`；仍支持已共享的 Engine 会话。增加 prepare-only、平台路径、超时和预期连接 ID 参数。仿真/Scope 失败返回非零。 |
| [scope_sources.json](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/scope_sources.json) | 显式绑定三个测量 Scope。旧模型兼容导出会丢失部分关闭 Scope 的变量名，因此准备时恢复正确名称并启用日志；不通过同名嵌套诊断 Scope 猜测信号含义。 |
| [AutomationTools](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/tools/automation.py)、[process_runner.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/process_runner.py) | 强制执行“准备模型/契约 → 启动控制器 → 等待控制器报告 ready → 仿真 → 验证结果和退出码”。准备失败不启动；过期契约不运行；超时停止该任务进程树；后台 BAT 不弹新控制台。 |
| [Competition 工程配置](D:/Code/MotorAI/MotorAIv2/Competition/competition_workspace.py) | 生成候选优化配置时传递 GMP 根目录、本地模型及连接 ID；候选 BAT 使用该契约。 |
| [网络配置工具](D:/Code/MotorAI/MotorAIv2/Competition/candidate_network_config.py)、[网络面板](D:/Code/MotorAI/MotorAIv2/Generate/ui/panels/cosim_config.py)、模板 `network.json` | 改为 UDP/TCP 和两个数据端口。保存不变的选项时保留模型生成的 ID；选项改变时使 ID 失效。模板只保存选项，不伪造 ID。本地模式也可编辑端口。 |
| [remote_sil_client.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/remote_sil_client.py)、[remote_sil_worker.py](D:/Code/MotorAI/MotorAIv2/silworker/remote_sil_worker.py) | 增加 `/prepare_simulation`，由远端最终模型产生契约，交给本地控制器；运行前校验同一 ID 和端口。worker 不再把新契约覆盖成旧四端口 JSON。 |
| `silworker/agent_silhelper`、[worker 配置](D:/Code/MotorAI/MotorAIv2/silworker/silworker_config.json) | 同步独立部署所需的 runner、CLI、Python 契约 helper 和 MATLAB helper；worker 的 `gmp_root` 可由自己的配置或环境给出。 |
| 本机 `motorai_settings.json` | `paths.gmp_root` 已切换到 `D:/Code/gmp_pro`。这是本机设置，不将当前磁盘路径写进通用源码。 |
| [回归检查](D:/Code/MotorAI/MotorAIv2/tests/test_gmp_sil_compatibility.py) | 覆盖旧配置/错误 ABI 拒绝、网络选项保存时的 ID 保留/失效、远程契约传播及准备失败禁止启动。 |

## 2. 模型和数据约定

采用 GMP 的统一 SIL 协议，而非旧的四端口协议。控制器接收 264 字节，发送 200 字节。连接 ID 来自最终保存位置的模型和通信块，不能从另一个候选或另一台机器复制后直接沿用。

首次准备时断开旧 SIL 面板的库链接，按规范 helper 升级 mask；电机 plant、板卡标定和信号接线不重建。MEX 直接编译 `GMP_PRO_LOCATION/tools/gmp_sil/sil_helper/GMP_SIL_Core.cpp`，缓存在候选目录 `motorai_sil_mex/<Release>`，没有复制或修改 GMP 的 C++ 协议实现。

真实验证发现模板中 `ScopeData2`、`ScopeData3` 的工作区保存关闭。入口根据 scope map 选择相应测量 Scope 并启用日志；同名嵌套诊断 Scope 不启用。新启用的 Scope 沿用已启用测量 Scope 的抽样设置，保留整个仿真时间轴。缺失或同层重名 Scope 在准备阶段报错，避免读旧数据或错配通道。

## 3. 使用和复验

新建工程使用已更新的模板。现有 `Output` 工程保存了旧工程副本和自己的 `gmp_path`，全局设置不会自动覆盖它们；应新建验证候选或按前述文件清单迁移其工程绑定，再重新执行候选配置。历史结果不作为本次新平台测试证据。

依赖优先来自 GMP 私有安装：`<GMP>/bin/vcpkg_installed/<triplet>/<triplet>`。若使用已经安装的其它依赖目录，可在启动 MotorAI 前设置：

```powershell
$env:GMP_SIL_DEPENDENCY_ROOT = '<existing triplet directory containing include/lib/bin>'
$env:GMP_SIL_DEPENDENCY_INCLUDE = "$env:GMP_SIL_DEPENDENCY_ROOT/include"
$env:GMP_MATLAB_EXECUTABLE = '<MATLAB>/bin/matlab.exe' # 自动发现失败或需要固定 Release 时
```

只准备候选模型而不启动控制器：

```powershell
python D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/run_local_job.py --model-path '<candidate>/project/simulate/model.slx' --gmp-root '<GMP root>' --prepare-only
```

本机使用 MATLAB R2025b、Simulink/Simscape Electrical、MATLAB 已配置的 MinGW MEX 编译器，以及已存在的 asio/json/fmt 依赖。没有下载安装依赖包，也没有运行付费 LLM 生成/调参请求。对其它 MATLAB Release、硬件目标和跨机器网络的覆盖需单独验证。

回归检查命令（MotorAIv2 根目录）：

```powershell
python -m unittest discover -s tests -p test_gmp_sil_compatibility.py
```

## 4. 验证记录

| 检查 | 结果与证据 |
| --- | --- |
| 当前模板重新生成四分支 | PID、SMC、LADRC speed/position 输出与此前完整编译、协议验证通过的代码逐字节一致。 |
| 当前正式属性表 + Release/x64 Rebuild | 96 个库源文件，0 编译/链接错误，输出 EXE；[构建记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_build_summary.json)。 |
| 从零直接 MSBuild/IDE Build | 构建前生成目录为 0 个文件，构建后为 96 个；0 编译/链接错误；[首次构建记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_ide_build_summary.json)。 |
| 携带旧缓存的直接 IDE Build | 模板的旧 89 文件缓存被重新生成并改用 96 文件，0 编译/链接错误；[缓存构建记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_cached_ide_build_summary.json)。 |
| Debug/x64 构建 | 返回 0，Debug fmt 依赖及运行 DLL 复制通过；[Debug 日志](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_debug_build.log)。 |
| Python 回归 | 5 个 unittest 通过（包含 worker 分发一致性检查）；17 个变更入口/关联 Python 文件的 py_compile 通过。 |
| PyQt5 网络面板 | 无界面测试通过：TCP 选择、本地端口可编辑、旧命令端口控件已移除。 |
| MATLAB 模型准备 | 原模板模型升级、新协议 MEX 构建、diagram update 和契约校验通过；[准备记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_matlab_prepare.json)。 |
| 真实 worker HTTP 准备 | 独立 worker 返回远端模型生成的 ID；不同模型位置的 ID 不同；错误 ID 被 HTTP 409 拒绝；[worker 记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_remote_prepare_summary.json)。 |
| 电机模型完整闭环 | MATLAB R2025b、PID 验证候选、原模型 StopTime=2 秒。40,000 个控制步；三个 Scope 输出五路信号，各 401 个点，时间轴 0～2 秒；无 Scope 映射错误；本地仿真 BAT、控制器 BAT 退出码均为 0；[闭环记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_closed_loop_summary.json)。 |
| TCP 协议 | MATLAB 生成 TCP 契约后，真实控制器和规范客户端完成握手、20 帧 264/200 字节收发及 completed，双方退出 0；[TCP 记录](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/implementation_tcp_summary.json)。TCP 电机 plant 仿真未单独运行。 |

存在 GMP 头文件编码/类型转换警告；“0 错误”不等于“0 警告”。未把通信、构建检查当作稳定性或性能指标合格的证明。多候选并发、跨机器 worker、完整 LLM 调参和硬件尚未验证。
