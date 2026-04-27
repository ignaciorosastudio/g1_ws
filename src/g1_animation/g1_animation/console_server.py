#!/usr/bin/env python3
"""
G1 console server — local HTTP/SSE bridge between the browser UI and the
Orin animation server.

Holds one persistent TCP connection to the Orin's wifi_animation_server
and exposes:

    GET  /                  — serves the browser UI from web/
    GET  /api/state         — current snapshot (clips, current clip, conn)
    GET  /api/events        — Server-Sent Events stream of state changes
    POST /api/play  {clip}  — play a clip
    POST /api/stop          — stop (blend to neutral)
    POST /api/speed {value} — set playback speed multiplier

Usage:
    python3 console_server.py --host 192.168.0.123
    open http://127.0.0.1:8080/
"""
import argparse
import json
import logging
import queue
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_ORIN_HOST = "192.168.0.123"
DEFAULT_ORIN_PORT = 9870
DEFAULT_HTTP_PORT = 8080
WEB_DIR = (Path(__file__).parent / "web").resolve()
STATUS_POLL_HZ = 4
RECONNECT_MIN_S = 0.5
RECONNECT_MAX_S = 5.0
SSE_KEEPALIVE_S = 15.0

log = logging.getLogger("console")


class OrinClient:
    """Persistent TCP client to the Orin animation server.

    A single socket is shared between the status-polling thread and HTTP
    handler threads under one lock; the Orin protocol is line-based
    request/response, so serialization is sufficient. State changes are
    pushed to subscribed SSE queues.
    """

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._sock_lock = threading.Lock()
        self._connected = False
        self._clips: list[str] = []
        self._current = "idle"
        self._latency_ms = 0.0
        self._subs: list[queue.Queue] = []
        self._sub_lock = threading.Lock()
        self._stop = threading.Event()

    # -- public API -----------------------------------------------------

    def start(self):
        threading.Thread(target=self._maintain, daemon=True).start()
        threading.Thread(target=self._poll, daemon=True).start()

    def stop(self):
        self._stop.set()

    def snapshot(self) -> dict:
        return {
            "type": "state",
            "connected": self._connected,
            "host": f"{self._host}:{self._port}",
            "clips": list(self._clips),
            "current": self._current,
            "latency_ms": round(self._latency_ms, 1),
        }

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._sub_lock:
            self._subs.append(q)
        q.put(self.snapshot())
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._sub_lock:
            if q in self._subs:
                self._subs.remove(q)

    def send(self, cmd: str) -> str:
        try:
            return self._raw_send(cmd)
        except ConnectionError as e:
            self._mark_disconnected(e)
            raise

    # -- internals ------------------------------------------------------

    def _broadcast(self, msg: dict):
        with self._sub_lock:
            for q in list(self._subs):
                try:
                    q.put_nowait(msg)
                except Exception:
                    pass

    def _maintain(self):
        backoff = RECONNECT_MIN_S
        while not self._stop.is_set():
            if self._connected:
                time.sleep(0.5)
                continue
            try:
                s = socket.create_connection((self._host, self._port), timeout=3.0)
                s.settimeout(5.0)
                with self._sock_lock:
                    self._sock = s
                    self._connected = True
                resp = self._raw_send("list")
                clips: list[str] = []
                if resp.startswith("OK "):
                    clips = sorted(c for c in resp[3:].split(",") if c)
                self._clips = clips
                log.info("Connected to %s:%d (%d clips)", self._host, self._port, len(clips))
                self._broadcast(self.snapshot())
                backoff = RECONNECT_MIN_S
            except (OSError, ConnectionError) as e:
                log.warning("Connect failed: %s — retry in %.1fs", e, backoff)
                self._mark_disconnected(e)
                self._stop.wait(backoff)
                backoff = min(backoff * 1.5, RECONNECT_MAX_S)

    def _poll(self):
        period = 1.0 / STATUS_POLL_HZ
        while not self._stop.is_set():
            self._stop.wait(period)
            if not self._connected:
                continue
            try:
                t0 = time.monotonic()
                resp = self._raw_send("status")
                self._latency_ms = (time.monotonic() - t0) * 1000.0
                if resp.startswith("OK "):
                    self._current = resp[3:].strip()
                    self._broadcast({
                        "type": "tick",
                        "current": self._current,
                        "latency_ms": round(self._latency_ms, 1),
                    })
            except ConnectionError as e:
                self._mark_disconnected(e)

    def _mark_disconnected(self, exc):
        with self._sock_lock:
            was_connected = self._connected
            self._connected = False
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
        if was_connected:
            log.warning("Lost connection: %s", exc)
            self._broadcast(self.snapshot())

    def _raw_send(self, cmd: str) -> str:
        with self._sock_lock:
            if self._sock is None:
                raise ConnectionError("not connected")
            try:
                self._sock.sendall((cmd + "\n").encode())
                buf = b""
                while b"\n" not in buf:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("server closed")
                    buf += chunk
                return buf.decode("utf-8", errors="replace").strip()
            except OSError as e:
                raise ConnectionError(str(e)) from e


