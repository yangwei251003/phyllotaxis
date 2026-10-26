#ifndef PHYLLO_H
#define PHYLLO_H
#include <stdint.h>
#include <stddef.h>

/* Portable candidate core. No pin assignment, clocks, HAL or flash operation. */
#define PHYLLO_FFT_N 512u
#define PHYLLO_BANDS 7u
#define PHYLLO_FS 16000u
#define PHYLLO_HOP 256u
#define PHYLLO_LED_MAX 144u
#define PHYLLO_TIMER_HZ 84000000u
#define PHYLLO_PWM_PERIOD 108u
#define PHYLLO_PWM_ZERO 28u
#define PHYLLO_PWM_ONE 54u
#define PHYLLO_RESET_SLOTS 240u
#define PHYLLO_PWM_SLOTS (PHYLLO_LED_MAX * 24u + PHYLLO_RESET_SLOTS)

typedef struct { uint8_t r,g,b; } phyllo_rgb;
typedef struct { float radius, angle; } phyllo_point;
typedef enum { PHYLLO_SPIRAL, PHYLLO_SPECTRUM, PHYLLO_PULSE } phyllo_mode;
typedef enum { PHYLLO_BOTANICAL, PHYLLO_EMBER, PHYLLO_OCEAN } phyllo_palette;
typedef struct { float level,bands[PHYLLO_BANDS],beat; } phyllo_signal;
typedef struct { phyllo_mode mode;phyllo_palette palette;float brightness,gain; } phyllo_render_config;
typedef struct {
    float re[PHYLLO_FFT_N], im[PHYLLO_FFT_N], window[PHYLLO_FFT_N];
    float previous[PHYLLO_FFT_N/2u+1u];
    float window_sum, flux_ema;
    uint32_t frames, last_onset;
    uint8_t onset_seen;
} phyllo_dsp;
typedef struct {
    float rms, bands[PHYLLO_BANDS], flux;
    uint16_t peak_bin;
    uint8_t onset;
} phyllo_features;

void phyllo_dsp_init(phyllo_dsp *state);
/* State must first be initialized with phyllo_dsp_init.
   512 normalized mono samples; successive valid calls advance 256 samples.
   Nonfinite samples are rejected before state changes. */
int phyllo_analyze(phyllo_dsp *state,const float *mono,phyllo_features *out);
/* 24-bit I2S sample in bits31:8; use unsigned arithmetic for portable sign extension. */
float phyllo_i2s24(uint16_t high,uint16_t low);
/* Same spatial/color formulas as web/engine.js for the same normalized inputs.
   Hardware brightness is capped at .35. Failure leaves output intact. */
int phyllo_render(const phyllo_point *points,size_t count,float time_s,
                  const phyllo_signal *signal,const phyllo_render_config *config,phyllo_rgb *out);
/* In-place conservative software model, not a physical overcurrent protector.
   Budget is LED-only, excluding controller/microphone. Returns -1 for invalid
   arguments (unchanged), -2 if budget is below modeled idle (pixels blacked out,
   budget NOT met; caller must report a fault), else scale [0,1]. */
float phyllo_limit_current(phyllo_rgb *rgb,size_t count,float budget_ma);
/* chain[i] identifies a unique geometry index. Invalid mappings leave output intact. */
size_t phyllo_encode(const phyllo_rgb *rgb,size_t count,const uint16_t *chain,
                     uint16_t *out,size_t capacity);
#endif
