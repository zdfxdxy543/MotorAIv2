# MotorAI

MotorAI 是面向 GMP 电机控制工程的 AI 辅助设计与自动调优工具。它可以把自然语言控制需求转换为控制环结构和可编译的 C 代码，并通过多候选方案、SIL 仿真、指标评分和跨轮策略迭代持续优化控制器参数与结构。

> 当前版本主要面向 Windows、GMP 工程和 MATLAB/Simulink 联合仿真环境。仅体验控制器生成或硬件配置功能时，不需要启动 MATLAB。

## 核心能力

- **自然语言生成控制器**：从中文或英文需求中选择控制环，生成稳定的 loop ID，并基于 GMP 模板输出 `ctl_main.c`、`ctl_main.h` 和 `paras.generated.h`。
- **多候选方案竞争**：为每个候选方案创建独立的源码、工程、日志和仿真目录，支持 PID、LADRC、SMC 等控制方法的差异化探索。
- **自动参数调优**：自动修改可调参数、编译工程、运行 SIL 仿真、计算性能指标，并记录每次参数变化与评价结果。
- **跨轮结构迭代**：汇总上一轮候选方案的评分和失败指标，由 LLM 生成下一轮的 exploit/explore 策略以及参数继承方案。
- **本地与远程 SIL**：既可连接本机共享 MATLAB Engine，也可通过轻量 HTTP Worker 在远程仿真机上运行 Simulink。
- **硬件配置工具**：浏览和编辑电机、驱动板预设，生成 GMP 使用的 `Motor_Model.h` 和 `Driver_Board.h`。

## 工作流程

```text
自然语言需求
    |
    v
控制环选择与 GMP C 代码生成
    |
    v
创建多个隔离候选工作区
    |
    v
编译 -> SIL 仿真 -> 指标计算 -> 参数调优
    |
    v
候选评分与本轮优胜方案
    |
    v
下一轮策略生成与参数继承（直到 max_rounds）
```

候选方案的最终得分来自确定性的指标评分逻辑，不由 LLM 直接打分。当前优胜方案按最高 `overall_score` 选出。

## 环境要求

### 基础环境

- Windows 10/11
- Python 3.10 或更高版本
- 可用的 GMP 工程目录
- OpenAI Chat Completions 兼容的大模型 API

### 完整优化流程

- MATLAB 与 Simulink
- 与 MATLAB 版本匹配的 MATLAB Engine for Python
- 可编译目标 GMP 工程的 Visual Studio/C/C++ 工具链
- 本地控制内核或已配置的远程 SIL 仿真机

## 快速开始

### 1. 创建 Python 环境

在仓库根目录执行：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install PyQt5 matplotlib openai
```

`PyQt5` 和 `matplotlib` 用于桌面端，`openai` 用于参数优化和跨轮策略生成。控制环生成模块本身通过标准库调用兼容接口。

如需运行 SIL，请从对应 MATLAB 安装目录安装 Engine。不同 MATLAB 版本支持的 Python 版本可能不同，请以 MathWorks 的版本兼容表为准：

```powershell
Set-Location "<MATLAB_ROOT>\extern\engines\python"
python -m pip install .
```

### 2. 配置 MotorAI

复制配置模板：

```powershell
Copy-Item motorai_settings.example.json motorai_settings.json
```

编辑 `motorai_settings.json`，至少填写以下字段：

```json
{
  "llm": {
    "api_key": "your-api-key",
    "model": "your-model-name",
    "base_url": "https://your-provider.example/v1",
    "temperature": 0.0,
    "timeout": 180
  },
  "paths": {
    "gmp_root": "E:/path/to/gmp_pro",
    "generate_root": "Generate",
    "optimize_root": "Optimize",
    "output_root": "E:/path/to/motorai-projects"
  }
}
```

- `base_url` 应指向兼容 OpenAI Chat Completions 的 API 根地址。
- `gmp_root` 是本机 GMP 仓库根目录。
- `output_root` 是新建 MotorAI 工程的默认保存位置。
- `motorai_settings.json` 已被 Git 忽略，请勿提交 API Key。
- 可通过环境变量 `MOTORAI_SETTINGS_PATH` 指向另一份配置文件。
- API Key 也可使用 `AI_API_KEY`、`DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` 环境变量提供。

也可以启动桌面端后，通过“文件 -> 设置”配置 GMP 路径、大模型和界面主题。

### 3. 启动桌面端

回到仓库根目录执行：

```powershell
python Generate\ui\main.py
```

推荐操作顺序：

1. 在“文件 -> 设置”中确认 GMP 根目录和模型配置。
2. 选择“文件 -> 新建”，设置工程名、单轮调优次数、候选数量和最大迭代轮数。
3. 输入控制需求和性能指标，生成候选控制器代码。
4. 根据本机或远程仿真环境配置网络与 SIL 参数。
5. 启动调优，在结果区查看控制结构、仿真曲线、指标得分和迭代摘要。

新建工程时会自动从 `Generate/Example/mcs_pmsm_nt` 复制模板，并为各候选方案创建隔离工作区。

## 命令行用法

### 生成控制器代码

直接把自然语言需求转换为 GMP 控制器源码：

```powershell
python Generate\run_llm_to_program.py "设计一个低超调、响应快速的 PMSM 速度控制器"
```

默认输出位于 `Generate/`：

- `controller_loop_ids_generated.json`
- `ctl_main.generated.c`
- `ctl_main.generated.h`
- `paras.generated.h`

写入指定候选工作区：

```powershell
python Generate\run_llm_to_program.py `
  "采用 LADRC 的 PMSM 速度控制器" `
  --candidate-dir "E:\MotorAIProjects\demo\candidates\candidate_01"
