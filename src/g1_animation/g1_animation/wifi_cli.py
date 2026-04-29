#!/usr/bin/env python3
"""
WiFi animation CLI — thin TCP client for the Orin animation server.

No ROS2 or SDK2 dependencies. Can run from any machine on the WiFi network.

Usage:
    python3 wifi_cli.py --host g1-orin.local
    ros2 run g1_animation wifi_cli          # if installed as ROS2 entry point
"""
import argparse
import socket
import sys

PORT = 9870


def connect(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect((host, port))
    sock.settimeout(10.0)
    return sock


def send_cmd(sock: socket.socket, cmd: str) -> str:
    """Send a command and read the response line."""
    sock.sendall((cmd + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("server disconnected")
        buf += chunk
    return buf.decode("utf-8", errors="replace").strip()


def main(args=None):
    parser = argparse.ArgumentParser(description="WiFi animation CLI")
    parser.add_argument("--host", default="g1-orin.local",
                        help="Animation server host (default: g1-orin.local)")
    parser.add_argument("--port", type=int, default=PORT,
                        help=f"Animation server port (default: {PORT})")
    parsed = parser.parse_args(args)

    print(f"Connecting to {parsed.host}:{parsed.port}...", flush=True)
    try:
        sock = connect(parsed.host, parsed.port)
    except OSError as e:
        print(f"Cannot connect: {e}")
        sys.exit(1)

    # Fetch clip list on connect
    try:
        resp = send_cmd(sock, "list")
        clips_str = resp.removeprefix("OK ") if resp.startswith("OK ") else resp
        print(f"Connected. Available clips: {clips_str}")
    except Exception as e:
        print(f"Connected, but failed to list clips: {e}")

    print("Commands: <clip_name> | stop | list | speed <val> | weight <0..1> | loop on/off | status | quit\n")

    while True:
        try:
            cmd = input("animation> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not cmd:
            continue

        if cmd.lower() in ("quit", "exit", "q"):
            break

        # Map bare clip names to "play <name>"
        parts = cmd.split()
        verb = parts[0].lower()
        if verb not in ("play", "stop", "speed", "weight", "loop", "list", "status"):
            cmd = f"play {cmd}"

        try:
            resp = send_cmd(sock, cmd)
            prefix = "OK" if resp.startswith("OK") else "ERR"
            msg = resp.removeprefix("OK ").removeprefix("ERR ")
            print(f"  [{prefix.lower()}] {msg}")
        except ConnectionError:
            print("  [error] lost connection to server")
            print("  Reconnecting...", flush=True)
            try:
                sock.close()
            except OSError:
                pass
            try:
                sock = connect(parsed.host, parsed.port)
                print("  Reconnected.")
            except OSError as e:
                print(f"  Cannot reconnect: {e}")
                break

    try:
        sock.close()
    except OSError:
        pass


if __name__ == "__main__":
    main()
