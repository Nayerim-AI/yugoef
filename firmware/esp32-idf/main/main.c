/**
 * Yugoef ESP32 WiFi Sensing Firmware
 * 
 * Reads WiFi RSSI periodically, computes motion score from RSSI variance,
 * classifies motion level, and sends structured JSON events to the
 * Yugoef cloud endpoint via HTTP POST.
 *
 * SPDX-License-Identifier: MIT
 */

#include <stdio.h>
#include <string.h>
#include <math.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_http_client.h"
#include "nvs_flash.h"

/* ── Tag for logging ─────────────────────────────────────────────── */
static const char *TAG = "yugoef";

/* ── Event group bits ───────────────────────────────────────────── */
#define WIFI_CONNECTED_BIT  BIT0
#define WIFI_FAIL_BIT       BIT1
#define MAX_RETRY           5

static EventGroupHandle_t s_wifi_event_group;
static int s_retry_num = 0;

/* ── RSSI rolling window ────────────────────────────────────────── */
#define WINDOW_SIZE         CONFIG_RSSI_WINDOW_SIZE
#define SAMPLE_INTERVAL_MS  CONFIG_RSSI_SAMPLE_INTERVAL_MS

static float rssi_window[WINDOW_SIZE];
static int   rssi_index = 0;
static int   rssi_count  = 0;

/* ──────────────────────────────────────────────────────────────────
 * WiFi event handler
 * ────────────────────────────────────────────────────────────────── */
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(TAG, "Retrying connection... (%d/%d)", s_retry_num, MAX_RETRY);
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
            ESP_LOGE(TAG, "Connection failed after %d retries", MAX_RETRY);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

/* ──────────────────────────────────────────────────────────────────
 * Initialise WiFi in station mode
 * ────────────────────────────────────────────────────────────────── */
static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    /* Register event handlers */
    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler, NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler, NULL,
                                                        &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid     = CONFIG_WIFI_SSID,
            .password = CONFIG_WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi STA started. Connecting to SSID: %s", CONFIG_WIFI_SSID);
}

/* ──────────────────────────────────────────────────────────────────
 * Wait for WiFi connection (blocks)
 * ────────────────────────────────────────────────────────────────── */
static bool wifi_wait_connected(void)
{
    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
                                           WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                           pdFALSE, pdFALSE,
                                           portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "Connected to WiFi '%s'", CONFIG_WIFI_SSID);
        return true;
    }
    ESP_LOGE(TAG, "Failed to connect to WiFi '%s'", CONFIG_WIFI_SSID);
    return false;
}

/* ──────────────────────────────────────────────────────────────────
 * Read current WiFi RSSI
 * ────────────────────────────────────────────────────────────────── */
static float read_rssi(void)
{
    wifi_ap_record_t ap_info;
    if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
        return (float)ap_info.rssi;
    }
    return 0.0f;
}

/* ──────────────────────────────────────────────────────────────────
 * Add RSSI sample to rolling window
 * ────────────────────────────────────────────────────────────────── */
static void rssi_push(float rssi)
{
    rssi_window[rssi_index] = rssi;
    rssi_index = (rssi_index + 1) % WINDOW_SIZE;
    if (rssi_count < WINDOW_SIZE) rssi_count++;
}

/* ──────────────────────────────────────────────────────────────────
 * Compute variance of RSSI samples in the window
 * ────────────────────────────────────────────────────────────────── */
static float rssi_variance(void)
{
    if (rssi_count < 2) return 0.0f;

    float mean = 0.0f;
    for (int i = 0; i < rssi_count; i++) {
        mean += rssi_window[i];
    }
    mean /= (float)rssi_count;

    float var = 0.0f;
    for (int i = 0; i < rssi_count; i++) {
        float diff = rssi_window[i] - mean;
        var += diff * diff;
    }
    var /= (float)rssi_count;
    return var;
}