```

只生成控制环选择 JSON：

```powershell
python Generate\controller_loop_id_exporter.py `
  "需要设计高性能位置控制器" `
  --output Generate\controller_loop_ids_generated.json
```

### 运行多候选竞赛

桌面端创建工程后，也可以使用命令行执行完整流程：

```powershell
python Competition\competition_runner.py `
  "E:\MotorAIProjects\demo\demo.json" `
  --candidates 4 `
  --parallel 2 `
  --optimize-parallel 1
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--candidates N` | 候选工作区数量，默认 4 |
| `--parallel N` | Generate 阶段并行数，默认 2 |
| `--optimize-parallel N` | 优化/仿真并行数，默认 1；多实例 MATLAB 环境再考虑提高 |
| `--dry-run` | 生成执行计划但不实际编译、仿真或调优 |
| `--skip-generate` | 复用已有生成结果 |
| `--skip-optimize` | 跳过优化阶段，仅处理已有结果 |
| `--force-init` | 重新初始化候选工作区，会覆盖候选目录中的现有内容 |

首次接入新工程时，建议先运行 `--dry-run` 检查解析出的路径和任务配置。

### 启动硬件配置工具

```powershell
python HardwareConfig\main.py
```

首次使用前请检查 `HardwareConfig/config.json` 中的 GMP 路径和头文件输出位置。

### 启动远程 SIL Worker

在远程仿真机上：

1. 安装 MATLAB Engine for Python。
2. 启动 MATLAB，并在命令窗口执行 `matlab.engine.shareEngine`。
3. 根据需要修改 `silworker/silworker_config.json`。
4. 启动 Worker：

```powershell
silworker\start_worker.bat
```

默认监听 `http://0.0.0.0:8787`，健康检查为 `GET /health`。生产网络中应使用防火墙限制访问，并通过 `allow_model_roots` 限定允许加载的模型目录。完整请求格式见 [silworker/README.md](silworker/README.md)。

## 工程输出结构

桌面端创建的工程大致如下：

```text
demo/
|-- demo.json                         # 工程需求、指标、停止条件
|-- common/
|   |-- user_requirement.json         # 所有候选共享的需求快照
|   `-- candidate_profiles.json       # 本轮候选策略
|-- candidates/
|   |-- candidate_01/
|   |   |-- candidate.json
|   |   |-- src/                      # 生成和调优后的控制源码
|   |   |-- project/                  # 候选独立 GMP/仿真工程
|   |   `-- log/
|   |       |-- generate/
|   |       `-- optimize/             # 仿真、评价、调优历史
|   `-- candidate_XX/
|-- rounds/
|   |-- round_XX/                     # 每轮备份、反馈与下一轮策略
|   `-- iteration_summary.json        # 跨轮摘要，供 UI 展示
`-- competition_run_result.json       # 最终候选得分和优胜方案
```

关键调优产物通常位于候选目录的 `log/optimize/`：

- `tuning_result.json`：本候选最终调优结果和总分。
- `evaluation_result.json`：最近一次指标计算结果。
- `optimization_history.jsonl`：逐次参数修改与评价历史。
- `simulation/processed.json`：语义化后的仿真信号。
- `candidate_evidence.json`：候选结构、参数变化和收敛证据。

## 目录说明

| 目录/文件 | 用途 |
| --- | --- |
| `Generate/` | 控制环选择、GMP C 代码生成、模板工程及桌面端 |
| `Optimize/` | 参数编辑、编译/仿真自动化、性能评价和调优 Agent |
| `Competition/` | 候选工作区、评分选优、轮次反馈和下一轮策略 |
| `HardwareConfig/` | 电机与驱动板配置、头文件生成工具 |
| `silworker/` | 无状态远程 Simulink HTTP Worker |
| `motorai_config.py` | 全局配置加载、默认值合并和路径解析 |
| `motorai_settings.example.json` | 可提交的配置模板 |
| `docs/known_issues_evaluation.md` | 评价模块已知问题与边界情况 |

更深入的模块说明：

- [Generate/README.md](Generate/README.md)
- [Generate/ui/README.md](Generate/ui/README.md)
- [Optimize/agent_optimize/README_modular_agent.md](Optimize/agent_optimize/README_modular_agent.md)
- [Optimize/agent_silhelper/README.md](Optimize/agent_silhelper/README.md)
- [silworker/README.md](silworker/README.md)

## 测试

无需 MATLAB 的竞赛工作区单元测试：

```powershell
python -m unittest discover -s Competition -p "test_*.py"
```

迭代摘要快速校验：

```powershell
python Competition\test_iteration_summary.py
```

完整端到端验证还依赖真实 GMP 工程、编译工具链和 MATLAB/Simulink 环境。

## 常见问题

### 找不到 API Key

确认 `motorai_settings.json` 的 `llm.api_key` 已配置，或在当前终端设置：

```powershell
$env:AI_API_KEY = "your-api-key"
```

### 提示没有共享的 MATLAB Session

先启动 MATLAB，并在 MATLAB 命令窗口执行：

```matlab
matlab.engine.shareEngine
```

然后使用同一 Windows 用户重新运行 MotorAI 或 SIL Worker。

### 编译或仿真路径不正确

依次检查：

1. `motorai_settings.json` 中的 `paths.gmp_root`。
2. 工程 JSON 中的 `gmp_path`、`sln_path` 和 `simulink_model_path`。
3. 候选目录下生成的 `agent_project.json` 和构建脚本。
4. 路径对应的工程、模型和编译工具是否在当前机器可用。

### 是否可以并行运行多个候选仿真

可以通过 `--optimize-parallel` 调整，但每个并行任务都必须拥有互不冲突的工程、端口和 MATLAB/仿真资源。默认值 1 更适合单 MATLAB Session 环境。

## License

本项目采用 [Apache License 2.0](LICENSE) 许可证。
