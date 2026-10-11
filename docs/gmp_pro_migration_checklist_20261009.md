# MotorAI 迁移到新版 gmp_pro：文件级修改清单与验证

> 实施更新：下面是先前的隔离方案验证记录。MotorAI 运行源码现已修改，最新状态见 [实施记录](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_migration_implementation_20261009.md)。

日期：2026-10-09。MotorAI 根目录为 `D:/Code/MotorAI/MotorAIv2`，目标平台为 `D:/Code/gmp_pro`。

已在隔离副本中准备 20 个构建/生成相关文件的改法，并完成源码生成、四种控制分支完整编译链接、VS Release/x64 Rebuild 和本机 UDP 协议测试。原 MotorAI/GMP 运行代码、全局设置和 Output 候选均未改写。本次新增的交付文件是诊断文档。

**仍需迁移 Simulink SIL 通信块与自动化启动顺序，才能恢复完整的生成—仿真—评分—调参流程。** 四个 EXE 可以运行，不代表现有旧 SLX 可以直接与它们通信。

## 1. 修改范围与基本原理

MotorAI 把用户需求转成控制环选择，使用根级 `Generate/Example` 模板和合并器生成 C 控制器；Competition 把控制器、仿真工程与 xplt 复制成独立候选；Optimize 编译候选、启动 Windows SIL 控制器，再由本地/远程 MATLAB 执行模型，读取 Scope 数据评分、修改参数并重新运行。

迁移需要同时修改“生成输入”和“工程模板”。只修改已有 Output 下的 ctl_main 或 gmp_src，下次生成/同步就会覆盖；只修改嵌套示例的 src，也不会修复根级模板生成的新控制器。

## 2. 构建与生成：必须修改的文件

表中“通过”表示对应改法已在隔离副本验证，不表示已应用到原项目。

