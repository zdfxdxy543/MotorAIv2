/*
 * Copyright (c) 2020 Texas Instruments Incorporated - http://www.ti.com
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 */

#ifndef BOARD_H
#define BOARD_H

//*****************************************************************************
//
// If building with a C++ compiler, make all of the definitions in this header
// have a C binding.
//
//*****************************************************************************
#ifdef __cplusplus
extern "C"
{
#endif

//
// Included Files
//

#include "driverlib.h"
#include "device.h"

//*****************************************************************************
//
// PinMux Configurations
//
//*****************************************************************************

//
// CANA -> IRIS_CAN Pinmux
//
//
// CANA_RX - GPIO Settings
//
#define GPIO_PIN_CANA_RX 33
#define IRIS_CAN_CANRX_GPIO 33
#define IRIS_CAN_CANRX_PIN_CONFIG GPIO_33_CANA_RX
//
// CANA_TX - GPIO Settings
//
#define GPIO_PIN_CANA_TX 32
#define IRIS_CAN_CANTX_GPIO 32
#define IRIS_CAN_CANTX_PIN_CONFIG GPIO_32_CANA_TX

//
// EPWM1 -> EPWM_J8_PHASE_U Pinmux
//
//
// EPWM1_A - GPIO Settings
//
#define GPIO_PIN_EPWM1_A 0
#define EPWM_J8_PHASE_U_EPWMA_GPIO 0
#define EPWM_J8_PHASE_U_EPWMA_PIN_CONFIG GPIO_0_EPWM1_A
//
// EPWM1_B - GPIO Settings
//
#define GPIO_PIN_EPWM1_B 1
#define EPWM_J8_PHASE_U_EPWMB_GPIO 1
#define EPWM_J8_PHASE_U_EPWMB_PIN_CONFIG GPIO_1_EPWM1_B

//
// EPWM4 -> EPWM_J8_PHASE_V Pinmux
//
//
// EPWM4_A - GPIO Settings
//
#define GPIO_PIN_EPWM4_A 6
#define EPWM_J8_PHASE_V_EPWMA_GPIO 6
#define EPWM_J8_PHASE_V_EPWMA_PIN_CONFIG GPIO_6_EPWM4_A
//
// EPWM4_B - GPIO Settings
//
#define GPIO_PIN_EPWM4_B 7
#define EPWM_J8_PHASE_V_EPWMB_GPIO 7
#define EPWM_J8_PHASE_V_EPWMB_PIN_CONFIG GPIO_7_EPWM4_B

//
// EPWM2 -> EPWM_J8_PHASE_W Pinmux
//
//
// EPWM2_A - GPIO Settings
//
#define GPIO_PIN_EPWM2_A 2
#define EPWM_J8_PHASE_W_EPWMA_GPIO 2
#define EPWM_J8_PHASE_W_EPWMA_PIN_CONFIG GPIO_2_EPWM2_A
//
// EPWM2_B - GPIO Settings
//
#define GPIO_PIN_EPWM2_B 3
#define EPWM_J8_PHASE_W_EPWMB_GPIO 3
#define EPWM_J8_PHASE_W_EPWMB_PIN_CONFIG GPIO_3_EPWM2_B

//
// EPWM3 -> EPWM_J4_PHASE_W Pinmux
//
//
// EPWM3_A - GPIO Settings
//
#define GPIO_PIN_EPWM3_A 4
#define EPWM_J4_PHASE_W_EPWMA_GPIO 4
#define EPWM_J4_PHASE_W_EPWMA_PIN_CONFIG GPIO_4_EPWM3_A
//
// EPWM3_B - GPIO Settings
//
#define GPIO_PIN_EPWM3_B 5
#define EPWM_J4_PHASE_W_EPWMB_GPIO 5
#define EPWM_J4_PHASE_W_EPWMB_PIN_CONFIG GPIO_5_EPWM3_B

//
// EPWM5 -> EPWM_J4_PHASE_V Pinmux
//
//
// EPWM5_A - GPIO Settings
//
#define GPIO_PIN_EPWM5_A 8
#define EPWM_J4_PHASE_V_EPWMA_GPIO 8
#define EPWM_J4_PHASE_V_EPWMA_PIN_CONFIG GPIO_8_EPWM5_A
//
// EPWM5_B - GPIO Settings
//
#define GPIO_PIN_EPWM5_B 9
#define EPWM_J4_PHASE_V_EPWMB_GPIO 9
#define EPWM_J4_PHASE_V_EPWMB_PIN_CONFIG GPIO_9_EPWM5_B

//
// EPWM6 -> EPWM_J4_PHASE_U Pinmux
//
//
// EPWM6_A - GPIO Settings
//
#define GPIO_PIN_EPWM6_A 10
#define EPWM_J4_PHASE_U_EPWMA_GPIO 10
#define EPWM_J4_PHASE_U_EPWMA_PIN_CONFIG GPIO_10_EPWM6_A
//
// EPWM6_B - GPIO Settings
//
#define GPIO_PIN_EPWM6_B 11
#define EPWM_J4_PHASE_U_EPWMB_GPIO 11
#define EPWM_J4_PHASE_U_EPWMB_PIN_CONFIG GPIO_11_EPWM6_B

//
// EQEP1 -> EQEP1_J12 Pinmux
//
//
// EQEP1_A - GPIO Settings
//
#define GPIO_PIN_EQEP1_A 35
#define EQEP1_J12_EQEPA_GPIO 35
#define EQEP1_J12_EQEPA_PIN_CONFIG GPIO_35_EQEP1_A
//
// EQEP1_B - GPIO Settings
//
#define GPIO_PIN_EQEP1_B 37
#define EQEP1_J12_EQEPB_GPIO 37
#define EQEP1_J12_EQEPB_PIN_CONFIG GPIO_37_EQEP1_B
//
// EQEP1_INDEX - GPIO Settings
//
#define GPIO_PIN_EQEP1_INDEX 59
#define EQEP1_J12_EQEPINDEX_GPIO 59
#define EQEP1_J12_EQEPINDEX_PIN_CONFIG GPIO_59_EQEP1_INDEX

//
// EQEP2 -> EQEP2_J13 Pinmux
//
//
// EQEP2_A - GPIO Settings
//
#define GPIO_PIN_EQEP2_A 14
#define EQEP2_J13_EQEPA_GPIO 14
#define EQEP2_J13_EQEPA_PIN_CONFIG GPIO_14_EQEP2_A
//
// EQEP2_B - GPIO Settings
//
#define GPIO_PIN_EQEP2_B 15
#define EQEP2_J13_EQEPB_GPIO 15
#define EQEP2_J13_EQEPB_PIN_CONFIG GPIO_15_EQEP2_B
//
// EQEP2_INDEX - GPIO Settings
//
#define GPIO_PIN_EQEP2_INDEX 26
#define EQEP2_J13_EQEPINDEX_GPIO 26
#define EQEP2_J13_EQEPINDEX_PIN_CONFIG GPIO_26_EQEP2_INDEX
//
// GPIO23 - GPIO Settings
//
#define LED_R_GPIO_PIN_CONFIG GPIO_23_GPIO23
//
// GPIO34 - GPIO Settings
//
#define LED_G_GPIO_PIN_CONFIG GPIO_34_GPIO34
//
// GPIO13 - GPIO Settings
//
#define ENABLE_GATE_GPIO_PIN_CONFIG GPIO_13_GPIO13
//
// GPIO17 - GPIO Settings
//
#define RESET_GATE_GPIO_PIN_CONFIG GPIO_17_GPIO17
//
// GPIO57 - GPIO Settings
//
#define MONITOR_IO_GPIO_PIN_CONFIG GPIO_57_GPIO57

//
// SCIA -> IRIS_UART_USB Pinmux
//
//
// SCIA_RX - GPIO Settings
//
#define GPIO_PIN_SCIA_RX 28
#define IRIS_UART_USB_SCIRX_GPIO 28
#define IRIS_UART_USB_SCIRX_PIN_CONFIG GPIO_28_SCIA_RX
//
// SCIA_TX - GPIO Settings
//
#define GPIO_PIN_SCIA_TX 29
#define IRIS_UART_USB_SCITX_GPIO 29
#define IRIS_UART_USB_SCITX_PIN_CONFIG GPIO_29_SCIA_TX

//*****************************************************************************
//
// ADC Configurations
//
//*****************************************************************************
#define IRIS_ADCA_BASE ADCA_BASE
#define IRIS_ADCA_RESULT_BASE ADCARESULT_BASE
#define J3_IW ADC_SOC_NUMBER0
#define J3_IW_FORCE ADC_FORCE_SOC0
#define J3_IW_ADC_BASE ADCA_BASE
#define J3_IW_RESULT_BASE ADCARESULT_BASE
#define J3_IW_SAMPLE_WINDOW 133.33333333333334
#define J3_IW_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_IW_CHANNEL ADC_CH_ADCIN9
#define J3_VDC ADC_SOC_NUMBER1
#define J3_VDC_FORCE ADC_FORCE_SOC1
#define J3_VDC_ADC_BASE ADCA_BASE
#define J3_VDC_RESULT_BASE ADCARESULT_BASE
#define J3_VDC_SAMPLE_WINDOW 133.33333333333334
#define J3_VDC_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_VDC_CHANNEL ADC_CH_ADCIN5
void IRIS_ADCA_init();

#define IRIS_ADCB_BASE ADCB_BASE
#define IRIS_ADCB_RESULT_BASE ADCBRESULT_BASE
#define J3_IU ADC_SOC_NUMBER0
#define J3_IU_FORCE ADC_FORCE_SOC0
#define J3_IU_ADC_BASE ADCB_BASE
#define J3_IU_RESULT_BASE ADCBRESULT_BASE
#define J3_IU_SAMPLE_WINDOW 133.33333333333334
#define J3_IU_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_IU_CHANNEL ADC_CH_ADCIN2
#define J3_VW ADC_SOC_NUMBER1
#define J3_VW_FORCE ADC_FORCE_SOC1
#define J3_VW_ADC_BASE ADCB_BASE
#define J3_VW_RESULT_BASE ADCBRESULT_BASE
#define J3_VW_SAMPLE_WINDOW 133.33333333333334
#define J3_VW_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_VW_CHANNEL ADC_CH_ADCIN1
#define J3_VU ADC_SOC_NUMBER2
#define J3_VU_FORCE ADC_FORCE_SOC2
#define J3_VU_ADC_BASE ADCB_BASE
#define J3_VU_RESULT_BASE ADCBRESULT_BASE
#define J3_VU_SAMPLE_WINDOW 133.33333333333334
#define J3_VU_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_VU_CHANNEL ADC_CH_ADCIN0
void IRIS_ADCB_init();

#define IRIS_ADCC_BASE ADCC_BASE
#define IRIS_ADCC_RESULT_BASE ADCCRESULT_BASE
#define J3_IV ADC_SOC_NUMBER0
#define J3_IV_FORCE ADC_FORCE_SOC0
#define J3_IV_ADC_BASE ADCC_BASE
#define J3_IV_RESULT_BASE ADCCRESULT_BASE
#define J3_IV_SAMPLE_WINDOW 133.33333333333334
#define J3_IV_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_IV_CHANNEL ADC_CH_ADCIN0
#define J3_VV ADC_SOC_NUMBER1
#define J3_VV_FORCE ADC_FORCE_SOC1
#define J3_VV_ADC_BASE ADCC_BASE
#define J3_VV_RESULT_BASE ADCCRESULT_BASE
#define J3_VV_SAMPLE_WINDOW 133.33333333333334
#define J3_VV_TRIGGER_SOURCE ADC_TRIGGER_EPWM1_SOCA
#define J3_VV_CHANNEL ADC_CH_ADCIN2
void IRIS_ADCC_init();


//*****************************************************************************
//
// ASYSCTL Configurations
//
//*****************************************************************************

//*****************************************************************************
//
// CAN Configurations
//
//*****************************************************************************
#define IRIS_CAN_BASE CANA_BASE

#define IRIS_CAN_MessageObj1_ID 257
#define IRIS_CAN_MessageObj2_ID 258
#define IRIS_CAN_MessageObj3_ID 259
#define IRIS_CAN_MessageObj4_ID 513
#define IRIS_CAN_MessageObj5_ID 514
#define IRIS_CAN_MessageObj6_ID 515
#define IRIS_CAN_MessageObj7_ID 516
#define IRIS_CAN_MessageObj8_ID 517
#define IRIS_CAN_MessageObj9_ID 518
#define IRIS_CAN_MessageObj10_ID 519
void IRIS_CAN_init();


//*****************************************************************************
//
// DAC Configurations
//
//*****************************************************************************
#define IRIS_DACA_BASE DACA_BASE
void IRIS_DACA_init();
#define IRIS_DACB_BASE DACB_BASE
void IRIS_DACB_init();

//*****************************************************************************
//
// EPWM Configurations
//
//*****************************************************************************
#define EPWM_J8_PHASE_U_BASE EPWM1_BASE
#define EPWM_J8_PHASE_U_TBPRD 2500
#define EPWM_J8_PHASE_U_COUNTER_MODE EPWM_COUNTER_MODE_UP_DOWN
#define EPWM_J8_PHASE_U_TBPHS 0
#define EPWM_J8_PHASE_U_CMPA 1250
#define EPWM_J8_PHASE_U_CMPB 625
#define EPWM_J8_PHASE_U_CMPC 0
#define EPWM_J8_PHASE_U_CMPD 0
#define EPWM_J8_PHASE_U_DBRED 100
#define EPWM_J8_PHASE_U_DBFED 100
#define EPWM_J8_PHASE_U_TZA_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J8_PHASE_U_TZB_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J8_PHASE_U_INTERRUPT_SOURCE EPWM_INT_TBCTR_ZERO
#define EPWM_J8_PHASE_V_BASE EPWM4_BASE
#define EPWM_J8_PHASE_V_TBPRD 2500
#define EPWM_J8_PHASE_V_COUNTER_MODE EPWM_COUNTER_MODE_UP_DOWN
#define EPWM_J8_PHASE_V_TBPHS 0
#define EPWM_J8_PHASE_V_CMPA 1250
#define EPWM_J8_PHASE_V_CMPB 625
#define EPWM_J8_PHASE_V_CMPC 0
#define EPWM_J8_PHASE_V_CMPD 0
#define EPWM_J8_PHASE_V_DBRED 100
#define EPWM_J8_PHASE_V_DBFED 100
#define EPWM_J8_PHASE_V_TZA_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J8_PHASE_V_TZB_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J8_PHASE_V_INTERRUPT_SOURCE EPWM_INT_TBCTR_ZERO
#define EPWM_J8_PHASE_W_BASE EPWM2_BASE
#define EPWM_J8_PHASE_W_TBPRD 2500
#define EPWM_J8_PHASE_W_COUNTER_MODE EPWM_COUNTER_MODE_UP_DOWN
#define EPWM_J8_PHASE_W_TBPHS 0
#define EPWM_J8_PHASE_W_CMPA 1250
#define EPWM_J8_PHASE_W_CMPB 625
#define EPWM_J8_PHASE_W_CMPC 0
#define EPWM_J8_PHASE_W_CMPD 0
#define EPWM_J8_PHASE_W_DBRED 100
#define EPWM_J8_PHASE_W_DBFED 100
#define EPWM_J8_PHASE_W_TZA_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J8_PHASE_W_TZB_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J8_PHASE_W_INTERRUPT_SOURCE EPWM_INT_TBCTR_ZERO
#define EPWM_J4_PHASE_W_BASE EPWM3_BASE
#define EPWM_J4_PHASE_W_TBPRD 2500
#define EPWM_J4_PHASE_W_COUNTER_MODE EPWM_COUNTER_MODE_UP_DOWN
#define EPWM_J4_PHASE_W_TBPHS 0
#define EPWM_J4_PHASE_W_CMPA 1250
#define EPWM_J4_PHASE_W_CMPB 625
#define EPWM_J4_PHASE_W_CMPC 0
#define EPWM_J4_PHASE_W_CMPD 0
#define EPWM_J4_PHASE_W_DBRED 100
#define EPWM_J4_PHASE_W_DBFED 100
#define EPWM_J4_PHASE_W_TZA_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J4_PHASE_W_TZB_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J4_PHASE_W_INTERRUPT_SOURCE EPWM_INT_TBCTR_ZERO
#define EPWM_J4_PHASE_V_BASE EPWM5_BASE
#define EPWM_J4_PHASE_V_TBPRD 2500
#define EPWM_J4_PHASE_V_COUNTER_MODE EPWM_COUNTER_MODE_UP_DOWN
#define EPWM_J4_PHASE_V_TBPHS 0
#define EPWM_J4_PHASE_V_CMPA 1250
#define EPWM_J4_PHASE_V_CMPB 625
#define EPWM_J4_PHASE_V_CMPC 0
#define EPWM_J4_PHASE_V_CMPD 0
#define EPWM_J4_PHASE_V_DBRED 100
#define EPWM_J4_PHASE_V_DBFED 100
#define EPWM_J4_PHASE_V_TZA_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J4_PHASE_V_TZB_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J4_PHASE_V_INTERRUPT_SOURCE EPWM_INT_TBCTR_ZERO
#define EPWM_J4_PHASE_U_BASE EPWM6_BASE
#define EPWM_J4_PHASE_U_TBPRD 2500
#define EPWM_J4_PHASE_U_COUNTER_MODE EPWM_COUNTER_MODE_UP_DOWN
#define EPWM_J4_PHASE_U_TBPHS 0
#define EPWM_J4_PHASE_U_CMPA 1250
#define EPWM_J4_PHASE_U_CMPB 625
#define EPWM_J4_PHASE_U_CMPC 0
#define EPWM_J4_PHASE_U_CMPD 0
#define EPWM_J4_PHASE_U_DBRED 100
#define EPWM_J4_PHASE_U_DBFED 100
#define EPWM_J4_PHASE_U_TZA_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J4_PHASE_U_TZB_ACTION EPWM_TZ_ACTION_HIGH_Z
#define EPWM_J4_PHASE_U_INTERRUPT_SOURCE EPWM_INT_TBCTR_ZERO

//*****************************************************************************
//
// EQEP Configurations
//
//*****************************************************************************
#define EQEP1_J12_BASE EQEP1_BASE
void EQEP1_J12_init();
#define EQEP2_J13_BASE EQEP2_BASE
void EQEP2_J13_init();

//*****************************************************************************
//
// GPIO Configurations
//
//*****************************************************************************
#define LED_R 23
void LED_R_init();
#define LED_G 34
void LED_G_init();
#define ENABLE_GATE 13
void ENABLE_GATE_init();
#define RESET_GATE 17
void RESET_GATE_init();
#define MONITOR_IO 57
void MONITOR_IO_init();

//*****************************************************************************
//
// INTERRUPT Configurations
//
//*****************************************************************************

// Interrupt Settings for INT_IRIS_ADCA_1
// ISR need to be defined for the registered interrupts
#define INT_IRIS_ADCA_1 INT_ADCA1
#define INT_IRIS_ADCA_1_INTERRUPT_ACK_GROUP INTERRUPT_ACK_GROUP1
extern __interrupt void MainISR(void);

// Interrupt Settings for INT_IRIS_CAN_0
// ISR need to be defined for the registered interrupts
#define INT_IRIS_CAN_0 INT_CANA0
#define INT_IRIS_CAN_0_INTERRUPT_ACK_GROUP INTERRUPT_ACK_GROUP9
extern __interrupt void INT_IRIS_CAN_0_ISR(void);

// Interrupt Settings for INT_IRIS_CAN_1
// ISR need to be defined for the registered interrupts
#define INT_IRIS_CAN_1 INT_CANA1
#define INT_IRIS_CAN_1_INTERRUPT_ACK_GROUP INTERRUPT_ACK_GROUP9
extern __interrupt void INT_IRIS_CAN_1_ISR(void);

// Interrupt Settings for INT_IRIS_UART_USB_RX
// ISR need to be defined for the registered interrupts
#define INT_IRIS_UART_USB_RX INT_SCIA_RX
#define INT_IRIS_UART_USB_RX_INTERRUPT_ACK_GROUP INTERRUPT_ACK_GROUP9
extern __interrupt void INT_IRIS_UART_USB_RX_ISR(void);

//*****************************************************************************
//
// SCI Configurations
//
//*****************************************************************************
#define IRIS_UART_USB_BASE SCIA_BASE
#define IRIS_UART_USB_BAUDRATE 256000
#define IRIS_UART_USB_CONFIG_WLEN SCI_CONFIG_WLEN_8
#define IRIS_UART_USB_CONFIG_STOP SCI_CONFIG_STOP_ONE
#define IRIS_UART_USB_CONFIG_PAR SCI_CONFIG_PAR_NONE
#define IRIS_UART_USB_FIFO_TX_LVL SCI_FIFO_TX0
#define IRIS_UART_USB_FIFO_RX_LVL SCI_FIFO_RX14
void IRIS_UART_USB_init();

//*****************************************************************************
//
// SYNC Scheme Configurations
//
//*****************************************************************************

//*****************************************************************************
//
// SYSCTL Configurations
//
//*****************************************************************************

//*****************************************************************************
//
// Board Configurations
//
//*****************************************************************************
void	Board_init();
void	ADC_init();
void	ASYSCTL_init();
void	CAN_init();
void	DAC_init();
void	EPWM_init();
void	EQEP_init();
void	GPIO_init();
void	INTERRUPT_init();
void	SCI_init();
void	SYNC_init();
void	SYSCTL_init();
void	PinMux_init();

//*****************************************************************************
//
// Mark the end of the C bindings section for C++ compilers.
//
//*****************************************************************************
#ifdef __cplusplus
}
#endif

#endif  // end of BOARD_H definition
