import os
import sys
import time
import cv2
from ultralytics import YOLO

from src.config import AppConfig
from src.zone import ZoneManager
from src.tracker import VehicleTracker
from src.visualizer import Visualizer


def main():
    cfg = AppConfig()

    print("=" * 50)
    print("  VEHICLE DETECTION & TRACKING SYSTEM (CY)")
    print("=" * 50)
    print(f"Model: {cfg.model_path}")
    print(f"Sumber Video: {cfg.source}")
    print(f"Mode Live: {cfg.is_live}")

    # 1. Inisialisasi Zona CY
    zone_mgr = ZoneManager(cfg.zone_file)
    if not zone_mgr.is_loaded():
        print("[INFO] Zona CY belum ada atau belum dikonfigurasi.")
        print("[INFO] Membuka jendela untuk menggambar zona...")
        if not zone_mgr.draw_interactive(cfg.source):
            print("[ERROR] Gagal mengatur zona CY. Program dihentikan.")
            return

    # 2. Inisialisasi Model YOLO & Video Capture
    if not os.path.exists(cfg.model_path):
        print(f"[ERROR] File model tidak ditemukan di: {cfg.model_path}")
        return

    model = YOLO(cfg.model_path)
    cap = cv2.VideoCapture(cfg.source)
    if not cap.isOpened():
        print(f"[ERROR] Gagal membuka video source: {cfg.source}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    tracker = VehicleTracker(cfg, zone_mgr)
    visualizer = Visualizer(cfg)

    frame_idx = 0
    t0 = time.time()

    print("\n[INFO] Deteksi & Tracking dimulai. Tekan 'Q' untuk keluar, 'Z' untuk gambar ulang zona.")

    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break

            frame_idx += 1
            current_time = (time.time() - t0) if cfg.is_live else (frame_idx / fps)

            # 3. Jalankan YOLO Tracking dengan ByteTrack
            results = model.track(
                frame,
                persist=True,
                classes=cfg.target_classes,
                conf=cfg.conf_threshold,
                tracker=cfg.tracker_config,
                imgsz=cfg.input_size,
                verbose=False,
            )[0]

            # 4. Kumpulkan raw detections
            raw_detections = []
            if results.boxes is not None and results.boxes.id is not None:
                ids = results.boxes.id.int().tolist()
                boxes = results.boxes.xyxy.tolist()
                classes = results.boxes.cls.int().tolist()

                for tid, box, cls_id in zip(ids, boxes, classes):
                    raw_detections.append((tid, tuple(box), cls_id))

            # 5. Update tracker logic (penggabungan kabin-trailer & pemisahan truk berdekatan)
            tracked_vehicles = tracker.update(raw_detections, current_time)

            # 6. Render visualisasi
            display_frame = frame.copy()
            visualizer.draw_zone(display_frame, zone_mgr.polygon)
            visualizer.draw_vehicles(display_frame, tracked_vehicles)
            visualizer.draw_dashboard(
                display_frame,
                active_count=tracker.get_active_count(),
                total_entered=tracker.total_entered,
                event_logs=tracker.event_logs,
            )

            cv2.imshow("CY Vehicle Detection & Tracking", display_frame)

            # 7. Kontrol Keyboard
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == ord("Q"):
                print("[INFO] Program dihentikan oleh pengguna.")
                break
            elif key == ord("z") or key == ord("Z"):
                cv2.destroyWindow("CY Vehicle Detection & Tracking")
                print("[INFO] Menggambar ulang zona CY...")
                zone_mgr.draw_interactive(cfg.source)

    except KeyboardInterrupt:
        print("\n[INFO] Dibatalkan oleh pengguna (Ctrl+C).")
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"[INFO] Selesai. Riwayat tersimpan di: {cfg.csv_file}")


if __name__ == "__main__":
    main()
