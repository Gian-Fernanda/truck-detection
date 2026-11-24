"""
CY Vehicle Detection & Tracking Web Dashboard Runner.
"""

from src.config import AppConfig
from src.engine import VideoEngine
from src.web_server import start_web_server


def main():
    cfg = AppConfig()

    print("=" * 60)
    print("  🚀 MEMULAI CY TRUCK MONITORING WEB DASHBOARD")
    print("=" * 60)
    print(f"Model: {cfg.model_path}")
    print(f"Sumber Video: {cfg.source}")
    print(f"Mode Live: {cfg.is_live}")

    engine = VideoEngine(cfg)
    engine.start()

    try:
        # Jalankan web server di port 5000 (bisa dibuka via http://localhost:5000)
        start_web_server(engine, host="0.0.0.0", port=5000)
    finally:
        engine.stop()


if __name__ == "__main__":
    main()
