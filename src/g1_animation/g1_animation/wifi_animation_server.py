#!/usr/bin/env python3
"""
WiFi animation server — runs on the Orin (Jetson).

Runs the full animation engine locally (200 Hz control loop + DDS) and
accepts lightweight text commands from the PC over TCP.

Usage:
    python3 wifi_animation_server.py --interface eth0 --clips-dir ~/clips
"""
import argparse
import json
import logging
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Optional

from unitree_sdk2py.core.channel import (
    ChannelPublisher,
    ChannelSubscriber,
    ChannelFactoryInitialize,
)
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC

log = logging.getLogger("anim-server")

# ---------------------------------------------------------------------------
# G1 constants (duplicated to avoid ROS2 / package dependencies)
# ---------------------------------------------------------------------------

UPPER_BODY_JOINTS = [
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]

G1_JOINT_INDEX = {
    "waist_yaw_joint":            12,
    "waist_roll_joint":           13,
    "waist_pitch_joint":          14,
    "left_shoulder_pitch_joint":  15,
    "left_shoulder_roll_joint":   16,
    "left_shoulder_yaw_joint":    17,
    "left_elbow_joint":           18,
    "left_wrist_roll_joint":      19,
    "left_wrist_pitch_joint":     20,
    "left_wrist_yaw_joint":       21,
    "right_shoulder_pitch_joint": 22,
    "right_shoulder_roll_joint":  23,
    "right_shoulder_yaw_joint":   24,
    "right_elbow_joint":          25,
    "right_wrist_roll_joint":     26,
    "right_wrist_pitch_joint":    27,
    "right_wrist_yaw_joint":      28,
}

NEUTRAL = [
    0.0, 0.0, 0.0,
    0.2907, 0.2249, 0.0003, 0.9769, 0.1021, 0.0, 0.0,
    0.2939, -0.2376, 0.0196, 0.9779, -0.1333, 0.0, 0.0,
]

WALKING_EXCLUDE = set()  # empty — animate all upper-body joints including waist

KP               = 60.0
KD               = 1.5
CONTROL_DT       = 0.005   # 200 Hz
WEIGHT_JOINT     = 29
WEIGHT_RAMP_STEPS = 200
MAX_JOINT_VEL    = 3.0     # rad/s
MAX_JOINT_ACCEL  = 2.0     # rad/s²
NUM_JOINTS       = len(UPPER_BODY_JOINTS)
PORT             = 9870


# ---------------------------------------------------------------------------
# Clip loading (from keyframes.py, no ROS2)
# ---------------------------------------------------------------------------

