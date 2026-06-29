/**
 * Yugoef ESP32 WiFi CSI Firmware
 *
 * Connects to WiFi, enables ESP-IDF CSI callback, serializes RAW_CSI packets
 * using Yugoef CSI Protocol v1, and sends them to the cloud UDP receiver.
 *
 * No AI API key is stored on the ESP32. The ESP32 only sends CSI metadata
 * and signed int8 I/Q payload bytes to the Yugoef backend.
 *
 * SPDX-License-Identifier: MIT
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "mbedtls/md.h"

#include "lwip/sockets.h"
#include "lwip/inet.h"

static const char *TAG = "yugoef-csi";

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1
#define MAX_RETRY          5

#define YUGOEF_MAGIC       0x59474631U /* 'YGF1' */
#define YUGOEF_VERSION     1
#define YUGOEF_HEADER_LEN  40
#define YUGOEF_MAX_PACKET  CONFIG_CSI_MAX_PACKET_SIZE
#define YUGOEF_AUTH_FLAG   0x01
#define YUGOEF_AUTH_TAG_LEN 16
#define YUGOEF_MAX_PAYLOAD (YUGOEF_MAX_PACKET - YUGOEF_HEADER_LEN - YUGOEF_AUTH_TAG_LEN)

#define MSG_NODE_HELLO 1
#define MSG_RAW_CSI    2
#define MSG_HEARTBEAT  3

static EventGroupHandle_t s_wifi_event_group;
static int s_retry_num = 0;
static int s_udp_sock = -1;
static struct sockaddr_in s_backend_addr;
static uint32_t s_boot_id = 0;
static uint32_t s_raw_sequence = 0;
static uint32_t s_heartbeat_sequence = 0;
static volatile uint32_t s_csi_sent = 0;
static volatile uint32_t s_csi_dropped = 0;

static void put_u16_be(uint8_t *buf, size_t off, uint16_t value)
{
    buf[off] = (uint8_t)((value >> 8) & 0xff);
    buf[off + 1] = (uint8_t)(value & 0xff);
}

static void put_u32_be(uint8_t *buf, size_t off, uint32_t value)
{
    buf[off] = (uint8_t)((value >> 24) & 0xff);
    buf[off + 1] = (uint8_t)((value >> 16) & 0xff);
    buf[off + 2] = (uint8_t)((value >> 8) & 0xff);
    buf[off + 3] = (uint8_t)(value & 0xff);
}

static uint32_t crc32_ieee(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xffffffffU;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) {
            uint32_t mask = -(crc & 1U);
            crc = (crc >> 1) ^ (0xedb88320U & mask);
        }
    }
    return ~crc;
}

static bool append_auth_tag(uint8_t *packet, uint16_t payload_len)
{
    const char *secret = CONFIG_YUGOEF_NODE_SECRET;
    if (secret == NULL || secret[0] == '\0') {
        return false;
    }

    const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (info == NULL) {
        return false;
    }

    uint8_t digest[32];
    mbedtls_md_context_t ctx;
    mbedtls_md_init(&ctx);
    if (mbedtls_md_setup(&ctx, info, 1) != 0) {
        mbedtls_md_free(&ctx);
        return false;
    }
    if (mbedtls_md_hmac_starts(&ctx, (const unsigned char *)secret, strlen(secret)) != 0 ||
        mbedtls_md_hmac_update(&ctx, packet, 36) != 0 ||
        mbedtls_md_hmac_update(&ctx, packet + YUGOEF_HEADER_LEN, payload_len) != 0 ||
        mbedtls_md_hmac_finish(&ctx, digest) != 0) {
        mbedtls_md_free(&ctx);
        return false;
    }
    mbedtls_md_free(&ctx);
    memcpy(packet + YUGOEF_HEADER_LEN + payload_len, digest, YUGOEF_AUTH_TAG_LEN);
    return true;
}

static uint32_t uptime_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

static uint8_t bandwidth_mhz(void)
{
    wifi_bandwidth_t bw = WIFI_BW20;
    if (esp_wifi_get_bandwidth(WIFI_IF_STA, &bw) == ESP_OK && bw == WIFI_BW40) {
        return 40;
    }
    return 20;
}

