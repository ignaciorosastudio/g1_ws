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
from unitree_sdk2py.utils.crc import CRC

from .keyframes import UPPER_BODY_JOINTS, ANIMATIONS


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

# Maximum joint speed (rad/s) — limits how fast any joint can move per tick.
# At 200 Hz each tick is 5 ms, so 0.5 rad/s → max 0.0025 rad per tick.
# Increase to allow faster animations; decrease for a slower, safer startup.
MAX_JOINT_VEL = 0.5   # rad/s
CONTROL_DT    = 0.005 # must match timer period

# arm_sdk weight register — motor_cmd[29].q controls blending between
# the locomotion controller's arm swing (0.0) and our commands (1.0).
WEIGHT_JOINT       = 29
WEIGHT_RAMP_STEPS  = 200   # steps to ramp weight down on shutdown (~1 s at 5 ms)


class RobotPublisher(Node):
    def __init__(self):
        super().__init__('robot_publisher')

        self.declare_parameter('network_interface', 'enp3s0')
        self.declare_parameter('loop', True)
        self.declare_parameter('dry_run', True)   # True = print only, don't send
        self.declare_parameter('animation', 'hands')
        self.declare_parameter('mode', 'damping')  # 'damping' or 'walking'

        self._iface     = self.get_parameter('network_interface').value
        self._loop      = self.get_parameter('loop').value
        self._dry       = self.get_parameter('dry_run').value
        anim_name       = self.get_parameter('animation').value
        self._mode      = self.get_parameter('mode').value

        if self._mode not in ('damping', 'walking'):
            raise ValueError(f"Invalid mode '{self._mode}'. Use 'damping' or 'walking'.")

        if anim_name not in ANIMATIONS:
            raise ValueError(
                f"Unknown animation '{anim_name}'. "
                f"Available: {', '.join(ANIMATIONS.keys())}"
            )

        self._state = None

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
        self._keyframes  = ANIMATIONS[anim_name]
        self.get_logger().info(f"Animation: '{anim_name}'")

        # Seed rate-limiter from live state so the first move is smooth.
        # Falls back to the first keyframe in dry-run mode.
        if self._state is not None:
            self._prev_positions = [
                self._state.motor_state[G1_JOINT_INDEX[j]].q
                for j in UPPER_BODY_JOINTS
            ]
        else:
            self._prev_positions = list(self._keyframes[0]["positions"])

        # 200 Hz control loop (Unitree expects high-freq commands)
        self.timer = self.create_timer(0.005, self.tick)

    def _init_sdk(self):
        """Initialize Unitree SDK2 channel."""
        ChannelFactoryInitialize(0, self._iface)
        self._crc = CRC()
        topic = "rt/arm_sdk" if self._mode == "walking" else "rt/lowcmd"
        self._cmd_pub = ChannelPublisher(topic, LowCmd_)
        self._cmd_pub.Init()
        self.get_logger().info(f"Publishing to {topic}")

        # Subscribe to state so we can read current positions before moving
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
        target = self._interpolate(elapsed)

        # Clamp each joint's step to MAX_JOINT_VEL * dt
        max_delta = MAX_JOINT_VEL * CONTROL_DT
        positions = []
        for prev, tgt in zip(self._prev_positions, target):
            delta = max(-max_delta, min(max_delta, tgt - prev))
            positions.append(prev + delta)
        self._prev_positions = positions

        if self._dry:
            # Just log — useful for verifying indices before going live
            preview = {name: f"{pos:.3f}"
                       for name, pos in zip(UPPER_BODY_JOINTS, positions)}
            self.get_logger().info(f"[DRY] t={elapsed:.2f}s  {preview}", throttle_duration_sec=0.5)
            return

        # Build LowCmd
        cmd = unitree_hg_msg_dds__LowCmd_()

        if self._mode == "damping":
            # Full low-level control — must mirror robot's mode_machine
            cmd.mode_pr      = 0
            cmd.mode_machine = self._state.mode_machine if self._state else 0
        else:
            # Walking mode: locomotion controller owns mode_machine;
            # set weight=1 so our commands fully override arm swing
            cmd.motor_cmd[WEIGHT_JOINT].q = 1.0

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

        cmd.crc = self._crc.Crc(cmd)
        self._cmd_pub.Write(cmd)

    def _release_walking_mode(self):
        """Ramp arm_sdk weight from 1 → 0 so the loco controller smoothly
        reclaims the arms instead of snapping to its own positions."""
        if self._mode != "walking" or self._dry:
            return
        self.get_logger().info("Releasing arm_sdk — ramping weight to 0...")
        for step in range(WEIGHT_RAMP_STEPS, -1, -1):
            cmd = unitree_hg_msg_dds__LowCmd_()
            cmd.motor_cmd[WEIGHT_JOINT].q = step / WEIGHT_RAMP_STEPS
            # Hold last commanded positions so the blend transitions from our
            # pose to the loco controller's pose rather than snapping to zero.
            for i, joint_name in enumerate(UPPER_BODY_JOINTS):
                idx = G1_JOINT_INDEX.get(joint_name)
                if idx is None:
                    continue
                motor = cmd.motor_cmd[idx]  # type: ignore[index]
                motor.q   = self._prev_positions[i]
                motor.dq  = 0.0
                motor.tau = 0.0
                motor.kp  = KP
                motor.kd  = KD
            cmd.crc = self._crc.Crc(cmd)
            self._cmd_pub.Write(cmd)
            time.sleep(CONTROL_DT)


def main(args=None):
    rclpy.init(args=args)
    node = RobotPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._release_walking_mode()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
if __name__ == '__main__':
    main()
