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
    python3 console_server.py --host g1-orin.local
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

DEFAULT_ORIN_HOST = "g1-orin.local"
DEFAULT_ORIN_PORT = 9870
DEFAULT_HTTP_PORT = 8080
DEFAULT_CUES_PATH = Path.home() / "g1_ws" / "cues.json"
WEB_DIR = (Path(__file__).parent / "web").resolve()
STATUS_POLL_HZ = 4
RECONNECT_MIN_S = 0.5
RECONNECT_MAX_S = 5.0
SSE_KEEPALIVE_S = 15.0

log = logging.getLogger("console")


def parse_time(v) -> float:
    """Accept either a float (seconds) or 'M:SS.s' / 'H:MM:SS.s' string."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(s)
    raise ValueError(f"bad time value: {v!r}")


def load_cues(path: Path) -> dict:
    """Read and validate the cue list JSON. Always returns a dict; on
    error, returns an empty list with a 'warning' field for the UI."""
    if not path.is_file():
        return {"name": None, "duration": 0.0, "cues": [],
                "warning": f"cue file not found: {path}",
                "path": str(path)}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return {"name": None, "duration": 0.0, "cues": [],
                "warning": f"failed to read cues: {e}",
                "path": str(path)}

    cues_out = []
    for i, raw in enumerate(data.get("cues", [])):
        try:
            t = parse_time(raw["t"])
        except (KeyError, ValueError) as e:
            log.warning("cue %d: skipped (%s)", i, e)
            continue
        cue = {
            "t": t,
            "action": raw.get("action", "play"),
        }
        if "clip"    in raw: cue["clip"]    = str(raw["clip"])
        if "label"   in raw: cue["label"]   = str(raw["label"])
        if "speed"   in raw:
            try: cue["speed"] = float(raw["speed"])
            except (TypeError, ValueError): pass
        if "preroll" in raw:
            try: cue["preroll"] = max(0.0, float(raw["preroll"]))
            except (TypeError, ValueError): pass
        cues_out.append(cue)
    cues_out.sort(key=lambda c: c["t"])

    last_t = cues_out[-1]["t"] if cues_out else 0.0
    duration = float(data.get("duration", last_t + 1.0))
    return {
        "name": data.get("name"),
        "duration": duration,
        "cues": cues_out,
        "path": str(path),
    }


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

    def refresh_clips(self):
        """Re-fetch the clip list from the Orin and broadcast the snapshot.
        Used after `record stop` so the new clip shows up as a tile."""
        try:
            resp = self._raw_send("list")
        except ConnectionError as e:
            self._mark_disconnected(e)
            return
        if resp.startswith("OK "):
            self._clips = sorted(c for c in resp[3:].split(",") if c)
            self._broadcast(self.snapshot())

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
CUES_PATH: Path     # set in main()
VIDEO_PATH: Path | None = None  # set in main(); None disables /api/video


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
        if url.path == "/api/cues":
            self._send_json(200, load_cues(CUES_PATH))
            return
        if url.path == "/api/video":
            self._handle_video()
            return
        if url.path == "/api/video/info":
            self._send_json(200, self._video_info())
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

        if url.path == "/api/cues":
            self._handle_save_cues(data)
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
        if ok and url.path == "/api/record/save":
            CLIENT.refresh_clips()
        self._send_json(200 if ok else 400, {"ok": ok, "msg": msg, "raw": resp})

    def _handle_save_cues(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("cues"), list):
            self._send_json(400, {"ok": False, "error": "missing 'cues' array"})
            return
        try:
            validated = []
            for raw in data["cues"]:
                if not isinstance(raw, dict):
                    continue
                t = parse_time(raw["t"])
                cue = {"t": t, "action": raw.get("action", "play")}
                for f in ("clip", "label"):
                    if raw.get(f):
                        cue[f] = str(raw[f])
                for f in ("speed", "preroll"):
                    if f in raw:
                        try:
                            cue[f] = float(raw[f])
                        except (TypeError, ValueError):
                            pass
                validated.append(cue)
            validated.sort(key=lambda c: c["t"])

            out = {"duration": float(data.get("duration", 0)), "cues": validated}
            if data.get("name"):
                out = {"name": str(data["name"]), **out}

            CUES_PATH.parent.mkdir(parents=True, exist_ok=True)
            if CUES_PATH.is_file():
                bak = CUES_PATH.with_suffix(CUES_PATH.suffix + ".bak")
                bak.write_bytes(CUES_PATH.read_bytes())
            tmp = CUES_PATH.with_suffix(CUES_PATH.suffix + ".tmp")
            tmp.write_text(json.dumps(out, indent=2) + "\n")
            tmp.replace(CUES_PATH)

            log.info("Saved %d cues to %s", len(validated), CUES_PATH)
            self._send_json(200, {"ok": True, "saved": len(validated),
                                  "path": str(CUES_PATH)})
        except (KeyError, ValueError) as e:
            self._send_json(400, {"ok": False, "error": f"invalid cue: {e}"})
        except OSError as e:
            log.exception("Failed to write cues")
            self._send_json(500, {"ok": False, "error": f"write failed: {e}"})

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
        if path == "/api/record/start":
            name = str(data.get("name", "")).strip()
            if not name or any(c.isspace() for c in name) or "/" in name:
                return None
            try:
                interval = float(data.get("interval", 0.1))
            except (TypeError, ValueError):
                return None
            interp = str(data.get("interp", "linear"))
            if interp not in ("linear", "smoothstep", "catmull_rom"):
                return None
            return f"record start name={name} interval={interval} interp={interp}"
        if path == "/api/record/stop_capture":
            return "record stop_capture"
        if path == "/api/record/save":
            return "record save"
        if path == "/api/record/cancel":
            return "record cancel"
        return None

    # ---- Video (Range-aware static serve) ----------------------------

    _VIDEO_CT = {
        ".mp4":  "video/mp4",
        ".m4v":  "video/mp4",
        ".webm": "video/webm",
        ".ogv":  "video/ogg",
        ".mov":  "video/quicktime",
    }

    def _video_info(self) -> dict:
        if VIDEO_PATH is None:
            return {"available": False}
        if not VIDEO_PATH.is_file():
            return {"available": False, "error": f"file not found: {VIDEO_PATH}"}
        return {
            "available": True,
            "url": "/api/video",
            "filename": VIDEO_PATH.name,
            "size": VIDEO_PATH.stat().st_size,
        }

    def _handle_video(self):
        if VIDEO_PATH is None or not VIDEO_PATH.is_file():
            self.send_error(404, "video not configured")
            return
        size = VIDEO_PATH.stat().st_size
        ct = self._VIDEO_CT.get(VIDEO_PATH.suffix.lower(), "application/octet-stream")
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        partial = False
        if rng and rng.startswith("bytes="):
            try:
                spec = rng[len("bytes="):].split(",", 1)[0].strip()
                a, b = spec.split("-", 1)
                if a:
                    start = int(a)
                if b:
                    end = int(b)
                if start < 0 or end >= size or start > end:
                    raise ValueError
                partial = True
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ct)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with VIDEO_PATH.open("rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

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
    global CLIENT, CUES_PATH, VIDEO_PATH

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
    parser.add_argument("--cues", default=str(DEFAULT_CUES_PATH),
                        help=f"Path to cue list JSON (default: {DEFAULT_CUES_PATH})")
    parser.add_argument("--video", default=None,
                        help="Path to a video file (mp4/webm) to preview "
                             "alongside the timeline. Optional.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if not WEB_DIR.is_dir():
        log.error("Web directory not found at %s", WEB_DIR)
        return 1

    CUES_PATH = Path(args.cues).expanduser()
    log.info("Cues path:    %s", CUES_PATH)

    if args.video:
        VIDEO_PATH = Path(args.video).expanduser()
        if VIDEO_PATH.is_file():
            log.info("Video preview: %s (%.1f MB)",
                     VIDEO_PATH, VIDEO_PATH.stat().st_size / 1e6)
        else:
            log.warning("Video file not found: %s — /api/video disabled", VIDEO_PATH)
            VIDEO_PATH = None

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
