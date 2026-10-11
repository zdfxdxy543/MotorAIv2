# MotorAI 与新版 gmp_pro 的兼容性分析

> 实施更新：用户随后授权修改 MotorAI；当前修改与最新验证见 [实施记录](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_migration_implementation_20261009.md)。下文保留最初诊断时的状态。

> 追加验证：文件级修改清单、完整编译链接、VS Rebuild 和新版 SIL 协议测试已完成，见 [迁移清单与验证](D:/Code/MotorAI/MotorAIv2/docs/gmp_pro_migration_checklist_20261009.md)。下文第 5 节保留初轮诊断记录；最新结论以追加报告为准。


分析日期：2026-10-09。比较对象：`D:/Code/MotorAI/MotorAIv2`、`D:/Code/gmp_pro_old`、`D:/Code/gmp_pro`。

结论：MotorAI 的旧工程模板、构建脚本和库版本耦合。更换 GMP 根目录并不能完成迁移。已复现的障碍包括旧生成器入口校验、生成器工作目录错误、固定源文件清单、运行时模块漏选、核心头文件搬迁、数值转换宏变化、项目板卡文件遗漏及已删除的 rt_trace。ADC/PWM 通道和 FOC 绑定的主要接口仍兼容，不需要重写这些控制模块。

本次是诊断与迁移方案验证，没有修改三个项目的运行源码、设置或既有候选结果。试改、生成和编译均在独立诊断目录中进行。未完成整个 EXE 的链接、Simulink 联合仿真及硬件验证。

## 1. MotorAI 的实际工作原理

当前代码生成主流程是“LLM 选择结构 + 确定性模板组装 + 仿真参数优化”。

```text
自然语言需求、硬件参数、指标与候选方案
  -> controller_loop_id_exporter：生成 selected_loops
  -> merge_loop_ids_into_ctl_main：选择 PID/SMC/LADRC 分支并替换模板标记
  -> ctl_main.c / ctl_main.h / paras.generated.h
  -> 复制静态 user_main 和 simulate 工程
  -> GMP source manager 复制当前平台库源码
  -> MSBuild 编译控制器 EXE
  -> MATLAB/Simulink 通过 UDP 运行 SIL
  -> Python 采集信号、计算指标并评分
  -> Optimize 修改允许调节的参数、重建和重跑
  -> Competition 排名、反馈并进入下一轮
```

`Generate/run_llm_to_program.py` 与 UI 的 `GenerateProgramWorker` 都调用模板合并器。控制代码主要来自 `Generate/Example/ctl_main.c`、`ctl_main.h`、`paras.h`；`user_main.c/.h` 是静态复制。候选仿真工程来自 `template_project_path` 的 `project/simulate`。这两套模板要同时迁移：只更新嵌套的 `Example/mcs_pmsm_nt/src`，不会修复根级代码模板的生成结果。

`Competition/competition_workspace.py:init_candidates` 直接复制整个 src 和 simulate 目录，随后调用 `configure_candidate_optimize`。后者校验 GMP 根目录、从 `Optimize/agent_optimize/Example` 复制构建 BAT，并改写工程属性表引用。因此应修改这些源模板，而不是只修某个 Output/candidate。

控制运行时仍遵循 GMP 的初始化及控制节拍：`setup_peripheral -> ctl_init -> init`，周期控制经 `ctl_input_callback -> ctl_dispatch -> ctl_output_callback` 执行。xplt 把 UDP 原始 ADC、编码器输入转成控制器接口，并把 PWM/监视量送回模型。

## 2. 已确认的阻塞点

### 2.1 根目录校验依赖已删除的旧 BAT

位置：`Optimize/config_project.py:28/44`，`Optimize/agent_optimize/Example/build_sln.bat:49/73`，`Example/start_exe.bat:80`。当前使用 `tools/facilities_generator/gmp_fac_generate_srcs_example.bat` 作为平台识别标记或 PATH 检查目标。

实测同一个 `resolve_gmp_root`：旧平台成功，新平台直接抛出 `FileNotFoundError`。这是初始化 candidate 时就会出现的故障，早于 C 编译。

建议用平台实际依赖的文件校验：`gmp_core.h`、`tools/facilities_generator/src_mgr/gmp_framework_dic.json`、`framework_sync_src_v3.py`；模拟构建另校验两份 `.props`。不要把旧示例 BAT 当成 GMP 的身份标记。删除旧 BAT 的 `where` 检查，用项目 source-manager 调用取代旧入口。

