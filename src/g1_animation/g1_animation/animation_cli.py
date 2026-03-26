#!/usr/bin/env python3
"""
G1 Animation CLI
Interactive terminal to trigger animation clips by name.
Run in a separate terminal while animation_publisher is running.

Usage:
    ros2 run g1_animation animation_cli
"""
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
import threading
import sys


class AnimationCLI(Node):

    def __init__(self):
        super().__init__('animation_cli')
        self._svc_clients = {}

    def _get_client(self, clip_name: str):
        """Lazily create a service client for a clip."""
        if clip_name not in self._svc_clients:
            self._svc_clients[clip_name] = self.create_client(
                Trigger, f'/animation/play/{clip_name}'
            )
        return self._svc_clients[clip_name]

    def _get_stop_client(self):
        if 'stop' not in self._svc_clients:
            self._svc_clients['stop'] = self.create_client(Trigger, '/animation/stop')
        return self._svc_clients['stop']

    def call(self, clip_name: str):
        if clip_name == 'stop':
            client = self._get_stop_client()
        else:
            client = self._get_client(clip_name)

        if not client.wait_for_service(timeout_sec=1.0):
            print(f"  [error] service not available for '{clip_name}'. "
                  f"Is animation_publisher running?")
            return

        future = client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)

        if future.result():
            status = "OK" if future.result().success else "FAIL"
            print(f"  [{status}] {future.result().message}")
        else:
            print(f"  [error] no response from service")

    def discover_clips(self):
        """List available /animation/play/* services."""
        names = []
        for name, _ in self.get_service_names_and_types():
            if name.startswith('/animation/play/'):
                names.append(name.split('/')[-1])
        return sorted(names)


def input_loop(node: AnimationCLI):
    clips = node.discover_clips()
    if clips:
        print(f"Available clips: {', '.join(clips)}")
    else:
        print("No clips found yet — make sure animation_publisher is running.")
    print("Commands: <clip_name> | stop | list | quit\n")

    while rclpy.ok():
        try:
            cmd = input("animation> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not cmd:
            continue
        elif cmd in ('quit', 'exit', 'q'):
            break
        elif cmd == 'list':
            clips = node.discover_clips()
            print(f"  Available: {', '.join(clips) if clips else 'none found'}")
        elif cmd == 'stop':
            node.call('stop')
        else:
            node.call(cmd)

    rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = AnimationCLI()

    # Run ROS spinning in background, input loop in main thread
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    input_loop(node)
    node.destroy_node()


if __name__ == '__main__':
    main()
