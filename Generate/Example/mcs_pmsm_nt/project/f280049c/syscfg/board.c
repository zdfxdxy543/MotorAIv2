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

#include "board.h"

//*****************************************************************************
//
// Board Configurations
// Initializes the rest of the modules. 
// Call this function in your application if you wish to do all module 
// initialization.
// If you wish to not use some of the initializations, instead of the 
// Board_init use the individual Module_inits
//
//*****************************************************************************
void Board_init()
{
	EALLOW;

	PinMux_init();
	SYSCTL_init();
	SYNC_init();
	ASYSCTL_init();
	ADC_init();
	CAN_init();
	DAC_init();
	EPWM_init();
	EQEP_init();
	GPIO_init();
	SCI_init();
	INTERRUPT_init();

	EDIS;
}

//*****************************************************************************
//
// PINMUX Configurations
//
//*****************************************************************************
void PinMux_init()
{
	//
	// PinMux for modules assigned to CPU1
	//
	
	//
	// CANA -> IRIS_CAN Pinmux
	//
	GPIO_setPinConfig(IRIS_CAN_CANRX_PIN_CONFIG);
	GPIO_setPadConfig(IRIS_CAN_CANRX_GPIO, GPIO_PIN_TYPE_STD | GPIO_PIN_TYPE_PULLUP);
	GPIO_setQualificationMode(IRIS_CAN_CANRX_GPIO, GPIO_QUAL_ASYNC);

	GPIO_setPinConfig(IRIS_CAN_CANTX_PIN_CONFIG);
	GPIO_setPadConfig(IRIS_CAN_CANTX_GPIO, GPIO_PIN_TYPE_STD | GPIO_PIN_TYPE_PULLUP);
	GPIO_setQualificationMode(IRIS_CAN_CANTX_GPIO, GPIO_QUAL_ASYNC);

	//
	// EPWM1 -> EPWM_J8_PHASE_U Pinmux
	//
	GPIO_setPinConfig(EPWM_J8_PHASE_U_EPWMA_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J8_PHASE_U_EPWMA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J8_PHASE_U_EPWMA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EPWM_J8_PHASE_U_EPWMB_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J8_PHASE_U_EPWMB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J8_PHASE_U_EPWMB_GPIO, GPIO_QUAL_SYNC);

	//
	// EPWM4 -> EPWM_J8_PHASE_V Pinmux
	//
	GPIO_setPinConfig(EPWM_J8_PHASE_V_EPWMA_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J8_PHASE_V_EPWMA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J8_PHASE_V_EPWMA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EPWM_J8_PHASE_V_EPWMB_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J8_PHASE_V_EPWMB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J8_PHASE_V_EPWMB_GPIO, GPIO_QUAL_SYNC);

	//
	// EPWM2 -> EPWM_J8_PHASE_W Pinmux
	//
	GPIO_setPinConfig(EPWM_J8_PHASE_W_EPWMA_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J8_PHASE_W_EPWMA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J8_PHASE_W_EPWMA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EPWM_J8_PHASE_W_EPWMB_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J8_PHASE_W_EPWMB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J8_PHASE_W_EPWMB_GPIO, GPIO_QUAL_SYNC);

	//
	// EPWM3 -> EPWM_J4_PHASE_W Pinmux
	//
	GPIO_setPinConfig(EPWM_J4_PHASE_W_EPWMA_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J4_PHASE_W_EPWMA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J4_PHASE_W_EPWMA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EPWM_J4_PHASE_W_EPWMB_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J4_PHASE_W_EPWMB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J4_PHASE_W_EPWMB_GPIO, GPIO_QUAL_SYNC);

	//
	// EPWM5 -> EPWM_J4_PHASE_V Pinmux
	//
	GPIO_setPinConfig(EPWM_J4_PHASE_V_EPWMA_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J4_PHASE_V_EPWMA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J4_PHASE_V_EPWMA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EPWM_J4_PHASE_V_EPWMB_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J4_PHASE_V_EPWMB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J4_PHASE_V_EPWMB_GPIO, GPIO_QUAL_SYNC);

	//
	// EPWM6 -> EPWM_J4_PHASE_U Pinmux
	//
	GPIO_setPinConfig(EPWM_J4_PHASE_U_EPWMA_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J4_PHASE_U_EPWMA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J4_PHASE_U_EPWMA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EPWM_J4_PHASE_U_EPWMB_PIN_CONFIG);
	GPIO_setPadConfig(EPWM_J4_PHASE_U_EPWMB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EPWM_J4_PHASE_U_EPWMB_GPIO, GPIO_QUAL_SYNC);

	//
	// EQEP1 -> EQEP1_J12 Pinmux
	//
	GPIO_setPinConfig(EQEP1_J12_EQEPA_PIN_CONFIG);
	GPIO_setPadConfig(EQEP1_J12_EQEPA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EQEP1_J12_EQEPA_GPIO, GPIO_QUAL_3SAMPLE);

	GPIO_setPinConfig(EQEP1_J12_EQEPB_PIN_CONFIG);
	GPIO_setPadConfig(EQEP1_J12_EQEPB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EQEP1_J12_EQEPB_GPIO, GPIO_QUAL_3SAMPLE);

	GPIO_setPinConfig(EQEP1_J12_EQEPINDEX_PIN_CONFIG);
	GPIO_setPadConfig(EQEP1_J12_EQEPINDEX_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EQEP1_J12_EQEPINDEX_GPIO, GPIO_QUAL_3SAMPLE);

	//
	// EQEP2 -> EQEP2_J13 Pinmux
	//
	GPIO_setPinConfig(EQEP2_J13_EQEPA_PIN_CONFIG);
	GPIO_setPadConfig(EQEP2_J13_EQEPA_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EQEP2_J13_EQEPA_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EQEP2_J13_EQEPB_PIN_CONFIG);
	GPIO_setPadConfig(EQEP2_J13_EQEPB_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EQEP2_J13_EQEPB_GPIO, GPIO_QUAL_SYNC);

	GPIO_setPinConfig(EQEP2_J13_EQEPINDEX_PIN_CONFIG);
	GPIO_setPadConfig(EQEP2_J13_EQEPINDEX_GPIO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(EQEP2_J13_EQEPINDEX_GPIO, GPIO_QUAL_SYNC);

	// GPIO23_VSW -> LED_R Pinmux
	GPIO_setPinConfig(GPIO_23_GPIO23);
	// GPIO34 -> LED_G Pinmux
	GPIO_setPinConfig(GPIO_34_GPIO34);
	// GPIO13 -> ENABLE_GATE Pinmux
	GPIO_setPinConfig(GPIO_13_GPIO13);
	// GPIO17 -> RESET_GATE Pinmux
	GPIO_setPinConfig(GPIO_17_GPIO17);
	// GPIO57 -> MONITOR_IO Pinmux
	GPIO_setPinConfig(GPIO_57_GPIO57);
	//
	// SCIA -> IRIS_UART_USB Pinmux
	//
	GPIO_setPinConfig(IRIS_UART_USB_SCIRX_PIN_CONFIG);
	GPIO_setPadConfig(IRIS_UART_USB_SCIRX_GPIO, GPIO_PIN_TYPE_STD | GPIO_PIN_TYPE_PULLUP);
	GPIO_setQualificationMode(IRIS_UART_USB_SCIRX_GPIO, GPIO_QUAL_ASYNC);

	GPIO_setPinConfig(IRIS_UART_USB_SCITX_PIN_CONFIG);
	GPIO_setPadConfig(IRIS_UART_USB_SCITX_GPIO, GPIO_PIN_TYPE_STD | GPIO_PIN_TYPE_PULLUP);
	GPIO_setQualificationMode(IRIS_UART_USB_SCITX_GPIO, GPIO_QUAL_ASYNC);


}

//*****************************************************************************
//
// ADC Configurations
//
//*****************************************************************************
void ADC_init(){
	IRIS_ADCA_init();
	IRIS_ADCB_init();
	IRIS_ADCC_init();
}

void IRIS_ADCA_init(){
	//
	// ADC Initialization: Write ADC configurations and power up the ADC
	//
	// Set the analog voltage reference selection and ADC module's offset trims.
	// This function sets the analog voltage reference to internal (with the reference voltage of 1.65V or 2.5V) or external for ADC
	// which is same as ASysCtl APIs.
	//
	ADC_setVREF(IRIS_ADCA_BASE, ADC_REFERENCE_INTERNAL, ADC_REFERENCE_2_5V);
	//
	// Configures the analog-to-digital converter module prescaler.
	//
	ADC_setPrescaler(IRIS_ADCA_BASE, ADC_CLK_DIV_2_0);
	//
	// Sets the timing of the end-of-conversion pulse
	//
	ADC_setInterruptPulseMode(IRIS_ADCA_BASE, ADC_PULSE_END_OF_ACQ_WIN);
	//
	// Sets the timing of early interrupt generation.
	//
	ADC_setInterruptCycleOffset(IRIS_ADCA_BASE, 0U);
	//
	// Powers up the analog-to-digital converter core.
	//
	ADC_enableConverter(IRIS_ADCA_BASE);
	//
	// Delay for 1ms to allow ADC time to power up
	//
	DEVICE_DELAY_US(5000);
	//
	// SOC Configuration: Setup ADC EPWM channel and trigger settings
	//
	// Disables SOC burst mode.
	//
	ADC_disableBurstMode(IRIS_ADCA_BASE);
	//
	// Sets the priority mode of the SOCs.
	//
	ADC_setSOCPriority(IRIS_ADCA_BASE, ADC_PRI_ALL_ROUND_ROBIN);
	//
	// Start of Conversion 0 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 0
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN9
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCA_BASE, ADC_SOC_NUMBER0, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN9, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCA_BASE, ADC_SOC_NUMBER0, ADC_INT_SOC_TRIGGER_NONE);
	//
	// Start of Conversion 1 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 1
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN5
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCA_BASE, ADC_SOC_NUMBER1, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN5, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCA_BASE, ADC_SOC_NUMBER1, ADC_INT_SOC_TRIGGER_NONE);
	//
	// ADC Interrupt 1 Configuration
	// 		Source	: ADC_SOC_NUMBER0
	// 		Interrupt Source: enabled
	//		Continuous Mode	: enabled
	//
	//
	ADC_setInterruptSource(IRIS_ADCA_BASE, ADC_INT_NUMBER1, ADC_SOC_NUMBER0);
	ADC_clearInterruptStatus(IRIS_ADCA_BASE, ADC_INT_NUMBER1);
	ADC_enableContinuousMode(IRIS_ADCA_BASE, ADC_INT_NUMBER1);
	ADC_enableInterrupt(IRIS_ADCA_BASE, ADC_INT_NUMBER1);
}