| 编号 | 原项目文件 | 具体修改 | 验证 |
| --- | --- | --- | --- |
| B01 | [Optimize/config_project.py](D:/Code/MotorAI/MotorAIv2/Optimize/config_project.py:28) | 改写 derive_gmp_root_from_sln_dir / resolve_gmp_root；用稳定文件校验根目录，移除对旧 example BAT 的依赖；删除仅凭祖先目录名 ctl 就返回父目录的回退。保留显式 gmp_path/gmp_root 优先。 | 旧、新平台根均被正确识别；无效目录被拒绝。 |
| B02 | [Example/build_sln.bat](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/Example/build_sln.bat:25) | 根目录定位/校验改用 gmp_core.h 和 src_mgr/framework_sync_src_v3.py；删除旧 BAT 的 where 检查；在本脚本中激活配置平台的 ensure_gmp_environment；先生成再启动 MSBuild；检查 JSON、生成脚本、gmp_runtime.c、ctl_component_interface.c，失败立刻返回非零。保留可由配置器改写的 SLN_PATH、SLN_DIR、GMP_PRO_LOCATION、LOG_DIR。 | 变量改写通过；实际构建 BAT 返回 0。 |
| B03 | [Example/start_exe.bat](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/Example/start_exe.bat:26) | 更新根目录识别；设置 GMP_PRO_LOCATION 并激活相同平台环境，让 EXE 继承正确 PATH/DLL 搜索目录；保留候选 SLN_DIR、日志和实际 EXE 名称。 | 实际启动 BAT、协议客户端和 EXE 均返回 0。 |
| B04 | [gmp_generate_src.bat](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/gmp_src_mgr/gmp_generate_src.bat)、[gmp_generate_inc.bat](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/gmp_src_mgr/gmp_generate_inc.bat)、[gmp_config.bat](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/gmp_src_mgr/gmp_config.bat) | 刷新为新版平台同名模板。关键是 `cd /d "%~dp0"`、环境 guard 和错误码传递；保留本项目 JSON，不能用另一个 suite 的模块选择覆盖它。 | 从 simulate 目录实际调用 source BAT 返回 0，正确生成 96 个源文件。inc/GUI 的改法已准备，未运行 GUI。 |
| B05 | [gmp_framework_config.json](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/gmp_src_mgr/gmp_framework_config.json) | 保留 src_only 与现有模块，在 selected_modules 追加 core/base\|port、core/rt；保证新运行时与 port 定义进入依赖闭包。 | gmp_runtime.c、interface 及新版 core 源码实际进入输出和链接。 |
| B06 | [DigialPower_simulink.vcxproj](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/DigialPower_simulink.vcxproj) | 将固定 GMP 源文件列表换成 `gmp_src_mgr\gmp_src\*.c` / `*.cpp`，保留本地 ctl_main、user_main、入口与 xplt 文件；属性表使用配置根；全部配置的 IncludePath 加入项目 src 和 xplt；C++17；需要并发 PDB 写入时加 /FS。新增项目板卡头。 | XML 解析通过；实际 Release/x64 Rebuild 返回 0，输出 EXE。 |
| B07 | [vcxproj.filters](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/DigialPower_simulink.vcxproj.filters) | 清理旧库源文件条目，或让生成库不依赖手工 filters 列表。该文件只影响 IDE 展示，不决定编译输入。 | 静态确认；非构建阻塞项。 |
| B08 | [根级 ctl_main.c](D:/Code/MotorAI/MotorAIv2/Generate/Example/ctl_main.c)、[ctl_main.h](D:/Code/MotorAI/MotorAIv2/Generate/Example/ctl_main.h)、[user_main.c](D:/Code/MotorAI/MotorAIv2/Generate/Example/user_main.c)、[user_main.h](D:/Code/MotorAI/MotorAIv2/Generate/Example/user_main.h) | 迁移 scheduler/datalink 头路径；把常量和实数表达式的 float2ctrl 改成 real2ctrl；修正 ENBALE_GMP_DL_PIL_SIM 拼写。运行时 parameter_gt 参数按语义用 param2ctrl。 | 四分支语法、完整编译和链接通过。当前用的是 float 后端，未验证 fixed-point/PIL。 |
| B09 | [merge_loop_ids_into_ctl_main.py](D:/Code/MotorAI/MotorAIv2/Generate/merge_loop_ids_into_ctl_main.py:232) | 修改生成字符串中的 float2ctrl，包括 LADRC speed enable、position enable、position step；不能只修已经生成的 C 文件。 | 用修改后的合并器重新生成 PID/SMC/LADRC 速度/LADRC 位置代码，均不再输出 float2ctrl。 |
| B10 | [嵌套模板 src](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/src) 中的 ctl_main.c/.h、user_main.c/.h | 同步 B08 的头路径、转换与 PIL 拼写，覆盖复制整个项目而不经过根级生成器的入口。 | 改法已准备；实际 VS 测试使用重新生成的 PID 文件。 |
| B11 | [ctrl_settings.h](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/xplt/ctrl_settings.h:43) 与新增项目 xplt/Driver_Board.h | 将旧 GMP 根目录的 MONKEY_BOARD 私有定义交付到项目 xplt，引用项目头。保留实际 ADC 增益/偏置、基值、PWM 参数。本次隔离副本使用旧工作区的同一板卡定义。 | 新版 interface 组件、全部工程编译通过。 |
| B12 | [xplt.peripheral.cpp](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/xplt/xplt.peripheral.cpp:18) | 删除 ctrl_rt_trace.h、trace 节点 enum/数组、注册和失效日志语句；保留 ADC/FOC 绑定与现有 monitor/Scope。不要恢复新平台已删除的 tracer。 | C++ 编译、链接、实际 EXE 启动通过。 |
| B13 | [motorai_settings.json](D:/Code/MotorAI/MotorAIv2/motorai_settings.json)、项目 JSON 和候选 JSON | 将 paths.gmp_root / gmp_path / gmp_root 指向用户选定的新平台，并重新配置新的验证候选；检查 BAT 与 vcxproj 最终值一致。不要只改全局设置后继续使用持久化旧根的候选。 | 本次隔离配置明确使用新根；原全局设置仍指向旧平台，未修改。 |

