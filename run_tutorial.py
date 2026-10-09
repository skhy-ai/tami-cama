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
    url = "http://127.0.0.1:8000/tutorial"
    print(f"\n[+] Opening Interactive Tutorial Viewer in your browser: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[!] Could not open browser automatically: {e}")
        print(f"[*] Please open your browser and navigate manually to: {url}")

if __name__ == "__main__":
    print("=========================================================================")
    print(" SKHY - TAMI INTERACTIVE TUTORIAL VIEWER & SIMULATOR")
    print(" Nuclear Fusion & Stellarator Control Stack Beginner Guide")
    print("=========================================================================")
    print("[*] Serving tutorial at: http://127.0.0.1:8000/tutorial")
    print("[*] Press Ctrl+C to stop the server at any time.\n")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