def load_clips(clips_dir: Path) -> dict:
    clips = {}
    if not clips_dir.is_dir():
        log.warning("Clips directory not found: %s", clips_dir)
        return clips
    for path in sorted(clips_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            clips[path.stem] = {
                "keyframes": data["keyframes"],
                "interp":    data.get("interp", "linear"),
            }
        except Exception as e:
            log.warning("Could not load %s: %s", path.name, e)
    return clips


# ---------------------------------------------------------------------------
# Animation engine (from animation_core.py, ROS2 removed)
# ---------------------------------------------------------------------------

class AnimationEngine:
    """Clip playback with interpolation and velocity/accel capping.

    Tracks an arm_sdk weight that is 0 while idle and 1 while a clip is
    playing, ramped smoothly each direction. The control loop reads
    ``engine.weight`` every tick and publishes it in motor_cmd[29].q.
    """

    def __init__(
        self,
        clips: dict,
        initial_positions=None,
        live_positions_fn=None,
        max_weight: float = 1.0,
        clips_dir: Optional[Path] = None,
        mode: str = "walking",
    ):
        self._clips = clips
        self._clips_dir = clips_dir
        self._mode = mode
        self._speed = 1.0
        self._loop = False
        self._playing = False
        self._current_clip = None
        self._queued_animation = None
        self._keyframes = []
        self._interp_mode = "linear"
        self._start_time = time.monotonic()
        self._current_positions = list(initial_positions or NEUTRAL)
        self._prev_velocities = [0.0] * NUM_JOINTS
        self._weight = 0.0
        self._target_weight = 0.0
        self._max_weight = max(0.0, min(1.0, max_weight))
        self._weight_step = 1.0 / WEIGHT_RAMP_STEPS
        self._live_positions_fn = live_positions_fn
        self._lock = threading.Lock()
        # Recording state
        self._recording = False
        self._record_buffer: list = []
        self._record_name = ""
        self._record_interval = 0.1
        self._record_interp = "linear"
        self._record_start_t = 0.0
        self._record_thread: Optional[threading.Thread] = None

    @property
    def status(self) -> str:
        if self._recording:
            return f"recording:{self._record_name}"
        return self._current_clip or "idle"

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def clip_names(self) -> list:
        return sorted(self._clips.keys())

    @property
    def weight(self) -> float:
        return self._weight

    def set_max_weight(self, val: float) -> str:
        if not 0.0 <= val <= 1.0:
            return "ERR weight must be in [0.0, 1.0]"
        with self._lock:
            self._max_weight = val
            if self._playing:
                self._target_weight = val
        return f"OK max weight set to {val:.2f}"

    def _reseed_from_live(self):
        # Called under self._lock when idle→playing; loco controller has
        # been driving the arms, so our cached _current_positions is stale.
        if self._live_positions_fn is None:
            return
        live = self._live_positions_fn()
        if live is not None:
            self._current_positions = list(live)
            self._prev_velocities = [0.0] * NUM_JOINTS

    def play(self, name: str) -> str:
        if name not in self._clips:
            return f"ERR unknown clip '{name}'"
        clip = self._clips[name]
        kfs = clip["keyframes"]
        if len(kfs) < 2:
            return f"ERR '{name}' has fewer than 2 keyframes"
        for i, kf in enumerate(kfs):
            if len(kf["positions"]) != NUM_JOINTS:
                return f"ERR [{name}] keyframe {i}: expected {NUM_JOINTS} positions, got {len(kf['positions'])}"
        with self._lock:
            if not self._playing:
                self._reseed_from_live()
            self._queued_animation = name
            self._keyframes = [
                {"time": 0.0, "positions": list(self._current_positions)},
                {"time": 1.0, "positions": list(NEUTRAL)},
            ]
            self._interp_mode = "linear"
            self._start_time = time.monotonic()
            self._loop = False
            self._playing = True
            self._target_weight = self._max_weight
        return f"OK Queued '{name}' — blending to neutral first"

    def stop(self) -> str:
        with self._lock:
            if not self._playing:
                self._reseed_from_live()
            self._queued_animation = None
            self._keyframes = [
                {"time": 0.0, "positions": list(self._current_positions)},
                {"time": 1.5, "positions": list(NEUTRAL)},
            ]
            self._interp_mode = "linear"
            self._start_time = time.monotonic()
            self._loop = False
            self._playing = True
            self._target_weight = self._max_weight
        return "OK Stopping — blending to neutral"

    def request_shutdown(self):
        """Stop playback and begin ramping weight to 0."""
        with self._lock:
            self._queued_animation = None
            self._playing = False
            self._current_clip = None
            self._target_weight = 0.0

    def set_speed(self, val: float) -> str:
        if val <= 0:
            return "ERR speed must be > 0"
        with self._lock:
            if self._playing:
                old_elapsed = (time.monotonic() - self._start_time) * self._speed
                self._speed = val
                self._start_time = time.monotonic() - old_elapsed / self._speed
            else:
                self._speed = val
        return f"OK speed set to {val:.2f}x"

    def set_loop(self, val: bool) -> str:
        self._loop = val
        return f"OK loop={'on' if val else 'off'}"

    # -- Recording ------------------------------------------------------

    def start_recording(self, name: str, interval: float, interp: str) -> str:
        sanitized = name.strip().lower().replace(" ", "_")
        if not sanitized or "/" in sanitized or ".." in sanitized:
            return f"ERR invalid recording name '{name}'"
        if not 0.005 <= interval <= 5.0:
            return "ERR interval must be between 0.005 and 5.0 seconds"
        if interp not in ("linear", "smoothstep", "catmull_rom"):
            return f"ERR unknown interp '{interp}'"
        if self._recording:
            return "ERR already recording"
        if self._playing:
            return "ERR cannot record while playing — stop first"
        if self._live_positions_fn is None:
            return "ERR no robot state available"
        if self._clips_dir is None:
            return "ERR no clips directory configured"

        with self._lock:
            self._recording = True
            self._record_name = sanitized
            self._record_interval = interval
            self._record_interp = interp
            self._record_buffer = []
            self._record_start_t = time.monotonic()
            self._target_weight = 0.0
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        log.info("Recording started: %s @ %.3fs interval, %s",
                 sanitized, interval, interp)
        return f"OK Recording '{sanitized}' @ {1.0/interval:.1f}fps"

    def _record_loop(self):
        start = self._record_start_t
        interval = self._record_interval
        n = 0
        while self._recording:
            t = time.monotonic() - start
            positions = self._live_positions_fn() if self._live_positions_fn else None
            if positions is not None:
                self._record_buffer.append(
                    (round(t, 4), [round(p, 4) for p in positions])
                )
            n += 1
            wait = (start + n * interval) - time.monotonic()
            if wait > 0:
                time.sleep(wait)

    def stop_capture(self) -> str:
        """Stop capturing frames; keep the buffer for a subsequent save."""
        if not self._recording:
            return "ERR not recording"
        with self._lock:
            self._recording = False
        if self._record_thread:
            self._record_thread.join(timeout=2.0)
        log.info("Capture stopped: %d frames buffered", len(self._record_buffer))
        return f"OK Capture stopped ({len(self._record_buffer)} frames buffered)"

    def save_recording(self) -> str:
        """Write the buffered frames to disk."""
        if self._recording:
            return "ERR still capturing — stop first"
        with self._lock:
            buf = list(self._record_buffer)
            name = self._record_name
            interp = self._record_interp
        if not buf:
            return "ERR no frames to save"
        if self._clips_dir is None:
            return "ERR no clips directory configured"

        keyframes = [{"time": t, "positions": pos} for t, pos in buf]
        data = {"interp": interp, "keyframes": keyframes}
        self._clips_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._clips_dir / f"{name}.json"
        out_path.write_text(json.dumps(data, indent=2))

        new_clips = load_clips(self._clips_dir)
        self._clips = new_clips

        with self._lock:
            self._record_buffer = []

        duration = buf[-1][0] if buf else 0.0
        log.info("Saved recording '%s': %d frames over %.2fs → %s",
                 name, len(buf), duration, out_path)
        return f"OK Saved '{name}' ({len(buf)} frames, {duration:.2f}s)"

    def cancel_recording(self) -> str:
        """Stop capture (if running) and discard the buffer."""
        if not self._recording and not self._record_buffer:
            return "ERR nothing to cancel"
        with self._lock:
            self._recording = False
            self._record_buffer = []
        if self._record_thread:
            self._record_thread.join(timeout=2.0)
        log.info("Recording cancelled")
        return "OK Recording cancelled"

    def tick(self):
        """Advance one 200 Hz step. Returns (positions, old_positions)."""
        with self._lock:
            return self._tick_inner()

    def _tick_inner(self):
        old_positions = list(self._current_positions)

        if self._playing:
            elapsed = (time.monotonic() - self._start_time) * self._speed

            if not self._loop and self._keyframes and elapsed >= self._keyframes[-1]["time"]:
                if self._queued_animation:
                    name = self._queued_animation
                    self._queued_animation = None
                    clip = self._clips[name]
                    self._keyframes = [
                        {"time": 0.0, "positions": list(self._current_positions)},
                        {"time": 0.5, "positions": clip["keyframes"][0]["positions"]},
                    ] + [
                        {"time": kf["time"] + 0.5, "positions": kf["positions"]}
                        for kf in clip["keyframes"]
                    ]
                    self._interp_mode = clip["interp"]
                    self._start_time = time.monotonic()
                    self._loop = self._loop  # preserve current loop setting
                    self._current_clip = name
                    elapsed = 0.0
                    log.info("Starting '%s'", name)
                else:
                    self._playing = False
                    self._current_clip = None

            if self._playing:
                target = self._interpolate(elapsed)
                max_step = MAX_JOINT_VEL * CONTROL_DT
                max_dv = MAX_JOINT_ACCEL * CONTROL_DT
                positions = []
                new_velocities = []
                for prev, tgt, prev_v in zip(self._current_positions, target, self._prev_velocities):
                    vel_capped = max(-max_step, min(max_step, tgt - prev))
                    new_v = max(prev_v - max_dv, min(prev_v + max_dv, vel_capped))
                    positions.append(prev + new_v)
                    new_velocities.append(new_v)
                self._current_positions = positions
                self._prev_velocities = new_velocities
            else:
                positions = old_positions
                self._prev_velocities = [0.0] * NUM_JOINTS
        else:
            positions = old_positions

        if not self._playing:
            self._target_weight = 0.0

        if self._weight < self._target_weight:
            self._weight = min(self._target_weight, self._weight + self._weight_step)
        elif self._weight > self._target_weight:
            self._weight = max(self._target_weight, self._weight - self._weight_step)

        return positions, old_positions

    def _interpolate(self, elapsed: float) -> list:
        kfs = self._keyframes
        total = kfs[-1]["time"]
        if elapsed > total:
            elapsed = elapsed % total if self._loop else total

        seg_idx = 0
        for i in range(len(kfs) - 1):
            if kfs[i]["time"] <= elapsed <= kfs[i + 1]["time"]:
                seg_idx = i
                break

        seg = kfs[seg_idx + 1]["time"] - kfs[seg_idx]["time"]
        raw_t = 0.0 if seg == 0 else (elapsed - kfs[seg_idx]["time"]) / seg

        if self._interp_mode == "smoothstep":
            t = raw_t * raw_t * (3.0 - 2.0 * raw_t)
        else:
            t = raw_t

        if self._interp_mode == "catmull_rom":
            i0 = max(seg_idx - 1, 0)
            i1 = seg_idx
            i2 = seg_idx + 1
            i3 = min(seg_idx + 2, len(kfs) - 1)
            return [
                self._catmull_rom(
                    kfs[i0]["positions"][j],
                    kfs[i1]["positions"][j],
                    kfs[i2]["positions"][j],
                    kfs[i3]["positions"][j],
                    t,
                )
                for j in range(NUM_JOINTS)
            ]

        return [
            kfs[seg_idx]["positions"][j] + t * (kfs[seg_idx + 1]["positions"][j] - kfs[seg_idx]["positions"][j])
            for j in range(NUM_JOINTS)
        ]

    @staticmethod
    def _catmull_rom(p0, p1, p2, p3, t):
        t2 = t * t
        t3 = t2 * t
        return 0.5 * (
            (2 * p1)
            + (-p0 + p2) * t
            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
            + (-p0 + 3 * p1 - 3 * p2 + p3) * t3
        )


# ---------------------------------------------------------------------------
# DDS bridge (from wifi_relay_server.py)
# ---------------------------------------------------------------------------

class DDSBridge:
    def __init__(self, interface: str, mode: str):
        ChannelFactoryInitialize(0, interface)
        self._crc = CRC()
        self._state = None
        self._mode = mode

        self._pub_damping = ChannelPublisher("rt/lowcmd", LowCmd_)
        self._pub_damping.Init()
        self._pub_walking = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self._pub_walking.Init()

        sub = ChannelSubscriber("rt/lowstate", LowState_)
        sub.Init(self._on_state, 10)
        log.info("DDS publishers ready on interface %s", interface)

        log.info("Waiting for robot state...")
        deadline = time.time() + 5.0
        while self._state is None and time.time() < deadline:
            time.sleep(0.1)
        if self._state is None:
            log.warning("No robot state after 5s — mode_machine will default to 0")
        else:
            log.info("Robot state received")

    def _on_state(self, msg: LowState_):
        self._state = msg

    def get_initial_positions(self) -> list:
        """Read current joint positions from live robot state."""
        if self._state is None:
            return None
        return [
            self._state.motor_state[G1_JOINT_INDEX[j]].q
            for j in UPPER_BODY_JOINTS
        ]

    def publish_cmd(self, positions: list, old_positions: list, weight: float = 1.0):
        cmd = unitree_hg_msg_dds__LowCmd_()
        walking = self._mode == "walking"

        if not walking:
            cmd.mode_pr = 0
            cmd.mode_machine = self._state.mode_machine if self._state else 0
        else:
            cmd.motor_cmd[WEIGHT_JOINT].q = weight

        for i, name in enumerate(UPPER_BODY_JOINTS):
            if walking and name in WALKING_EXCLUDE:
                continue
            idx = G1_JOINT_INDEX[name]
            motor = cmd.motor_cmd[idx]
            motor.mode = 1
            motor.q = positions[i]
            motor.dq = (positions[i] - old_positions[i]) / CONTROL_DT
            motor.tau = 0.0
            motor.kp = KP
            motor.kd = KD

        cmd.crc = self._crc.Crc(cmd)
        pub = self._pub_walking if walking else self._pub_damping
        pub.Write(cmd)


# ---------------------------------------------------------------------------
# 200 Hz control loop
# ---------------------------------------------------------------------------

_running = True


def control_loop(engine: AnimationEngine, bridge: DDSBridge):
    while _running:
        t0 = time.monotonic()
        positions, old_positions = engine.tick()
        # While recording, the operator hand-poses the robot — don't fight
        # them by publishing motor commands.
        if not engine.recording:
            bridge.publish_cmd(positions, old_positions, engine.weight)
        elapsed = time.monotonic() - t0
        time.sleep(max(0, CONTROL_DT - elapsed))


# ---------------------------------------------------------------------------
# TCP command server
# ---------------------------------------------------------------------------

def handle_client(conn: socket.socket, engine: AnimationEngine, clips: dict):
    conn.settimeout(None)  # blocking reads — no timeout needed
    buf = b""

    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                cmd = line.decode("utf-8", errors="replace").strip()
                if not cmd:
                    continue
                resp = dispatch(cmd, engine, clips)
                try:
                    conn.sendall((resp + "\n").encode())
                except OSError:
                    return
        except OSError:
            break

    log.info("Client disconnected")


def dispatch(cmd: str, engine: AnimationEngine, clips: dict) -> str:
    parts = cmd.split()
    verb = parts[0].lower()

    if verb == "play" and len(parts) >= 2:
        name = parts[1]
        resp = engine.play(name)
        log.info("play %s → %s", name, resp)
        return resp

    elif verb == "stop":
        resp = engine.stop()
        log.info("stop → %s", resp)
        return resp

    elif verb == "speed" and len(parts) >= 2:
        try:
            val = float(parts[1])
        except ValueError:
            return "ERR invalid speed value"
        resp = engine.set_speed(val)
        log.info("speed %s → %s", parts[1], resp)
        return resp

    elif verb == "weight" and len(parts) >= 2:
        try:
            val = float(parts[1])
        except ValueError:
            return "ERR invalid weight value"
        resp = engine.set_max_weight(val)
        log.info("weight %s → %s", parts[1], resp)
        return resp

    elif verb == "loop" and len(parts) >= 2:
        val = parts[1].lower() in ("true", "1", "on", "yes")
        return engine.set_loop(val)

    elif verb == "list":
        return "OK " + ",".join(engine.clip_names)

    elif verb == "status":
        return "OK " + engine.status

    elif verb == "record" and len(parts) >= 2:
        sub = parts[1].lower()
        if sub == "start":
            kwargs = {}
            for arg in parts[2:]:
                if "=" not in arg:
                    return f"ERR bad record arg '{arg}' (expected key=value)"
                k, v = arg.split("=", 1)
                kwargs[k] = v
            name = kwargs.get("name", "my_animation")
            try:
                interval = float(kwargs.get("interval", "0.1"))
            except ValueError:
                return f"ERR invalid interval '{kwargs.get('interval')}'"
            interp = kwargs.get("interp", "linear")
            resp = engine.start_recording(name, interval, interp)
            log.info("record start → %s", resp)
            return resp
        if sub == "stop_capture":
            resp = engine.stop_capture()
            log.info("record stop_capture → %s", resp)
            return resp
        if sub == "save":
            resp = engine.save_recording()
            log.info("record save → %s", resp)
            return resp
        if sub == "cancel":
            resp = engine.cancel_recording()
            log.info("record cancel → %s", resp)
            return resp
        return f"ERR unknown record subcommand '{sub}'"

    else:
        return f"ERR unknown command: {cmd}"


def serve(port: int, engine: AnimationEngine, clips: dict):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    log.info("Listening on 0.0.0.0:%d", port)

    while _running:
        try:
            conn, addr = srv.accept()
        except OSError:
            break
        log.info("Client connected: %s:%d", *addr)
        try:
            handle_client(conn, engine, clips)
        finally:
            conn.close()
            log.info("Connection closed, waiting for next client...")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _running

    parser = argparse.ArgumentParser(description="G1 WiFi animation server")
    parser.add_argument("--interface", default="eth0",
                        help="Network interface to MCU (default: eth0)")
    parser.add_argument("--port", type=int, default=PORT,
                        help=f"TCP listen port (default: {PORT})")
    parser.add_argument("--clips-dir", default=str(Path.home() / "clips"),
                        help="Directory containing clip .json files")
    parser.add_argument("--mode", default="walking", choices=["damping", "walking"],
                        help="Control mode (default: walking)")
    parser.add_argument("--weight", type=float, default=1.0,
                        help="Max arm_sdk weight in [0.0, 1.0]. Lower values blend "
                             "with the loco controller's arm swing so walking/running "
                             "stays enabled while clips play (default: 1.0)")
    args = parser.parse_args()
    if not 0.0 <= args.weight <= 1.0:
        parser.error("--weight must be in [0.0, 1.0]")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Load clips
    clips = load_clips(Path(args.clips_dir))
    if not clips:
        log.warning("No clips found in %s", args.clips_dir)
    else:
        log.info("Loaded %d clips: %s", len(clips), ", ".join(sorted(clips)))

    # Init DDS
    bridge = DDSBridge(args.interface, args.mode)

    # Init animation engine — seed from live robot state if available,
    # and let the engine re-read live state on each idle→playing transition
    # (arms move under loco control while weight=0, so cached positions go stale).
    initial = bridge.get_initial_positions()
    if initial:
        log.info("Seeded positions from live robot state")
    engine = AnimationEngine(
        clips,
        initial_positions=initial,
        live_positions_fn=bridge.get_initial_positions,
        max_weight=args.weight,
        clips_dir=Path(args.clips_dir),
        mode=args.mode,
    )
    log.info("Max arm_sdk weight = %.2f", args.weight)

    # Start 200 Hz control loop in background thread
    ctrl_thread = threading.Thread(
        target=control_loop, args=(engine, bridge), daemon=True
    )
    ctrl_thread.start()
    log.info("200 Hz control loop started (mode=%s)", args.mode)

    # SIGTERM (from `systemctl stop`) must reach the same shutdown path as
    # Ctrl+C so the weight ramp runs. Raising KeyboardInterrupt from the
    # handler unblocks socket.accept() on the main thread.
    def _on_term(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, _on_term)

    # Run TCP command server in main thread
    try:
        serve(args.port, engine, clips)
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Shutdown requested — ramping arm_sdk weight to 0...")
        engine.request_shutdown()
        deadline = time.monotonic() + 2.0
        while engine.weight > 0.01 and time.monotonic() < deadline:
            time.sleep(0.01)
        _running = False
        time.sleep(CONTROL_DT * 4)  # let control loop publish the final weight=0 frames
        log.info("Shutdown complete (weight=%.3f)", engine.weight)


if __name__ == "__main__":
    main()