void IRIS_ADCB_init(){
	//
	// ADC Initialization: Write ADC configurations and power up the ADC
	//
	// Set the analog voltage reference selection and ADC module's offset trims.
	// This function sets the analog voltage reference to internal (with the reference voltage of 1.65V or 2.5V) or external for ADC
	// which is same as ASysCtl APIs.
	//
	ADC_setVREF(IRIS_ADCB_BASE, ADC_REFERENCE_INTERNAL, ADC_REFERENCE_2_5V);
	//
	// Configures the analog-to-digital converter module prescaler.
	//
	ADC_setPrescaler(IRIS_ADCB_BASE, ADC_CLK_DIV_2_0);
	//
	// Sets the timing of the end-of-conversion pulse
	//
	ADC_setInterruptPulseMode(IRIS_ADCB_BASE, ADC_PULSE_END_OF_ACQ_WIN);
	//
	// Sets the timing of early interrupt generation.
	//
	ADC_setInterruptCycleOffset(IRIS_ADCB_BASE, 0U);
	//
	// Powers up the analog-to-digital converter core.
	//
	ADC_enableConverter(IRIS_ADCB_BASE);
	//
	// Delay for 1ms to allow ADC time to power up
	//
	DEVICE_DELAY_US(5000);
	//
	// SOC Configuration: Setup ADC EPWM channel and trigger settings
	//
	// Disables SOC burst mode.
	//
	ADC_disableBurstMode(IRIS_ADCB_BASE);
	//
	// Sets the priority mode of the SOCs.
	//
	ADC_setSOCPriority(IRIS_ADCB_BASE, ADC_PRI_ALL_ROUND_ROBIN);
	//
	// Start of Conversion 0 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 0
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN2
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCB_BASE, ADC_SOC_NUMBER0, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN2, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCB_BASE, ADC_SOC_NUMBER0, ADC_INT_SOC_TRIGGER_NONE);
	//
	// Start of Conversion 1 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 1
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN1
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCB_BASE, ADC_SOC_NUMBER1, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN1, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCB_BASE, ADC_SOC_NUMBER1, ADC_INT_SOC_TRIGGER_NONE);
	//
	// Start of Conversion 2 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 2
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN0
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCB_BASE, ADC_SOC_NUMBER2, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN0, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCB_BASE, ADC_SOC_NUMBER2, ADC_INT_SOC_TRIGGER_NONE);
}

