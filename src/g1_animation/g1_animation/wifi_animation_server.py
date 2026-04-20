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
import socket
import threading
import time
from pathlib import Path

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
    """Clip playback with interpolation and velocity/accel capping."""

    def __init__(self, clips: dict, initial_positions: list = None):
        self._clips = clips
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
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
        return self._current_clip or "idle"

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
            self._queued_animation = name
            self._keyframes = [
                {"time": 0.0, "positions": list(self._current_positions)},
                {"time": 1.0, "positions": list(NEUTRAL)},
            ]
            self._interp_mode = "linear"
            self._start_time = time.monotonic()
            self._loop = False
            self._playing = True
        return f"OK Queued '{name}' — blending to neutral first"

    def stop(self) -> str:
        with self._lock:
            self._queued_animation = None
            self._keyframes = [
                {"time": 0.0, "positions": list(self._current_positions)},
                {"time": 1.5, "positions": list(NEUTRAL)},
            ]
            self._interp_mode = "linear"
            self._start_time = time.monotonic()
            self._loop = False
            self._playing = True
        return "OK Stopping — blending to neutral"

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

    def publish_cmd(self, positions: list, old_positions: list):
        cmd = unitree_hg_msg_dds__LowCmd_()
        walking = self._mode == "walking"

        if not walking:
            cmd.mode_pr = 0
            cmd.mode_machine = self._state.mode_machine if self._state else 0
        else:
            cmd.motor_cmd[WEIGHT_JOINT].q = 1.0

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

    def release_walking_mode(self, last_positions: list):
        if self._mode != "walking":
            return
        log.info("Releasing walking mode — ramping weight to 0...")
        for step in range(WEIGHT_RAMP_STEPS, -1, -1):
            cmd = unitree_hg_msg_dds__LowCmd_()
            cmd.motor_cmd[WEIGHT_JOINT].q = step / WEIGHT_RAMP_STEPS
            for i, name in enumerate(UPPER_BODY_JOINTS):
                if name in WALKING_EXCLUDE:
                    continue
                idx = G1_JOINT_INDEX[name]
                motor = cmd.motor_cmd[idx]
                motor.q = last_positions[i]
                motor.dq = 0.0
                motor.tau = 0.0
                motor.kp = KP
                motor.kd = KD
            cmd.crc = self._crc.Crc(cmd)
            self._pub_walking.Write(cmd)
            time.sleep(CONTROL_DT)
        log.info("Walking mode released")


# ---------------------------------------------------------------------------
# 200 Hz control loop
# ---------------------------------------------------------------------------

_running = True


def control_loop(engine: AnimationEngine, bridge: DDSBridge):
    while _running:
        t0 = time.monotonic()
        positions, old_positions = engine.tick()
        bridge.publish_cmd(positions, old_positions)
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

    elif verb == "loop" and len(parts) >= 2:
        val = parts[1].lower() in ("true", "1", "on", "yes")
        return engine.set_loop(val)

    elif verb == "list":
        names = sorted(clips.keys())
        return "OK " + ",".join(names)

    elif verb == "status":
        return "OK " + engine.status

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
    args = parser.parse_args()

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

    # Init animation engine — seed from live robot state if available
    initial = bridge.get_initial_positions()
    if initial:
        log.info("Seeded positions from live robot state")
    engine = AnimationEngine(clips, initial_positions=initial)

    # Start 200 Hz control loop in background thread
    ctrl_thread = threading.Thread(
        target=control_loop, args=(engine, bridge), daemon=True
    )
    ctrl_thread.start()
    log.info("200 Hz control loop started (mode=%s)", args.mode)

    # Run TCP command server in main thread
    try:
        serve(args.port, engine, clips)
    except KeyboardInterrupt:
        pass
    finally:
        _running = False
        bridge.release_walking_mode(engine._current_positions)
        log.info("Shutdown complete")


if __name__ == "__main__":
    main()