### B01 稳定根目录标识

验证以下文件，而不是已经删除的 gmp_fac_generate_srcs_example.bat：

```python
required = (
    'gmp_core.h',
    'tools/facilities_generator/src_mgr/gmp_framework_dic.json',
    'tools/facilities_generator/src_mgr/framework_sync_src_v3.py',
    'csp/windows_simulink/GMPCorePropertySheet.props',
    'tools/facilities_generator/GMPSrcGenPropertySheet.props',
)
```

隔离修改中的完整实现位于 [proposed/config_project.py](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/proposed/Optimize/config_project.py)。校验旧根成功仅验证定位逻辑，不能据此宣称迁移后的所有 C 模板仍支持旧版 GMP。

### B05 新增模块

追加到 selected_modules：

```json
[
  {"root": "core", "module": "base|port"},
  {"root": "core", "module": "rt"}
]
```

同一项目配置使用旧/新平台时分别生成 89/95 个源文件；补齐新运行时后生成 96 个。新版生成器会修剪不再选择的源文件，建议在新的候选或隔离副本中第一次同步，保留原调参结果。

### B06 生成时机与工程源码

```xml
<ClCompile Include="gmp_src_mgr\gmp_src\*.c" />
<ClCompile Include="gmp_src_mgr\gmp_src\*.cpp" />
```

MSBuild 在加载工程时展开通配符，所以必须在启动 MSBuild **之前**同步源码。仅依靠 PreBuildEvent 在第一次没有 gmp_src 的构建中生成文件，会晚于源文件项求值。迁移首次执行 Rebuild；后续调参继续使用增量 Build，无需每轮重编整个库。

原列表中的 gmp_dev_util.c、gmp_process_mgr.c、gmp_std_error_code.c、gmp_std_port.c、windows_rt_tracer.cpp 已不对应新平台输出；新平台还新增 datalink、ring_buffer、function_scheduler、CAN 和控制组件等文件。无需把旧平台源文件混回来补列表。

### B08 头路径与数值调用

| 原 include | 新 include |
| --- | --- |
| core/pm/function_scheduler.h | core/pm/function_scheduler/function_scheduler.h |
| core/dev/pil_core.h | core/dev/datalink/pil_core.h |
| core/dev/mem_presp.h | core/dev/datalink/mem_presp.h |
| core/dev/tunable.h | core/dev/datalink/tunable.h |

```c
ctrl_gt smc_vel_ref_pu = real2ctrl(0.0f);  /* 常量初始化 */
/* parameter_gt 的运行时参数按数值后端语义用 param2ctrl(value)。 */
```

新平台已移除 float2ctrl。SMC 全局初始化会直接报 C2099；其他分支可能先表现为 C4013，再在链接中成为未定义符号。验证时把 C4013 提升为错误，避免误把“带警告的语法通过”当成兼容。

ADC/FOC 的 control_port、主要 init/step/attach 签名本身仍兼容。无需改写整套 interface。错误落在 interface 的 include 链上，常常真正缺的是项目板卡头。

## 3. 运行协议：同样必须修改

新增发现：新版 [windows_simulink_main.cpp](D:/Code/gmp_pro/csp/windows_simulink/src/windows_simulink_main.cpp:65) 使用 [gmp_sil_helper.hpp](D:/Code/gmp_pro/tools/gmp_sil/sil_helper/gmp_sil_helper.hpp:76)，已经改为统一 TCP/UDP 会话协议；MotorAI 原模板仍是旧四端口配置。

实际将成功链接的新 EXE 配合原 network.json 启动，返回码为 1，报错为：

```text
Cannot establish GMP SIL session: Invalid GMP SIL configuration:
[json.exception.out_of_range.403] key 'connection_id' not found
```

