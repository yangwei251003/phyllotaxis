#include "phyllo.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static phyllo_dsp dsp;
static float samples[PHYLLO_FFT_N];
static uint16_t pwm[PHYLLO_PWM_SLOTS+1u];
static void analyze_test(void) {
    phyllo_features f;
    phyllo_dsp_init(&dsp);
    assert(phyllo_analyze(&dsp,samples,&f));
    assert(f.rms==0&&f.flux==0&&!f.onset);
    for(size_t i=0;i<PHYLLO_FFT_N;i++)samples[i]=.5f*sinf(2*3.14159265358979323846f*32*(float)i/512)+.2f;
    assert(phyllo_analyze(&dsp,samples,&f));
    assert(fabsf(f.rms-.35355339f)<.00001f&&f.peak_bin==32u);
    assert(f.onset);
    assert(f.bands[3]>.1f);
    for(size_t b=0;b<PHYLLO_BANDS;b++)if(b!=3u)assert(f.bands[b]<.001f);
    /* A stable tone should not repeatedly trigger after its initial onset. */
    for(int i=0;i<20;i++){assert(phyllo_analyze(&dsp,samples,&f));assert(!f.onset);}
    phyllo_dsp old=dsp;phyllo_features oldout=f;
    float invalid[]={NAN,INFINITY,1.0001f,-1.0001f};
    for(size_t j=0;j<sizeof(invalid)/sizeof(invalid[0]);j++) {
        samples[12]=invalid[j];
        assert(!phyllo_analyze(&dsp,samples,&f));
        assert(!memcmp(&old,&dsp,sizeof(dsp))&&!memcmp(&oldout,&f,sizeof(f)));
    }
    assert(!phyllo_analyze(&dsp,NULL,&f));
    assert(!memcmp(&old,&dsp,sizeof(dsp))&&!memcmp(&oldout,&f,sizeof(f)));
    memset(samples,0,sizeof(samples));
    assert(phyllo_analyze(&dsp,samples,&f));assert(!f.onset&&f.rms==0);
    /* Compare selected complex FFT bins with an independent direct DFT. */
    for(size_t i=0;i<PHYLLO_FFT_N;i++)samples[i]=.18f*sinf(.071f*(float)i)+.12f*cosf(.62f*(float)i);
    assert(phyllo_analyze(&dsp,samples,&f));
    double mean=0;for(size_t i=0;i<PHYLLO_FFT_N;i++)mean+=samples[i];mean/=PHYLLO_FFT_N;
    for(size_t k=0;k<PHYLLO_FFT_N;k+=7u){
        double re=0,im=0;
        for(size_t i=0;i<PHYLLO_FFT_N;i++){
            double a=-2*3.14159265358979323846*(double)(k*i)/PHYLLO_FFT_N;
            double v=((double)samples[i]-mean)*dsp.window[i];re+=v*cos(a);im+=v*sin(a);
        }
        assert(fabs(re-dsp.re[k])<.001&&fabs(im-dsp.im[k])<.001);
    }
}
static void onset_boundary_test(void) {
    phyllo_features f;phyllo_dsp_init(&dsp);
    for(unsigned frame=0;frame<=6;frame++) {
        int tone=frame==1||frame==3||frame==6;
        for(size_t i=0;i<PHYLLO_FFT_N;i++)samples[i]=tone?.5f*sinf(2*3.14159265358979323846f*32*(float)i/512):0;
        assert(phyllo_analyze(&dsp,samples,&f));
        assert(f.onset==(frame==1||frame==6));
    }
}
static void codec_test(void) {
    assert(phyllo_i2s24(0,0)==0);
    assert(phyllo_i2s24(0x8000,0)==-1);
    assert(phyllo_i2s24(0x7fff,0xff00)>.99999f);
    assert(phyllo_i2s24(0xffff,0xff00)==-1.0f/8388608.0f);
    assert(phyllo_i2s24(0x1234,0x5600)==phyllo_i2s24(0x1234,0x56ff));
    phyllo_rgb rgb[2]={{0x80,0x01,0x00},{0x00,0xff,0x80}};uint16_t chain[2]={1,0};
    const size_t len=2*24u+PHYLLO_RESET_SLOTS;
    pwm[len]=0xaaaa;
    assert(phyllo_encode(rgb,2,chain,pwm,len)==len&&pwm[len]==0xaaaa);
    uint32_t expected[2]={0xff0080,0x018000};
    for(size_t i=0;i<2;i++)for(unsigned bit=0;bit<24;bit++)assert(pwm[i*24+bit]==((expected[i]&(1u<<(23u-bit)))?54:28));
    for(size_t i=48;i<len;i++)assert(pwm[i]==0);
    uint16_t saved[PHYLLO_PWM_SLOTS+1u];memcpy(saved,pwm,sizeof(pwm));
    chain[1]=1;
    assert(!phyllo_encode(rgb,2,chain,pwm,len)&&!memcmp(saved,pwm,sizeof(pwm)));
    chain[1]=0;assert(!phyllo_encode(rgb,2,chain,pwm,len-1u)&&!memcmp(saved,pwm,sizeof(pwm)));
}
static void timing_current_test(void) {
    const double tick=1e9/PHYLLO_TIMER_HZ;
    const double t0h=PHYLLO_PWM_ZERO*tick,t0l=(PHYLLO_PWM_PERIOD-PHYLLO_PWM_ZERO)*tick;
    const double t1h=PHYLLO_PWM_ONE*tick,t1l=(PHYLLO_PWM_PERIOD-PHYLLO_PWM_ONE)*tick;
    assert(t0h>=220&&t0h<=380&&t0l>=580&&t0l<=1000);
    assert(t1h>=580&&t1h<=1000&&t1l>=580&&t1l<=1000);
    assert(PHYLLO_PWM_PERIOD*tick>=1250&&PHYLLO_RESET_SLOTS*PHYLLO_PWM_PERIOD*tick>280000);
    phyllo_rgb white[PHYLLO_LED_MAX];
    for(size_t i=0;i<PHYLLO_LED_MAX;i++)white[i]=(phyllo_rgb){255,255,255};
    float scale=phyllo_limit_current(white,PHYLLO_LED_MAX,2000);assert(scale>0&&scale<1);
    float current=PHYLLO_LED_MAX;
    for(size_t i=0;i<PHYLLO_LED_MAX;i++)current+=(white[i].r+white[i].g+white[i].b)*20.0f/255.0f;
    assert(current<=2000);
    assert(phyllo_limit_current(white,PHYLLO_LED_MAX,PHYLLO_LED_MAX)==0);
    for(size_t i=0;i<PHYLLO_LED_MAX;i++)white[i]=(phyllo_rgb){255,255,255};
    assert(phyllo_limit_current(white,PHYLLO_LED_MAX,9000)==1);
    assert(phyllo_limit_current(white,PHYLLO_LED_MAX,PHYLLO_LED_MAX-.1f)==-2);
    for(size_t i=0;i<PHYLLO_LED_MAX;i++)assert(!white[i].r&&!white[i].g&&!white[i].b);
}
static void render_test(void) {
    phyllo_point p[144];phyllo_rgb out[144],saved[144];
    for(size_t i=0;i<144;i++)p[i]=(phyllo_point){76*sqrtf(((float)i+.5f)/144),(float)i*2.399963229728653f};
    phyllo_signal s={0};phyllo_render_config c={PHYLLO_SPECTRUM,PHYLLO_BOTANICAL,.22f,1};
    assert(phyllo_render(p,144,1,&s,&c,out));
    for(size_t i=0;i<144;i++)assert(!out[i].r&&!out[i].g&&!out[i].b);
    s.level=.5f;s.beat=1;for(size_t i=0;i<7;i++)s.bands[i]=1;
    for(int mode=PHYLLO_SPIRAL;mode<=PHYLLO_PULSE;mode++)for(int palette=PHYLLO_BOTANICAL;palette<=PHYLLO_OCEAN;palette++) {
        c.mode=(phyllo_mode)mode;c.palette=(phyllo_palette)palette;c.brightness=10;
        assert(phyllo_render(p,144,3.5f,&s,&c,out));
        for(size_t i=0;i<144;i++)assert(out[i].r<=89&&out[i].g<=89&&out[i].b<=89);
    }
    memcpy(saved,out,sizeof(out));s.bands[3]=NAN;
    assert(!phyllo_render(p,144,1,&s,&c,out)&&!memcmp(saved,out,sizeof(out)));
}
int main(void){analyze_test();onset_boundary_test();codec_test();timing_current_test();render_test();printf("PASS: FFT/DFT, silence, DC/RMS, 1kHz band, first onset and 80ms boundary, atomic invalid input, I2S sign/padding, GRB/permutation/bounds, V6 timing, attainable current budgets, 3 effects/3 palettes\nDSP state: %u bytes\n",(unsigned)sizeof(dsp));return 0;}