必须先修改 `Optimize/agent_optimize/Example/build_sln.bat`，因为 Competition 每次会从这里复制。只改同目录外的 `agent_optimize/build_sln.bat` 会被下一次配置覆盖。

### 2.2 旧项目 source-manager BAT 没有切换工作目录

MotorAI 模板的 `gmp_src_mgr/gmp_generate_src.bat` 直接启动 Python，没有 `cd /d "%~dp0"`。新版属性表从工程目录调用这个项目 BAT；生成器则用 `os.getcwd()` 查找 `gmp_framework_config.json`。结果会在 simulate 根目录寻找本应在 gmp_src_mgr 中的配置。

实测从错误目录启动新版生成器：退出码为 0，输出 `Global dictionary or local configuration not found. Skipping synchronization.`，没有生成 `gmp_src`。因此它可能继续编译复制来的旧源码，同时使用新版 GMP 头文件，形成版本混用。

最小修复：刷新项目 BAT，使用新版 `tools/facilities_generator/src_mgr/gmp_src_mgr` 的三份 canonical BAT，保留项目自己的 JSON。新版 BAT 已包含工作目录切换、环境激活及错误传播。MotorAI 还应检查预期源文件，不能只看退出码。

### 2.3 VS 工程固定列出了旧源码，且漏选新运行时

MotorAI 的 `Generate/Example/mcs_pmsm_nt/project/simulate/DigialPower_simulink.vcxproj` 固定列出各个库 `.c/.cpp`。

用模板的同一份 JSON 真实生成源文件：旧平台生成 89 个文件，新平台生成 95 个文件。新生成结果中，这五个旧工程条目已经不存在：

```text
gmp_dev_util.c
gmp_process_mgr.c
gmp_std_error_code.c
gmp_std_port.c
windows_rt_tracer.cpp
```

新版还生成 `error_code.c`、`function_scheduler.c`、`gmp_datalink.c`、`gmp_dl_facility.c`、`ring_buffer.c` 等旧固定清单没有列出的文件。真实 source sync 会删除不再需要的旧文件；因此成功生成后，旧工程仍可能报“源文件不存在”，或者漏编译新实现并产生链接错误。

模板的 117 个 selected_modules 在新版注册表中均有效；不能把问题归结为 JSON 全部不兼容。但它们的 127 个依赖闭包中没有 `core|rt`。旧 `core|std` 曾带入 `gmp_std_port.c`，新版标准类型与运行时已拆分。需要显式增加：

```json
{"root": "core", "module": "base|port"}
{"root": "core", "module": "rt"}
```

这两项应追加到 selected_modules 数组，而不是创建另一份完整 JSON。实测追加后正常生成 `gmp_runtime.c`，总计 96 个源文件。

建议沿用新版 GMP 套件的源文件通配方式，替换旧的逐文件库清单：

```xml
<ClCompile Include="gmp_src_mgr\gmp_src\*.c" />
<ClCompile Include="gmp_src_mgr\gmp_src\*.cpp" />
```

保留项目自己的 ctl_main、user_main、仿真入口和 xplt 编译条目。注意 MSBuild 在加载工程时展开通配符，因此应在调用 MSBuild 前先完成 source sync；只依赖 PreBuildEvent 不能保证一个空候选工程首次构建就包含刚生成的文件。

### 2.4 核心头文件搬迁

以下路径在旧平台存在，在新平台不存在，应修改 MotorAI 根级 Example 模板及仍使用的目标工程模板：

| 旧路径 | 新路径 |
| --- | --- |
| `core/dev/pil_core.h` | `core/dev/datalink/pil_core.h` |
| `core/dev/mem_presp.h` | `core/dev/datalink/mem_presp.h` |
| `core/dev/tunable.h` | `core/dev/datalink/tunable.h` |
| `core/pm/function_scheduler.h` | `core/pm/function_scheduler/function_scheduler.h` |

涉及 `Generate/Example/ctl_main.c/.h`、`user_main.c/.h`。已在隔离副本中复现 `ctl_main.h` 的 C1083；改正这些路径后，既有候选的 ctl_main 和 user_main 通过 C 语法检查。

另外，PIL 条件宏应把 `ENBALE_GMP_DL_PIL_SIM` 改为 `ENABLE_GMP_DL_PIL_SIM`。当前 SIL 不开启该分支时它不是立即阻塞点，但不修正会使新版正确宏无法开启 MotorAI 的 PIL 回调。

### 2.5 数值转换宏有真正的 API 变化

新版 `ctl/math_block/ctrl_gt/float_macros.h` 删除 `float2ctrl` 和 `ctrl2float`；转换入口集中到 `ctl/math_block/gmp_math.h`。现在使用 `real2ctrl`、`param2ctrl`、`ctrl2param` 等。

