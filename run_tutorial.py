#!/usr/bin/env python3
"""
SKHY - TAMI Tutorial Viewer Launcher
Starts the local web server and automatically opens the interactive tutorial viewer in the default browser.
"""

import sys
import os
import webbrowser
import threading
import time
import uvicorn

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from data_lake_api.ai_ingestion_api import app

def open_browser():
    time.sleep(1.2)
    url = "http://127.0.0.1:8000/manual"
    print(f"\n[+] Opening Engineering Technical Manual in your browser: {url}")
    print("[*] Note: 3D Mission Control Digital Twin is available at: http://127.0.0.1:8000/\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[!] Could not open browser automatically: {e}")
        print(f"[*] Please open your browser and navigate manually to: {url}")

if __name__ == "__main__":
    print("=========================================================================")
    print(" SKHY - TAMI ENGINEERING TECHNICAL DOSSIER & MANUAL")
    print(" Nuclear Fusion & Multi-Reactor Control Stack Technical Guide")
    print("=========================================================================")
    print("[*] Technical Manual: http://127.0.0.1:8000/manual")
    print("[*] Mission Control:  http://127.0.0.1:8000/")
    print("[*] Press Ctrl+C to stop the server at any time.\n")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
