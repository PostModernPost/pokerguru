"""Start the trainer:  python -m trainer   (optional: --port 8000)"""

from __future__ import annotations

import argparse
import logging
import socket

import uvicorn

from trainer.api.app import create_app


def lan_ip() -> str | None:
    """This computer's address on the local network (what the phone should use)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the Wi-Fi interface
            return s.getsockname()[0]
    except OSError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the poker trainer web server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = create_app()
    ip = lan_ip()
    print()
    print(f"  On this computer:  http://localhost:{args.port}")
    if ip:
        print(f"  On your phone:     http://{ip}:{args.port}   (same Wi-Fi)")
    print("  Press Ctrl+C to stop.")
    print()
    # host 0.0.0.0 lets other devices on your network (your phone) connect.
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
