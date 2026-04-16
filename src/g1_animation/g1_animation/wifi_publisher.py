#!/usr/bin/env python3
"""
WiFi publisher — sends animation commands to the Orin relay over TCP.

Drop-in replacement for RobotPublisher: inherits AnimationCore for clip
playback, interpolation, and velocity capping, but outputs via TCP instead
of DDS.
"""
import socket
import logging
import rclpy
from sensor_msgs.msg import JointState

from .animation_core import AnimationCore
from .keyframes import UPPER_BODY_JOINTS
from .wifi_relay_protocol import (
    PORT,
    pack_motor_cmd,
    pack_stop,
    HEARTBEAT,
)

CONTROL_DT = 0.005  # 200 Hz — must match relay server


class WifiPublisher(AnimationCore):

    def __init__(self):
        super().__init__('wifi_publisher', control_dt=CONTROL_DT)

        self.declare_parameter('relay_host', '192.168.0.123')
        self.declare_parameter('relay_port', PORT)
        self.declare_parameter('dry_run', True)
        self.declare_parameter('mode', 'damping')

        self._host = self.get_parameter('relay_host').value
        self._port = self.get_parameter('relay_port').value
        self._dry  = self.get_parameter('dry_run').value
        self._mode = self.get_parameter('mode').value

        if self._mode not in ('damping', 'walking'):
            raise ValueError(f"Invalid mode '{self._mode}'. Use 'damping' or 'walking'.")

        self._mode_byte = 0 if self._mode == 'damping' else 1
        self._sock = None

        if self._dry:
            self.get_logger().warn(
                "DRY RUN mode — commands will NOT be sent to the relay. "
                "Set dry_run:=false to connect."
            )
        else:
            self._connect()

        # Joint states publisher for RViz monitoring
        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)

        self.get_logger().info(
            f"WiFi publisher ready (relay={self._host}:{self._port}, "
            f"mode={self._mode}, dry_run={self._dry})"
        )

    # ------------------------------------------------------------------
    # TCP connection
    # ------------------------------------------------------------------

    def _connect(self):
        """Connect (or reconnect) to the relay server."""
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((self._host, self._port))
            sock.settimeout(None)
            # Disable Nagle for low-latency small writes
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock = sock
            self.get_logger().info(f"Connected to relay at {self._host}:{self._port}")
        except OSError as e:
            self._sock = None
            self.get_logger().error(f"Cannot connect to relay: {e}")

    def _send_raw(self, data: bytes):
        """Send bytes, reconnecting on failure."""
        if self._sock is None:
            self._connect()
        if self._sock is None:
            return  # still can't connect
        try:
            self._sock.sendall(data)
        except OSError as e:
            self.get_logger().warn(f"Send failed ({e}), reconnecting...")
            self._sock = None
            self._connect()

    # ------------------------------------------------------------------
    # AnimationCore interface
    # ------------------------------------------------------------------

    def _send(self, positions: list, old_positions: list):
        # Publish joint states for RViz regardless of dry_run
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name     = UPPER_BODY_JOINTS
        js.position = positions
        js.velocity = [(p - o) / self.CONTROL_DT for p, o in zip(positions, old_positions)]
        self.js_pub.publish(js)

        if self._dry:
            return

        velocities = [(p - o) / self.CONTROL_DT for p, o in zip(positions, old_positions)]
        data = pack_motor_cmd(self._mode_byte, positions, velocities)
        self._send_raw(data)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _release(self):
        """Send stop message so the Orin can ramp down walking mode."""
        if self._dry or self._sock is None:
            return
        try:
            self._sock.sendall(pack_stop(self._mode_byte))
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None


def main(args=None):
    rclpy.init(args=args)
    node = WifiPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._release()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
