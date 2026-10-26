#include "phyllo.h"
#include <math.h>
#include <string.h>
#define PI_F 3.14159265358979323846f

void phyllo_dsp_init(phyllo_dsp *s) {
    if (!s) return;
    memset(s,0,sizeof(*s));
    for (size_t i=0;i<PHYLLO_FFT_N;i++) {
        s->window[i]=0.5f-0.5f*cosf(2.0f*PI_F*(float)i/(float)(PHYLLO_FFT_N-1u));
        s->window_sum+=s->window[i];
    }
}
static void fft(phyllo_dsp *s) {
    size_t j=0;
    for (size_t i=1;i<PHYLLO_FFT_N;i++) {
        size_t bit=PHYLLO_FFT_N>>1u;
        for (;j&bit;bit>>=1u) j^=bit;
        j^=bit;
        if (i<j) {
            float t=s->re[i];s->re[i]=s->re[j];s->re[j]=t;
            t=s->im[i];s->im[i]=s->im[j];s->im[j]=t;
        }
    }
    for(size_t len=2;len<=PHYLLO_FFT_N;len<<=1u) {
        const float angle=-2.0f*PI_F/(float)len;
        const float wr0=cosf(angle),wi0=sinf(angle);
        for(size_t base=0;base<PHYLLO_FFT_N;base+=len) {
            float wr=1.0f,wi=0.0f;
            for(size_t k=0;k<len/2u;k++) {
                const size_t a=base+k,b=a+len/2u;
                float vr=s->re[b]*wr-s->im[b]*wi;
                float vi=s->re[b]*wi+s->im[b]*wr;
                float ur=s->re[a],ui=s->im[a];
                s->re[a]=ur+vr;s->im[a]=ui+vi;
                s->re[b]=ur-vr;s->im[b]=ui-vi;
                float next=wr*wr0-wi*wi0;
                wi=wr*wi0+wi*wr0;wr=next;
            }
        }
    }
}
int phyllo_analyze(phyllo_dsp *s,const float *mono,phyllo_features *out) {
    static const float edges[PHYLLO_BANDS+1u]={60,140,300,600,1200,2400,4800,8000};
    if(!s||!mono||!out||s->window_sum<=0) return 0;
    float mean=0;
    for(size_t i=0;i<PHYLLO_FFT_N;i++) {
        if(!isfinite(mono[i])||fabsf(mono[i])>1.0f) return 0;
        mean+=mono[i];
    }
    mean/=(float)PHYLLO_FFT_N;
    phyllo_features f={0};
    for(size_t i=0;i<PHYLLO_FFT_N;i++) {
        const float x=mono[i]-mean;
        f.rms+=x*x;s->re[i]=x*s->window[i];s->im[i]=0;
    }
    f.rms=sqrtf(f.rms/(float)PHYLLO_FFT_N);
    fft(s);
    float peak=0; unsigned band_count[PHYLLO_BANDS]={0};
    for(size_t k=1;k<=PHYLLO_FFT_N/2u;k++) {
        float mag=sqrtf(s->re[k]*s->re[k]+s->im[k]*s->im[k])*2.0f/s->window_sum;
        if(k==PHYLLO_FFT_N/2u) mag*=0.5f;
        if(mag>peak){peak=mag;f.peak_bin=(uint16_t)k;}
        const float delta=mag-s->previous[k];
        if(delta>0)f.flux+=delta;
        s->previous[k]=mag;
        const float hz=(float)(k*PHYLLO_FS)/(float)PHYLLO_FFT_N;
        for(size_t b=0;b<PHYLLO_BANDS;b++) {
            if(hz>=edges[b]&&hz<edges[b+1u]) {
                f.bands[b]+=mag*mag;band_count[b]++;break;
            }
        }
    }
    for(size_t b=0;b<PHYLLO_BANDS;b++)
        if(band_count[b])f.bands[b]=sqrtf(f.bands[b]/(float)band_count[b]);
    /* 5 hops = 80ms refractory. Initial onset allowed, then use wrapping subtraction. */
    float threshold=fmaxf(0.035f,s->flux_ema*2.2f);
    if(f.rms>0.005f&&f.flux>threshold&&(!s->onset_seen||(uint32_t)(s->frames-s->last_onset)>=5u)) {
        f.onset=1;s->last_onset=s->frames;s->onset_seen=1;
    }
    s->flux_ema=0.9f*s->flux_ema+0.1f*f.flux;s->frames++;
    *out=f;return 1;
}
float phyllo_i2s24(uint16_t high,uint16_t low) {
    uint32_t v=(((uint32_t)high<<16u)|(uint32_t)low)>>8u;
    int32_t signed24=(v&0x800000u)?(int32_t)(v&0x7fffffu)-8388608:(int32_t)v;
    return (float)signed24/8388608.0f;
}
static float clip(float x,float high){return fmaxf(0,fminf(high,x));}
static phyllo_rgb hsv(float hue,float value) {
    hue=fmodf(hue,360);if(hue<0)hue+=360;
    float c=value*.72f,x=c*(1-fabsf(fmodf(hue/60,2)-1)),m=value-c;
    float r=0,g=0,b=0;
    if(hue<60){r=c;g=x;}else if(hue<120){r=x;g=c;}
    else if(hue<180){g=c;b=x;}else if(hue<240){g=x;b=c;}
    else if(hue<300){r=x;b=c;}else{r=c;b=x;}
    phyllo_rgb rgb={(uint8_t)roundf(clip(r+m,1)*255),(uint8_t)roundf(clip(g+m,1)*255),(uint8_t)roundf(clip(b+m,1)*255)};
    return rgb;
}
int phyllo_render(const phyllo_point *points,size_t n,float t,const phyllo_signal *s,const phyllo_render_config *c,phyllo_rgb *out) {
    if(!points||!s||!c||!out||n==0u||n>PHYLLO_LED_MAX||!isfinite(t)||t<0||!isfinite(s->level)||!isfinite(s->beat)||!isfinite(c->brightness)||!isfinite(c->gain)||(unsigned)c->mode>(unsigned)PHYLLO_PULSE||(unsigned)c->palette>(unsigned)PHYLLO_OCEAN)return 0;
    float maxr=0;
    for(size_t i=0;i<PHYLLO_BANDS;i++)if(!isfinite(s->bands[i]))return 0;
    for(size_t i=0;i<n;i++) {
        if(!isfinite(points[i].radius)||!isfinite(points[i].angle)||points[i].radius<0)return 0;
        maxr=fmaxf(maxr,points[i].radius);
    }
    if(maxr<=0)return 0;
    float gain=clip(c->gain,4),level=clip(s->level*gain,1),brightness=clip(c->brightness,.35f);
    for(size_t i=0;i<n;i++) {
        float rr=points[i].radius/maxr,aa=fmodf(points[i].angle,2*PI_F),e;
        if(c->mode==PHYLLO_SPECTRUM) {
            unsigned band=(unsigned)(rr*7);if(band>6)band=6;
            e=clip(s->bands[band]*gain,1)*(.65f+.35f*sinf(aa-t*2));
        }else if(c->mode==PHYLLO_PULSE) {
            float ring=fmodf(t*.28f+clip(s->beat,1)*.1f,1);
            e=clip(1-fabsf(rr-ring)/.18f,1)*(.2f+level*.8f)+level*.15f;
        }else {
            float w=fmaxf(0,sinf(aa*3-rr*12+t*(.8f+level*2)));
            e=(.12f+.88f*w*w*w)*(.22f+level*.78f);
        }
        float hue=c->palette==PHYLLO_EMBER?22+rr*40:c->palette==PHYLLO_OCEAN?175+rr*65:130+rr*85+sinf(t*.15f)*18;
        out[i]=hsv(hue,clip(e,1)*brightness);
    }
    return 1;
}
float phyllo_limit_current(phyllo_rgb *rgb,size_t n,float budget) {
    if(!rgb||n==0u||n>PHYLLO_LED_MAX||!isfinite(budget)||budget<0)return -1;
    if(budget<(float)n){memset(rgb,0,n*sizeof(*rgb));return -2;}
    /* Deliberately conservative 1mA idle + 20mA/channel, independent of V6 typical. */
    float channels=0;
    for(size_t i=0;i<n;i++)channels+=(float)(rgb[i].r+rgb[i].g+rgb[i].b);
    float active=channels*20.0f/255.0f;
    float allowed=fmaxf(0,budget-(float)n);
    float scale=active>allowed&&active>0?allowed/active:1;
    for(size_t i=0;i<n;i++) {
        rgb[i].r=(uint8_t)((float)rgb[i].r*scale);
        rgb[i].g=(uint8_t)((float)rgb[i].g*scale);
        rgb[i].b=(uint8_t)((float)rgb[i].b*scale);
    }
    return scale;
}
size_t phyllo_encode(const phyllo_rgb *rgb,size_t n,const uint16_t *chain,uint16_t *out,size_t capacity) {
    if(!rgb||!chain||!out||n==0u||n>PHYLLO_LED_MAX||capacity<n*24u+PHYLLO_RESET_SLOTS)return 0;
    uint8_t seen[PHYLLO_LED_MAX]={0};
    for(size_t i=0;i<n;i++){if(chain[i]>=n||seen[chain[i]])return 0;seen[chain[i]]=1;}
    size_t pos=0;
    for(size_t i=0;i<n;i++) {
        phyllo_rgb p=rgb[chain[i]];
        uint32_t grb=((uint32_t)p.g<<16u)|((uint32_t)p.r<<8u)|p.b;
        for(int bit=23;bit>=0;bit--)out[pos++]=(grb&(1u<<(unsigned)bit))?PHYLLO_PWM_ONE:PHYLLO_PWM_ZERO;
    }
    for(size_t i=0;i<PHYLLO_RESET_SLOTS;i++)out[pos++]=0;
    return pos;
}
