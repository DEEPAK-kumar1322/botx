"""
BotX AI Trading Terminal - Unified Backend API & Web Server Runner.

Starts FastAPI on port 8085 serving both API endpoints and the frontend dashboard.
"""

import os
import sys
import threading
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.server import app

def run_delta_worker():
    """Background worker for 24/7 Delta Exchange India Micro Scanner & Auto-Execution."""
    if os.getenv("DELTA_API_KEY") and os.getenv("DELTA_API_SECRET"):
        try:
            from run_delta_micro_bot import DeltaMicroBot
            print("[Cloud Worker] Starting 24/7 Delta Micro Trading Bot background worker...")
            bot = DeltaMicroBot(auto_trade=True, max_margin_inr=float(os.getenv("MAX_MARGIN_INR", 25.0)))
            bot.run(interval=60)
        except Exception as e:
            print(f"[Cloud Worker Error]: {e}")

def start_server():
    port = int(os.getenv("PORT", 8085))
    host = "0.0.0.0"
    print(f"\n=======================================================")
    print(f"  BotX AI Trading Terminal Server")
    print(f"  Dashboard: http://{host}:{port}")
    print(f"  Interactive API Docs: http://{host}:{port}/docs")
    print(f"=======================================================\n")
    
    # Only start background worker thread if explicitly enabled (e.g. Render cloud deployment)
    if os.getenv("RUN_EMBEDDED_WORKER", "false").lower() == "true":
        threading.Thread(target=run_delta_worker, daemon=True).start()
    
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    start_server()
