#ifndef PHYLLO_BOARD_H
#define PHYLLO_BOARD_H
#include "stm32f4xx_hal.h"
#include "phyllo.h"
/* Candidate assignments only; received board and manufactured panel unverified. */
#define AUDIO_DMA_WORDS (PHYLLO_HOP * 8u)
#define LED_LEADING_SLOTS 2u
#define LED_DRIVER_SLOTS (PHYLLO_PWM_SLOTS+LED_LEADING_SLOTS)
extern I2S_HandleTypeDef hi2s2;
extern TIM_HandleTypeDef htim1;
extern UART_HandleTypeDef huart2;
extern DMA_HandleTypeDef hdma_audio,hdma_led;
void board_init(void);
void board_fault(uint32_t code);
void led_driver_init(void);
int led_driver_submit(const uint16_t *slots,size_t count);
void led_driver_stop(void);
uint32_t led_driver_busy(void);
#endif
