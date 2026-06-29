# Tutorial: Firmware ESP32-IDF untuk Yugoef WiFi Sensing

## 📋 Daftar Isi
1. [Pendahuluan](#pendahuluan)
2. [Prasyarat](#prasyarat)
3. [Instalasi ESP-IDF](#instalasi-esp-idf)
4. [Konfigurasi Firmware](#konfigurasi-firmware)
5. [Build dan Flash](#build-dan-flash)
6. [Monitoring Output](#monitoring-output)
7. [Verifikasi Data di Cloud](#verifikasi-data-di-cloud)
8. [Troubleshooting](#troubleshooting)

---

## Pendahuluan

Firmware ini mengubah ESP32 menjadi sensor WiFi yang membaca RSSI (Received Signal Strength Indicator) secara periodik, menghitung skor gerakan berdasarkan varians RSSI, dan mengirim event terstruktur ke backend Yugoef melalui HTTP POST.

**Fitur:**
- Koneksi WiFi otomatis dengan retry
- Sampling RSSI setiap 2 detik (configurable)
- Rolling window untuk perhitungan varians
- Klasifikasi motion level: none / medium / high
- HTTP POST ke endpoint cloud Yugoef
- Konfigurasi mudah via `idf.py menuconfig`

---

## Prasyarat

### Hardware
- ESP32 DevKit (ESP32, ESP32-S3, ESP32-C3, dll)
- Kabel USB (micro-USB atau USB-C tergantung board)
- Komputer Linux/Mac/Windows

### Software
- ESP-IDF v5.2 atau lebih baru
- Python 3.8+
- Git

---

## Instalasi ESP-IDF

### Linux/Mac

```bash
# Clone ESP-IDF
cd ~/esp
git clone -b v5.2 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf

# Install tools
./install.sh esp32

# Set environment variables (tambahkan ke ~/.bashrc atau ~/.zshrc)
source ~/esp/esp-idf/export.sh
```

### Windows

Download installer dari: https://dl.espressif.com/dl/esp-idf/

Atau gunakan ESP-IDF Tools Installer.

### Verifikasi Instalasi

```bash
idf.py --version
# Output: ESP-IDF v5.2.x
```

---

## Konfigurasi Firmware

### 1. Clone atau Download Firmware

```bash
cd /home/orangepi/projects/research/yugoef/firmware/esp32-idf/
```

### 2. Buka Menu Konfigurasi

```bash
idf.py menuconfig
```

Akan muncul interface berbasis teks (ncurses).

### 3. Konfigurasi WiFi Credentials

Navigasi ke:
```
Yugoef WiFi Sensing Configuration
  → WiFi SSID
  → WiFi Password
```

**Langkah-langkah:**
1. Gunakan **panah atas/bawah** untuk navigasi
2. Tekan **Enter** pada "WiFi SSID"
3. Ketik nama WiFi Anda (contoh: `MyHomeWiFi`)
4. Tekan **Enter** untuk simpan
5. Ulangi untuk "WiFi Password"

### 4. Konfigurasi Cloud Endpoint

Navigasi ke:
```
Yugoef WiFi Sensing Configuration
  → Cloud Endpoint URL
```

Masukkan URL endpoint Yugoef cloud Anda:
```
http://192.168.1.100:8000/v1/ingest
```

**Format URL:**
- Lokal: `http://<IP_SERVER>:8000/v1/ingest`
- Remote: `https://yugoef.example.com/v1/ingest`

### 5. Konfigurasi Device ID (Opsional)

```
Yugoef WiFi Sensing Configuration
  → Device ID
```

Ubah jika Anda punya multiple ESP32:
```
esp32-devkit-01
esp32-devkit-02
```

### 6. Konfigurasi Sampling (Opsional)

**RSSI Sample Interval:**
- Default: 2000 ms (2 detik)
- Range: 500 - 10000 ms

**RSSI Rolling Window Size:**
- Default: 10 samples
- Range: 5 - 20 samples

### 7. Simpan dan Keluar

1. Tekan **S** untuk save
2. Tekan **Enter** untuk konfirmasi (file tersimpan sebagai `sdkconfig`)
3. Tekan **Q** untuk keluar dari menuconfig

---

## Build dan Flash

### 1. Set Target Chip

```bash
idf.py set-target esp32
```

Untuk chip lain:
```bash
idf.py set-target esp32s3  # ESP32-S3
idf.py set-target esp32c3  # ESP32-C3
```

### 2. Build Firmware

```bash
idf.py build
```

**Expected output:**
```
Project build complete. To flash, run this command:
/home/orangepi/.espressif/python_env/idf5.2_py3.10_env/bin/python ../../../esp/esp-idf/components/esptool_py/esptool/esptool.py ...
```

**Build time:** ~2-5 menit (tergantung spesifikasi komputer)

### 3. Hubungkan ESP32 ke Komputer

1. Colokkan kabel USB ke ESP32 dan komputer
2. Cek port serial:
   ```bash
   ls /dev/ttyUSB*
   # atau
   ls /dev/ttyACM*
   ```

**Common ports:**
- Linux: `/dev/ttyUSB0` atau `/dev/ttyACM0`
- Mac: `/dev/cu.usbserial-*` atau `/dev/cu.usbmodem*`
- Windows: `COM3`, `COM4`, dll (cek Device Manager)

### 4. Set Port Serial

```bash
export ESPPORT=/dev/ttyUSB0
```

Atau gunakan flag:
```bash
idf.py -p /dev/ttyUSB0 flash
```

### 5. Flash Firmware

```bash
idf.py -p /dev/ttyUSB0 flash
```

**Proses flashing:**
```
esptool.py v4.7.0
Serial port /dev/ttyUSB0
Connecting....
Chip is ESP32-D0WD-V3 (revision v3.0)
Features: WiFi, BT, Dual Core, 240MHz, VRef calibration in efuse, Coding Scheme None
Crystal is 40MHz
MAC: 24:6f:28:xx:xx:xx
Uploading stub...
Running stub...
Stub running...
Changing baud rate to 460800
Changed.
Configuring flash size...
Flash will be erased from 0x00001000 to 0x00007fff...
Flash will be erased from 0x00008000 to 0x00008fff...
Flash will be erased from 0x00010000 to 0x000e7fff...
Compressed 24768 bytes to 15123...
Writing at 0x00001000... (100 %)
Wrote 24768 bytes (15123 compressed) at 0x00001000 in 0.4 seconds...
Compressed 3072 bytes to 103...
Writing at 0x00008000... (100 %)
Wrote 3072 bytes (103 compressed) at 0x00008000 in 0.1 seconds...
Compressed 913408 bytes to 512345...
Writing at 0x00010000... (100 %)
Wrote 913408 bytes (512345 compressed) at 0x00010000 in 12.3 seconds...
Hash of data verified.

Leaving...
Hard resetting via RTS pin...
```

**ESP32 akan otomatis restart setelah flash selesai.**

---

## Monitoring Output

### 1. Buka Serial Monitor

```bash
idf.py -p /dev/ttyUSB0 monitor
```

### 2. Expected Output

```
I (312) yugoef: ===========================================
I (317) yugoef:   Yugoef WiFi Sensing Firmware v1.0
I (322) yugoef:   Device: esp32-devkit-01
I (327) yugoef:   Endpoint: http://192.168.1.100:8000/v1/ingest
I (332) yugoef: ===========================================
I (337) yugoef: WiFi STA started. Connecting to SSID: MyHomeWiFi
I (1234) yugoef: Got IP: 192.168.1.42
I (1235) yugoef: Connected to WiFi 'MyHomeWiFi'
I (1236) yugoef: Sensing task started (interval=2000ms, window=10)
I (3236) yugoef: RSSI=-45.0 dBm | variance=0.0000 | motion=none
I (3237) yugoef: Payload: {"source":"esp32-devkit-01","event":{"type":"sensing_update","classification":{"presence":false,"motion_level":"none","confidence":0.00},"features":{"motion_band_power":0.0000,"rssi_variance":0.0000,"rssi_current":-45.0}}}
I (3456) yugoef: HTTP POST status: 200
I (5236) yugoef: RSSI=-46.0 dBm | variance=0.2500 | motion=medium
I (5237) yugoef: Payload: {"source":"esp32-devkit-01","event":{"type":"sensing_update","classification":{"presence":true,"motion_level":"medium","confidence":0.25},"features":{"motion_band_power":0.2500,"rssi_variance":0.2500,"rssi_current":-46.0}}}
I (5456) yugoef: HTTP POST status: 200
```

### 3. Keluar dari Monitor

Tekan **Ctrl+]** untuk keluar dari serial monitor.

---

## Verifikasi Data di Cloud

### 1. Cek Log Backend FastAPI

Jika backend Yugoef sudah running:

```bash
# Di server backend
tail -f /var/log/yugoef/app.log
```

**Expected log:**
```
INFO:     192.168.1.42:12345 - "POST /v1/ingest HTTP/1.1" 200 OK
INFO:yugoef.ingest:Received event from esp32-devkit-01: motion_level=medium, confidence=0.25
```

### 2. Test Endpoint dengan curl

```bash
# Test manual dari komputer lain
curl -X POST http://192.168.1.100:8000/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source": "test-device",
    "event": {
      "type": "sensing_update",
      "classification": {
        "presence": true,
        "motion_level": "medium",
        "confidence": 0.75
      },
      "features": {
        "motion_band_power": 0.42,
        "rssi_variance": 0.35,
        "rssi_current": -50.0
      }
    }
  }'
```

**Expected response:**
```json
{
  "status": "ok",
  "message": "Event ingested successfully",
  "event_id": "evt_abc123xyz"
}
```

### 3. Cek Database

Jika menggunakan PostgreSQL/SQLite:

```sql
SELECT * FROM events 
WHERE source = 'esp32-devkit-01' 
ORDER BY timestamp DESC 
LIMIT 10;
```

### 4. Visualisasi di Dashboard

Buka Yugoef dashboard (jika ada):
```
http://192.168.1.100:8000/dashboard
```

Lihat real-time motion detection dari ESP32 Anda.

---

## Troubleshooting

### ❌ Masalah: "Failed to connect to WiFi"

**Gejala:**
```
E (5234) yugoef: Connection failed after 5 retries
```

**Solusi:**
1. **Cek SSID dan password:**
   ```bash
   idf.py menuconfig
   # Pastikan SSID dan password benar (case-sensitive)
   ```

2. **Cek jarak ke router:**
   - Dekatkan ESP32 ke router WiFi
   - RSSI < -80 dBm = sinyal terlalu lemah

3. **Cek band WiFi:**
   - ESP32 hanya support 2.4 GHz
   - Pastikan router broadcasting di 2.4 GHz (bukan hanya 5 GHz)

4. **Cek auth mode:**
   ```c
   // Di main.c, ubah jika perlu:
   .threshold.authmode = WIFI_AUTH_WPA_PSK,  // WPA
   .threshold.authmode = WIFI_AUTH_WPA2_PSK, // WPA2 (default)
   .threshold.authmode = WIFI_AUTH_OPEN,     // Open network
   ```

---

### ❌ Masalah: "HTTP POST failed: ESP_ERR_HTTP_CONNECT"

**Gejala:**
```
E (7234) yugoef: HTTP POST failed: ESP_ERR_HTTP_CONNECT
```

**Solusi:**
1. **Cek backend running:**
   ```bash
   # Di server backend
   systemctl status yugoef
   # atau
   ps aux | grep uvicorn
   ```

2. **Cek URL endpoint:**
   ```bash
   idf.py menuconfig
   # Pastikan URL benar, contoh: http://192.168.1.100:8000/v1/ingest
   ```

3. **Test koneksi dari ESP32:**
   ```bash
   # Ping dari komputer di network yang sama
   ping 192.168.1.100
   ```

4. **Cek firewall:**
   ```bash
   # Di server backend
   sudo ufw allow 8000/tcp
   ```

5. **Cek IP address ESP32:**
   ```
   I (1234) yugoef: Got IP: 192.168.1.42
   ```
   Pastikan ESP32 dan backend di subnet yang sama.

---

### ❌ Masalah: "Failed to open /dev/ttyUSB0: Permission denied"

**Solusi:**
```bash
# Tambahkan user ke group dialout
sudo usermod -aG dialout $USER

# Logout dan login kembali, atau:
newgrp dialout

# Atau gunakan sudo (tidak recommended)
sudo idf.py -p /dev/ttyUSB0 flash
```

---

### ❌ Masalah: Build error "fatal error: esp_wifi.h: No such file or directory"

**Solusi:**
```bash
# Pastikan environment variables di-set
source ~/esp/esp-idf/export.sh

# Tambahkan ke ~/.bashrc:
echo 'source ~/esp/esp-idf/export.sh' >> ~/.bashrc
source ~/.bashrc
```

---

### ❌ Masalah: ESP32 restart terus (boot loop)

**Gejala:**
```
rst:0x10 (RTCWDT_RTC_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)
...
abort() was called at PC 0x400d1234
```

**Solusi:**
1. **Erase flash dan re-flash:**
   ```bash
   idf.py -p /dev/ttyUSB0 erase-flash
   idf.py -p /dev/ttyUSB0 flash
   ```

2. **Cek power supply:**
   - Gunakan power supply yang stabil (minimal 500mA)
   - Hindari USB hub tanpa power

3. **Cek stack size:**
   ```c
   // Di main.c, tambahkan stack size jika perlu:
   xTaskCreate(sensing_task, "sensing_task", 8192, NULL, 5, NULL);
   ```

---

### ❌ Masalah: RSSI selalu 0 atau variance tidak berubah

**Solusi:**
1. **Cek WiFi connection:**
   ```
   I (1234) yugoef: Connected to WiFi 'MyHomeWiFi'
   ```

2. **Test manual RSSI read:**
   ```c
   // Tambahkan debug di sensing_task:
   wifi_ap_record_t ap_info;
   if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
       ESP_LOGI(TAG, "AP: %s, RSSI: %d", ap_info.ssid, ap_info.rssi);
   }
   ```

3. **Cek rolling window size:**
   ```bash
   idf.py menuconfig
   # Pastikan RSSI Rolling Window Size >= 5
   ```

---

### ❌ Masalah: "nvs_flash_init failed: ESP_ERR_NVS_NO_FREE_PAGES"

**Solusi:**
```bash
idf.py -p /dev/ttyUSB0 erase-flash
idf.py -p /dev/ttyUSB0 flash
```

---

### ❌ Masalah: HTTP status 400/422 dari backend

**Gejala:**
```
I (5456) yugoef: HTTP POST status: 422
```

**Solusi:**
1. **Cek JSON payload format:**
   ```bash
   # Copy payload dari serial monitor dan test manual:
   curl -X POST http://192.168.1.100:8000/v1/ingest \
     -H "Content-Type: application/json" \
     -d '{"source":"esp32-devkit-01","event":{...}}'
   ```

2. **Cek backend validation:**
   - Lihat log backend untuk detail error
   - Pastikan field required ada di payload

3. **Update firmware jika schema berubah:**
   ```c
   // Edit main.c, function send_event()
   // Sesuaikan JSON structure dengan backend schema
   ```

---

### ❌ Masalah: Build sangat lambat

**Solusi:**
```bash
# Gunakan parallel build
idf.py build -j8  # 8 cores

# Atau:
export MAKEFLAGS="-j8"
idf.py build
```

---

### ❌ Masalah: "CMake Error: Could not find compiler"

**Solusi:**
```bash
# Install build dependencies
# Ubuntu/Debian:
sudo apt-get install git wget flex bison gperf python3 python3-pip \
  python3-venv cmake ninja-build ccache libffi-dev libssl-dev \
  dfu-util libusb-1.0-0

# Mac:
brew install cmake ninja dfu-util python3 ccache
```

---

## Tips dan Best Practices

### 1. Optimasi Power Consumption

Untuk aplikasi battery-powered:
```c
// Gunakan light sleep antara sampling
esp_sleep_enable_timer_wakeup(SAMPLE_INTERVAL_MS * 1000);
esp_light_sleep_start();
```

### 2. Multiple ESP32 Devices

Gunakan device ID unik:
```bash
# Device 1
idf.py menuconfig  # Set Device ID: esp32-living-room

# Device 2
idf.py menuconfig  # Set Device ID: esp32-bedroom
```

### 3. HTTPS Support

Untuk production, gunakan HTTPS:
```c
// Tambahkan certificate bundle
esp_http_client_config_t config = {
    .url = "https://yugoef.example.com/v1/ingest",
    .crt_bundle_attach = esp_crt_bundle_attach,
};
```

Enable di menuconfig:
```
Component config → ESP TLS → Enable ESP TLS CA Bundle
```

### 4. Logging Level

Ubah log level untuk debugging:
```
Component config → Log output → Default log verbosity
  - Error (default untuk production)
  - Warning
  - Info (default untuk development)
  - Debug
  - Verbose
```

### 5. OTA Updates

Untuk update firmware over-the-air, tambahkan:
```
Component config → ESP System Settings → Enable OTA
```

---

## Resource Links

- **ESP-IDF Documentation:** https://docs.espressif.com/projects/esp-idf/en/v5.2/
- **ESP32 Datasheet:** https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf
- **ESP32 Forum:** https://esp32.com/
- **Yugoef Project:** /home/orangepi/projects/research/yugoef/

---

## FAQ

**Q: Bisa pakai ESP32-S3 atau ESP32-C3?**  
A: Ya, ubah target dengan `idf.py set-target esp32s3` atau `esp32c3`.

**Q: Berapa power consumption?**  
A: ~80mA saat aktif, ~10μA saat deep sleep.

**Q: Bisa connect ke WiFi 5 GHz?**  
A: Tidak, ESP32 hanya support 2.4 GHz.

**Q: Bagaimana jika router menggunakan WPA3?**  
A: Ubah authmode di main.c ke `WIFI_AUTH_WPA3_PSK`.

**Q: Bisa kirim data ke MQTT broker?**  
A: Ya, tambahkan component `esp_mqtt` dan modifikasi `send_event()`.

---

## Changelog

### v1.0 (2026-06-29)
- Initial release
- WiFi RSSI sensing
- Motion classification
- HTTP POST to Yugoef cloud

---

**Happy hacking! 🚀**
