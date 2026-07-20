################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
build-686021071: ../280049C_LaunchPad.syscfg
	@echo 'Building file: "$<"'
	@echo 'Invoking: SysConfig'
	"C:/ti/ccs1281/ccs/utils/sysconfig_1.21.0/sysconfig_cli.bat" --script "E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/280049C_LaunchPad.syscfg" -o "syscfg" -s "E:/Related_Github_Project/GMP_Else/gmp_pro/.metadata/product.json" -s "C:/ti/c2000/C2000Ware_5_04_00_00/.metadata/sdk.json" -d "TMS320F280049C" -p "100PZ" --compiler ccs
	@echo 'Finished building: "$<"'
	@echo ' '

syscfg/board.c: build-686021071 ../280049C_LaunchPad.syscfg
syscfg/board.h: build-686021071
syscfg/board.cmd.genlibs: build-686021071
syscfg/board.opt: build-686021071
syscfg/board.json: build-686021071
syscfg/pinmux.csv: build-686021071
syscfg/epwm.dot: build-686021071
syscfg/device.c: build-686021071
syscfg/device.h: build-686021071
syscfg/adc.dot: build-686021071
syscfg/c2000ware_libraries.cmd.genlibs: build-686021071
syscfg/c2000ware_libraries.opt: build-686021071
syscfg/c2000ware_libraries.c: build-686021071
syscfg/c2000ware_libraries.h: build-686021071
syscfg/clocktree.h: build-686021071
syscfg: build-686021071

syscfg/%.obj: ./syscfg/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: C2000 Compiler'
	"C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/bin/cl2000" -v28 -ml -mt --cla_support=cla2 --float_support=fpu32 --tmu_support=tmu0 --vcu_support=vcu0 -O2 --fp_mode=relaxed --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro" --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro/csp/c28x_syscfg/" --include_path="C:/Users/28933/Documents/github/gmp_pro" --include_path="C:/Users/28933/Documents/github/gmp_pro/csp/c28x_syscfg/" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/src" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/xplt" --include_path="C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/headers/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/common/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/driverlib/f28004x/driverlib" --advice:performance=all --define=_FLASH -g --diag_warning=225 --diag_wrap=off --display_error_number --abi=eabi --preproc_with_compile --preproc_dependency="syscfg/$(basename $(<F)).d_raw" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/Debug/syscfg" --obj_directory="syscfg" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

f28004x_codestartbranch.obj: C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/common/source/f28004x_codestartbranch.asm $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: C2000 Compiler'
	"C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/bin/cl2000" -v28 -ml -mt --cla_support=cla2 --float_support=fpu32 --tmu_support=tmu0 --vcu_support=vcu0 -O2 --fp_mode=relaxed --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro" --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro/csp/c28x_syscfg/" --include_path="C:/Users/28933/Documents/github/gmp_pro" --include_path="C:/Users/28933/Documents/github/gmp_pro/csp/c28x_syscfg/" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/src" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/xplt" --include_path="C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/headers/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/common/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/driverlib/f28004x/driverlib" --advice:performance=all --define=_FLASH -g --diag_warning=225 --diag_wrap=off --display_error_number --abi=eabi --preproc_with_compile --preproc_dependency="$(basename $(<F)).d_raw" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/Debug/syscfg" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


