# MotorAI F280049C project

[中文说明](README_CN.md)

This is the existing hardware template for `Generate/Example/mcs_pmsm_nt`.
Each candidate contains `src`, `project/simulate` and `project/f280049c`.
Both targets use the candidate's shared `src`, including `paras.generated.h`.
CCS links application files through `PARENT-2-PROJECT_LOC/src` and searches
`../../src` for headers. Parameter updates are used directly on the next hardware
build, without copying parameter files or maintaining another application snapshot.
Candidates have independent control sources and parameters. Older candidates gain
the hardware target when continued. Board bindings, custom motor/board headers,
generated SysConfig C/H files, startup assembly and Flash linker scripts are local.

GMP and C2000Ware stay external. In the candidate's CCS project, configure
GMP-Core-C28x and C2000WARE 5.4.0.00 in Project Properties > General > Products.
The generator uses the GMP product version registered by the selected checkout
when its CCS metadata is present. Set Resource > Linked Resources > Path Variables > GMP_ROOT to the same
GMP checkout. GMP C sources are linked resources; merely adding header paths does
not supply their implementations. The build uses TI C2000 CGT 22.6.2.LTS, EABI and
Flash in both configurations. New candidates retain SysConfig support in both
configurations, with an explicit input script and the C2000Ware SDK manifest.
CCS generates and compiles `Debug/syscfg` or `Release/syscfg` at build time.
The copied root `syscfg` files are excluded from these builds to avoid duplicates.

Import `project/f280049c` into CCS and build the Debug or Release configuration.
Use `target_config/TMS320F280049C_LaunchPad.ccxml` for XDS110 programming of the
resulting `.out` file.
Actual programming requires connected hardware. Keep CCS linked sources in sync
when adding GMP modules; existing hardware projects preserve manual changes.
Open the root `280049C_LaunchPad.syscfg` to edit peripheral setup, then rebuild.
Older candidates regain missing SysConfig editor settings when continued, while
keeping their existing build exclusions and board sources. If their script has
been edited separately, reconcile its peripheral names and bindings before
enabling generation and excluding the copied root `syscfg` sources.
The local custom motor/board parameters and BUILD_LEVEL=5 come from the existing
MotorAI hardware target and need validation on the intended motor and board.
Simulation tuning does not update hardware ADC/PWM mappings, sampling frequency,
motor or board constants, and does not build or flash hardware automatically.
Copy the whole candidate folder to keep its shared `src` available.
