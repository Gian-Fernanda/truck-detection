import os
import sys
import time
import argparse
import cv2
from ultralytics import YOLO

from src.config import AppConfig
from src.zone import ZoneManager
from src.tracker import VehicleTracker
from src.visualizer import Visualizer
from src.engine import VideoEngine
from src.web_server import start_web_server


def run_gui(cfg: AppConfig):
    """Menjalankan monitoring dengan tampilan OpenCV Desktop Window."""
    print("=" * 60)
    print("  VEHICLE DETECTION & TRACKING SYSTEM (DESKTOP GUI)")
    print("=" * 60)
    print(f"Model: {cfg.model_path}")
    print(f"Sumber Video: {cfg.source}")

    # 1. Inisialisasi Zona CY
    zone_mgr = ZoneManager(cfg.zone_file)
    if not zone_mgr.is_loaded():
        print("[INFO] Zona CY belum ada. Menggambar zona interaktif...")
        if not zone_mgr.draw_interactive(cfg.source):
            print("[ERROR] Gagal mengatur zona CY. Program dihentikan.")
            return

    # 2. Inisialisasi Model & Capture
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

            # YOLO Tracking ByteTrack
            results = model.track(
                frame,
                persist=True,
                classes=cfg.target_classes,
                conf=cfg.conf_threshold,
                tracker=cfg.tracker_config,
                imgsz=cfg.input_size,
                verbose=False,
            )[0]

            raw_detections = []
            if results.boxes is not None and results.boxes.id is not None:
                ids = results.boxes.id.int().tolist()
                boxes = results.boxes.xyxy.tolist()
                classes = results.boxes.cls.int().tolist()
                for tid, box, cls_id in zip(ids, boxes, classes):
                    raw_detections.append((tid, tuple(box), cls_id))

            tracked_vehicles = tracker.update(raw_detections, current_time)

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

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                print("[INFO] Dihentikan oleh pengguna.")
                break
            elif key in (ord("z"), ord("Z")):
                cv2.destroyWindow("CY Vehicle Detection & Tracking")
                zone_mgr.draw_interactive(cfg.source)

    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"[INFO] Riwayat tersimpan di: {cfg.csv_file}")


def run_web(cfg: AppConfig, host: str = "0.0.0.0", port: int = 5000):
    """Menjalankan monitoring langsung di Web Dashboard Browser (Default)."""
    engine = VideoEngine(cfg)
    engine.start()
    try:
        start_web_server(engine, host=host, port=port)
    finally:
        engine.stop()


def main():
    parser = argparse.ArgumentParser(description="CY Vehicle Monitoring System")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Jalankan dalam mode Desktop OpenCV GUI (default: Web Dashboard)",
    )
    parser.add_argument("--port", type=int, default=5000, help="Port untuk Web Dashboard (default: 5000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host untuk Web Dashboard (default: 0.0.0.0)")
    args = parser.parse_args()

    cfg = AppConfig()

    if args.gui:
        run_gui(cfg)
    else:
        run_web(cfg, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