MotorAI 的 `Generate/Example/ctl_main.c`、`ctl_main.h`，以及 `Generate/merge_loop_ids_into_ctl_main.py:265/270/323` 写死了 `float2ctrl`。仅改生成后的 C 文件不够，合并器下次还会重新输出旧名字。

最低限度，把常量/实数表达式的调用改成：

```c
real2ctrl(0.02f)
real2ctrl(0.0f)
```

对 parameter_gt 参数使用 `param2ctrl`；需要向模型或调参域输出时使用 `ctrl2param`，并按接收端类型明确转换。不要为了绕过错误把 ctrl_gt 手工 typedef 成 float，这会破坏其他数值后端。

实测仅修正头文件路径后，SMC 的三个全局初值出现 C2099“初始值不是常量”；PID/LADRC 则出现 C4013，把 `float2ctrl` 当成返回 int 的外部函数。后一种情况即使语法检查退出码为 0，也不能认为可以正确链接或运行。

对隔离生成代码进一步换成 `real2ctrl` 后，PID、SMC、LADRC 速度环和 LADRC 位置环四个分支均通过 `/Zs /W3 /we4013` 检查。

### 2.6 MONKEY_BOARD 是旧工作区的私有文件，未随项目交付

MotorAI 模拟模板的 `xplt/ctrl_settings.h:43` 引用 `<MONKEY_BOARD.h>`。该文件在旧 GMP 根目录存在，在新 GMP 根目录不存在，且不在所检查的 MotorAI 模板 xplt 中。

实测编译新版 `ctl_component_interface.c` 时，经过 `gmp_math -> gmp_type -> xplt.config -> ctrl_settings` 后报 `MONKEY_BOARD.h` 不存在。这解释了为什么错误看起来发生在 interface 组件，但真正缺失的是工程硬件配置。

应把板卡参数作为项目输入交付，例如 `xplt/Driver_Board.h`，并在 ctrl_settings 中引用它。可由 HardwareConfig 导出或复制已确认的板卡定义；保持原来的 ADC 增益、偏置、电压/电流基值和 PWM 参数，不能换成另一块默认板卡的数据。

诊断中只把旧 MONKEY_BOARD 定义放到隔离项目的 xplt，保留其旧 preset include，就使新版 interface 组件通过编译。

### 2.7 已移除的 rt_trace 仍在模板中

`Generate/Example/mcs_pmsm_nt/project/simulate/xplt/xplt.peripheral.cpp:18` 引用 `ctrl_rt_trace.h`，还声明 `trace_rt_node_t` 并调用 `trace_rt_register_node`。新平台没有这个头和 `windows_rt_tracer.cpp`。新版 GMP 的维护规则明确要求模拟项目不再恢复该模块。

本模板的活动 trace 代码只注册一个节点，日志调用已经注释。最小修改是删除这组 include、节点 enum/数组和注册语句，同时去掉 VS 中的旧 tracer 源文件条目。现有 monitor/Scope 继续负责 MotorAI 的评估信号。

实测 C++ 平台副本在保留 trace 时因头文件缺失失败，删除这些 trace 代码后通过 `/Zs /std:c++17`。这项验证使用本机已有 vcpkg 头文件，没有安装或下载依赖。

## 3. interface 与硬件 preset 的区别

比较 `adc_channel.h`、`adc_ptr_channel.h`、`pwm_channel.h`、`spwm_modulator.h`、`interface_base.h` 及 FOC/encoder 后确认：

- `ptr_adc_channel_t`、`tri_ptr_adc_channel_t` 的 control_port 仍存在。
- `ctl_init_ptr_adc_channel`、`ctl_init_tri_ptr_adc_channel`、相应 step 函数及 `ctl_attach_foc_core_port` 的主要签名仍兼容。
- 新版组件更多地直接包含 gmp_math/gmp_type，减少对完整 gmp_core 运行时的依赖；断言从 gmp_base_assert 转向 gmp_ctl_assert。
- 不应替换整套 interface 为旧版，也不应把旧 gmp_core 头或旧核心实现混进新平台。

新版同时存在旧 `ctl/component/hardware_preset` 目录和新 SDPE 输出 `ctl/hardware_preset`。当前测试选用的旧 SM060R20B30MNAD 预设和 inverter_3ph_general 头仍在，因此“全部旧硬件头路径已删除”不符合该 checkout 的实际情况。

