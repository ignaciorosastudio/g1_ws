#!/usr/bin/env python3
"""
G1 Animation Publisher
Digital preview of robot_publisher — use this for safe debugging before
deploying to hardware. Publishes /joint_states for RViz.
"""
import rclpy
from sensor_msgs.msg import JointState

from .animation_core import AnimationCore
from .keyframes import UPPER_BODY_JOINTS


class AnimationPublisher(AnimationCore):

    def __init__(self):
        super().__init__('animation_publisher', control_dt=0.02)

        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)

        self.get_logger().info("Animation publisher ready.")

    def _send(self, positions: list, old_positions: list):
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name         = UPPER_BODY_JOINTS
        js.position     = positions
        js.velocity     = [(p - o) / self.CONTROL_DT for p, o in zip(positions, old_positions)]
        self.js_pub.publish(js)


def main(args=None):
    rclpy.init(args=args)
    node = AnimationPublisher()
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
