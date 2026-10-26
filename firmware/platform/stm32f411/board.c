#include "board.h"

I2S_HandleTypeDef hi2s2;
TIM_HandleTypeDef htim1;
UART_HandleTypeDef huart2;
DMA_HandleTypeDef hdma_audio,hdma_led;
volatile uint32_t phyllo_fault_code;
/* Vendor Reset_Handler invokes newlib's constructor dispatcher. This C-only
   image has no host process/startup/exit or dynamic initialization. */
void _init(void){}
void _fini(void){}

void board_fault(uint32_t code) {
    __disable_irq();
    phyllo_fault_code=code;
    __HAL_RCC_GPIOB_CLK_ENABLE();
    GPIOB->BSRR=(uint32_t)GPIO_PIN_5<<16u;
    if(htim1.Instance==TIM1) led_driver_stop();
    for(;;) __NOP();
}
static void require_ok(HAL_StatusTypeDef status,uint32_t code) {
    if(status!=HAL_OK) board_fault(code);
}
static void clocks(void) {
    RCC_OscInitTypeDef osc={0};
    RCC_ClkInitTypeDef clk={0};
    RCC_PeriphCLKInitTypeDef peripheral={0};
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);
    osc.OscillatorType=RCC_OSCILLATORTYPE_HSE;
    osc.HSEState=RCC_HSE_ON;
    osc.PLL.PLLState=RCC_PLL_ON;osc.PLL.PLLSource=RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM=25;osc.PLL.PLLN=168;osc.PLL.PLLP=RCC_PLLP_DIV2;osc.PLL.PLLQ=7;
    require_ok(HAL_RCC_OscConfig(&osc),1);
    clk.ClockType=RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource=RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider=RCC_SYSCLK_DIV1;clk.APB1CLKDivider=RCC_HCLK_DIV2;clk.APB2CLKDivider=RCC_HCLK_DIV1;
    require_ok(HAL_RCC_ClockConfig(&clk,FLASH_LATENCY_2),2);
    peripheral.PeriphClockSelection=RCC_PERIPHCLK_I2S;
    peripheral.PLLI2S.PLLI2SM=25;peripheral.PLLI2S.PLLI2SN=256;peripheral.PLLI2S.PLLI2SR=5;
    require_ok(HAL_RCCEx_PeriphCLKConfig(&peripheral),3);
    __HAL_RCC_I2S_CONFIG(RCC_I2SCLKSOURCE_PLLI2S);
    if(HAL_RCC_GetHCLKFreq()!=PHYLLO_TIMER_HZ) board_fault(4);
}
static void pins(void) {
    GPIO_InitTypeDef pin={0};
    __HAL_RCC_GPIOA_CLK_ENABLE();__HAL_RCC_GPIOB_CLK_ENABLE();
    /* Active-high enable drives the buffer's OE pull-down NMOS, never LED GND.
       Its gate pulldown and buffer OE pullup keep DATA disabled at reset. */
    HAL_GPIO_WritePin(GPIOB,GPIO_PIN_5,GPIO_PIN_RESET);
    pin.Pin=GPIO_PIN_5;pin.Mode=GPIO_MODE_OUTPUT_PP;pin.Pull=GPIO_PULLDOWN;pin.Speed=GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB,&pin);
    pin.Pin=GPIO_PIN_0|GPIO_PIN_1;pin.Mode=GPIO_MODE_INPUT;pin.Pull=GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB,&pin);
    pin.Pin=GPIO_PIN_8;pin.Mode=GPIO_MODE_AF_PP;pin.Pull=GPIO_PULLDOWN;
    pin.Speed=GPIO_SPEED_FREQ_VERY_HIGH;pin.Alternate=GPIO_AF1_TIM1;HAL_GPIO_Init(GPIOA,&pin);
    pin.Pin=GPIO_PIN_12|GPIO_PIN_13|GPIO_PIN_15;pin.Alternate=GPIO_AF5_SPI2;pin.Pull=GPIO_NOPULL;
    HAL_GPIO_Init(GPIOB,&pin);
    pin.Pin=GPIO_PIN_2|GPIO_PIN_3;pin.Alternate=GPIO_AF7_USART2;pin.Pull=GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA,&pin);
}
static void peripherals(void) {
    __HAL_RCC_DMA1_CLK_ENABLE();__HAL_RCC_DMA2_CLK_ENABLE();
    __HAL_RCC_SPI2_CLK_ENABLE();__HAL_RCC_TIM1_CLK_ENABLE();__HAL_RCC_USART2_CLK_ENABLE();
    hdma_audio.Instance=DMA1_Stream3;hdma_audio.Init.Channel=DMA_CHANNEL_0;
    hdma_audio.Init.Direction=DMA_PERIPH_TO_MEMORY;
    hdma_audio.Init.PeriphInc=DMA_PINC_DISABLE;hdma_audio.Init.MemInc=DMA_MINC_ENABLE;
    hdma_audio.Init.PeriphDataAlignment=DMA_PDATAALIGN_HALFWORD;hdma_audio.Init.MemDataAlignment=DMA_MDATAALIGN_HALFWORD;
    hdma_audio.Init.Mode=DMA_CIRCULAR;hdma_audio.Init.Priority=DMA_PRIORITY_VERY_HIGH;
    hdma_audio.Init.FIFOMode=DMA_FIFOMODE_DISABLE;
    require_ok(HAL_DMA_Init(&hdma_audio),10);
    hi2s2.Instance=SPI2;hi2s2.Init.Mode=I2S_MODE_MASTER_RX;
    hi2s2.Init.Standard=I2S_STANDARD_PHILIPS;hi2s2.Init.DataFormat=I2S_DATAFORMAT_24B;
    hi2s2.Init.MCLKOutput=I2S_MCLKOUTPUT_DISABLE;hi2s2.Init.AudioFreq=I2S_AUDIOFREQ_16K;
    hi2s2.Init.CPOL=I2S_CPOL_LOW;hi2s2.Init.ClockSource=I2S_CLOCK_PLL;
    hi2s2.Init.FullDuplexMode=I2S_FULLDUPLEXMODE_DISABLE;
    __HAL_LINKDMA(&hi2s2,hdmarx,hdma_audio);
    require_ok(HAL_I2S_Init(&hi2s2),11);
    /* Exact nominal 51.2MHz / 50 / 64; inspect at runtime as well as compile. */
    if((SPI2->I2SPR&(SPI_I2SPR_I2SDIV|SPI_I2SPR_ODD|SPI_I2SPR_MCKOE))!=25u) board_fault(12);
    if(HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_I2S)!=51200000u||
       !__HAL_RCC_GET_FLAG(RCC_FLAG_PLLI2SRDY)||(RCC->CFGR&RCC_CFGR_I2SSRC))board_fault(17);
    hdma_led.Instance=DMA2_Stream5;hdma_led.Init.Channel=DMA_CHANNEL_6;
    hdma_led.Init.Direction=DMA_MEMORY_TO_PERIPH;
    hdma_led.Init.PeriphInc=DMA_PINC_DISABLE;hdma_led.Init.MemInc=DMA_MINC_ENABLE;
    hdma_led.Init.PeriphDataAlignment=DMA_PDATAALIGN_HALFWORD;hdma_led.Init.MemDataAlignment=DMA_MDATAALIGN_HALFWORD;
    hdma_led.Init.Mode=DMA_NORMAL;hdma_led.Init.Priority=DMA_PRIORITY_HIGH;
    hdma_led.Init.FIFOMode=DMA_FIFOMODE_DISABLE;
    require_ok(HAL_DMA_Init(&hdma_led),13);
    htim1.Instance=TIM1;htim1.Init.Prescaler=0;htim1.Init.CounterMode=TIM_COUNTERMODE_UP;
    htim1.Init.Period=PHYLLO_PWM_PERIOD-1u;htim1.Init.ClockDivision=TIM_CLOCKDIVISION_DIV1;
    htim1.Init.RepetitionCounter=0;htim1.Init.AutoReloadPreload=TIM_AUTORELOAD_PRELOAD_DISABLE;
    require_ok(HAL_TIM_PWM_Init(&htim1),14);
    TIM_OC_InitTypeDef oc={0};
    oc.OCMode=TIM_OCMODE_PWM1;oc.Pulse=0;oc.OCPolarity=TIM_OCPOLARITY_HIGH;
    oc.OCNPolarity=TIM_OCNPOLARITY_HIGH;oc.OCFastMode=TIM_OCFAST_DISABLE;
    oc.OCIdleState=TIM_OCIDLESTATE_RESET;oc.OCNIdleState=TIM_OCNIDLESTATE_RESET;
    require_ok(HAL_TIM_PWM_ConfigChannel(&htim1,&oc,TIM_CHANNEL_1),15);
    __HAL_LINKDMA(&htim1,hdma[TIM_DMA_ID_UPDATE],hdma_led);
    /* Keep inactive output low with advanced timer output disabled. */
    SET_BIT(TIM1->BDTR,TIM_BDTR_OSSI|TIM_BDTR_OSSR);
    huart2.Instance=USART2;huart2.Init.BaudRate=115200;
    huart2.Init.WordLength=UART_WORDLENGTH_8B;huart2.Init.StopBits=UART_STOPBITS_1;
    huart2.Init.Parity=UART_PARITY_NONE;huart2.Init.Mode=UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl=UART_HWCONTROL_NONE;huart2.Init.OverSampling=UART_OVERSAMPLING_16;
    require_ok(HAL_UART_Init(&huart2),16);
    HAL_NVIC_SetPriority(DMA1_Stream3_IRQn,1,0);HAL_NVIC_EnableIRQ(DMA1_Stream3_IRQn);
    HAL_NVIC_SetPriority(DMA2_Stream5_IRQn,2,0);HAL_NVIC_EnableIRQ(DMA2_Stream5_IRQn);
}
void board_init(void) {HAL_Init();clocks();pins();peripherals();led_driver_init();}
void DMA1_Stream3_IRQHandler(void){HAL_DMA_IRQHandler(&hdma_audio);}
void DMA2_Stream5_IRQHandler(void){HAL_DMA_IRQHandler(&hdma_led);}
void SysTick_Handler(void){HAL_IncTick();}
void NMI_Handler(void){board_fault(90);}
void HardFault_Handler(void){board_fault(91);}
void MemManage_Handler(void){board_fault(92);}
void BusFault_Handler(void){board_fault(93);}
void UsageFault_Handler(void){board_fault(94);}