void IRIS_ADCC_init(){
	//
	// ADC Initialization: Write ADC configurations and power up the ADC
	//
	// Set the analog voltage reference selection and ADC module's offset trims.
	// This function sets the analog voltage reference to internal (with the reference voltage of 1.65V or 2.5V) or external for ADC
	// which is same as ASysCtl APIs.
	//
	ADC_setVREF(IRIS_ADCC_BASE, ADC_REFERENCE_INTERNAL, ADC_REFERENCE_2_5V);
	//
	// Configures the analog-to-digital converter module prescaler.
	//
	ADC_setPrescaler(IRIS_ADCC_BASE, ADC_CLK_DIV_2_0);
	//
	// Sets the timing of the end-of-conversion pulse
	//
	ADC_setInterruptPulseMode(IRIS_ADCC_BASE, ADC_PULSE_END_OF_ACQ_WIN);
	//
	// Sets the timing of early interrupt generation.
	//
	ADC_setInterruptCycleOffset(IRIS_ADCC_BASE, 0U);
	//
	// Powers up the analog-to-digital converter core.
	//
	ADC_enableConverter(IRIS_ADCC_BASE);
	//
	// Delay for 1ms to allow ADC time to power up
	//
	DEVICE_DELAY_US(5000);
	//
	// SOC Configuration: Setup ADC EPWM channel and trigger settings
	//
	// Disables SOC burst mode.
	//
	ADC_disableBurstMode(IRIS_ADCC_BASE);
	//
	// Sets the priority mode of the SOCs.
	//
	ADC_setSOCPriority(IRIS_ADCC_BASE, ADC_PRI_ALL_ROUND_ROBIN);
	//
	// Start of Conversion 0 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 0
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN0
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCC_BASE, ADC_SOC_NUMBER0, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN0, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCC_BASE, ADC_SOC_NUMBER0, ADC_INT_SOC_TRIGGER_NONE);
	//
	// Start of Conversion 1 Configuration
	//
	//
	// Configures a start-of-conversion (SOC) in the ADC and its interrupt SOC trigger.
	// 	  	SOC number		: 1
	//	  	Trigger			: ADC_TRIGGER_EPWM1_SOCA
	//	  	Channel			: ADC_CH_ADCIN2
	//	 	Sample Window	: 8 SYSCLK cycles
	//		Interrupt Trigger: ADC_INT_SOC_TRIGGER_NONE
	//
	ADC_setupSOC(IRIS_ADCC_BASE, ADC_SOC_NUMBER1, ADC_TRIGGER_EPWM1_SOCA, ADC_CH_ADCIN2, 8U);
	ADC_setInterruptSOCTrigger(IRIS_ADCC_BASE, ADC_SOC_NUMBER1, ADC_INT_SOC_TRIGGER_NONE);
}


//*****************************************************************************
//
// ASYSCTL Configurations
//
//*****************************************************************************
void ASYSCTL_init(){
	//
	// asysctl initialization
	//
	// Disables the temperature sensor output to the ADC.
	//
	ASysCtl_disableTemperatureSensor();
	//
	// Set the analog voltage reference selection to internal.
	//
	ASysCtl_setAnalogReferenceInternal( ASYSCTL_VREFHIA | ASYSCTL_VREFHIB | ASYSCTL_VREFHIC );
	//
	// Set the internal analog voltage reference selection to 2.5V.
	//
	ASysCtl_setAnalogReference2P5( ASYSCTL_VREFHIA | ASYSCTL_VREFHIB | ASYSCTL_VREFHIC );
}

//*****************************************************************************
//
// CAN Configurations
//
//*****************************************************************************
void CAN_init(){
	IRIS_CAN_init();
}