补几个 JSON 键仍不足以兼容旧通信块：双方还必须完成 session_hello、使用相同连接 ID 和 payload 长度、传输带帧数据及结束状态。不要用任意 UUID 写入真实 network.json；真实模型的 ID 必须与其 Mask 初始化得到的值一致。

| 编号 | 文件/入口 | 必须修改的内容 | 当前验证状态 |
| --- | --- | --- | --- |
| R01 | [模板 network.json](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/network.json) | 使用新版契约：schema_version、transport、role、connection_id、数据收发两端口、双向字节数和超时等。命令状态随协议帧发送，旧两个命令端口不再承担新版通信。 | 原配置启动失败已复现；正确契约通过 EXE 回环验证。 |
| R02 | [MCS_STD_PMSM_MODEL.slx](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/MCS_STD_PMSM_MODEL.slx)、[2022b 模型](D:/Code/MotorAI/MotorAIv2/Generate/Example/mcs_pmsm_nt/project/simulate/MCS_STD_PMSM_MODEL_2022b.slx) | 安装目标 MATLAB Release 对应的新版 gmp_sil_core_pack / GMP_SIL_Core MEX；刷新库链接或替换旧通信块，确认 Mask、S-function 参数和 helper 均为新版。保留电机模型、采样时间、ADC/PWM、编码器和 Scope 映射。旧 SLX 内已确认残留 MaskCmdTxPort/MaskCmdRxPort。 | SLX XML 静态确认；未在 MATLAB 中升级或仿真。 |
| R03 | [candidate_network_config.py](D:/Code/MotorAI/MotorAIv2/Competition/candidate_network_config.py:39) | 新平台分支使用两端口/transport 配置；保存时不要用旧默认字段整体覆盖已准备好的完整 network.json。将网络用户输入保存到候选，再通过模型预处理生成最终控制器契约。修改 default/_normalize/_build_backend/list/save 及 CLI。 | 静态定位；产品代码未实施。 |
| R04 | [cosim_config.py](D:/Code/MotorAI/MotorAIv2/Generate/ui/panels/cosim_config.py:82) | 新平台 UI 提供 UDP/TCP、目标地址、两个数据端口；停止把旧命令端口写回新契约；若仍支持旧平台，按协议分别处理。 | 静态定位；未做 GUI 回归。 |
| R05 | [local_sil_runner.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/local_sil_runner.py:87) 与 [automation.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_optimize/agent_core/tools/automation.py) | 增加 prepare 阶段：加载最终候选模型、设置最新通信块参数、更新模型得到确定的 connection_id/ABI/JSON；检查契约后启动控制器，最后 sim。调用 start_exe 单独入口也应校验已经 prepare。 | 手工准备契约后 build/start BAT 和 EXE 全链路通过；自动 MATLAB prepare 未实施。 |
| R06 | [remote_sil_client.py](D:/Code/MotorAI/MotorAIv2/Optimize/agent_silhelper/remote_sil_client.py:110) 与 [remote_sil_worker.py](D:/Code/MotorAI/MotorAIv2/silworker/remote_sil_worker.py:180) | 同步新字段；worker 不得再用四端口 JSON 整体覆盖模型生成的契约。远程流程需要先 prepare 并返回实际远端模型的 ID、ABI、端口，再把同一契约交给控制器，随后运行模型。远程模型绝对路径参与 ID，不能沿用本机另一个路径算出的 ID。 | 静态定位；未验证远程服务。 |

### 保留数据 ABI，升级网络协议

当前项目选择的真实缓冲区仍是 dp_sil 类型。新旧 [std_sil_dp_interface.h](D:/Code/gmp_pro/ctl/component/digital_power/basic/std_sil_dp_interface.h) 的字段布局可以沿用：

| 方向 | packed 字段 | 字节数 |
| --- | --- | --- |
| Simulink → 控制器 | time: double；adc_result[24]: uint32；panel[16]: double；digital[8]: int32 | 264 |
| 控制器 → Simulink | enable: double；pwm_cmp[8]: uint32；dac[8]: uint32；monitor[16]: double | 200 |

