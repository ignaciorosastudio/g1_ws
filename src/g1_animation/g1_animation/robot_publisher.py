#!/usr/bin/env python3
"""
G1 Robot Publisher
Sends joint trajectory to the real Unitree G1 EDU+ via Unitree SDK2 / CycloneDDS.
Run AFTER confirming the animation looks correct in RViz.

Prerequisites:
  - Robot powered on and in damping/debug mode
  - PC IP: 192.168.123.99, robot IP: 192.168.123.161
  - CYCLONEDDS_URI pointing to cyclonedds.xml
  - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
"""
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock
import time
import math

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.core.channel import ChannelSubscriber

from .keyframes import UPPER_BODY_JOINTS, WAVE_ANIMATION


# G1 joint index mapping (SDK2 ordering for upper body)
# These indices correspond to the LowCmd motor array — verify against SDK docs
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

# PD gains — start conservative, tune after confirming comms work
KP = 60.0   # position gain
KD = 1.5    # damping gain


class RobotPublisher(Node):
    def __init__(self):
        super().__init__('robot_publisher')

        self.declare_parameter('network_interface', 'enp3s0')
        self.declare_parameter('loop', True)
        self.declare_parameter('dry_run', True)   # True = print only, don't send

        self._iface = self.get_parameter('network_interface').value
        self._loop  = self.get_parameter('loop').value
        self._dry   = self.get_parameter('dry_run').value

        if self._dry:
            self.get_logger().warn(
                "DRY RUN mode — commands will be printed but NOT sent to the robot. "
                "Set dry_run:=false to enable real commands."
            )
        else:
            self.get_logger().warn(
                "LIVE mode — commands will be sent to the robot. "
                "Make sure the robot is in Debug/Damping mode!"
            )
            self._init_sdk()

        self._start_time = time.time()
        self._keyframes  = WAVE_ANIMATION

        # 200 Hz control loop (Unitree expects high-freq commands)
        self.timer = self.create_timer(0.005, self.tick)

    def _init_sdk(self):
        """Initialize Unitree SDK2 channel."""
        ChannelFactoryInitialize(0, self._iface)
        self._cmd_pub = ChannelPublisher("rt/lowcmd", LowCmd_)
        self._cmd_pub.Init()

        # Subscribe to state so we can read current positions before moving
        self._state = None
        sub = ChannelSubscriber("rt/lowstate", LowState_)
        sub.Init(self._state_callback, 10)
        self.get_logger().info(f"SDK2 initialized on interface: {self._iface}")

        # Wait for first state message
        self.get_logger().info("Waiting for robot state...")
        timeout = time.time() + 5.0
        while self._state is None and time.time() < timeout:
            time.sleep(0.1)
        if self._state is None:
            raise RuntimeError(
                "No state received from robot after 5s. "
                "Check network connection and that robot is powered on."
            )
        self.get_logger().info("Robot state received — ready to send commands.")

    def _state_callback(self, msg: LowState_):
        self._state = msg

    def _interpolate(self, elapsed: float) -> list[float]:
        """Linear interpolation between keyframes."""
        total = self._keyframes[-1]["time"]
        if elapsed > total:
            elapsed = elapsed % total if self._loop else total

        kf0 = self._keyframes[0]
        kf1 = self._keyframes[-1]
        for i in range(len(self._keyframes) - 1):
            if self._keyframes[i]["time"] <= elapsed <= self._keyframes[i+1]["time"]:
                kf0 = self._keyframes[i]
                kf1 = self._keyframes[i+1]
                break

        seg = kf1["time"] - kf0["time"]
        t = 0.0 if seg == 0 else (elapsed - kf0["time"]) / seg

        return [
            kf0["positions"][j] + t * (kf1["positions"][j] - kf0["positions"][j])
            for j in range(len(UPPER_BODY_JOINTS))
        ]

    def tick(self):
        elapsed = time.time() - self._start_time
        positions = self._interpolate(elapsed)

        if self._dry:
            # Just log — useful for verifying indices before going live
            preview = {name: f"{pos:.3f}"
                       for name, pos in zip(UPPER_BODY_JOINTS, positions)}
            self.get_logger().info(f"[DRY] t={elapsed:.2f}s  {preview}", throttle_duration_sec=0.5)
            return

        # Build LowCmd
        cmd = unitree_hg_msg_dds__LowCmd_()
        cmd.mode_pr = 0   # position+velocity mode
        cmd.mode_machine = 0

        for i, joint_name in enumerate(UPPER_BODY_JOINTS):
            idx = G1_JOINT_INDEX.get(joint_name)
            if idx is None:
                continue
            cmd.motor_cmd[idx].mode = 1   # position control
            cmd.motor_cmd[idx].q    = positions[i]
            cmd.motor_cmd[idx].dq   = 0.0
            cmd.motor_cmd[idx].tau  = 0.0
            cmd.motor_cmd[idx].kp   = KP
            cmd.motor_cmd[idx].kd   = KD

        self._cmd_pub.Write(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = RobotPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
if __name__ == '__main__':
    main()
