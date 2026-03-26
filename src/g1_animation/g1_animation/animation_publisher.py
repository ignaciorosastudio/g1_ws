#!/usr/bin/env python3
"""
G1 Animation Publisher
Publishes a JointTrajectory to /upper_body_trajectory for RViz preview.
Run alongside G1Pilot's robot_state_publisher for visualization.
"""
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from .keyframes import UPPER_BODY_JOINTS, WAVE_ANIMATION


class AnimationPublisher(Node):
    def __init__(self):
        super().__init__('animation_publisher')
        self.declare_parameter('animation', 'wave')
        self.declare_parameter('loop', True)

        self.pub = self.create_publisher(
            JointTrajectory,
            '/upper_body_trajectory',
            10
        )

        # Also publish joint_states for RViz robot model update
        from sensor_msgs.msg import JointState
        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)

        self._keyframes = WAVE_ANIMATION
        self._frame_idx = 0
        self._loop = self.get_parameter('loop').value
        self._start_time = self.get_clock().now()

        # Timer fires at 50 Hz to update joint_states for smooth RViz preview
        self.timer = self.create_timer(0.02, self.tick)
        self.get_logger().info("Animation publisher started. Publishing to /upper_body_trajectory")

    def tick(self):
        """Interpolate between keyframes and publish joint states."""
        from sensor_msgs.msg import JointState
        import math

        elapsed = (self.get_clock().now() - self._start_time).nanoseconds / 1e9
        total_duration = self._keyframes[-1]["time"]

        if elapsed > total_duration:
            if self._loop:
                self._start_time = self.get_clock().now()
                elapsed = 0.0
            else:
                return

        # Find surrounding keyframes
        kf_before = self._keyframes[0]
        kf_after = self._keyframes[-1]
        for i in range(len(self._keyframes) - 1):
            if self._keyframes[i]["time"] <= elapsed <= self._keyframes[i+1]["time"]:
                kf_before = self._keyframes[i]
                kf_after = self._keyframes[i+1]
                break
                
        for i, kf in enumerate(self._keyframes):
           if len(kf["positions"]) != len(UPPER_BODY_JOINTS):
               self.get_logger().error(
               f"Keyframe {i} length mismatch: "
               f"{len(kf['positions'])} vs {len(UPPER_BODY_JOINTS)}"
           )

        # Linear interpolation
        seg_duration = kf_after["time"] - kf_before["time"]
        if seg_duration == 0:
            t = 0.0
        else:
            t = (elapsed - kf_before["time"]) / seg_duration

        positions = [
            kf_before["positions"][j] + t * (kf_after["positions"][j] - kf_before["positions"][j])
            for j in range(len(UPPER_BODY_JOINTS))
        ]

        # Publish JointState for RViz
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name = UPPER_BODY_JOINTS
        js.position = positions
        self.js_pub.publish(js)

    def publish_full_trajectory(self):
        """Publish the complete trajectory (used by loco_client on real robot)."""
        msg = JointTrajectory()
        msg.joint_names = UPPER_BODY_JOINTS
        for kf in self._keyframes:
            pt = JointTrajectoryPoint()
            pt.positions = kf["positions"]
            t = kf["time"]
            pt.time_from_start = Duration(
                sec=int(t),
                nanosec=int((t % 1) * 1_000_000_000)
            )
            msg.points.append(pt)
        self.pub.publish(msg)
        self.get_logger().info(f"Full trajectory published ({len(self._keyframes)} keyframes)")


def main(args=None):
    rclpy.init(args=args)
    node = AnimationPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
