from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
import numpy as np
import time
import csv
import os

from src.config import AppConfig
from src.zone import ZoneManager


@dataclass
class VehicleRecord:
    display_id: int
    canonical_id: int
    class_id: int
    entry_time: float
    last_seen_time: float
    is_active: bool
    last_box: Tuple[float, float, float, float]
    track_ids: Set[int] = field(default_factory=set)


def calculate_iou(box_a: Tuple[float, float, float, float], box_b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter_area = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter_area <= 0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union_area = area_a + area_b - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


class VehicleTracker:
    """Handles vehicle identity association, cabin-trailer merging, and stay duration logging."""

    def __init__(self, config: AppConfig, zone_manager: ZoneManager):
        self.cfg = config
        self.zone = zone_manager

        self.vehicles: Dict[int, VehicleRecord] = {}  # canonical_id -> VehicleRecord
        self.raw_to_canonical: Dict[int, int] = {}    # raw_track_id -> canonical_id
        self.display_counter = 0

        self.event_logs: List[str] = []
        self.total_entered = 0
        self.csv_file = None
        self.csv_writer = None
        self._init_csv()

    def _init_csv(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.cfg.csv_file)), exist_ok=True)
        file_exists = os.path.exists(self.cfg.csv_file)
        self.csv_file = open(self.cfg.csv_file, "a", newline="", encoding="utf-8-sig")
        self.csv_writer = csv.writer(self.csv_file)
        if not file_exists or os.path.getsize(self.cfg.csv_file) == 0:
            self.csv_writer.writerow(
                ["No. Truk", "Jenis", "Waktu Masuk CY (detik)", "Waktu Keluar CY (detik)", "Lama Stay (menit)"]
            )
            self.csv_file.flush()

    def close(self):
        # Tutup semua kendaraan aktif saat selesai
        for v in self.vehicles.values():
            if v.is_active:
                self._record_exit(v)
        if self.csv_file:
            self.csv_file.close()

    def _is_cabin_trailer_pair(
        self,
        box_a: Tuple[float, float, float, float],
        box_b: Tuple[float, float, float, float],
        raw_id_a: int,
        raw_id_b: int,
    ) -> bool:
        """Pemeriksaan ketat apakah 2 box adalah kabin & trailer dari 1 truk yang sama (BUKAN 2 truk terpisah)."""
        # 1. Jika kedua box sudah memiliki track ID aktif terpisah sebelumnya, JANGAN PERNAH DIGABUNG
        can_a = self.raw_to_canonical.get(raw_id_a)
        can_b = self.raw_to_canonical.get(raw_id_b)
        if can_a is not None and can_b is not None and can_a != can_b:
            veh_a = self.vehicles.get(can_a)
            veh_b = self.vehicles.get(can_b)
            if veh_a is not None and veh_b is not None and veh_a.is_active and veh_b.is_active:
                return False

        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        h_a = ay2 - ay1
        h_b = by2 - by1
        avg_h = (h_a + h_b) / 2.0

        # Cek jarak horizontal
        gap_x = max(ax1, bx1) - min(ax2, bx2)
        max_allowed_gap = avg_h * self.cfg.merge_gap_ratio

        # Cek tumpang tindih vertikal
        top_y = max(ay1, by1)
        bot_y = min(ay2, by2)
        vertical_overlap = max(0.0, bot_y - top_y)
        min_h = min(h_a, h_b)
        overlap_ratio = vertical_overlap / min_h if min_h > 0 else 0.0

        # Dua box hanya digabung jika jaraknya sangat rapat dan sejajar secara vertikal
        if gap_x <= max_allowed_gap and overlap_ratio >= self.cfg.min_overlap_ratio:
            return True
        return False

    def _merge_detections(self, detections: List[Tuple[int, Tuple[float, float, float, float], int]]):
        """Menggabungkan fragmen kabin+trailer yang benar-benar 1 kendaraan."""
        if not self.cfg.enable_cabin_merging:
            return [[[d]] for d in detections]

        groups = [[d] for d in detections]
        merged = True
        while merged:
            merged = False
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    # 1 truk maksimal 2 komponen (kabin + trailer)
                    if len(groups[i]) + len(groups[j]) > self.cfg.max_merge_count:
                        continue

                    # Periksa apakah ada pasangan box yang cocok
                    should_merge = False
                    for item_a in groups[i]:
                        for item_b in groups[j]:
                            id_a, box_a, _ = item_a
                            id_b, box_b, _ = item_b
                            if self._is_cabin_trailer_pair(box_a, box_b, id_a, id_b):
                                should_merge = True
                                break
                        if should_merge:
                            break

                    if should_merge:
                        groups[i].extend(groups[j])
                        del groups[j]
                        merged = True
                        break
                if merged:
                    break
        return groups

    def _find_lost_vehicle_recovery(
        self,
        box: Tuple[float, float, float, float],
        already_matched_canonical_ids: Set[int],
    ) -> Optional[int]:
        """Memulihkan track ID kendaraan yang sempat hilang (occlusion) tanpa merebut kendaraan aktif lain."""
        if not self.cfg.enable_track_recovery:
            return None

        bx1, by1, bx2, by2 = box
        bcx, bcy = (bx1 + bx2) / 2.0, by2
        height = by2 - by1

        best_canonical = None
        best_score = 0.0

        for can_id, v in self.vehicles.items():
            # Hanya cocokkan dengan kendaraan yang SEDANG HILANG (belum terdeteksi di frame ini)
            if can_id in already_matched_canonical_ids:
                continue
            if not v.is_active:
                continue

            last_box = v.last_box
            iou = calculate_iou(box, last_box)
            if iou >= self.cfg.recovery_iou_min:
                if iou > best_score:
                    best_score = iou
                    best_canonical = can_id
            else:
                # Cek jarak titik bawah tengah jika pergerakan minim
                lx1, ly1, lx2, ly2 = last_box
                lcx, lcy = (lx1 + lx2) / 2.0, ly2
                dist = ((bcx - lcx) ** 2 + (bcy - lcy) ** 2) ** 0.5
                max_dist = height * self.cfg.recovery_max_distance_ratio
                if dist <= max_dist:
                    score = 1.0 - (dist / max_dist)
                    if score > best_score:
                        best_score = score
                        best_canonical = can_id

        return best_canonical

    def update(
        self,
        raw_detections: List[Tuple[int, Tuple[float, float, float, float], int]],
        current_time: float,
    ) -> List[Tuple[int, Tuple[float, float, float, float], int, bool]]:
        """
        Input: list of (raw_track_id, (x1, y1, x2, y2), class_id)
        Output: list of (display_id, (x1, y1, x2, y2), class_id, in_zone)
        """
        # 1. Gabungkan kabin + trailer yang valid
        groups = self._merge_detections(raw_detections)

        current_frame_matched_canonical: Set[int] = set()
        frame_results = []

        # 2. Proses setiap kelompok deteksi di frame ini
        for group in groups:
            # Hitung bounding box gabungan
            x1 = min(item[1][0] for item in group)
            y1 = min(item[1][1] for item in group)
            x2 = max(item[1][2] for item in group)
            y2 = max(item[1][3] for item in group)
            combined_box = (x1, y1, x2, y2)

            # Titik bawah-tengah (posisi roda di jalan)
            cx, cy = (x1 + x2) / 2.0, y2
            in_zone = self.zone.contains_point(cx, cy)
            cls_id = 7 if len(group) > 1 else group[0][2]

            # Cari canonical ID dari mapping yang sudah ada
            can_id = None
            for raw_id, _, _ in group:
                mapped = self.raw_to_canonical.get(raw_id)
                if mapped is not None and mapped in self.vehicles:
                    can_id = mapped
                    break

            # Jika belum terdaftar dan berada di dalam CY, coba pulihkan dari lost tracks
            if can_id is None and in_zone:
                can_id = self._find_lost_vehicle_recovery(combined_box, current_frame_matched_canonical)

            # Jika benar-benar baru, buat canonical ID baru
            if can_id is None:
                can_id = min(item[0] for item in group)

            # Daftarkan semua raw_id di grup ini ke canonical ID
            for raw_id, _, _ in group:
                self.raw_to_canonical[raw_id] = can_id

            current_frame_matched_canonical.add(can_id)

            # Update atau buat data kendaraan
            if in_zone:
                if can_id not in self.vehicles:
                    self.display_counter += 1
                    self.total_entered += 1
                    display_id = self.display_counter
                    self.vehicles[can_id] = VehicleRecord(
                        display_id=display_id,
                        canonical_id=can_id,
                        class_id=cls_id,
                        entry_time=current_time,
                        last_seen_time=current_time,
                        is_active=True,
                        last_box=combined_box,
                        track_ids={item[0] for item in group},
                    )
                    log_text = f"[{current_time:.1f}s] MASUK  Truk #{display_id}"
                    print(log_text)
                    self.event_logs.append(log_text)
                else:
                    v = self.vehicles[can_id]
                    v.last_seen_time = current_time
                    v.is_active = True
                    v.last_box = combined_box
                    v.track_ids.update(item[0] for item in group)
                    display_id = v.display_id
            else:
                display_id = self.vehicles[can_id].display_id if can_id in self.vehicles else -1

            frame_results.append((display_id, combined_box, cls_id, in_zone))

        # 3. Cek kendaraan yang sudah keluar (timeout)
        self._check_timeouts(current_time)

        return frame_results

    def _check_timeouts(self, current_time: float):
        for can_id, v in list(self.vehicles.items()):
            if v.is_active and (current_time - v.last_seen_time) > self.cfg.exit_timeout_seconds:
                v.is_active = False
                self._record_exit(v)

    def _record_exit(self, v: VehicleRecord):
        stay_minutes = round((v.last_seen_time - v.entry_time) / 60.0, 2)
        cls_name = self.cfg.class_labels.get(v.class_id, "Truk")
        self.csv_writer.writerow([
            v.display_id,
            cls_name,
            round(v.entry_time, 1),
            round(v.last_seen_time, 1),
            stay_minutes,
        ])
        self.csv_file.flush()
        log_text = f"[{v.last_seen_time:.1f}s] KELUAR Truk #{v.display_id} ({stay_minutes} mnt)"
        print(log_text)
        self.event_logs.append(log_text)

    def get_active_count(self) -> int:
        return sum(1 for v in self.vehicles.values() if v.is_active)
