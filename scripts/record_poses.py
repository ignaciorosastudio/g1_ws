#!/usr/bin/env python3
"""
Interactive pose recorder for the Unitree G1.
Put the robot in damping mode, move it to a pose by hand, press Enter to capture.
Outputs a ready-to-paste keyframes block when done.

Usage:
    python3 ~/g1_ws/scripts/record_poses.py enp46s0
    python3 ~/g1_ws/scripts/record_poses.py enp46s0 --spacing 0.5
"""
import sys
import time
import argparse
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

# Joint name -> motor index mapping
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
    parser = argparse.ArgumentParser(description="Interactive G1 pose recorder")
    parser.add_argument("interface", nargs="?", default="enp46s0",
                        help="Network interface (default: enp46s0)")
    parser.add_argument("--spacing", type=float, default=1.0,
                        help="Time spacing between keyframes in seconds (default: 1.0)")
    parser.add_argument("--name", type=str, default="MY_ANIMATION",
                        help="Animation variable name in output (default: MY_ANIMATION)")
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
            time.sleep(0.1)
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

    def print_current(self):
        pos = self.current_positions()
        print("  " + ", ".join(f"{v:7.4f}" for v in pos))


def print_keyframe(positions: list, timestamp: float, label: str):
    pos_str = ", ".join(f"{v:.4f}" for v in positions)
    print(f"    # {label}")
    print(f"    {{'time': {timestamp:.2f}, 'positions': [{pos_str}]}},")


def main():
    args = parse_args()

    print("=" * 60)
    print("  G1 Pose Recorder")
    print("=" * 60)
    print(f"  Interface : {args.interface}")
    print(f"  Spacing   : {args.spacing}s between keyframes")
    print(f"  Output    : {args.name}")
    print()
    print("  Controls:")
    print("    Enter         — capture current pose")
    print("    l <label>     — capture with a custom label")
    print("    d             — discard last captured pose")
    print("    p             — preview current joint positions")
    print("    q / done      — finish and print output")
    print("=" * 60)
    print()

    recorder = PoseRecorder(args.interface)

    captured = []   # list of (label, positions)
    print("Robot is ready. Move to first pose and press Enter.\n")

    while True:
        try:
            raw = input(f"[{len(captured)} captured] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw or raw == "":
            # Capture with auto label
            label = f"pose_{len(captured) + 1}"
            pos = recorder.current_positions()
            captured.append((label, pos))
            print(f"  Captured '{label}':")
            print_keyframe(pos, len(captured) * args.spacing - args.spacing, label)
            print()

        elif raw.startswith("l "):
            # Capture with custom label
            label = raw[2:].strip() or f"pose_{len(captured) + 1}"
            pos = recorder.current_positions()
            captured.append((label, pos))
            print(f"  Captured '{label}':")
            print_keyframe(pos, len(captured) * args.spacing - args.spacing, label)
            print()

        elif raw == "d":
            if captured:
                removed = captured.pop()
                print(f"  Discarded '{removed[0]}'")
            else:
                print("  Nothing to discard.")

        elif raw == "p":
            print("  Current positions:")
            recorder.print_current()
            print()

        elif raw in ("q", "done", "exit", "quit"):
            break

        else:
            print("  Unknown command. Use Enter, l <label>, d, p, or q.")

    # --- Output ---
    if not captured:
        print("No poses captured.")
        return

    print()
    print("=" * 60)
    print("  Paste this into keyframes.py:")
    print("=" * 60)
    print()
    print(f"{args.name} = [")
    for i, (label, pos) in enumerate(captured):
        t = round(i * args.spacing, 3)
        pos_str = ", ".join(f"{v:.4f}" for v in pos)
        print(f"    # {label}")
        print(f"    {{'time': {t}, 'positions': [{pos_str}]}},")
    print("]")
    print()

    # Also write to a file
    outfile = f"/tmp/{args.name.lower()}_recorded.py"
    with open(outfile, "w") as f:
        f.write(f"# Recorded with record_poses.py\n\n")
        f.write(f"UPPER_BODY_JOINTS = {UPPER_BODY_JOINTS!r}\n\n")
        f.write(f"{args.name} = [\n")
        for i, (label, pos) in enumerate(captured):
            t = round(i * args.spacing, 3)
            pos_str = ", ".join(f"{v:.4f}" for v in pos)
            f.write(f"    # {label}\n")
            f.write(f"    {{'time': {t}, 'positions': [{pos_str}]}},\n")
        f.write("]\n")

    print(f"  Also saved to: {outfile}")
    print("=" * 60)


if __name__ == "__main__":
    main()