/* ──────────────────────────────────────────────────────────────────
 * Classify motion level from variance (motion_score)
 * ────────────────────────────────────────────────────────────────── */
static const char *classify_motion(float motion_score)
{
    if (motion_score < 0.15f) return "none";
    if (motion_score <= 0.55f) return "medium";
    return "high";
}

/* ──────────────────────────────────────────────────────────────────
 * Build JSON payload and POST to cloud endpoint
 * ────────────────────────────────────────────────────────────────── */
static esp_err_t send_event(float motion_score, const char *motion_level,
                            float rssi_current, float rssi_variance_val)
{
    /* Build JSON manually (no external deps) */
    char payload[512];
    int confidence = (int)(motion_score * 100.0f);
    if (confidence > 100) confidence = 100;
    float confidence_f = (float)confidence / 100.0f;

    int len = snprintf(payload, sizeof(payload),
        "{"
          "\"source\":\"%s\","
          "\"event\":{"
            "\"type\":\"sensing_update\","
            "\"classification\":{"
              "\"presence\":%s,"
              "\"motion_level\":\"%s\","
              "\"confidence\":%.2f"
            "},"
            "\"features\":{"
              "\"motion_band_power\":%.4f,"
              "\"rssi_variance\":%.4f,"
              "\"rssi_current\":%.1f"
            "}"
          "}"
        "}",
        CONFIG_DEVICE_ID,
        (strcmp(motion_level, "none") != 0) ? "true" : "false",
        motion_level,
        confidence_f,
        motion_score,
        rssi_variance_val,
        rssi_current
    );

    if (len < 0 || len >= (int)sizeof(payload)) {
        ESP_LOGE(TAG, "JSON payload too large");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Payload: %s", payload);

    esp_http_client_config_t config = {
        .url = CONFIG_CLOUD_ENDPOINT_URL,
        .timeout_ms = 5000,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "Failed to init HTTP client");
        return ESP_FAIL;
    }

    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, payload, len);

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int status = esp_http_client_get_status_code(client);
        ESP_LOGI(TAG, "HTTP POST status: %d", status);
    } else {
        ESP_LOGE(TAG, "HTTP POST failed: %s", esp_err_to_name(err));
    }

    esp_http_client_cleanup(client);
    return err;
}

/* ──────────────────────────────────────────────────────────────────
 * Main sensing loop task
 * ────────────────────────────────────────────────────────────────── */
static void sensing_task(void *pvParameters)
{
    ESP_LOGI(TAG, "Sensing task started (interval=%dms, window=%d)",
             SAMPLE_INTERVAL_MS, WINDOW_SIZE);

    while (1) {
        float rssi = read_rssi();
        rssi_push(rssi);

        float var = rssi_variance();
        const char *level = classify_motion(var);

        ESP_LOGI(TAG, "RSSI=%.1f dBm | variance=%.4f | motion=%s",
                 rssi, var, level);

        send_event(var, level, rssi, var);

        vTaskDelay(pdMS_TO_TICKS(SAMPLE_INTERVAL_MS));
    }
}

/* ──────────────────────────────────────────────────────────────────
 * app_main — entry point
 * ────────────────────────────────────────────────────────────────── */
void app_main(void)
{
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "  Yugoef WiFi Sensing Firmware v1.0");
    ESP_LOGI(TAG, "  Device: %s", CONFIG_DEVICE_ID);
    ESP_LOGI(TAG, "  Endpoint: %s", CONFIG_CLOUD_ENDPOINT_URL);
    ESP_LOGI(TAG, "===========================================");

    /* Initialise NVS (required by WiFi driver) */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    /* Start WiFi */
    wifi_init_sta();

    if (!wifi_wait_connected()) {
        ESP_LOGE(TAG, "WiFi connection failed. Rebooting in 5s...");
        vTaskDelay(pdMS_TO_TICKS(5000));
        esp_restart();
    }

    /* Start sensing task */
    xTaskCreate(sensing_task, "sensing_task", 4096, NULL, 5, NULL);
}
