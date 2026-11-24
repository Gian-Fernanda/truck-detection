import time
import threading
import os
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from ultralytics import YOLO

from src.config import AppConfig
from src.zone import ZoneManager
from src.tracker import VehicleTracker
from src.visualizer import Visualizer


class VideoEngine:
    """Thread-safe background engine for video ingestion, YOLO tracking, and stats streaming."""

    def __init__(self, config: AppConfig):
        self.cfg = config
        self.zone_mgr = ZoneManager(self.cfg.zone_file)
        self.tracker = VehicleTracker(self.cfg, self.zone_mgr)
        self.visualizer = Visualizer(self.cfg)

        self.model: Optional[YOLO] = None
        self.cap: Optional[cv2.VideoCapture] = None

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Shared frame & telemetry buffer
        self.latest_encoded_jpeg: Optional[bytes] = None
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.current_fps: float = 0.0
        self.frame_count: int = 0
        self.resolution: str = "0x0"
        self.is_video_ended: bool = False
        self.error_message: Optional[str] = None

        # Telemetry history for charts
        self.occupancy_history: List[Dict[str, Any]] = []

    def start(self):
        if self.running:
            return

        if not os.path.exists(self.cfg.model_path):
            self.error_message = f"Model YOLO tidak ditemukan di: {self.cfg.model_path}"
            print(f"[Engine] ERROR: {self.error_message}")
            return

        print(f"[Engine] Memuat model YOLO: {self.cfg.model_path} ...")
        self.model = YOLO(self.cfg.model_path)

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("[Engine] Video engine background worker dimulai.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        self.tracker.close()
        print("[Engine] Video engine dihentikan.")

    def _run_loop(self):
        self.cap = cv2.VideoCapture(self.cfg.source)
        if not self.cap.isOpened():
            self.error_message = f"Gagal membuka video source: {self.cfg.source}"
            print(f"[Engine] ERROR: {self.error_message}")
            self.running = False
            return

        fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.resolution = f"{width}x{height}"

        prev_time = time.time()
        start_time = time.time()
        last_chart_record = 0

        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                if not self.cfg.is_live:
                    # Video file: loop back to beginning for continuous dashboard preview
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.05)
                    continue
                else:
                    time.sleep(0.1)
                    continue

            self.frame_count += 1
            now = time.time()
            elapsed_sim = (now - start_time) if self.cfg.is_live else (self.frame_count / fps)

            # Hitung FPS real-time
            dt = now - prev_time
            prev_time = now
            inst_fps = 1.0 / dt if dt > 0 else fps
            self.current_fps = round(inst_fps * 0.2 + self.current_fps * 0.8, 1)

            # YOLO Inference & ByteTrack
            results = self.model.track(
                frame,
                persist=True,
                classes=self.cfg.target_classes,
                conf=self.cfg.conf_threshold,
                tracker=self.cfg.tracker_config,
                imgsz=self.cfg.input_size,
                verbose=False,
            )[0]

            raw_detections = []
            if results.boxes is not None and results.boxes.id is not None:
                ids = results.boxes.id.int().tolist()
                boxes = results.boxes.xyxy.tolist()
                classes = results.boxes.cls.int().tolist()
                for tid, box, cls_id in zip(ids, boxes, classes):
                    raw_detections.append((tid, tuple(box), cls_id))

            # Update Tracker logic
            with self.lock:
                tracked_vehicles = self.tracker.update(raw_detections, elapsed_sim)

            # Render overlay frame
            display_frame = frame.copy()
            self.visualizer.draw_zone(display_frame, self.zone_mgr.polygon)
            self.visualizer.draw_vehicles(display_frame, tracked_vehicles)
            self.visualizer.draw_dashboard(
                display_frame,
                active_count=self.tracker.get_active_count(),
                total_entered=self.tracker.total_entered,
                event_logs=self.tracker.event_logs,
            )

            # Encode frame to JPEG with optimal web compression
            ret, buffer = cv2.imencode(".jpg", display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret:
                with self.lock:
                    self.latest_encoded_jpeg = buffer.tobytes()
                    self.latest_raw_frame = frame

            # Record telemetry for charts every 2 seconds
            if now - last_chart_record >= 2.0:
                last_chart_record = now
                timestamp_str = time.strftime("%H:%M:%S")
                with self.lock:
                    self.occupancy_history.append({
                        "time": timestamp_str,
                        "occupancy": self.tracker.get_active_count(),
                        "total_in": self.tracker.total_entered,
                    })
                    if len(self.occupancy_history) > 30:
                        self.occupancy_history.pop(0)

            # Cap frame rate slightly if local video file to avoid CPU overloading
            if not self.cfg.is_live:
                delay = max(0.001, (1.0 / fps) - (time.time() - now))
                time.sleep(delay)

    def get_latest_frame(self) -> Optional[bytes]:
        with self.lock:
            return self.latest_encoded_jpeg

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            active_count = self.tracker.get_active_count()
            total_entered = self.tracker.total_entered
            total_exited = sum(1 for v in self.tracker.vehicles.values() if not v.is_active)

            # Average stay duration (minutes)
            completed_stays = [
                (v.last_seen_time - v.entry_time) / 60.0
                for v in self.tracker.vehicles.values()
                if not v.is_active
            ]
            avg_stay = round(sum(completed_stays) / len(completed_stays), 1) if completed_stays else 0.0

            # Active & Recent Vehicles Table Data
            vehicles_list = []
            for v in sorted(self.tracker.vehicles.values(), key=lambda x: x.display_id, reverse=True):
                duration_min = round((v.last_seen_time - v.entry_time) / 60.0, 1)
                cls_name = self.cfg.class_labels.get(v.class_id, "Truk")
                status = "Aktif di CY" if v.is_active else "Sudah Keluar"
                vehicles_list.append({
                    "id": v.display_id,
                    "type": cls_name,
                    "entry_time": round(v.entry_time, 1),
                    "last_seen": round(v.last_seen_time, 1),
                    "duration_min": duration_min,
                    "is_active": v.is_active,
                    "status": status,
                })

            return {
                "active_count": active_count,
                "total_entered": total_entered,
                "total_exited": total_exited,
                "avg_stay_minutes": avg_stay,
                "fps": self.current_fps,
                "resolution": self.resolution,
                "logs": self.tracker.event_logs[-20:][::-1],
                "vehicles": vehicles_list,
                "occupancy_history": list(self.occupancy_history),
                "zone_points": self.zone_mgr.polygon.tolist() if self.zone_mgr.is_loaded() else [],
                "error": self.error_message,
            }

    def update_zone(self, points: List[List[int]]) -> bool:
        """Update polygon points dynamically from web dashboard."""
        with self.lock:
            self.zone_mgr.save_polygon(points)
            print(f"[Engine] Zone updated from Web: {points}")
            return True
