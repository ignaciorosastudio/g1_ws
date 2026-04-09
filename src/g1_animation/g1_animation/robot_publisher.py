#!/usr/bin/env python3
"""
G1 Robot Publisher
Sends joint trajectory to the real Unitree G1 EDU+ via Unitree SDK2 / CycloneDDS.
Run AFTER confirming the animation looks correct in RViz with animation_publisher.

Prerequisites:
  - Robot powered on and in damping/debug mode
  - PC IP: 192.168.123.99, robot IP: 192.168.123.161
  - CYCLONEDDS_URI pointing to cyclonedds.xml
  - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
"""
import time
import rclpy
from sensor_msgs.msg import JointState

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.utils.crc import CRC

from .animation_core import AnimationCore
from .keyframes import UPPER_BODY_JOINTS


# G1 joint index mapping (SDK2 ordering for upper body)
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

KP = 60.0   # position gain
KD = 1.5    # damping gain

CONTROL_DT         = 0.005  # s — 200 Hz control loop
WEIGHT_JOINT       = 29     # arm_sdk weight register
WEIGHT_RAMP_STEPS  = 200    # steps to ramp weight down on shutdown (~1 s)

WALKING_EXCLUDE = {"waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"}

# Verify at import time that every joint in UPPER_BODY_JOINTS has a known index
_missing = [j for j in UPPER_BODY_JOINTS if j not in G1_JOINT_INDEX]
if _missing:
    raise RuntimeError(f"G1_JOINT_INDEX is missing entries for: {_missing}")


class RobotPublisher(AnimationCore):

    def __init__(self):
        super().__init__('robot_publisher', control_dt=CONTROL_DT)

        self.declare_parameter('network_interface', 'enp3s0')
        self.declare_parameter('dry_run', True)
        self.declare_parameter('mode', 'damping')

        self._iface = self.get_parameter('network_interface').value
        self._dry   = self.get_parameter('dry_run').value
        self._mode  = self.get_parameter('mode').value
        self._state = None

        if self._mode not in ('damping', 'walking'):
            raise ValueError(f"Invalid mode '{self._mode}'. Use 'damping' or 'walking'.")

        if self._dry:
            self.get_logger().warn(
                "DRY RUN mode — commands will NOT be sent to the robot. "
                "Set dry_run:=false to enable real commands."
            )
        else:
            self.get_logger().warn(
                "LIVE mode — commands will be sent to the robot. "
                "Make sure the robot is in Debug/Damping mode!"
            )
            self._init_sdk()
            # Seed initial position from live robot state
            if self._state is not None:
                self._current_positions = [
                    self._state.motor_state[G1_JOINT_INDEX[j]].q
                    for j in UPPER_BODY_JOINTS
                ]

        # Joint states publisher — active in dry-run for RViz preview
        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)

        self.get_logger().info("Robot publisher ready.")

    # ------------------------------------------------------------------
    # SDK
    # ------------------------------------------------------------------

    def _init_sdk(self):
        ChannelFactoryInitialize(0, self._iface)
        self._crc = CRC()
        topic = "rt/arm_sdk" if self._mode == "walking" else "rt/lowcmd"
        self._cmd_pub = ChannelPublisher(topic, LowCmd_)
        self._cmd_pub.Init()
        self.get_logger().info(f"Publishing to {topic}")

        sub = ChannelSubscriber("rt/lowstate", LowState_)
        sub.Init(self._state_callback, 10)
        self.get_logger().info(f"SDK2 initialized on interface: {self._iface}")

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

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _send(self, positions: list, old_positions: list):
        # Always publish joint states — useful for RViz monitoring in both modes
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name         = UPPER_BODY_JOINTS
        js.position     = positions
        js.velocity     = [(p - o) / self.CONTROL_DT for p, o in zip(positions, old_positions)]
        self.js_pub.publish(js)

        if self._dry:
            return

        cmd = unitree_hg_msg_dds__LowCmd_()

        if self._mode == "damping":
            cmd.mode_pr      = 0
            cmd.mode_machine = self._state.mode_machine if self._state else 0
        else:
            cmd.motor_cmd[WEIGHT_JOINT].q = 1.0

        for i, joint_name in enumerate(UPPER_BODY_JOINTS):
            if self._mode == "walking" and joint_name in WALKING_EXCLUDE:
                continue
            idx = G1_JOINT_INDEX.get(joint_name)
            if idx is None:
                continue
            motor = cmd.motor_cmd[idx]  # type: ignore[index]
            motor.mode = 1
            motor.q    = positions[i]
            motor.dq   = (positions[i] - old_positions[i]) / self.CONTROL_DT
            motor.tau  = 0.0
            motor.kp   = KP
            motor.kd   = KD

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
            for i, joint_name in enumerate(UPPER_BODY_JOINTS):
                if joint_name in WALKING_EXCLUDE:
                    continue
                idx = G1_JOINT_INDEX.get(joint_name)
                if idx is None:
                    continue
                motor = cmd.motor_cmd[idx]  # type: ignore[index]
                motor.q   = self._current_positions[i]
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