void IRIS_CAN_init(){
	CAN_initModule(IRIS_CAN_BASE);
	//
	// Refer to the Driver Library User Guide for information on how to set
	// tighter timing control. Additionally, consult the device data sheet
	// for more information about the CAN module clocking.
	//
	CAN_setBitTiming(IRIS_CAN_BASE, 7, 0, 15, 7, 3);
	//
	// Enable CAN Interrupts
	//
	CAN_enableInterrupt(IRIS_CAN_BASE, CAN_INT_IE0);
	CAN_enableGlobalInterrupt(IRIS_CAN_BASE, CAN_GLOBAL_INT_CANINT0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 1
	//      Message Identifier: 257
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_RX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 1, IRIS_CAN_MessageObj1_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_RX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 2
	//      Message Identifier: 258
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_RX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 2, IRIS_CAN_MessageObj2_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_RX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 3
	//      Message Identifier: 259
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_RX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 3, IRIS_CAN_MessageObj3_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_RX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 4
	//      Message Identifier: 513
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 4, IRIS_CAN_MessageObj4_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 5
	//      Message Identifier: 514
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 5, IRIS_CAN_MessageObj5_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 6
	//      Message Identifier: 515
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 6, IRIS_CAN_MessageObj6_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 7
	//      Message Identifier: 516
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 7, IRIS_CAN_MessageObj7_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 8
	//      Message Identifier: 517
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 8, IRIS_CAN_MessageObj8_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 9
	//      Message Identifier: 518
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 9, IRIS_CAN_MessageObj9_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	//
	// Initialize the transmit message object used for sending CAN messages.
	// Message Object Parameters:
	//      Message Object ID Number: 10
	//      Message Identifier: 519
	//      Message Frame: CAN_MSG_FRAME_STD
	//      Message Type: CAN_MSG_OBJ_TYPE_TX
	//      Message ID Mask: 0
	//      Message Object Flags: 
	//      Message Data Length: 0 Bytes
	//
	CAN_setupMessageObject(IRIS_CAN_BASE, 10, IRIS_CAN_MessageObj10_ID, CAN_MSG_FRAME_STD,CAN_MSG_OBJ_TYPE_TX, 0, 0,0);
	CAN_setInterruptMux(IRIS_CAN_BASE, 0);
	//
	// Start CAN module operations
	//
	CAN_startModule(IRIS_CAN_BASE);
}

//*****************************************************************************
//
// DAC Configurations
//
//*****************************************************************************
void DAC_init(){
	IRIS_DACA_init();
	IRIS_DACB_init();
}

void IRIS_DACA_init(){
	//
	// Set DAC reference voltage.
	//
	DAC_setReferenceVoltage(IRIS_DACA_BASE, DAC_REF_ADC_VREFHI);
	//
	// Set DAC gain mode.
	//
	DAC_setGainMode(IRIS_DACA_BASE, DAC_GAIN_ONE);
	//
	// Set DAC load mode.
	//
	DAC_setLoadMode(IRIS_DACA_BASE, DAC_LOAD_SYSCLK);
	//
	// Enable the DAC output
	//
	DAC_enableOutput(IRIS_DACA_BASE);
	//
	// Set the DAC shadow output
	//
	DAC_setShadowValue(IRIS_DACA_BASE, 500U);

	//
	// Delay for buffered DAC to power up.
	//
	DEVICE_DELAY_US(5000);
}
void IRIS_DACB_init(){
	//
	// Set DAC reference voltage.
	//
	DAC_setReferenceVoltage(IRIS_DACB_BASE, DAC_REF_ADC_VREFHI);
	//
	// Set DAC gain mode.
	//
	DAC_setGainMode(IRIS_DACB_BASE, DAC_GAIN_ONE);
	//
	// Set DAC load mode.
	//
	DAC_setLoadMode(IRIS_DACB_BASE, DAC_LOAD_SYSCLK);
	//
	// Enable the DAC output
	//
	DAC_enableOutput(IRIS_DACB_BASE);
	//
	// Set the DAC shadow output
	//
	DAC_setShadowValue(IRIS_DACB_BASE, 500U);

	//
	// Delay for buffered DAC to power up.
	//
	DEVICE_DELAY_US(5000);
}

//*****************************************************************************
//
// EPWM Configurations
//
//*****************************************************************************
void EPWM_init(){
    EPWM_setClockPrescaler(EPWM_J8_PHASE_U_BASE, EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);	
    EPWM_setTimeBasePeriod(EPWM_J8_PHASE_U_BASE, 2500);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_U_BASE, EPWM_GL_REGISTER_TBPRD_TBPRDHR);	
    EPWM_setTimeBaseCounter(EPWM_J8_PHASE_U_BASE, 0);	
    EPWM_setTimeBaseCounterMode(EPWM_J8_PHASE_U_BASE, EPWM_COUNTER_MODE_UP_DOWN);	
    EPWM_setCountModeAfterSync(EPWM_J8_PHASE_U_BASE, EPWM_COUNT_MODE_UP_AFTER_SYNC);	
    EPWM_enablePhaseShiftLoad(EPWM_J8_PHASE_U_BASE);	
    EPWM_setPhaseShift(EPWM_J8_PHASE_U_BASE, 0);	
    EPWM_setSyncOutPulseMode(EPWM_J8_PHASE_U_BASE, EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J8_PHASE_U_BASE, EPWM_COUNTER_COMPARE_A, 1250);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_U_BASE, EPWM_GL_REGISTER_CMPA_CMPAHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J8_PHASE_U_BASE, EPWM_COUNTER_COMPARE_A, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J8_PHASE_U_BASE, EPWM_COUNTER_COMPARE_B, 625);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_U_BASE, EPWM_GL_REGISTER_CMPB_CMPBHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J8_PHASE_U_BASE, EPWM_COUNTER_COMPARE_B, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_U_BASE, EPWM_GL_REGISTER_AQCTLA_AQCTLA2);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setDeadBandDelayPolarity(EPWM_J8_PHASE_U_BASE, EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);	
    EPWM_setDeadBandDelayMode(EPWM_J8_PHASE_U_BASE, EPWM_DB_RED, true);	
    EPWM_setRisingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_U_BASE, EPWM_RED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableRisingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_U_BASE);	
    EPWM_setRisingEdgeDelayCount(EPWM_J8_PHASE_U_BASE, 100);	
    EPWM_setDeadBandDelayMode(EPWM_J8_PHASE_U_BASE, EPWM_DB_FED, true);	
    EPWM_setFallingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_U_BASE, EPWM_FED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableFallingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_U_BASE);	
    EPWM_setFallingEdgeDelayCount(EPWM_J8_PHASE_U_BASE, 100);	
    EPWM_enableInterrupt(EPWM_J8_PHASE_U_BASE);	
    EPWM_setInterruptSource(EPWM_J8_PHASE_U_BASE, EPWM_INT_TBCTR_ZERO);	
    EPWM_setInterruptEventCount(EPWM_J8_PHASE_U_BASE, 1);	
    EPWM_enableADCTrigger(EPWM_J8_PHASE_U_BASE, EPWM_SOC_A);	
    EPWM_setADCTriggerSource(EPWM_J8_PHASE_U_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);	
    EPWM_setADCTriggerEventPrescale(EPWM_J8_PHASE_U_BASE, EPWM_SOC_A, 1);	
    EPWM_setClockPrescaler(EPWM_J8_PHASE_V_BASE, EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);	
    EPWM_setTimeBasePeriod(EPWM_J8_PHASE_V_BASE, 2500);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_V_BASE, EPWM_GL_REGISTER_TBPRD_TBPRDHR);	
    EPWM_setTimeBaseCounter(EPWM_J8_PHASE_V_BASE, 0);	
    EPWM_setTimeBaseCounterMode(EPWM_J8_PHASE_V_BASE, EPWM_COUNTER_MODE_UP_DOWN);	
    EPWM_setCountModeAfterSync(EPWM_J8_PHASE_V_BASE, EPWM_COUNT_MODE_UP_AFTER_SYNC);	
    EPWM_enablePhaseShiftLoad(EPWM_J8_PHASE_V_BASE);	
    EPWM_setPhaseShift(EPWM_J8_PHASE_V_BASE, 0);	
    EPWM_setSyncOutPulseMode(EPWM_J8_PHASE_V_BASE, EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J8_PHASE_V_BASE, EPWM_COUNTER_COMPARE_A, 1250);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_V_BASE, EPWM_GL_REGISTER_CMPA_CMPAHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J8_PHASE_V_BASE, EPWM_COUNTER_COMPARE_A, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J8_PHASE_V_BASE, EPWM_COUNTER_COMPARE_B, 625);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_V_BASE, EPWM_GL_REGISTER_CMPB_CMPBHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J8_PHASE_V_BASE, EPWM_COUNTER_COMPARE_B, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_V_BASE, EPWM_GL_REGISTER_AQCTLA_AQCTLA2);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setDeadBandDelayPolarity(EPWM_J8_PHASE_V_BASE, EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);	
    EPWM_setDeadBandDelayMode(EPWM_J8_PHASE_V_BASE, EPWM_DB_RED, true);	
    EPWM_setRisingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_V_BASE, EPWM_RED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableRisingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_V_BASE);	
    EPWM_setRisingEdgeDelayCount(EPWM_J8_PHASE_V_BASE, 100);	
    EPWM_setDeadBandDelayMode(EPWM_J8_PHASE_V_BASE, EPWM_DB_FED, true);	
    EPWM_setFallingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_V_BASE, EPWM_FED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableFallingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_V_BASE);	
    EPWM_setFallingEdgeDelayCount(EPWM_J8_PHASE_V_BASE, 100);	
    EPWM_enableInterrupt(EPWM_J8_PHASE_V_BASE);	
    EPWM_setInterruptSource(EPWM_J8_PHASE_V_BASE, EPWM_INT_TBCTR_ZERO);	
    EPWM_setInterruptEventCount(EPWM_J8_PHASE_V_BASE, 1);	
    EPWM_enableADCTrigger(EPWM_J8_PHASE_V_BASE, EPWM_SOC_A);	
    EPWM_setADCTriggerSource(EPWM_J8_PHASE_V_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);	
    EPWM_setADCTriggerEventPrescale(EPWM_J8_PHASE_V_BASE, EPWM_SOC_A, 1);	
    EPWM_setClockPrescaler(EPWM_J8_PHASE_W_BASE, EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);	
    EPWM_setTimeBasePeriod(EPWM_J8_PHASE_W_BASE, 2500);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_W_BASE, EPWM_GL_REGISTER_TBPRD_TBPRDHR);	
    EPWM_setTimeBaseCounter(EPWM_J8_PHASE_W_BASE, 0);	
    EPWM_setTimeBaseCounterMode(EPWM_J8_PHASE_W_BASE, EPWM_COUNTER_MODE_UP_DOWN);	
    EPWM_setCountModeAfterSync(EPWM_J8_PHASE_W_BASE, EPWM_COUNT_MODE_UP_AFTER_SYNC);	
    EPWM_enablePhaseShiftLoad(EPWM_J8_PHASE_W_BASE);	
    EPWM_setPhaseShift(EPWM_J8_PHASE_W_BASE, 0);	
    EPWM_setSyncOutPulseMode(EPWM_J8_PHASE_W_BASE, EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J8_PHASE_W_BASE, EPWM_COUNTER_COMPARE_A, 1250);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_W_BASE, EPWM_GL_REGISTER_CMPA_CMPAHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J8_PHASE_W_BASE, EPWM_COUNTER_COMPARE_A, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J8_PHASE_W_BASE, EPWM_COUNTER_COMPARE_B, 625);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_W_BASE, EPWM_GL_REGISTER_CMPB_CMPBHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J8_PHASE_W_BASE, EPWM_COUNTER_COMPARE_B, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_enableGlobalLoadRegisters(EPWM_J8_PHASE_W_BASE, EPWM_GL_REGISTER_AQCTLA_AQCTLA2);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J8_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setDeadBandDelayPolarity(EPWM_J8_PHASE_W_BASE, EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);	
    EPWM_setDeadBandDelayMode(EPWM_J8_PHASE_W_BASE, EPWM_DB_RED, true);	
    EPWM_setRisingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_W_BASE, EPWM_RED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableRisingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_W_BASE);	
    EPWM_setRisingEdgeDelayCount(EPWM_J8_PHASE_W_BASE, 100);	
    EPWM_setDeadBandDelayMode(EPWM_J8_PHASE_W_BASE, EPWM_DB_FED, true);	
    EPWM_setFallingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_W_BASE, EPWM_FED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableFallingEdgeDelayCountShadowLoadMode(EPWM_J8_PHASE_W_BASE);	
    EPWM_setFallingEdgeDelayCount(EPWM_J8_PHASE_W_BASE, 100);	
    EPWM_enableInterrupt(EPWM_J8_PHASE_W_BASE);	
    EPWM_setInterruptSource(EPWM_J8_PHASE_W_BASE, EPWM_INT_TBCTR_ZERO);	
    EPWM_setInterruptEventCount(EPWM_J8_PHASE_W_BASE, 1);	
    EPWM_enableADCTrigger(EPWM_J8_PHASE_W_BASE, EPWM_SOC_A);	
    EPWM_setADCTriggerSource(EPWM_J8_PHASE_W_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);	
    EPWM_setADCTriggerEventPrescale(EPWM_J8_PHASE_W_BASE, EPWM_SOC_A, 1);	
    EPWM_setClockPrescaler(EPWM_J4_PHASE_W_BASE, EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);	
    EPWM_setTimeBasePeriod(EPWM_J4_PHASE_W_BASE, 2500);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_W_BASE, EPWM_GL_REGISTER_TBPRD_TBPRDHR);	
    EPWM_setTimeBaseCounter(EPWM_J4_PHASE_W_BASE, 0);	
    EPWM_setTimeBaseCounterMode(EPWM_J4_PHASE_W_BASE, EPWM_COUNTER_MODE_UP_DOWN);	
    EPWM_setCountModeAfterSync(EPWM_J4_PHASE_W_BASE, EPWM_COUNT_MODE_UP_AFTER_SYNC);	
    EPWM_enablePhaseShiftLoad(EPWM_J4_PHASE_W_BASE);	
    EPWM_setPhaseShift(EPWM_J4_PHASE_W_BASE, 0);	
    EPWM_setSyncOutPulseMode(EPWM_J4_PHASE_W_BASE, EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J4_PHASE_W_BASE, EPWM_COUNTER_COMPARE_A, 1250);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_W_BASE, EPWM_GL_REGISTER_CMPA_CMPAHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J4_PHASE_W_BASE, EPWM_COUNTER_COMPARE_A, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J4_PHASE_W_BASE, EPWM_COUNTER_COMPARE_B, 625);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_W_BASE, EPWM_GL_REGISTER_CMPB_CMPBHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J4_PHASE_W_BASE, EPWM_COUNTER_COMPARE_B, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_W_BASE, EPWM_GL_REGISTER_AQCTLA_AQCTLA2);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_W_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setDeadBandDelayPolarity(EPWM_J4_PHASE_W_BASE, EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);	
    EPWM_setDeadBandDelayMode(EPWM_J4_PHASE_W_BASE, EPWM_DB_RED, true);	
    EPWM_setRisingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_W_BASE, EPWM_RED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableRisingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_W_BASE);	
    EPWM_setRisingEdgeDelayCount(EPWM_J4_PHASE_W_BASE, 100);	
    EPWM_setDeadBandDelayMode(EPWM_J4_PHASE_W_BASE, EPWM_DB_FED, true);	
    EPWM_setFallingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_W_BASE, EPWM_FED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableFallingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_W_BASE);	
    EPWM_setFallingEdgeDelayCount(EPWM_J4_PHASE_W_BASE, 100);	
    EPWM_enableInterrupt(EPWM_J4_PHASE_W_BASE);	
    EPWM_setInterruptSource(EPWM_J4_PHASE_W_BASE, EPWM_INT_TBCTR_ZERO);	
    EPWM_setInterruptEventCount(EPWM_J4_PHASE_W_BASE, 1);	
    EPWM_enableADCTrigger(EPWM_J4_PHASE_W_BASE, EPWM_SOC_A);	
    EPWM_setADCTriggerSource(EPWM_J4_PHASE_W_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);	
    EPWM_setADCTriggerEventPrescale(EPWM_J4_PHASE_W_BASE, EPWM_SOC_A, 1);	
    EPWM_setClockPrescaler(EPWM_J4_PHASE_V_BASE, EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);	
    EPWM_setTimeBasePeriod(EPWM_J4_PHASE_V_BASE, 2500);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_V_BASE, EPWM_GL_REGISTER_TBPRD_TBPRDHR);	
    EPWM_setTimeBaseCounter(EPWM_J4_PHASE_V_BASE, 0);	
    EPWM_setTimeBaseCounterMode(EPWM_J4_PHASE_V_BASE, EPWM_COUNTER_MODE_UP_DOWN);	
    EPWM_setCountModeAfterSync(EPWM_J4_PHASE_V_BASE, EPWM_COUNT_MODE_UP_AFTER_SYNC);	
    EPWM_enablePhaseShiftLoad(EPWM_J4_PHASE_V_BASE);	
    EPWM_setPhaseShift(EPWM_J4_PHASE_V_BASE, 0);	
    EPWM_setSyncOutPulseMode(EPWM_J4_PHASE_V_BASE, EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J4_PHASE_V_BASE, EPWM_COUNTER_COMPARE_A, 1250);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_V_BASE, EPWM_GL_REGISTER_CMPA_CMPAHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J4_PHASE_V_BASE, EPWM_COUNTER_COMPARE_A, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J4_PHASE_V_BASE, EPWM_COUNTER_COMPARE_B, 625);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_V_BASE, EPWM_GL_REGISTER_CMPB_CMPBHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J4_PHASE_V_BASE, EPWM_COUNTER_COMPARE_B, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_V_BASE, EPWM_GL_REGISTER_AQCTLA_AQCTLA2);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_V_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setDeadBandDelayPolarity(EPWM_J4_PHASE_V_BASE, EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);	
    EPWM_setDeadBandDelayMode(EPWM_J4_PHASE_V_BASE, EPWM_DB_RED, true);	
    EPWM_setRisingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_V_BASE, EPWM_RED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableRisingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_V_BASE);	
    EPWM_setRisingEdgeDelayCount(EPWM_J4_PHASE_V_BASE, 100);	
    EPWM_setDeadBandDelayMode(EPWM_J4_PHASE_V_BASE, EPWM_DB_FED, true);	
    EPWM_setFallingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_V_BASE, EPWM_FED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableFallingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_V_BASE);	
    EPWM_setFallingEdgeDelayCount(EPWM_J4_PHASE_V_BASE, 100);	
    EPWM_enableInterrupt(EPWM_J4_PHASE_V_BASE);	
    EPWM_setInterruptSource(EPWM_J4_PHASE_V_BASE, EPWM_INT_TBCTR_ZERO);	
    EPWM_setInterruptEventCount(EPWM_J4_PHASE_V_BASE, 1);	
    EPWM_enableADCTrigger(EPWM_J4_PHASE_V_BASE, EPWM_SOC_A);	
    EPWM_setADCTriggerSource(EPWM_J4_PHASE_V_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);	
    EPWM_setADCTriggerEventPrescale(EPWM_J4_PHASE_V_BASE, EPWM_SOC_A, 1);	
    EPWM_setClockPrescaler(EPWM_J4_PHASE_U_BASE, EPWM_CLOCK_DIVIDER_1, EPWM_HSCLOCK_DIVIDER_1);	
    EPWM_setTimeBasePeriod(EPWM_J4_PHASE_U_BASE, 2500);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_U_BASE, EPWM_GL_REGISTER_TBPRD_TBPRDHR);	
    EPWM_setTimeBaseCounter(EPWM_J4_PHASE_U_BASE, 0);	
    EPWM_setTimeBaseCounterMode(EPWM_J4_PHASE_U_BASE, EPWM_COUNTER_MODE_UP_DOWN);	
    EPWM_setCountModeAfterSync(EPWM_J4_PHASE_U_BASE, EPWM_COUNT_MODE_UP_AFTER_SYNC);	
    EPWM_enablePhaseShiftLoad(EPWM_J4_PHASE_U_BASE);	
    EPWM_setPhaseShift(EPWM_J4_PHASE_U_BASE, 0);	
    EPWM_setSyncOutPulseMode(EPWM_J4_PHASE_U_BASE, EPWM_SYNC_OUT_PULSE_ON_COUNTER_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J4_PHASE_U_BASE, EPWM_COUNTER_COMPARE_A, 1250);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_U_BASE, EPWM_GL_REGISTER_CMPA_CMPAHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J4_PHASE_U_BASE, EPWM_COUNTER_COMPARE_A, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_setCounterCompareValue(EPWM_J4_PHASE_U_BASE, EPWM_COUNTER_COMPARE_B, 625);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_U_BASE, EPWM_GL_REGISTER_CMPB_CMPBHR);	
    EPWM_setCounterCompareShadowLoadMode(EPWM_J4_PHASE_U_BASE, EPWM_COUNTER_COMPARE_B, EPWM_COMP_LOAD_ON_CNTR_ZERO);	
    EPWM_enableGlobalLoadRegisters(EPWM_J4_PHASE_U_BASE, EPWM_GL_REGISTER_AQCTLA_AQCTLA2);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_HIGH, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_LOW, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_A, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_ZERO);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_PERIOD);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPA);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_UP_CMPB);	
    EPWM_setActionQualifierAction(EPWM_J4_PHASE_U_BASE, EPWM_AQ_OUTPUT_B, EPWM_AQ_OUTPUT_NO_CHANGE, EPWM_AQ_OUTPUT_ON_TIMEBASE_DOWN_CMPB);	
    EPWM_setDeadBandDelayPolarity(EPWM_J4_PHASE_U_BASE, EPWM_DB_FED, EPWM_DB_POLARITY_ACTIVE_LOW);	
    EPWM_setDeadBandDelayMode(EPWM_J4_PHASE_U_BASE, EPWM_DB_RED, true);	
    EPWM_setRisingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_U_BASE, EPWM_RED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableRisingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_U_BASE);	
    EPWM_setRisingEdgeDelayCount(EPWM_J4_PHASE_U_BASE, 100);	
    EPWM_setDeadBandDelayMode(EPWM_J4_PHASE_U_BASE, EPWM_DB_FED, true);	
    EPWM_setFallingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_U_BASE, EPWM_FED_LOAD_ON_CNTR_ZERO);	
    EPWM_disableFallingEdgeDelayCountShadowLoadMode(EPWM_J4_PHASE_U_BASE);	
    EPWM_setFallingEdgeDelayCount(EPWM_J4_PHASE_U_BASE, 100);	
    EPWM_enableInterrupt(EPWM_J4_PHASE_U_BASE);	
    EPWM_setInterruptSource(EPWM_J4_PHASE_U_BASE, EPWM_INT_TBCTR_ZERO);	
    EPWM_setInterruptEventCount(EPWM_J4_PHASE_U_BASE, 1);	
    EPWM_enableADCTrigger(EPWM_J4_PHASE_U_BASE, EPWM_SOC_A);	
    EPWM_setADCTriggerSource(EPWM_J4_PHASE_U_BASE, EPWM_SOC_A, EPWM_SOC_TBCTR_ZERO);	
    EPWM_setADCTriggerEventPrescale(EPWM_J4_PHASE_U_BASE, EPWM_SOC_A, 1);	
}

