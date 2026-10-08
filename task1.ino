#include <Arduino.h>

#include "driver/adc.h"
#include "soc/adc_channel.h"

// ESP32 ADC1 Channel 6 = GPIO34
#define ADC_CHANNEL       ADC1_CHANNEL_6
#define ADC_PIN           34

// ADC attenuation
// 11 dB gives a larger measurable input range.
#define ADC_ATTENUATION   ADC_ATTEN_DB_11

// ADC resolution
#define ADC_WIDTH         ADC_WIDTH_BIT_12

// ---------- Sampling ----------
#define SAMPLE_RATE       10000UL       // 10 kS/s
#define BLOCK_SIZE        1024


// ---------- Timing ----------
// GPIO used for oscilloscope timing verification
#define SAMPLE_SYNC_PIN   26

// ---------- Serial ----------
#define SERIAL_BAUD       1000000UL

// ============================================================
// DOUBLE BUFFER
// ============================================================
uint16_t sampleBufferA[BLOCK_SIZE];
uint16_t sampleBufferB[BLOCK_SIZE];


// ============================================================
// HARDWARE TIMER
// ============================================================
hw_timer_t *sampleTimer = NULL;

portMUX_TYPE timerMux =
    portMUX_INITIALIZER_UNLOCKED;

SemaphoreHandle_t sampleSemaphore;

QueueHandle_t blockQueue;

volatile uint32_t sampleCount = 0;
volatile uint32_t timerEventCount = 0;
volatile uint32_t overrunCount = 0;

void IRAM_ATTR onSampleTimer()
{
    BaseType_t higherPriorityTaskWoken = pdFALSE;

    timerEventCount++;

    xSemaphoreGiveFromISR(
        sampleSemaphore,
        &higherPriorityTaskWoken
    );

    if (higherPriorityTaskWoken)
    {
        portYIELD_FROM_ISR();
    }
}


void setupADC()
{
    adc1_config_width(ADC_WIDTH);

    adc1_config_channel_atten(
        ADC_CHANNEL,
        ADC_ATTENUATION
    );
}

void setupSampleTimer()
{
    sampleTimer = timerBegin(1000000); 

    timerAttachInterrupt(
        sampleTimer,
        &onSampleTimer
    );

    timerAlarm(
        sampleTimer,
        1000000 / SAMPLE_RATE,  
        true,
        0
    );
}

void adcTask(void *parameter)
{
    uint16_t *currentBuffer;
    uint8_t currentBufferID;

    size_t sampleIndex = 0;

    currentBuffer = sampleBufferA;
    currentBufferID = 0;

    while (true)
    {
        if (xSemaphoreTake(
                sampleSemaphore,
                portMAX_DELAY
            ) == pdTRUE)
        {
            digitalWrite(SAMPLE_SYNC_PIN, HIGH);

            uint16_t sample = adc1_get_raw(ADC_CHANNEL);

            currentBuffer[sampleIndex] = sample;

            sampleIndex++;
            sampleCount++;


            digitalWrite(SAMPLE_SYNC_PIN, LOW);

            if (sampleIndex >= BLOCK_SIZE)
            {
                BaseType_t queueResult;

                queueResult =
                    xQueueSend(
                        blockQueue,
                        &currentBufferID,
                        0
                    );

                if (queueResult != pdTRUE)
                {
                    overrunCount++;
                }

                if (currentBufferID == 0)
                {
                    currentBuffer = sampleBufferB;
                    currentBufferID = 1;
                }
                else
                {
                    currentBuffer = sampleBufferA;
                    currentBufferID = 0;
                }

                sampleIndex = 0;
            }
        }
    }
}

void sendBlock(uint8_t bufferID)
{
    uint16_t *buffer;

    if (bufferID == 0)
    {
        buffer = sampleBufferA;
    }
    else
    {
        buffer = sampleBufferB;
    }

    uint8_t header[4];

    header[0] = 0xAA;
    header[1] = 0x55;

    uint16_t N = BLOCK_SIZE;

    memcpy(
        &header[2],
        &N,
        sizeof(uint16_t)
    );

    Serial.write(
        header,
        sizeof(header)
    );

    Serial.write(
        (uint8_t *)buffer,
        BLOCK_SIZE * sizeof(uint16_t)
    );
}

void serialTask(void *parameter)
{
    uint8_t bufferID;

    while (true)
    {
        if (xQueueReceive(
                blockQueue,
                &bufferID,
                portMAX_DELAY
            ) == pdTRUE)
        {
            sendBlock(bufferID);
        }
    }
}


void setup()
{
    Serial.begin(SERIAL_BAUD);
    delay(1000);

    pinMode(
        SAMPLE_SYNC_PIN,
        OUTPUT
    );

    digitalWrite(
        SAMPLE_SYNC_PIN,
        LOW
    );

    setupADC();

    sampleSemaphore = xSemaphoreCreateBinary();

    if (sampleSemaphore == NULL)
    {
        // Fallback error mode
        while (true)
        {
            delay(1000);
        }
    }

    blockQueue = xQueueCreate(2, sizeof(uint8_t));

    if (blockQueue == NULL)
    {
        // Fallback error mode
        while (true)
        {
            delay(1000);
        }
    }

    setupSampleTimer();

    xTaskCreatePinnedToCore(
        adcTask,
        "ADC_Acquisition",
        4096,
        NULL,
        3,
        NULL,
        0
    );

    xTaskCreatePinnedToCore(
        serialTask,
        "Serial_Transmission",
        4096,
        NULL,
        1,
        NULL,
        1
    );

    delay(100);

    Serial.write(0xAA);
}


void loop()
{

    vTaskDelay(portMAX_DELAY);
}