#!/usr/bin/env python
"""
MASTER STARTUP - Backend + Frontend + Electron
"""
import subprocess
import time
import os
import sys

print("\n" + "="*70)
print("ADA V2 - COMPLETE STARTUP")
print("="*70)

os.chdir(r"C:\Users\LENOVO\Desktop\ada_v2")

print("\nStarting all services...")
print("-" * 70)

try:
    print("\n1. Starting Backend Server (Python)...")
    backend_cmd = [sys.executable, "backend/server.py"]
    backend_proc = subprocess.Popen(
        backend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=r"C:\Users\LENOVO\Desktop\ada_v2"
    )
    print(f"   Backend started (PID: {backend_proc.pid})")
    time.sleep(3)
    
    print("\n2. Starting Frontend + Electron (npm run dev)...")
    frontend_cmd = "npm run dev"
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        shell=True,
        cwd=r"C:\Users\LENOVO\Desktop\ada_v2"
    )
    print(f"   Frontend + Electron started (PID: {frontend_proc.pid})")
    
    print("\n" + "="*70)
    print("ALL SERVICES STARTED!")
    print("="*70)
    print("""
Backend:     http://localhost:8000
Frontend:    http://localhost:5173
Electron:    Desktop window

Press Ctrl+C to stop all services
""")
    
    frontend_proc.wait()
    
except KeyboardInterrupt:
    print("\nShutting down...")
    backend_proc.terminate()
    frontend_proc.terminate()
except Exception as e:
    print(f"\nERROR: {e}")