这两个数字由实际模型类型/尺寸/对齐与 C 的 sizeof 同时确认。当前工程中 pc_simulate_buffer.h 还存在其他未启用的结构，不应拿它们的大小填写契约。此次客户端使用 packed 结构和 static_assert 校验 264/200；真实 EXE 的 startup 也检查 JSON 长度与内部缓冲区是否一致。

### 必须统一生成者、端口方向和启动顺序

优先使用平台的 [gmp_prepare_sil_connection.m](D:/Code/gmp_pro/slib/simulink_lib_src/src/gmp_prepare_sil_connection.m)，它按保存后的模型规范路径、block path、transport、地址、端口、ABI 生成稳定连接 ID，并原子写入模型目录的 network.json。

端口从两端视角互换：

| 字段 | 示例值 | 含义 |
| --- | --- | --- |
| 控制器 receive_port | 12500 | Simulink 的目标接收端口 / MaskMsgTxPort |
| 控制器 transmit_port | 12501 | Simulink 本地 UDP 接收端口 / MaskMsgRxPort |
| 客户端 transmit_port | 12500 | 控制器监听端口 |
| 客户端 receive_port | 12501 | 客户端本地接收端口 |

执行顺序应为：

1. 在模型最终保存位置加载/配置新版通信块，并运行初始化或 diagram update，生成连接 ID 与 ABI 契约。模型首次真实 major step 才进行网络连接。
2. 将该契约提供给实际控制器的工作目录，确保候选端口不冲突；远程时由远端模型 prepare 返回契约。
3. 启动控制器，确认进程存活并已进入等待会话阶段。
4. 执行 sim，发送同一连接 ID 的握手与数据，结束时发送 completed/aborted/faulted 状态。
5. 检查 EXE 退出码、仿真状态、结果文件时间戳，再进入评分。失败不要读取上一轮残留数据。

平台还有 [upgrade_gmp_sil_core_transport_mask.m](D:/Code/gmp_pro/slib/simulink_lib_src/src/upgrade_gmp_sil_core_transport_mask.m)，可作为升级规则参考；它只处理特定 MaskType 且 LinkStatus=none 的块，不能直接假设对 MotorAI 的库链接块调用后全部生效。实际迁移应在模型副本中确认库链接与 Mask/S-function 参数。

## 4. 依赖、编码与可延后项

- 原项目依赖 manifest 仍包含 asio、fmt、nlohmann-json。正式部署要让新版 GMP 环境、MSBuild/vcpkg 和 EXE DLL 搜索使用同一套已恢复依赖。本次复用已有本机安装树并在隔离工程中关闭 manifest 恢复，未验证新的私有环境安装、下载或全局 VS 集成。隔离用 validation_dependencies.props 不能作为产品模板原样提交。
- 原 xplt.peripheral.cpp 是 GBK，隔离副本已转换成 UTF-8 后使用 /utf-8；正式改动应明确统一项目文件编码，不能仅给 GBK 文件加 /utf-8。GMP 仍有部分 GBK 头，编译出现 C4828 等编码警告；结果是“0 错误通过”，不是“0 警告”。
- 旧 component/hardware_preset 的选用头仍存在，板卡和电机标定可以保留。若进一步对接新 SDPE preset，另外修改 HardwareConfig 的目录扫描和宏解析（旧 MOTOR_PARAM_* 与新按电机名加前缀的 RS/LD/LQ 等），不能只换路径。它不是本次最小构建修复的前置条件。
- vcxproj.filters 的清理、固定点数值后端、PIL、其他平台目标与多候选并发，可在基本 SIL 单工况恢复后回归。编译时出现的 PDB 并行写入问题与头/API 迁移是不同问题，/FS 应单独验证。

## 5. 已执行验证

工具链：MSVC v143 14.44.35207、Windows SDK 10.0.26100.0、VS 18 的 MSBuild。控制数值后端为 USING_FLOAT_FPU。

