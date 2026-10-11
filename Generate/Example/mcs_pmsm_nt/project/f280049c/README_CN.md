# MotorAI F280049C 工程

[English](README.md)

唯一模板是现有的 `Generate/Example/mcs_pmsm_nt/project/f280049c`。
新建 MotorAI 工程时，每个候选包含以下结构：

```text
candidate_01/
  src/                   控制源码和 paras.generated.h
  project/
    simulate/            仿真工程
    f280049c/            CCS 硬件工程
```

两个工程共用该候选的 `src`。CCS 通过 `PARENT-2-PROJECT_LOC/src` 链接控制
源码，并从 `../../src` 查找头文件。调优更新 `src/paras.generated.h` 后，
硬件工程下次编译直接使用最新参数，无需复制参数或另外维护硬件源码副本。
每个候选独立使用自己的源码和参数。已有候选在继续运行时会补齐硬件工程。
自定义电机/板卡头文件、SysConfig 生成的 C/H、启动汇编和 Flash 链接文件均
保存在候选的硬件工程中；不复制 GMP、C2000Ware 库目录。

CCS 导入候选的 `project/f280049c` 后，在 Project Properties > General > Products
配置 GMP-Core-C28x、C2000WARE 5.4.0.00；生成器读取所选 GMP 目录中已注册的
CCS 产品版本（存在注册元数据时）。在 Resource > Linked Resources
> Path Variables 中将 GMP_ROOT 指向同一个 GMP 根目录。
GMP 的 C 文件通过链接资源参与编译，只有头文件路径不足以完成链接。
Debug、Release 均为 Flash/EABI，使用 TI C2000 CGT 22.6.2.LTS。
新候选的 Debug、Release 均保留 SysConfig 工具，并明确指定根目录的脚本和
C2000Ware SDK manifest。CCS 编译时自动生成并编译 `Debug/syscfg` 或
`Release/syscfg`；随工程复制的根目录 `syscfg` 源码被排除，避免重复编译。

在 CCS 中构建 Debug 或 Release 配置，使用生成的 `.out` 文件烧写。
LaunchPad 使用 `target_config/TMS320F280049C_LaunchPad.ccxml` 配置 XDS110。
实际烧写需要连接硬件。模块配置在 `gmp_src_mgr/gmp_framework_config.json`；
新增 GMP 模块时同步 CCS 的链接源文件列表。已有硬件工程不会覆盖，以保护手动修改。
打开根目录的 `280049C_LaunchPad.syscfg` 修改外设后，重新编译即可。
已有候选在继续运行时补齐丢失的 SysConfig 编辑器配置，保留原来的构建排除
设置和板卡源码。如果脚本曾被单独修改，应先核对外设名称及板卡绑定，再启用
脚本生成并排除根目录 `syscfg` 的旧源码。
原工程的自定义电机、板卡参数和 BUILD_LEVEL=5 保留，仍需在实际硬件上验证。
仿真调优不会自动修改硬件的 ADC/PWM 映射、采样频率、电机/板卡参数，
也不会自动编译或烧写硬件。复制候选时应保留整个 candidate 目录，以保留共享 src。
