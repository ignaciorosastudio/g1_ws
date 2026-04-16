#!/usr/bin/env python3
"""
G1 Animation CLI
Interactive terminal to trigger animation clips by name.
Run in a separate terminal while animation_publisher is running.

Usage:
    ros2 run g1_animation animation_cli
"""
import time
import threading
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType


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

    def _wait_for_future(self, future, timeout_sec: float = 2.0):
        """Wait for a future to complete.

        The spin loop runs in a background thread so we must NOT call
        spin_until_future_complete — spinning the same node from two threads
        is undefined behaviour in rclpy. Instead we just poll until done.
        """
        deadline = time.monotonic() + timeout_sec
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.005)

    def call(self, clip_name: str):
        if clip_name == 'stop':
            client = self._get_stop_client()
        else:
            client = self._get_client(clip_name)

        if not client.wait_for_service(timeout_sec=1.0):
            print(f"  [error] service not available for '{clip_name}'. "
                  f"Is the animation node running?")
            return

        future = client.call_async(Trigger.Request())
        self._wait_for_future(future)

        if future.result():
            status = "OK" if future.result().success else "FAIL"
            print(f"  [{status}] {future.result().message}")
        else:
            print(f"  [error] no response from service")

    def _get_param_client(self):
        """Return the parameter client for whichever animation node is running."""
        for node_name in ('robot_publisher', 'wifi_publisher', 'animation_publisher'):
            key = f'_param_client_{node_name}'
            if not hasattr(self, key):
                setattr(self, key, self.create_client(
                    SetParameters, f'/{node_name}/set_parameters'
                ))
            client = getattr(self, key)
            if client.wait_for_service(timeout_sec=0.5):
                return client
        return None

    def set_speed(self, speed: float):
        client = self._get_param_client()
        if client is None:
            print("  [error] no animation node available")
            return

        pv = ParameterValue()
        pv.type = ParameterType.PARAMETER_DOUBLE
        pv.double_value = speed

        param = Parameter()
        param.name = 'speed'
        param.value = pv

        req = SetParameters.Request()
        req.parameters = [param]

        future = client.call_async(req)
        self._wait_for_future(future)

        if future.result():
            result = future.result().results[0]
            if result.successful:
                print(f"  [OK] speed set to {speed:.2f}x")
            else:
                print(f"  [FAIL] {result.reason}")
        else:
            print("  [error] no response from service")

    def discover_clips(self):
        """List available /animation/play/* services."""
        names = []
        for name, _ in self.get_service_names_and_types():
            if name.startswith('/animation/play/'):
                names.append(name.split('/')[-1])
        return sorted(names)


def input_loop(node: AnimationCLI):
    print("Waiting for animation node...", flush=True)
    sentinel = node.create_client(Trigger, '/animation/stop')
    if sentinel.wait_for_service(timeout_sec=10.0):
        clips = node.discover_clips()
        print(f"Connected. Available clips: {', '.join(clips) if clips else 'none found'}")
    else:
        print("No animation node found after 10s — check that the publisher is running and using the same env.")
    print("Commands: <clip_name> | stop | list | speed <value> | quit\n")

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
        elif cmd.startswith('speed'):
            parts = cmd.split()
            if len(parts) != 2:
                print("  Usage: speed <value>  (e.g. speed 0.5, speed 2.0)")
            else:
                try:
                    val = float(parts[1])
                    if val <= 0:
                        raise ValueError
                    node.set_speed(val)
                except ValueError:
                    print("  Usage: speed <positive number>  (e.g. speed 0.5, speed 2.0)")
        else:
            node.call(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = AnimationCLI()

    # Run ROS spinning in background, input loop in main thread.
    # Service futures are completed by the spin thread; input_loop polls them
    # via _wait_for_future rather than calling spin_until_future_complete,
    # which would conflict with the background spin.
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    input_loop(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