//*****************************************************************************
//
// EQEP Configurations
//
//*****************************************************************************
void EQEP_init(){
	EQEP1_J12_init();
	EQEP2_J13_init();
}

void EQEP1_J12_init(){
	//
	// Set the strobe input source of the eQEP module.
	//
	EQEP_setStrobeSource(EQEP1_J12_BASE,EQEP_STROBE_FROM_GPIO);
	//
	// Sets the polarity of the eQEP module's input signals.
	//
	EQEP_setInputPolarity(EQEP1_J12_BASE,false,false,false,false);
	//
	// Configures eQEP module's quadrature decoder unit.
	//
	EQEP_setDecoderConfig(EQEP1_J12_BASE, (EQEP_CONFIG_QUADRATURE | EQEP_CONFIG_2X_RESOLUTION | EQEP_CONFIG_NO_SWAP | EQEP_CONFIG_IGATE_DISABLE));
	//
	// Set the emulation mode of the eQEP module.
	//
	EQEP_setEmulationMode(EQEP1_J12_BASE,EQEP_EMULATIONMODE_STOPIMMEDIATELY);
	//
	// Configures eQEP module position counter unit.
	//
	EQEP_setPositionCounterConfig(EQEP1_J12_BASE,EQEP_POSITION_RESET_IDX,128U);
	//
	// Sets the current encoder position.
	//
	EQEP_setPosition(EQEP1_J12_BASE,0U);
	//
	// Disables the eQEP module unit timer.
	//
	EQEP_disableUnitTimer(EQEP1_J12_BASE);
	//
	// Disables the eQEP module watchdog timer.
	//
	EQEP_disableWatchdog(EQEP1_J12_BASE);
	//
	// Configures the quadrature modes in which the position count can be latched.
	//
	EQEP_setLatchMode(EQEP1_J12_BASE,(EQEP_LATCH_CNT_READ_BY_CPU|EQEP_LATCH_RISING_STROBE|EQEP_LATCH_RISING_INDEX));
	//
	// Set the quadrature mode adapter (QMA) module mode.
	//
	EQEP_setQMAModuleMode(EQEP1_J12_BASE,EQEP_QMA_MODE_BYPASS);
	//
	// Configures the mode in which the position counter is initialized.
	//
	EQEP_setPositionInitMode(EQEP1_J12_BASE,(EQEP_INIT_DO_NOTHING));
	//
	// Sets the software initialization of the encoder position counter.
	//
	EQEP_setSWPositionInit(EQEP1_J12_BASE,false);
	//
	// Sets the init value for the encoder position counter.
	//
	EQEP_setInitialPosition(EQEP1_J12_BASE,0U);
	//
	// Enables the eQEP module.
	//
	EQEP_enableModule(EQEP1_J12_BASE);
}
void EQEP2_J13_init(){
	//
	// Set the strobe input source of the eQEP module.
	//
	EQEP_setStrobeSource(EQEP2_J13_BASE,EQEP_STROBE_FROM_GPIO);
	//
	// Sets the polarity of the eQEP module's input signals.
	//
	EQEP_setInputPolarity(EQEP2_J13_BASE,false,false,false,false);
	//
	// Configures eQEP module's quadrature decoder unit.
	//
	EQEP_setDecoderConfig(EQEP2_J13_BASE, (EQEP_CONFIG_QUADRATURE | EQEP_CONFIG_2X_RESOLUTION | EQEP_CONFIG_NO_SWAP | EQEP_CONFIG_IGATE_DISABLE));
	//
	// Set the emulation mode of the eQEP module.
	//
	EQEP_setEmulationMode(EQEP2_J13_BASE,EQEP_EMULATIONMODE_STOPIMMEDIATELY);
	//
	// Configures eQEP module position counter unit.
	//
	EQEP_setPositionCounterConfig(EQEP2_J13_BASE,EQEP_POSITION_RESET_IDX,10000U);
	//
	// Sets the current encoder position.
	//
	EQEP_setPosition(EQEP2_J13_BASE,0U);
	//
	// Disables the eQEP module unit timer.
	//
	EQEP_disableUnitTimer(EQEP2_J13_BASE);
	//
	// Disables the eQEP module watchdog timer.
	//
	EQEP_disableWatchdog(EQEP2_J13_BASE);
	//
	// Configures the quadrature modes in which the position count can be latched.
	//
	EQEP_setLatchMode(EQEP2_J13_BASE,(EQEP_LATCH_CNT_READ_BY_CPU|EQEP_LATCH_RISING_STROBE|EQEP_LATCH_RISING_INDEX));
	//
	// Set the quadrature mode adapter (QMA) module mode.
	//
	EQEP_setQMAModuleMode(EQEP2_J13_BASE,EQEP_QMA_MODE_BYPASS);
	//
	// Configures the mode in which the position counter is initialized.
	//
	EQEP_setPositionInitMode(EQEP2_J13_BASE,(EQEP_INIT_DO_NOTHING));
	//
	// Sets the software initialization of the encoder position counter.
	//
	EQEP_setSWPositionInit(EQEP2_J13_BASE,false);
	//
	// Sets the init value for the encoder position counter.
	//
	EQEP_setInitialPosition(EQEP2_J13_BASE,0U);
	//
	// Enables the eQEP module.
	//
	EQEP_enableModule(EQEP2_J13_BASE);
}

