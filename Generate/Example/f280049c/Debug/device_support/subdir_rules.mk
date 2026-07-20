################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
device_support/%.obj: ../device_support/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: C2000 Compiler'
	"C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/bin/cl2000" -v28 -ml -mt --cla_support=cla2 --float_support=fpu32 --tmu_support=tmu0 --vcu_support=vcu0 -O2 --fp_mode=relaxed --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro" --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro/csp/c28x_syscfg/" --include_path="C:/Users/28933/Documents/github/gmp_pro" --include_path="C:/Users/28933/Documents/github/gmp_pro/csp/c28x_syscfg/" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/src" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/xplt" --include_path="C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/headers/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/common/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/driverlib/f28004x/driverlib" --advice:performance=all --define=_FLASH -g --diag_warning=225 --diag_wrap=off --display_error_number --abi=eabi --preproc_with_compile --preproc_dependency="device_support/$(basename $(<F)).d_raw" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/Debug/syscfg" --obj_directory="device_support" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

device_support/%.obj: ../device_support/%.asm $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: C2000 Compiler'
	"C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/bin/cl2000" -v28 -ml -mt --cla_support=cla2 --float_support=fpu32 --tmu_support=tmu0 --vcu_support=vcu0 -O2 --fp_mode=relaxed --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro" --include_path="E:/Related_Github_Project/GMP_Else/gmp_pro/csp/c28x_syscfg/" --include_path="C:/Users/28933/Documents/github/gmp_pro" --include_path="C:/Users/28933/Documents/github/gmp_pro/csp/c28x_syscfg/" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/src" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/xplt" --include_path="C:/ti/ccs1281/ccs/tools/compiler/ti-cgt-c2000_22.6.1.LTS/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/headers/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/device_support/f28004x/common/include" --include_path="C:/ti/c2000/C2000Ware_5_04_00_00/driverlib/f28004x/driverlib" --advice:performance=all --define=_FLASH -g --diag_warning=225 --diag_wrap=off --display_error_number --abi=eabi --preproc_with_compile --preproc_dependency="device_support/$(basename $(<F)).d_raw" --include_path="E:/Related_Github_Project/gmp_pro/ctl/suite/mcs_pmsm_nt2/project/f280049c/Debug/syscfg" --obj_directory="device_support" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


