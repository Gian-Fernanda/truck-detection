# Container Yard (CY) Vehicle Detection & Tracking

Sistem cerdas berbasis **YOLOv8 + ByteTrack** untuk mendeteksi, melacak, dan mencatat waktu tinggal (*stay duration*) kendaraan truk/kontainer yang masuk dan keluar di area Container Yard (CY).

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
├── data/                           # Data hasil deteksi & log CSV
│   └── riwayat_truk_cy.csv         # Catatan No. Truk, Jenis, Jam Masuk/Keluar, & Durasi Stay
│
├── models/                         # Model weights YOLO (.pt, .onnx, dll)
│   ├── yolov8m.pt
│   └── yolov8n.pt
│
├── src/                            # Source code modular
│   ├── __init__.py
│   ├── config.py                   # Pengaturan terpusat (path, threshold, timing)
│   ├── zone.py                     # Manajemen polygon area CY & tool gambar interaktif
│   ├── tracker.py                  # Logika asosiasi ID, penggabungan kabin-trailer & timeout
│   └── visualizer.py               # Render bounding box, label ID, dan panel HUD
│
├── main.py                         # Entry point utama aplikasi
├── requirements.txt                # Daftar dependensi Python
├── .gitignore                      # Konfigurasi file yang diabaikan Git
└── README.md                       # Dokumentasi project
```

---

## 🚀 Cara Menjalankan

### 1. Jalankan Program Utama
```bash
python main.py
```

### 2. Kontrol Saat Program Berjalan
- **`Q`**: Keluar dari aplikasi.
- **`Z`**: Menggambar ulang area polygon zona CY langsung di jendela video.

---

## ⚙️ Pengaturan & Kustomisasi (`src/config.py`)

Anda dapat mengubah parameter deteksi dan video di file [`src/config.py`](file:///c:/Users/ADVAN/project/vehicle-detection/src/config.py):
- `source`: Path video lokal (contoh: `r"C:\path\to\video.mp4"`) atau RTSP stream CCTV.
- `is_live`: Set ke `True` jika menggunakan CCTV / RTSP real-time.
- `model_path`: Model YOLO yang digunakan (misalnya `yolov8m.pt` atau `yolov8n.pt`).
- `exit_timeout_seconds`: Durasi toleransi (detik) sebelum truk dianggap keluar dari area CY setelah hilang dari pandangan.
- `merge_gap_ratio` & `min_overlap_ratio`: Ambang batas pemisahan truk berdekatan vs penggabungan kabin-trailer.
