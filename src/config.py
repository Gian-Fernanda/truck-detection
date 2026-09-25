from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import os

# Root directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

@dataclass
class AppConfig:
    # --- Input Source ---
    source: str = r"C:\Users\ADVAN\Videos\Captures\cyy.mp4"  # Path file video atau RTSP URL
    is_live: bool = False                                   # False = file video, True = RTSP / CCTV live
    
    # --- Model & Detection Settings ---
    model_path: str = str(BASE_DIR / "models" / "yolov8m.pt")
    input_size: int = 640
    conf_threshold: float = 0.25
    target_classes: List[int] = field(default_factory=lambda: [5, 7])  # 5: bus, 7: truck
    class_labels: Dict[int, str] = field(default_factory=lambda: {5: "Bus", 7: "Truk"})

    # --- Tracker Settings ---
    tracker_config: str = str(BASE_DIR / "configs" / "bytetrack_cy.yaml")
    
    # --- CY Zone & Files ---
    zone_file: str = str(BASE_DIR / "configs" / "cy_zone.json")
    csv_file: str = str(BASE_DIR / "data" / "riwayat_truk_cy.csv")
    
    # --- Vehicle Stay & Exit Timing ---
    exit_timeout_seconds: float = 8.0  # Truk dianggap keluar jika tidak terdeteksi selama X detik
    
    # --- Cabin + Trailer Merging Parameters ---
    enable_cabin_merging: bool = True
    merge_gap_ratio: float = 0.08      # Jarak maksimal antar kotak (8% dari tinggi truk)
    min_overlap_ratio: float = 0.50    # Minimal overlap vertikal
    max_merge_count: int = 2           # Maksimal 2 kotak (kabin + trailer)
    
    # --- Re-identification / Lost Track Recovery ---
    enable_track_recovery: bool = True
    recovery_iou_min: float = 0.3      # Minimal IoU untuk memulihkan track yang sempat hilang
    recovery_max_distance_ratio: float = 0.25  # Maksimal pergeseran posisi (25% dari tinggi box)
    
    # --- Visualizer / HUD UI ---
    panel_font_scale: float = 0.45
    panel_line_spacing: int = 18
    max_log_rows: int = 8
