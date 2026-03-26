#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import sys
import termios
import tty
import select
import time
from .keyframes import UPPER_BODY_JOINTS

class PoseCapture(Node):
    def __init__(self):
        super().__init__('pose_capture')

        self.subscription = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_callback,
            10
        )

        self.latest_msg = None
        self.start_time = time.time()

        self.get_logger().info(
            "Pose Capture Ready!\n"
            "Press 's' to save keyframe\n"
            "Press 'q' to quit\n"
        )

        # Timer to check keyboard input
        self.timer = self.create_timer(0.05, self.keyboard_loop)

    def joint_callback(self, msg):
        self.latest_msg = msg

    def keyboard_loop(self):
        if self.kbhit():
            c = sys.stdin.read(1)

            if c == 's':
                self.save_pose()
            elif c == 'q':
                self.get_logger().info("Exiting...")
                rclpy.shutdown()

    def save_pose(self):
        if self.latest_msg is None:
            self.get_logger().warn("No joint_states received yet")
            return

        # Map joint names → positions
        joint_map = dict(zip(self.latest_msg.name, self.latest_msg.position))

        try:
            filtered = [joint_map[j] for j in UPPER_BODY_JOINTS]
        except KeyError as e:
            self.get_logger().error(f"Missing joint: {e}")
            return

        t = time.time() - self.start_time

        keyframe = {
            "time": round(t, 2),
            "positions": [round(p, 4) for p in filtered]
        }

        print(keyframe)

    def kbhit(self):
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        return dr != []


def main(args=None):
    rclpy.init(args=args)

    # Setup terminal for non-blocking input
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)

    node = PoseCapture()

    try:
        rclpy.spin(node)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()