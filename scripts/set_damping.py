#!/usr/bin/env python3
"""
Sets the G1 to damping mode before running animations.
Run this once after powering on, before launching robot_deploy.launch.py.

Usage:
    python3 ~/g1_ws/scripts/set_damping.py enp46s0
"""
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

iface = sys.argv[1] if len(sys.argv) > 1 else 'enp46s0'
print(f"Connecting on interface: {iface}")

ChannelFactoryInitialize(0, iface)

client = LocoClient()
client.Init()

time.sleep(0.5)  # give DDS time to discover the robot

client.Damp()
print("Robot is in damping mode — safe to send animation commands")