| 验证 | 实际结果 |
| --- | --- |
| 根目录解析 old/new/invalid | 旧、新根通过；无效根按预期拒绝。 |
| build/start BAT 配置器变量改写 | 通过，指向隔离候选与新 GMP 根。 |
| 从 simulate cwd 调用刷新后的 gmp_generate_src.bat | 返回 0；生成 96 个源文件，runtime/interface 均存在。 |
| 修改后的合并器重新生成四种控制分支 | PID、SMC、LADRC speed、LADRC position 均生成成功，不再输出 float2ctrl。 |
| 四分支 MSVC /Zs /W3 /we4013 | 全部通过。 |
| 四分支完整 C/C++ 编译与链接 | 每个目标编译新平台 96 个库源文件及 4 个本地文件；全部输出 EXE，编译/链接返回 0。依赖 ctl_main.h 的公共单元按各分支重新编译，未混用 PID 对象。 |
| 修改后的 VS 工程 Release/x64 Rebuild | 返回 0；0 编译错误，生成 Motor_Control_Suite_SIL_Env.exe；存在编码/转换等警告。 |
| 新 EXE + 原四端口 network.json | 返回 1，明确报 connection_id 缺失。 |
| 四个 EXE + 新协议客户端 | 每个握手成功，连续收发 20 帧 264/200 字节，发送 completed；客户端与控制器均返回 0。 |
| VS Rebuild 输出的 EXE + 新协议客户端 | 同样通过握手/20 帧/结束流程。 |
| 实际 build_sln.bat → start_exe.bat → 新协议客户端 | 三者均返回 0，已验证环境 guard、工作目录、日志、生成、构建、启动与结束。 |
| 原 MotorAI SLX + MATLAB/Simulink 电机闭环 | 未执行。当前验证 Python 环境没有 matlab.engine；也未取得可用共享 MATLAB 会话。 |
| 远程 worker、多候选并发、自动评分/调参 | 未执行。 |

网络测试使用本机 127.0.0.1 和临时可用端口，未连接远程 worker。普通沙箱内单进程 UDP 自发自收也超时；外部允许执行的同一测试通过。MSBuild 普通沙箱中程序数据库服务报 C1902，同一隔离 Rebuild 在允许执行环境中通过，故这两个沙箱现象不归因于 MotorAI 的源码兼容性。

20 帧测试是通信/控制器启动冒烟测试，输入为合成 ADC/时间数据，**没有电机 plant、扰动或参考轨迹，不能证明闭环稳定性、性能指标或评分正确性**。

## 6. 产物与复验

隔离工作目录：[gmp_compat](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat)。

- [20 个隔离修改文件清单](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/proposed_changes.json)，对应文件保存在 [proposed](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/proposed)。这部分是构建/生成改法，不含尚未实施的 MATLAB/GUI/远程协议迁移。
- [配置与生成结果](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/migration_config_summary.json)。
- [完整编译链接结果](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/full_build_summary.json)。
- [VS Rebuild 结果](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/msbuild_summary.json) 和 [完整日志](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/msbuild_rebuild.log)。
- [四分支 UDP 测试结果](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/runtime_summary.json)。
- [实际 BAT 全流程结果](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/bat_pipeline_summary.json)。

复现脚本：[validate_migration.py](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/validate_migration.py)、[full_link.py](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/full_link.py)、[msbuild_validation.py](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/msbuild_validation.py)、[runtime_probe.py](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/runtime_probe.py)、[bat_pipeline_validation.py](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat/bat_pipeline_validation.py)。脚本里的 D:/Code 和工具链路径仅用于本机诊断，不应硬编码进产品代码。

实施顺序建议：先 B01–B12 恢复生成/构建，建立新的验证候选；再 R01–R05 恢复本地 SIL；确认一条真实电机工况、ADC/PWM/encoder/Scope 和评分一致后，再做远程 worker 与多候选回归。B13 的全局切换应在新模板/协议准备好后执行。