CLIENT: OrinClient  # set in main()


class Handler(BaseHTTPRequestHandler):
    server_version = "G1Console/1.0"

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)

    # -- helpers --------------------------------------------------------

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        if not path.is_file():
            self.send_error(404)
            return
        ct = {
            ".html": "text/html; charset=utf-8",
            ".js":   "application/javascript; charset=utf-8",
            ".css":  "text/css; charset=utf-8",
            ".svg":  "image/svg+xml",
            ".ico":  "image/x-icon",
        }.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # -- routes ---------------------------------------------------------

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/events":
            self._handle_sse()
            return
        if url.path == "/api/state":
            self._send_json(200, CLIENT.snapshot())
            return
        rel = url.path.lstrip("/") or "index.html"
        target = (WEB_DIR / rel).resolve()
        try:
            target.relative_to(WEB_DIR)
        except ValueError:
            self.send_error(403)
            return
        self._send_file(target)

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return

        cmd = self._build_cmd(url.path, data)
        if cmd is None:
            self._send_json(400, {"ok": False, "error": "bad request"})
            return

        try:
            resp = CLIENT.send(cmd)
        except ConnectionError as e:
            self._send_json(503, {"ok": False, "error": f"disconnected: {e}"})
            return

        ok = resp.startswith("OK")
        msg = resp.removeprefix("OK ").removeprefix("ERR ")
        self._send_json(200 if ok else 400, {"ok": ok, "msg": msg, "raw": resp})

    def _build_cmd(self, path: str, data: dict) -> str | None:
        if path == "/api/play":
            clip = str(data.get("clip", "")).strip()
            if not clip or any(c.isspace() for c in clip):
                return None
            return f"play {clip}"
        if path == "/api/stop":
            return "stop"
        if path == "/api/speed":
            try:
                v = float(data.get("value"))
            except (TypeError, ValueError):
                return None
            if v <= 0 or v > 10:
                return None
            return f"speed {v}"
        return None

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = CLIENT.subscribe()
        try:
            while True:
                try:
                    msg = q.get(timeout=SSE_KEEPALIVE_S)
                    chunk = f"data: {json.dumps(msg)}\n\n".encode()
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            CLIENT.unsubscribe(q)


def main():
    global CLIENT

    parser = argparse.ArgumentParser(description="G1 console server")
    parser.add_argument("--host", default=DEFAULT_ORIN_HOST,
                        help=f"Orin animation server host (default: {DEFAULT_ORIN_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_ORIN_PORT,
                        help=f"Orin animation server port (default: {DEFAULT_ORIN_PORT})")
    parser.add_argument("--listen", default="127.0.0.1",
                        help="Local HTTP bind address (default: 127.0.0.1)")
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT,
                        help=f"Local HTTP port (default: {DEFAULT_HTTP_PORT})")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open a browser window on startup")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if not WEB_DIR.is_dir():
        log.error("Web directory not found at %s", WEB_DIR)
        return 1

    CLIENT = OrinClient(args.host, args.port)
    CLIENT.start()

    httpd = ThreadingHTTPServer((args.listen, args.http_port), Handler)
    browser_host = "127.0.0.1" if args.listen in ("0.0.0.0", "") else args.listen
    url = f"http://{browser_host}:{args.http_port}/"
    log.info("Console UI:   %s", url)
    log.info("Bridging to:  %s:%d", args.host, args.port)

    if not args.no_browser:
        # Open after a short delay so any startup logs land before the
        # browser starts hammering the server.
        def _open():
            time.sleep(0.3)
            try:
                if not webbrowser.open(url, new=2):
                    log.info("Could not open a browser — visit %s manually", url)
            except Exception as e:
                log.info("Browser launch failed (%s) — visit %s manually", e, url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        CLIENT.stop()
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
