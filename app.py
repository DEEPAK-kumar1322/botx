"""
BotX AI Trading Terminal - Unified Backend API & Web Server Runner.

Starts FastAPI on port 8085 serving both API endpoints and the frontend dashboard.
"""

import sys
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.server import app

def start_server(host: str = "127.0.0.1", port: int = 8085):
    print(f"\n=======================================================")
    print(f"  BotX AI Trading Terminal Server")
    print(f"  Dashboard & API: http://localhost:{port}")
    print(f"  Interactive API Docs: http://localhost:{port}/docs")
    print(f"=======================================================\n")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    start_server()