static esp_err_t udp_send_packet(const uint8_t *packet, size_t len)
{
    if (s_udp_sock < 0) {
        return ESP_ERR_INVALID_STATE;
    }
    int sent = sendto(s_udp_sock, packet, len, 0,
                      (struct sockaddr *)&s_backend_addr,
                      sizeof(s_backend_addr));
    if (sent < 0 || (size_t)sent != len) {
        return ESP_FAIL;
    }
    return ESP_OK;
}

static size_t build_packet(uint8_t message_type,
                           uint32_t sequence,
                           uint8_t wifi_channel,
                           uint8_t bw_mhz,
                           uint8_t antenna_index,
                           uint8_t antenna_count,
                           uint16_t subcarrier_count,
                           int8_t rssi_dbm,
                           int8_t noise_floor_dbm,
                           const uint8_t *payload,
                           uint16_t payload_len,
                           uint8_t *out,
                           size_t out_len)
{
    bool use_auth = CONFIG_YUGOEF_NODE_SECRET[0] != '\0';
    uint16_t wire_payload_len = payload_len + (use_auth ? YUGOEF_AUTH_TAG_LEN : 0);
    size_t total_len = YUGOEF_HEADER_LEN + wire_payload_len;
    if (out_len < total_len || total_len > YUGOEF_MAX_PACKET) {
        return 0;
    }

    memset(out, 0, total_len);
    put_u32_be(out, 0, YUGOEF_MAGIC);
    out[4] = YUGOEF_VERSION;
    out[5] = message_type;
    out[6] = YUGOEF_HEADER_LEN;
    out[7] = use_auth ? YUGOEF_AUTH_FLAG : 0; /* flags */
    put_u16_be(out, 8, CONFIG_YUGOEF_NODE_ID);
    put_u16_be(out, 10, CONFIG_YUGOEF_ROOM_ID);
    put_u32_be(out, 12, s_boot_id);
    put_u32_be(out, 16, sequence);
    put_u32_be(out, 20, uptime_ms());
    out[24] = wifi_channel;
    out[25] = bw_mhz;
    out[26] = antenna_index;
    out[27] = antenna_count;
    put_u16_be(out, 28, subcarrier_count);
    out[30] = (uint8_t)rssi_dbm;
    out[31] = (uint8_t)noise_floor_dbm;
    put_u16_be(out, 32, wire_payload_len);
    put_u16_be(out, 34, 0); /* reserved */

    if (payload_len > 0 && payload != NULL) {
        memcpy(out + YUGOEF_HEADER_LEN, payload, payload_len);
    }
    if (use_auth && !append_auth_tag(out, payload_len)) {
        return 0;
    }

    uint32_t crc = crc32_ieee(out, 36);
    if (wire_payload_len > 0) {
        uint32_t payload_crc_seed = crc ^ 0xffffffffU;
        for (uint16_t i = 0; i < wire_payload_len; i++) {
            payload_crc_seed ^= out[YUGOEF_HEADER_LEN + i];
            for (int bit = 0; bit < 8; bit++) {
                uint32_t mask = -(payload_crc_seed & 1U);
                payload_crc_seed = (payload_crc_seed >> 1) ^ (0xedb88320U & mask);
            }
        }
        crc = ~payload_crc_seed;
    }
    put_u32_be(out, 36, crc);
    return total_len;
}

static void send_heartbeat(void)
{
    uint8_t packet[YUGOEF_HEADER_LEN + YUGOEF_AUTH_TAG_LEN];
    size_t len = build_packet(MSG_HEARTBEAT,
                              s_heartbeat_sequence++,
                              CONFIG_YUGOEF_WIFI_CHANNEL,
                              bandwidth_mhz(),
                              0,
                              1,
                              0,
                              0,
                              -95,
                              NULL,
                              0,
                              packet,
                              sizeof(packet));
    if (len > 0) {
        udp_send_packet(packet, len);
    }
}

