#include "board.h"
#include "layout_generated.h"
#include <math.h>
#include <string.h>

#define HOP_WORDS (PHYLLO_HOP*4u)
#define QUEUE_SLOTS 4u
static uint16_t audio_dma[AUDIO_DMA_WORDS];
static uint16_t audio_queue[QUEUE_SLOTS][HOP_WORDS];
static uint32_t queue_seq[QUEUE_SLOTS];
static volatile uint32_t producer,consumer,audio_blocks,audio_dropped,audio_errors;
static volatile uint32_t last_audio_ms;
static float overlap[PHYLLO_FFT_N];
static phyllo_dsp dsp;
static phyllo_features features;
static phyllo_signal signal_state;
static phyllo_rgb pixels[PHYLLO_LED_MAX];
static uint16_t pwm[LED_DRIVER_SLOTS];
static phyllo_render_config config={PHYLLO_SPIRAL,PHYLLO_BOTANICAL,.15f,1.5f};
static uint32_t led_frames,analysis_max_cycles,previous_seq,window_hops;

/* Single producer (DMA ISR) / single consumer. A queue slot is not reused
   until the consumer has converted it. Copy prevents live-DMA overwrite. */
static void capture_half(size_t offset) {
    uint32_t head=producer,next=(head+1u)%QUEUE_SLOTS;
    ++audio_blocks;last_audio_ms=HAL_GetTick();
    /* SEN0526/MSM261S4030H0R power-up maximum is 20ms (datasheet).
       Keep seventeen 16ms blocks (272ms) as conservative startup/transient
       discard policy; this is not a required microphone clock count. */
    if(audio_blocks<=17u)return;
    if(next==consumer){++audio_dropped;return;}
    memcpy(audio_queue[head],audio_dma+offset,HOP_WORDS*sizeof(uint16_t));
    queue_seq[head]=audio_blocks;__DMB();producer=next;
}
void HAL_I2S_RxHalfCpltCallback(I2S_HandleTypeDef *h){if(h==&hi2s2)capture_half(0);}
void HAL_I2S_RxCpltCallback(I2S_HandleTypeDef *h){if(h==&hi2s2)capture_half(HOP_WORDS);}
void HAL_I2S_ErrorCallback(I2S_HandleTypeDef *h){if(h==&hi2s2){++audio_errors;board_fault(40);}}
static float unit(float x){return fmaxf(0,fminf(x,1));}
static int consume_audio(void) {
    uint32_t tail=consumer;
    if(tail==producer)return 0;
    __DMB();uint32_t seq=queue_seq[tail];
    if(window_hops&&seq!=previous_seq+1u){window_hops=0;memset(overlap,0,sizeof(overlap));phyllo_dsp_init(&dsp);}
    previous_seq=seq;
    memmove(overlap,overlap+PHYLLO_HOP,PHYLLO_HOP*sizeof(float));
    /* Candidate SEN0526 SEL explicitly wired to GND => first (left) slot.
       The module's 100k resistor pulls down DOUT, not SEL. */
    for(size_t i=0;i<PHYLLO_HOP;i++)overlap[i+PHYLLO_HOP]=phyllo_i2s24(audio_queue[tail][4u*i],audio_queue[tail][4u*i+1u]);
    __DMB();consumer=(tail+1u)%QUEUE_SLOTS;
    if(window_hops<2u)++window_hops;
    if(window_hops==2u) {
        uint32_t start=DWT->CYCCNT;
        if(!phyllo_analyze(&dsp,overlap,&features))board_fault(41);
        uint32_t elapsed=DWT->CYCCNT-start;
        if(elapsed>analysis_max_cycles)analysis_max_cycles=elapsed;
        /* Fixed sensitivity, no claim of sound pressure calibration. */
        float level=unit(features.rms*24.0f);
        signal_state.level=.65f*signal_state.level+.35f*level;
        for(size_t b=0;b<PHYLLO_BANDS;b++)signal_state.bands[b]=.55f*signal_state.bands[b]+.45f*unit(features.bands[b]*40.0f);
        signal_state.beat=features.onset?1.0f:signal_state.beat*.88f;
    }
    return 1;
}
typedef struct {uint32_t changed,pressed;uint8_t raw,stable,long_done;} key_state;
static key_state keys[2]={{0,0,1,1,0},{0,0,1,1,0}};
static void buttons(uint32_t now) {
    for(unsigned k=0;k<2u;k++) {
        key_state *s=&keys[k];
        uint8_t raw=(uint8_t)(HAL_GPIO_ReadPin(GPIOB,k==0u?GPIO_PIN_0:GPIO_PIN_1)==GPIO_PIN_SET);
        if(raw!=s->raw){s->raw=raw;s->changed=now;}
        if(s->stable!=raw&&(uint32_t)(now-s->changed)>=25u) {
            s->stable=raw;
            if(!raw){s->pressed=now;s->long_done=0;}
            else if(!s->long_done) {
                if(k==0u)config.mode=(phyllo_mode)(((unsigned)config.mode+1u)%3u);
                else config.palette=(phyllo_palette)(((unsigned)config.palette+1u)%3u);
            }
        }
        if(!s->stable&&!s->long_done&&(uint32_t)(now-s->pressed)>=700u) {
            if(k==0u)config.brightness=config.brightness>=.34f?.05f:config.brightness+.05f;
            else config.gain=config.gain>=3.9f?.5f:config.gain+.5f;
            s->long_done=1;
        }
    }
}
/* Bounded integer-only telemetry; no libc stdio, heap or float formatter. */
static void append_text(char *out,size_t capacity,size_t *used,const char *text) {
    while(*text&&*used<capacity-1u)out[(*used)++]=*text++;
    out[*used]='\0';
}
static void append_number(char *out,size_t capacity,size_t *used,uint32_t value) {
    char digits[10];size_t n=0;
    do{digits[n++]=(char)('0'+value%10u);value/=10u;}while(value&&n<sizeof(digits));
    while(n&&*used<capacity-1u)out[(*used)++]=digits[--n];
    out[*used]='\0';
}
static void report(uint32_t now) {
    char line[256];size_t used=0;
    const char *names[]={"ms","blocks","drop","errors","frames","peak","rms_ppm","fft_cycles_max"};
    uint32_t values[]={now,audio_blocks,audio_dropped,audio_errors,led_frames,
        features.peak_bin,(uint32_t)(features.rms*1000000.0f),analysis_max_cycles};
    append_text(line,sizeof(line),&used,"{\"type\":\"phyllo\",\"candidate\":true");
    for(size_t i=0;i<sizeof(values)/sizeof(values[0]);i++) {
        append_text(line,sizeof(line),&used,",\"");append_text(line,sizeof(line),&used,names[i]);
        append_text(line,sizeof(line),&used,"\":");append_number(line,sizeof(line),&used,values[i]);
    }
    append_text(line,sizeof(line),&used,"}\r\n");
    (void)HAL_UART_Transmit(&huart2,(uint8_t*)line,(uint16_t)used,30);
}
int main(void) {
    board_init();phyllo_dsp_init(&dsp);
    CoreDebug->DEMCR|=CoreDebug_DEMCR_TRCENA_Msk;DWT->CYCCNT=0;DWT->CTRL|=DWT_CTRL_CYCCNTENA_Msk;
    HAL_Delay(100); /* Supply settling; the separate discard policy is above. */
    if(phyllo_encode(pixels,PHYLLO_LED_MAX,led_chain,pwm+LED_LEADING_SLOTS,PHYLLO_PWM_SLOTS)!=PHYLLO_PWM_SLOTS)board_fault(50);
    HAL_GPIO_WritePin(GPIOB,GPIO_PIN_5,GPIO_PIN_SET);
    if(!led_driver_submit(pwm,LED_DRIVER_SLOTS))board_fault(51);
    last_audio_ms=HAL_GetTick();
    /* 1024 24-bit channel words => 2048 uint16_t DMA transfers. */
    if(HAL_I2S_Receive_DMA(&hi2s2,audio_dma,PHYLLO_HOP*4u)!=HAL_OK)board_fault(52);
    uint32_t last_frame=0,last_report=0;
    for(;;) {
        if(__HAL_I2S_GET_FLAG(&hi2s2,I2S_FLAG_OVR)){++audio_errors;board_fault(42);}
        while(consume_audio()){}
        uint32_t now=HAL_GetTick();buttons(now);
        if((uint32_t)(now-last_audio_ms)>500u)board_fault(53);
        if(!led_driver_busy()&&(uint32_t)(now-last_frame)>=33u) {
            last_frame=now;
            if(!phyllo_render(led_points,PHYLLO_LED_MAX,(float)now*.001f,&signal_state,&config,pixels))board_fault(54);
            if(phyllo_limit_current(pixels,PHYLLO_LED_MAX,2500.0f)<0)board_fault(55);
            if(phyllo_encode(pixels,PHYLLO_LED_MAX,led_chain,pwm+LED_LEADING_SLOTS,PHYLLO_PWM_SLOTS)!=PHYLLO_PWM_SLOTS)board_fault(56);
            if(!led_driver_submit(pwm,LED_DRIVER_SLOTS))board_fault(57);
            ++led_frames;
        }
        if((uint32_t)(now-last_report)>=1000u) {
            last_report=now;report(now);
        }
        __WFI();
    }
}
