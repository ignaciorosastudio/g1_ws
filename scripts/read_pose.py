#!/usr/bin/env python3
"""
Reads and prints the current joint positions from the real robot.
Use this to capture poses for keyframes.

Usage:
    python3 ~/g1_ws/scripts/read_pose.py enp46s0
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'g1_animation'))

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from g1_animation.keyframes import UPPER_BODY_JOINTS
from g1_animation.robot_publisher import G1_JOINT_INDEX


print("Ready to read robot state (waiting 5s)")
time.sleep(5.0)

iface = sys.argv[1] if len(sys.argv) > 1 else 'enp46s0'
ChannelFactoryInitialize(0, iface)

received = []

def state_callback(msg: LowState_):
    positions = {}
    for name, idx in G1_JOINT_INDEX.items():
        positions[name] = round(msg.motor_state[idx].q, 4)
    received.append(positions)

sub = ChannelSubscriber("rt/lowstate", LowState_)
sub.Init(state_callback, 10)

print("Reading robot state... (waiting 2s)")
time.sleep(2.0)

if received:
    latest = received[-1]
    print("\nCurrent joint positions (copy into keyframes.py):")
    print("positions = [")
    for name in UPPER_BODY_JOINTS:
        print(f"    {latest.get(name, 0.0)},  # {name}")
    print("]")
else:
    print("No state received — is the robot connected and powered on?")
