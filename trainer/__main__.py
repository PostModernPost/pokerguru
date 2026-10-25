"""Start the trainer:  python -m trainer   (optional: --port 8000)"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from trainer.api.app import create_app
from trainer.version import current_version


def lan_ip() -> str | None:
    """This computer's address on the local network (what the phone should use)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the Wi-Fi interface
            return s.getsockname()[0]
    except OSError:
        return None


def trainer_already_running(port: int) -> bool:
    """True if a Poker Trainer answers on this port already (a second window was opened)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/options", timeout=2) as resp:
            return resp.status == 200 and b"spot_types" in resp.read()
    except (urllib.error.URLError, OSError, ValueError):
        return False


def running_version(port: int) -> str | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=2) as r:
            return json.loads(r.read()).get("version")
    except Exception:
        return None


def stop_running_trainer(port: int) -> None:
    """Ask the old server (ours, on this computer) to exit, and wait for the port to free up."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", method="POST")
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass
    for _ in range(50):
        if port_is_free(port):
            return
        time.sleep(0.2)


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def open_browser_when_ready(url: str, timeout: float = 120) -> None:
    """Open the app in the browser once the server answers (runs in a background thread)."""
    def wait():
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(url + "/api/summary", timeout=2)
                webbrowser.open(url)
                return
            except (urllib.error.URLError, OSError, ValueError):
                time.sleep(0.5)
    threading.Thread(target=wait, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the poker trainer web server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser automatically")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    port = args.port
    if trainer_already_running(port):
        url = f"http://localhost:{port}"
        if running_version(port) == current_version():
            print(f"\n  Poker Trainer is already running at {url} (another window has it open).")
            print("  Opening that one. Close this window; use the other window to stop the server.\n")
            if not args.no_browser:
                webbrowser.open(url)
            return
        print(f"\n  An older Poker Trainer is still running at {url}; replacing it with the updated one.")
        stop_running_trainer(port)
    if not port_is_free(port):
        # Something else owns the port: move to the next free one and say so.
        for candidate in range(port + 1, port + 11):
            if port_is_free(candidate):
                print(f"\n  Port {port} is in use by another program; using {candidate} instead.")
                port = candidate
                break
        else:
            print(f"\n  Ports {port}-{port + 10} are all in use. Close other programs and try again.")
            return

    app = create_app()
    ip = lan_ip()
    url = f"http://localhost:{port}"
    print()
    print(f"  On this computer:  {url}")
    if ip:
        print(f"  On your phone:     http://{ip}:{port}   (same Wi-Fi)")
    print("  Press Ctrl+C to stop.")
    print()
    if not args.no_browser:
        open_browser_when_ready(url)
    # host 0.0.0.0 lets other devices on your network (your phone) connect.
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
