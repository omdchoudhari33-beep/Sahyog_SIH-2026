"""
Starts every Sahyog backend service (Language Normalizer, Evidence
Extractor, Triage & Route, Orchestrator, ULB Dispatch, Track B Innovation,
Industry Partnership, Lifecycle Outcome, Transparency Layer - see SERVICES
below) and streams their combined output into one timestamped,
per-service-tagged log file instead of nine separate windows.

Usage:
    python start_pipeline.py

Ctrl+C stops every service cleanly.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Windows defaults a redirected/piped stdout to the system's ANSI codepage
# (cp1252 here), not UTF-8 - fine for plain ASCII debug prints, but this
# pipeline's whole point is multilingual text (Hindi/Bengali/Odia/Santali
# Ol Chiki...), and any service that prints one of those strings (or, as hit
# live, a non-ASCII character in a citizen-uploaded filename) crashes that
# request with UnicodeEncodeError - see "2.Evidence Extractor/main.py"'s
# `print(f"Saved original image to {image_path}")`. PYTHONUTF8=1 forces each
# child's own stdout/stderr to real UTF-8 (PEP 540); reconfiguring this
# script's own stdout covers the `print(stamped)` below, which re-emits
# that same child output and would otherwise hit the identical crash one
# level up.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "sahyog.log"

SERVICES = [
    {
        "name": "agent1",
        "dir": ROOT / "1.Language normalizer",
        "module": "app.main:app",
        "port": 8001,
    },
    {
        "name": "agent2",
        "dir": ROOT / "2.Evidence Extractor",
        "module": "main:app",
        "port": 8002,
    },
    {
        "name": "agent3",
        "dir": ROOT / "3.Triage and route",
        "module": "app.main:app",
        "port": 8003,
    },
    {
        "name": "orchestrator",
        "dir": ROOT / "4.Orchestrator",
        "module": "app.main:app",
        # Not 8000: an unidentified Windows system service (Session 0,
        # "Manager.exe", no resolvable path/vendor) holds an exclusive
        # dual-stack lock on 8000 on this machine, rejecting binds on both
        # 0.0.0.0 and 127.0.0.1. Moved to 8005 rather than touching that
        # process, which is unsafe to kill without knowing what it is.
        "port": 8005,
        "extra_args": ["--host", "0.0.0.0"],
    },
    {
        "name": "agent5",
        "dir": ROOT / "5.ULB Dispatch",
        "module": "app.main:app",
        "port": 8004,
    },
    {
        "name": "agent6",
        "dir": ROOT / "6.Track B Innovation",
        "module": "app.main:app",
        "port": 8006,
    },
    {
        "name": "agent7",
        "dir": ROOT / "7.Industry Partnership",
        "module": "app.main:app",
        "port": 8007,
    },
    {
        "name": "agent8",
        "dir": ROOT / "8.Lifecycle Outcome",
        "module": "app.main:app",
        "port": 8008,
    },
    {
        "name": "agent9",
        "dir": ROOT / "9.Transparency Layer",
        "module": "app.main:app",
        "port": 8009,
    },
]

DEPENDENCIES = [
    ("Postgres (Agent 3's DB)", "127.0.0.1", 5432,
     'cd "3.Triage and route" && docker compose up -d --build'),
    ("Ollama (Agent 2's local models + Agent 3's Ask Sahyog RAG)", "127.0.0.1", 11434,
     # --gpus=all is required - without it Ollama silently falls back to
     # CPU inference, which is roughly 9x slower for C1/C3 on this box
     # (measured: 5.2s vs 33.2s for text, 10s vs 106s for vision).
     "docker run -d --gpus=all --name ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama"),
]

log_lock = threading.Lock()


def port_is_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_dependencies() -> None:
    print("Checking external dependencies (Postgres, Ollama)...")
    for label, host, port, fix in DEPENDENCIES:
        if port_is_open(host, port):
            print(f"  [ok]   {label} - reachable on {host}:{port}")
        else:
            print(f"  [WARN] {label} - not reachable on {host}:{port}")
            print(f"         start it with: {fix}")
    print()


def stream_output(name: str, pipe, log_handle) -> None:
    for line in iter(pipe.readline, ""):
        if not line:
            break
        stamped = f"[{datetime.now().strftime('%H:%M:%S')}] [{name:12}] {line.rstrip()}"
        with log_lock:
            print(stamped)
            log_handle.write(stamped + "\n")
            log_handle.flush()
    pipe.close()


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)
    check_dependencies()

    log_handle = open(LOG_FILE, "a", encoding="utf-8")
    log_handle.write(f"\n===== Sahyog pipeline started {datetime.now().isoformat()} =====\n")

    processes: list[tuple[str, subprocess.Popen]] = []
    threads: list[threading.Thread] = []

    for svc in SERVICES:
        venv_python = svc["dir"] / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            print(
                f"[WARN] {svc['name']}: no venv at {venv_python} - skipping.\n"
                f"       Run: cd \"{svc['dir'].name}\" && python -m venv .venv "
                f"&& .venv\\Scripts\\pip install -r requirements.txt"
            )
            continue

        cmd = [
            str(venv_python), "-m", "uvicorn", svc["module"],
            "--port", str(svc["port"]),
            *svc.get("extra_args", []),
        ]
        proc = subprocess.Popen(
            cmd,
            cwd=svc["dir"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        processes.append((svc["name"], proc))
        t = threading.Thread(target=stream_output, args=(svc["name"], proc.stdout, log_handle), daemon=True)
        t.start()
        threads.append(t)
        print(f"Started {svc['name']} on port {svc['port']} (pid {proc.pid})")

    if not processes:
        print("Nothing to start - no service has a venv set up yet.")
        return 1

    print(f"\nAll services launching. Centralized log: {LOG_FILE}")
    print("Citizen UI: run citizen-portal separately (see its own README)")
    print("Dashboard:  http://127.0.0.1:8005/dashboard")
    print(
        "Ask Sahyog (RAG): first run, in \"3.Triage and route\": "
        "psql \"$DATABASE_URL\" -f schema_004_kb_chunks.sql && "
        "python -m app.rag_ingest"
    )
    print("Press Ctrl+C to stop everything.\n")

    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                code = proc.poll()
                if code is not None:
                    print(f"[WARN] {name} exited with code {code} - see {LOG_FILE}")
    except KeyboardInterrupt:
        print("\nStopping all services...")
        for name, proc in processes:
            proc.terminate()
        for name, proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        log_handle.write(f"===== Sahyog pipeline stopped {datetime.now().isoformat()} =====\n")
        log_handle.close()
        print("Stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
