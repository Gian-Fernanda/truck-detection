# Container Yard (CY) Vehicle Detection & Monitoring Web Dashboard

Sistem cerdas berbasis **YOLOv8 + ByteTrack** dengan **Interactive Real-time Web Dashboard** untuk mendeteksi, melacak, memvisualisasikan, dan mencatat waktu tinggal (*stay duration*) armada truk/kontainer yang masuk dan keluar di area Container Yard (CY).

---

## ✨ Fitur Web Dashboard

1. **🔴 Live Video Stream & AI Tracking**:
   - Streaming video / RTSP CCTV real-time (~30 FPS) dengan overlay Bounding Box dan Polygon Zona CY.
   - Indikator live status, FPS counter, dan resolusi video.
2. **📊 Real-time KPI Summary Cards**:
   - **Truk di CY Saat Ini**: Jumlah kendaraan yang sedang berada di dalam batas zona CY.
   - **Total Truk Masuk**: Akumulasi seluruh kendaraan yang terdeteksi masuk.
   - **Total Truk Keluar**: Kendaraan yang sudah selesai masa tinggal.
   - **Rata-rata Durasi Stay**: Rata-rata waktu tinggal kendaraan dalam menit.
3. **📈 Grafik Tren Kepadatan (Occupancy Trend)**:
   - Visualisasi kurva real-time tren volume truk di CY menggunakan Chart.js.
4. **📝 Live Event Logs Feed**:
   - Catatan waktu nyata setiap kejadian truk masuk dan keluar dengan label warna dan timestamp.
5. **📋 Tabel Riwayat & Filter Kendaraan**:
   - Pencarian No. Truk dan status (Aktif / Sudah Keluar).
   - Tombol **Export CSV** untuk mengunduh riwayat lengkap.
6. **🖌️ Atur Zona CY Interaktif di Web**:
   - Tombol *"Atur Zona CY"* memungkinkan Anda menggambar polygon batas area CY langsung dengan klik mouse di atas canvas video!

---

## 📁 Struktur Direktori Project

```text
vehicle-detection/
│
├── configs/                        # Konfigurasi sistem
│   ├── bytetrack_cy.yaml           # Parameter tracker ByteTrack
│   ├── botsort_cy.yaml             # Parameter tracker BoTSORT (opsional)
│   └── cy_zone.json                # Koordinat polygon zona CY
│
├── data/                           # Direktori hasil log & CSV
│   └── riwayat_truk_cy.csv         # Catatan No. Truk, Jenis, Jam Masuk/Keluar, & Durasi Stay
│
├── models/                         # Model weights YOLO (.pt, .onnx, dll)
│   ├── yolov8m.pt
│   └── yolov8n.pt
│
├── src/                            # Source code modular
│   ├── __init__.py
│   ├── config.py                   # Centralized configuration (parameter, path, timing)
│   ├── zone.py                     # Manajemen polygon area CY
│   ├── tracker.py                  # Logika tracking & pemisahan truk berdekatan
│   ├── visualizer.py               # Render bounding box, label ID, dan HUD panel
│   ├── engine.py                   # Worker background video processing & telemetry
│   └── web_server.py               # Built-in lightweight HTTP & MJPEG live stream server
│
├── static/                         # Aset Frontend Dashboard
│   ├── css/
│   │   └── style.css               # Design system glassmorphism modern
│   └── js/
│       └── app.js                  # Client telemetry polling, canvas drawing & Chart.js
│
├── templates/
│   └── index.html                  # Halaman Web Dashboard
│
├── main.py                         # Entry point utama (Web Dashboard & Desktop GUI)
├── app.py                          # Shortcut runner khusus Web Dashboard
├── requirements.txt                # Dependensi project
├── .gitignore                      # Konfigurasi Git ignore
└── README.md                       # Dokumentasi project
```

---

## 🚀 Cara Menjalankan

### 1. Jalankan Mode Web Dashboard (Rekomendasi)
```bash
python main.py
```
atau:
```bash
python app.py
```
Buka browser Anda dan akses:
👉 **[http://localhost:5000](http://localhost:5000)** atau **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

### 2. Jalankan Mode Desktop OpenCV GUI (Opsional)
Jika ingin menjalankan tampilan jendela OpenCV desktop standar:
```bash
python main.py --gui
```
- Tekan **`Q`** untuk berhenti dan menyimpan data.
- Tekan **`Z`** untuk menggambar ulang polygon zona CY.