若进一步迁到新 SDPE preset，则需另外适配 HardwareConfig：新电机宏是 `SM060R20B30MNAD_RS/LD/LQ/...`，现有 parser 只识别 `MOTOR_PARAM_*`，路径扫描也固定到旧目录。不能只替换扫描路径。对接新 preset 时应映射字段或直接读取 SDPE 元数据，并保留 Ld/Lq 与原参数单位。此项可以在基本构建恢复后再做，不是当前最小修复的前置条件。

## 4. 建议的最小实施顺序

1. 修正 `Optimize/config_project.py` 的 GMP 根校验及构建/启动 BAT 源模板。把配置中的 GMP 根作为当前构建的统一来源，传给 source sync、MSBuild 和子进程。
2. 刷新仿真模板的三个 gmp_src_mgr BAT，保留项目配置并追加 core runtime/base 模块。构建脚本在进入 MSBuild 前完成生成，并验证 gmp_runtime.c、ctl_component_interface.c 等预期产物。
3. 更新仿真 vcxproj 的生成库源码清单、两份属性表导入以及 src/xplt include 路径。现有 `modify_simulink_vcxproj` 已能改写属性表导入，可继续复用。
4. 更新根级 `Generate/Example/ctl_main.c/.h`、`user_main.c/.h` 的核心头路径、转换调用和 PIL 拼写；同步修改合并器生成的 C 字符串。
5. 把真实板卡参数放入项目 xplt，移除仿真模板的 rt_trace 代码。
6. 用新模板生成新的验证候选，保存原有 Output 调参结果。核对 project/candidate 中 gmp_path 与全局设置 paths.gmp_root，防止既有 JSON 继续指向旧平台。
7. 先完成 Clean/Rebuild 和完整链接，再运行一条 SIL 工况，检查启动、ADC 标定、PWM、反馈和评分信号；之后验证四个控制分支及多候选运行。

GMP 根路径应继续来自用户设置，本文使用的 D:/Code 路径只是本次诊断位置，不应硬编码进产品源码。

当前模型使用 `dp_sil_rx_buf_t/dp_sil_tx_buf_t`，而非另一个 `mtr_sil_*` 缓冲区。修复时继续保持现有 packed 数据类型、ADC 顺序、编码器通道和 Scope 映射。追加运行验证发现新版 CSP 已改为统一 TCP/UDP 会话协议，旧四端口通信必须迁移为数据两端口与握手/状态帧，详见追加报告第 3 节；不能只保持旧数据协议，也不能用其他 suite 的监视映射覆盖 MotorAI 模型。

## 5. 验证证据与限制

使用本机 MSVC v143（14.44.35207）、Windows SDK 10.0.26100.0。以下均是隔离副本或直接只读编译：

| 检查 | 结果 |
| --- | --- |
| MotorAI resolve_gmp_root：old/new | old 成功，new 复现 FileNotFoundError |
| 同一 ADC/FOC API 探针：old/new | 两者均通过 C 语法检查 |
| 新版 interface 组件、最小有效配置 | 通过 |
| 新版 interface + 原 MotorAI xplt | 缺 MONKEY_BOARD.h |
| 给项目提供真实板卡定义 | interface 通过 |
| 原 generated ctl_main 使用新库 | 缺 core/dev/pil_core.h |
| 更新核心头路径 | 既有候选 ctl_main/user_main 语法通过，但另查转换宏警告 |
| 四分支模板仅迁移头路径 | SMC C2099；其余存在 float2ctrl C4013 |
| 四分支再迁移数值转换 | 全部通过 /Zs /W3 /we4013 |
| 原 xplt C++ trace / 删除 trace | 前者 C1083，后者语法通过 |
| 旧/新平台实际 source generation | 89/95 个源文件；新平台补运行时后 96 个 |
| 错误工作目录下 source generation | 返回 0，无输出源树，只有 skip 警告 |

诊断目录：[gmp_compat](C:/Users/wimme/.codex/visualizations/2026/10/09/01a1203a-b471-7683-9a1e-8c4009b8a6e3/gmp_compat)。主要记录：`summary.json`、`generation_summary.json`、`mode_summary.json`、`migrated_mode_summary.json`、`cpp_summary.json` 及对应 `.log`。`reproduce.py` 保留基础 API 与路径场景的复现；四分支额外检查的产物保存在 modes 目录。

语法通过不能代替 EXE 链接、SIL 闭环或硬件验证。现有 Output/test1/test2 的日志还包含 C1041 并行 PDB 写入错误；这是另一类构建问题，不应拿它替代本次已复现的新平台兼容性问题。未取得用户原始新平台报错栈，本报告列出的是当前代码可直接复现的失败及静态确定的后续阻塞。
