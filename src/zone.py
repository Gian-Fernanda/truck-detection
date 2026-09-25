import json
import os
import cv2
import numpy as np
from pathlib import Path


class ZoneManager:
    """Manages the Container Yard (CY) polygon zone detection and drawing."""

    def __init__(self, zone_file_path: str):
        self.zone_file_path = zone_file_path
        self.polygon = None
        self.load_or_empty()

    def load_or_empty(self) -> bool:
        if os.path.exists(self.zone_file_path):
            try:
                with open(self.zone_file_path, "r", encoding="utf-8") as f:
                    points = json.load(f)
                    self.polygon = np.array(points, dtype=np.int32)
                return True
            except Exception as e:
                print(f"[ZoneManager] Gagal memuat file zona: {e}")
        self.polygon = None
        return False

    def is_loaded(self) -> bool:
        return self.polygon is not None and len(self.polygon) >= 3

    def save_polygon(self, points):
        self.polygon = np.array(points, dtype=np.int32)
        os.makedirs(os.path.dirname(os.path.abspath(self.zone_file_path)), exist_ok=True)
        with open(self.zone_file_path, "w", encoding="utf-8") as f:
            json.dump(points, f)
        print(f"[ZoneManager] Zona CY berhasil disimpan ke: {self.zone_file_path}")

    def contains_point(self, x: float, y: float) -> bool:
        """Cek apakah titik (x, y) berada di dalam polygon zona CY."""
        if not self.is_loaded():
            return True  # Jika zona belum diatur, default anggap semua di dalam
        return cv2.pointPolygonTest(self.polygon, (float(x), float(y)), False) >= 0

    def draw_interactive(self, source_path: str):
        """Membuka UI OpenCV untuk menggambar polygon zona CY interaktif."""
        cap = cv2.VideoCapture(source_path)
        ok, frame = cap.read()
        cap.release()

        if not ok:
            print(f"[ZoneManager] Gagal membaca frame dari {source_path}")
            return False

        points = []

        def on_mouse(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                points.append([int(x), int(y)])

        window_name = "Gambar Zona CY - Klik Titik, ENTER=Simpan, R=Reset, Q=Batal"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, on_mouse)

        while True:
            display_frame = frame.copy()
            if len(points) > 0:
                cv2.polylines(display_frame, [np.array(points, dtype=np.int32)], False, (0, 255, 255), 2)
                for pt in points:
                    cv2.circle(display_frame, tuple(pt), 4, (0, 255, 255), -1)

            cv2.putText(
                display_frame,
                "Klik titik batas area CY | ENTER: Selesai | R: Reset | Q: Keluar",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            cv2.imshow(window_name, display_frame)

            key = cv2.waitKey(20) & 0xFF
            if key == 13 and len(points) >= 3:  # ENTER
                self.save_polygon(points)
                break
            elif key == ord("r") or key == ord("R"):
                points = []
            elif key == ord("q") or key == ord("Q"):
                break

        cv2.destroyWindow(window_name)
        return self.is_loaded()