static void send_node_hello(void)
{
    const char hello[] = "yugoef-esp32-csi-v1";
    uint8_t packet[YUGOEF_HEADER_LEN + sizeof(hello) + YUGOEF_AUTH_TAG_LEN];
    size_t len = build_packet(MSG_NODE_HELLO,
                              0,
                              CONFIG_YUGOEF_WIFI_CHANNEL,
                              bandwidth_mhz(),
                              0,
                              1,
                              0,
                              0,
                              -95,
                              (const uint8_t *)hello,
                              (uint16_t)sizeof(hello),
                              packet,
                              sizeof(packet));
    if (len > 0) {
        udp_send_packet(packet, len);
    }
}

static void csi_rx_cb(void *ctx, wifi_csi_info_t *info)
{
    (void)ctx;
    if (info == NULL || info->buf == NULL || info->len <= 0) {
        return;
    }

    uint16_t payload_len = (uint16_t)info->len;
    if (payload_len > YUGOEF_MAX_PAYLOAD) {
        s_csi_dropped++;
        return;
    }

    uint8_t packet[YUGOEF_MAX_PACKET];
    uint16_t subcarrier_count = payload_len / 2;
    size_t len = build_packet(MSG_RAW_CSI,
                              s_raw_sequence++,
                              info->rx_ctrl.channel,
                              bandwidth_mhz(),
                              0,
                              1,
                              subcarrier_count,
                              (int8_t)info->rx_ctrl.rssi,
                              -95,
                              (const uint8_t *)info->buf,
                              payload_len,
                              packet,
                              sizeof(packet));
    if (len == 0) {
        s_csi_dropped++;
        return;
    }
    if (udp_send_packet(packet, len) == ESP_OK) {
        s_csi_sent++;
    } else {
        s_csi_dropped++;
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    (void)arg;
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

static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler, NULL, NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = CONFIG_WIFI_SSID,
            .password = CONFIG_WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(TAG, "WiFi STA started. Connecting to SSID: %s", CONFIG_WIFI_SSID);
}

static bool wifi_wait_connected(void)
{
    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
                                           WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                           pdFALSE,
                                           pdFALSE,
                                           portMAX_DELAY);
    if (bits & WIFI_CONNECTED_BIT) {
        return true;
    }
    return false;
}

static esp_err_t udp_init(void)
{
    s_udp_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (s_udp_sock < 0) {
        ESP_LOGE(TAG, "Failed to create UDP socket");
        return ESP_FAIL;
    }

    memset(&s_backend_addr, 0, sizeof(s_backend_addr));
    s_backend_addr.sin_family = AF_INET;
    s_backend_addr.sin_port = htons(CONFIG_YUGOEF_UDP_PORT);
    if (inet_pton(AF_INET, CONFIG_YUGOEF_UDP_HOST, &s_backend_addr.sin_addr) != 1) {
        ESP_LOGE(TAG, "Invalid UDP host: %s", CONFIG_YUGOEF_UDP_HOST);
        close(s_udp_sock);
        s_udp_sock = -1;
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "UDP target %s:%d", CONFIG_YUGOEF_UDP_HOST, CONFIG_YUGOEF_UDP_PORT);
    return ESP_OK;
}

static void csi_init(void)
{
    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = false,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_rx_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    ESP_LOGI(TAG, "CSI callback enabled");
}

static void heartbeat_task(void *pvParameters)
{
    (void)pvParameters;
    while (true) {
        send_heartbeat();
        ESP_LOGI(TAG, "heartbeat sent, csi_sent=%lu, csi_dropped=%lu",
                 (unsigned long)s_csi_sent,
                 (unsigned long)s_csi_dropped);
        vTaskDelay(pdMS_TO_TICKS(CONFIG_HEARTBEAT_INTERVAL_MS));
    }
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    s_boot_id = esp_random();
    ESP_LOGI(TAG, "Yugoef ESP32 CSI firmware boot_id=%lu", (unsigned long)s_boot_id);

    wifi_init_sta();
    if (!wifi_wait_connected()) {
        ESP_LOGE(TAG, "WiFi unavailable; stopping");
        return;
    }
    if (udp_init() != ESP_OK) {
        ESP_LOGE(TAG, "UDP unavailable; stopping");
        return;
    }

    send_node_hello();
    csi_init();
    xTaskCreate(heartbeat_task, "yugoef_heartbeat", 4096, NULL, 5, NULL);
}
