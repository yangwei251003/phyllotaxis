#include "board.h"

static volatile uint32_t busy;
static uint32_t started_at;
/* DMA owns caller's buffer until busy becomes zero. No CC1 DMA request. */
void led_driver_stop(void) {
    __HAL_TIM_DISABLE_DMA(&htim1,TIM_DMA_UPDATE);
    CLEAR_BIT(TIM1->CR1,TIM_CR1_CEN);
    CLEAR_BIT(TIM1->CCMR1,TIM_CCMR1_OC1PE);
    TIM1->CCR1=0;
    SET_BIT(TIM1->CCMR1,TIM_CCMR1_OC1PE);
    (void)HAL_TIM_PWM_Stop(&htim1,TIM_CHANNEL_1);
    __DMB();busy=0;
}
static void completed(DMA_HandleTypeDef *dma) {
    if(dma==&hdma_led) led_driver_stop();
}
static void failed(DMA_HandleTypeDef *dma) {
    (void)dma;board_fault(30);
}
void led_driver_init(void) {
    hdma_led.XferCpltCallback=completed;hdma_led.XferErrorCallback=failed;
    hdma_led.XferHalfCpltCallback=NULL;
    led_driver_stop();
}
uint32_t led_driver_busy(void) {
    if(busy&&(uint32_t)(HAL_GetTick()-started_at)>20u) board_fault(31);
    return busy;
}
int led_driver_submit(const uint16_t *slots,size_t count) {
    if(!slots||count!=LED_DRIVER_SLOTS||led_driver_busy())return 0;
    /* Start at zero duty: enabling MOE before CEN cannot stretch the first high
       pulse. The first data bit begins only at a running timer update. */
    for(size_t i=0;i<LED_LEADING_SLOTS;i++)if(slots[i]!=0u)return 0;
    /* At TC, last two slots are not completely emitted. 238 complete reset
       periods = 306us; require all 240 zeros, including both pipeline slots. */
    for(size_t i=count-PHYLLO_RESET_SLOTS;i<count;i++)if(slots[i]!=0u)return 0;
    for(size_t i=LED_LEADING_SLOTS;i<count-PHYLLO_RESET_SLOTS;i++)
        if(slots[i]!=PHYLLO_PWM_ZERO&&slots[i]!=PHYLLO_PWM_ONE)return 0;
    __HAL_TIM_DISABLE_DMA(&htim1,TIM_DMA_UPDATE);
    CLEAR_BIT(TIM1->CR1,TIM_CR1_CEN);
    /* Seed the active first slot, then the preloaded second slot. No UG after
       this point: it would advance the preload before the first bit. */
    CLEAR_BIT(TIM1->CCMR1,TIM_CCMR1_OC1PE);TIM1->CCR1=slots[0];
    SET_BIT(TIM1->CCMR1,TIM_CCMR1_OC1PE);TIM1->CCR1=slots[1];
    TIM1->CNT=0;TIM1->SR=0;
    if(HAL_DMA_Start_IT(&hdma_led,(uint32_t)(slots+2),(uint32_t)&TIM1->CCR1,(uint32_t)(count-2u))!=HAL_OK)return 0;
    started_at=HAL_GetTick();__DMB();busy=1;
    __HAL_TIM_ENABLE_DMA(&htim1,TIM_DMA_UPDATE);
    if(HAL_TIM_PWM_Start(&htim1,TIM_CHANNEL_1)!=HAL_OK)board_fault(32);
    return 1;
}
