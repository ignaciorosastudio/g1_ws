#!/usr/bin/env python3
"""
Continuous pose recorder for the Unitree G1.
Put the robot in damping mode, press Enter to start recording.
The robot's joint positions are sampled every --interval seconds.
Press Enter again (or Ctrl+C) to stop and emit a ready-to-paste keyframes block.

Usage:
    python3 ~/g1_ws/scripts/record_continuous.py enp46s0
    python3 ~/g1_ws/scripts/record_continuous.py enp46s0 --interval 0.1
    python3 ~/g1_ws/scripts/record_continuous.py enp46s0 --interval 0.05 --name WAVE
"""
import os
import sys
import json
import time
import argparse
import threading
from pathlib import Path
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

CLIPS_DIR = Path(os.environ.get("G1_CLIPS_DIR", Path.home() / "g1_ws" / "clips"))

# Joint name -> motor index mapping (upper body only)
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

UPPER_BODY_JOINTS = list(G1_JOINT_INDEX.keys())


def parse_args():
    parser = argparse.ArgumentParser(description="Continuous G1 pose recorder")
    parser.add_argument("interface", nargs="?", default="enp46s0",
                        help="Network interface (default: enp46s0)")
    parser.add_argument("--interval", type=float, default=0.1,
                        help="Seconds between samples (default: 0.1 → 10 fps)")
    parser.add_argument("--name", type=str, default="my_animation",
                        help="Clip name (becomes <name>.json in the clips folder)")
    parser.add_argument("--interp", type=str, default="linear",
                        choices=["linear", "smoothstep", "catmull_rom"],
                        help="Interpolation mode (default: linear)")
    return parser.parse_args()


class PoseRecorder:

    def __init__(self, iface: str):
        self._latest = None
        ChannelFactoryInitialize(0, iface)
        sub = ChannelSubscriber("rt/lowstate", LowState_)
        sub.Init(self._callback, 10)

        print("Connecting to robot...", end="", flush=True)
        timeout = time.time() + 5.0
        while self._latest is None and time.time() < timeout:
            time.sleep(0.05)
            print(".", end="", flush=True)

        if self._latest is None:
            print("\n[error] No state received. Check connection and robot power.")
            sys.exit(1)
        print(" connected.\n")

    def _callback(self, msg: LowState_):
        self._latest = msg

    def current_positions(self) -> list:
        msg = self._latest
        return [
            round(msg.motor_state[G1_JOINT_INDEX[name]].q, 4)
            for name in UPPER_BODY_JOINTS
        ]


def recording_loop(recorder: PoseRecorder, interval: float,
                   frames: list, stop_event: threading.Event):
    """Sample robot state at `interval` seconds until stop_event is set."""
    start = time.monotonic()
    while not stop_event.is_set():
        t = round(time.monotonic() - start, 4)
        pos = recorder.current_positions()
        frames.append((t, pos))
        # Sleep until next sample, accounting for time spent sampling
        next_tick = start + len(frames) * interval
        wait = next_tick - time.monotonic()
        if wait > 0:
            time.sleep(wait)


def write_output(frames: list, name: str, interp: str):
    clip_name = name.lower().replace(" ", "_")
    keyframes = [{"time": round(t, 4), "positions": pos} for t, pos in frames]
    data = {"interp": interp, "keyframes": keyframes}

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    outfile = CLIPS_DIR / f"{clip_name}.json"
    outfile.write_text(json.dumps(data, indent=2))

    print()
    print("=" * 60)
    print(f"  Saved clip '{clip_name}' → {outfile}")
    print(f"  {len(frames)} frames, interp: {interp}")
    print(f"  Reload the animation publisher to pick it up.")
    print("=" * 60)


def main():
    args = parse_args()
    fps = 1.0 / args.interval

    print("=" * 60)
    print("  G1 Continuous Pose Recorder")
    print("=" * 60)
    print(f"  Interface  : {args.interface}")
    print(f"  Sample rate: {fps:.1f} fps  ({args.interval}s interval)")
    print(f"  Output     : {args.name}.json → {CLIPS_DIR}")
    print(f"  Interp     : {args.interp}")
    print()
    print("  Controls:")
    print("    Enter         — start / stop recording")
    print("    Ctrl-C        — stop recording and emit output")
    print("=" * 60)
    print()

    recorder = PoseRecorder(args.interface)

    try:
        input("  Move robot to starting position, then press Enter to START recording...")
    except (EOFError, KeyboardInterrupt):
        print()
        return

    frames = []
    stop_event = threading.Event()
    thread = threading.Thread(target=recording_loop,
                              args=(recorder, args.interval, frames, stop_event),
                              daemon=True)
    thread.start()
    print(f"\n  [REC] Recording at {fps:.1f} fps — press Enter or Ctrl-C to stop.\n")

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print()

    stop_event.set()
    thread.join()

    duration = frames[-1][0] if frames else 0.0
    print(f"  Stopped. Captured {len(frames)} frames over {duration:.2f}s.")

    if not frames:
        print("No frames captured.")
        return

    write_output(frames, args.name, args.interp)


if __name__ == "__main__":
    main()
