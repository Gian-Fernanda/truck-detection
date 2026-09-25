import cv2
import numpy as np
from typing import List, Tuple
from src.config import AppConfig


class Visualizer:
    """Renders overlays, bounding boxes, polygon zones, and real-time statistics panels."""

    def __init__(self, config: AppConfig):
        self.cfg = config

    def draw_zone(self, frame: np.ndarray, polygon: np.ndarray):
        if polygon is not None and len(polygon) >= 3:
            cv2.polylines(frame, [polygon], True, (0, 255, 255), 2)

    def draw_vehicles(
        self,
        frame: np.ndarray,
        vehicles: List[Tuple[int, Tuple[float, float, float, float], int, bool]],
    ):
        for display_id, box, cls_id, in_zone in vehicles:
            x1, y1, x2, y2 = map(int, box)
            cx, cy = int((x1 + x2) / 2), y2

            color = (0, 220, 0) if in_zone else (0, 0, 240)

            # Bounding box & bottom center dot
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, (cx, cy), 4, color, -1)

            # Text label
            label = f"Truk #{display_id}" if display_id > 0 else "Di Luar CY"
            
            # Label background box for clean readability
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                frame,
                label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )

    def draw_dashboard(
        self,
        frame: np.ndarray,
        active_count: int,
        total_entered: int,
        event_logs: List[str],
    ):
        summary_text = f"Truk di CY: {active_count} | Total Masuk: {total_entered}"
        recent_logs = [summary_text] + event_logs[-self.cfg.max_log_rows:][::-1]

        panel_w = 420
        panel_h = 16 + self.cfg.panel_line_spacing * (len(recent_logs) + 1)

        # Semi-transparent overlay panel
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (10 + panel_w, panel_h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        for i, text in enumerate(recent_logs):
            color = (0, 255, 255) if i == 0 else (255, 255, 255)
            font_thick = 2 if i == 0 else 1
            y_pos = 32 + i * self.cfg.panel_line_spacing
            cv2.putText(
                frame,
                text,
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.cfg.panel_font_scale,
                color,
                font_thick,
                cv2.LINE_AA,
            )