//*****************************************************************************
//
// GPIO Configurations
//
//*****************************************************************************
void GPIO_init(){
	LED_R_init();
	LED_G_init();
	ENABLE_GATE_init();
	RESET_GATE_init();
	MONITOR_IO_init();
}

void LED_R_init(){
	GPIO_setPadConfig(LED_R, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(LED_R, GPIO_QUAL_SYNC);
	GPIO_setDirectionMode(LED_R, GPIO_DIR_MODE_OUT);
	GPIO_setControllerCore(LED_R, GPIO_CORE_CPU1);
}
void LED_G_init(){
	GPIO_setPadConfig(LED_G, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(LED_G, GPIO_QUAL_SYNC);
	GPIO_setDirectionMode(LED_G, GPIO_DIR_MODE_OUT);
	GPIO_setControllerCore(LED_G, GPIO_CORE_CPU1);
}
void ENABLE_GATE_init(){
	GPIO_setPadConfig(ENABLE_GATE, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(ENABLE_GATE, GPIO_QUAL_SYNC);
	GPIO_setDirectionMode(ENABLE_GATE, GPIO_DIR_MODE_OUT);
	GPIO_setControllerCore(ENABLE_GATE, GPIO_CORE_CPU1);
}
void RESET_GATE_init(){
	GPIO_setPadConfig(RESET_GATE, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(RESET_GATE, GPIO_QUAL_SYNC);
	GPIO_setDirectionMode(RESET_GATE, GPIO_DIR_MODE_OUT);
	GPIO_setControllerCore(RESET_GATE, GPIO_CORE_CPU1);
}
void MONITOR_IO_init(){
	GPIO_setPadConfig(MONITOR_IO, GPIO_PIN_TYPE_STD);
	GPIO_setQualificationMode(MONITOR_IO, GPIO_QUAL_SYNC);
	GPIO_setDirectionMode(MONITOR_IO, GPIO_DIR_MODE_OUT);
	GPIO_setControllerCore(MONITOR_IO, GPIO_CORE_CPU1);
}

//*****************************************************************************
//
// INTERRUPT Configurations
//
//*****************************************************************************
void INTERRUPT_init(){
	
	// Interrupt Settings for INT_IRIS_ADCA_1
	// ISR need to be defined for the registered interrupts
	Interrupt_register(INT_IRIS_ADCA_1, &MainISR);
	Interrupt_enable(INT_IRIS_ADCA_1);
	
	// Interrupt Settings for INT_IRIS_CAN_0
	// ISR need to be defined for the registered interrupts
	Interrupt_register(INT_IRIS_CAN_0, &INT_IRIS_CAN_0_ISR);
	Interrupt_disable(INT_IRIS_CAN_0);
	
	// Interrupt Settings for INT_IRIS_CAN_1
	// ISR need to be defined for the registered interrupts
	Interrupt_register(INT_IRIS_CAN_1, &INT_IRIS_CAN_1_ISR);
	Interrupt_disable(INT_IRIS_CAN_1);
	
	// Interrupt Settings for INT_IRIS_UART_USB_RX
	// ISR need to be defined for the registered interrupts
	Interrupt_register(INT_IRIS_UART_USB_RX, &INT_IRIS_UART_USB_RX_ISR);
	Interrupt_enable(INT_IRIS_UART_USB_RX);
}
//*****************************************************************************
//
// SCI Configurations
//
//*****************************************************************************
void SCI_init(){
	IRIS_UART_USB_init();
}

void IRIS_UART_USB_init(){
	SCI_clearInterruptStatus(IRIS_UART_USB_BASE, SCI_INT_RXFF | SCI_INT_TXFF | SCI_INT_FE | SCI_INT_OE | SCI_INT_PE | SCI_INT_RXERR | SCI_INT_RXRDY_BRKDT | SCI_INT_TXRDY);
	SCI_clearOverflowStatus(IRIS_UART_USB_BASE);
	SCI_resetTxFIFO(IRIS_UART_USB_BASE);
	SCI_resetRxFIFO(IRIS_UART_USB_BASE);
	SCI_resetChannels(IRIS_UART_USB_BASE);
	SCI_setConfig(IRIS_UART_USB_BASE, DEVICE_LSPCLK_FREQ, IRIS_UART_USB_BAUDRATE, (SCI_CONFIG_WLEN_8|SCI_CONFIG_STOP_ONE|SCI_CONFIG_PAR_NONE));
	SCI_disableLoopback(IRIS_UART_USB_BASE);
	SCI_performSoftwareReset(IRIS_UART_USB_BASE);
	SCI_enableInterrupt(IRIS_UART_USB_BASE, SCI_INT_RXFF);
	SCI_setFIFOInterruptLevel(IRIS_UART_USB_BASE, SCI_FIFO_TX0, SCI_FIFO_RX14);
	SCI_enableInterrupt(IRIS_UART_USB_BASE, SCI_INT_FE | SCI_INT_OE);
	SCI_enableFIFO(IRIS_UART_USB_BASE);
	SCI_enableModule(IRIS_UART_USB_BASE);
}

//*****************************************************************************
//
// SYNC Scheme Configurations
//
//*****************************************************************************
void SYNC_init(){
	SysCtl_setSyncOutputConfig(SYSCTL_SYNC_OUT_SRC_EPWM1SYNCOUT);
	//
	// For EPWM1, the sync input is: SYSCTL_SYNC_IN_SRC_EXTSYNCIN1
	//
	SysCtl_setSyncInputConfig(SYSCTL_SYNC_IN_EPWM4, SYSCTL_SYNC_IN_SRC_EPWM1SYNCOUT);
	SysCtl_setSyncInputConfig(SYSCTL_SYNC_IN_EPWM7, SYSCTL_SYNC_IN_SRC_EPWM1SYNCOUT);
	SysCtl_setSyncInputConfig(SYSCTL_SYNC_IN_ECAP1, SYSCTL_SYNC_IN_SRC_EPWM1SYNCOUT);
	SysCtl_setSyncInputConfig(SYSCTL_SYNC_IN_ECAP4, SYSCTL_SYNC_IN_SRC_EPWM1SYNCOUT);
	SysCtl_setSyncInputConfig(SYSCTL_SYNC_IN_ECAP6, SYSCTL_SYNC_IN_SRC_EPWM1SYNCOUT);
	//
	// SOCA
	//
	SysCtl_enableExtADCSOCSource(0);
	//
	// SOCB
	//
	SysCtl_enableExtADCSOCSource(0);
}
//*****************************************************************************
//
// SYSCTL Configurations
//
//*****************************************************************************
void SYSCTL_init(){
	//
    // sysctl initialization
	//

    SysCtl_disableMCD();


    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCA, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCB, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCB, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCB, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCC, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCC, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ADCC, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS1, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS2, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS2, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS2, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS3, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS3, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS3, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS4, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS4, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS4, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS5, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS5, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS5, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS6, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS6, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS6, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS7, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS7, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CMPSS7, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_DACA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_DACA, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_DACA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_DACB, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_DACB, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_DACB, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA1, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA2, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA2, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA2, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA3, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA3, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA3, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA4, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA4, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA4, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA5, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA5, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA5, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA6, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA6, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA6, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA7, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA7, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PGA7, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM1, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM2, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM2, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM2, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM3, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM3, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM3, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM4, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM4, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM4, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM5, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM5, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM5, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM6, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM6, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM6, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM7, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM7, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM7, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM8, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM8, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EPWM8, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EQEP1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EQEP1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EQEP1, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EQEP2, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EQEP2, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_EQEP2, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP1, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP2, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP2, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP2, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP3, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP3, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP3, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP4, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP4, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP4, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP5, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP5, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP5, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP6, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP6, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP6, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP7, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP7, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_ECAP7, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SDFM1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SDFM1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SDFM1, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB1, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB1, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB2, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB2, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB3, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB3, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB4, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLB4, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLA1PROMCRC, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CLA1PROMCRC, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SPIA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SPIA, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SPIA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SPIB, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SPIB, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_SPIB, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PMBUSA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PMBUSA, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_PMBUSA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_LINA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_LINA, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_LINA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CANA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CANA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CANB, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_CANB, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_FSIATX, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_FSIATX, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_FSIATX, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_FSIARX, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_FSIARX, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_FSIARX, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_HRPWMA, 
        SYSCTL_ACCESS_CPU1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_HRPWMA, 
        SYSCTL_ACCESS_CLA1, SYSCTL_ACCESS_FULL);
    SysCtl_setPeripheralAccessControl(SYSCTL_ACCESS_HRPWMA, 
        SYSCTL_ACCESS_DMA1, SYSCTL_ACCESS_FULL);

    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CLA1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_DMA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_TIMER0);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_TIMER1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_TIMER2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_HRPWM);
    SysCtl_disablePeripheral(SYSCTL_PERIPH_CLK_TBCLKSYNC);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM3);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM4);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM5);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM6);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM7);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EPWM8);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP3);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP4);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP5);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP6);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ECAP7);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EQEP1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_EQEP2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_SD1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_SCIA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_SCIB);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_SPIA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_SPIB);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_I2CA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CANA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CANB);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ADCA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ADCB);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_ADCC);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS3);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS4);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS5);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS6);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CMPSS7);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA3);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA4);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA5);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA6);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PGA7);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_DACA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_DACB);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CLB1);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CLB2);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CLB3);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_CLB4);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_FSITXA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_FSIRXA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_LINA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_PMBUSA);
    SysCtl_enablePeripheral(SYSCTL_PERIPH_CLK_DCC0);

}

