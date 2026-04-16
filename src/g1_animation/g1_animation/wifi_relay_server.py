#!/usr/bin/env python3
"""
WiFi relay server — runs on the Orin (Jetson).

Receives struct-packed motor commands from the PC over TCP and forwards
them to the G1 MCU via DDS on eth0.  No ROS2 dependency.

Usage:
    python3 wifi_relay_server.py [--interface eth0] [--port 9870]
"""
import argparse
import socket
import time
import logging

from unitree_sdk2py.core.channel import (
    ChannelPublisher,
    ChannelSubscriber,
    ChannelFactoryInitialize,
)
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC

from wifi_relay_protocol import (
    PORT,
    NUM_JOINTS,
    MOTOR_CMD,
    STOP,
    HEARTBEAT,
    MOTOR_CMD_SIZE,
    STOP_SIZE,
    unpack_motor_cmd,
    unpack_stop,
)

log = logging.getLogger("relay")

# ---------------------------------------------------------------------------
# G1 constants (duplicated from robot_publisher to avoid ROS2 dependency)
# ---------------------------------------------------------------------------

UPPER_BODY_JOINTS = [
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]

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

WALKING_EXCLUDE = {"waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"}

KP              = 60.0
KD              = 1.5
CONTROL_DT      = 0.005   # 200 Hz
WEIGHT_JOINT    = 29
WEIGHT_RAMP_STEPS = 200

# ---------------------------------------------------------------------------
# DDS helpers
# ---------------------------------------------------------------------------

class DDSBridge:
    """Manages DDS publishers/subscriber for the relay."""

    def __init__(self, interface: str):
        ChannelFactoryInitialize(0, interface)
        self._crc = CRC()
        self._state = None

        self._pub_damping = ChannelPublisher("rt/lowcmd", LowCmd_)
        self._pub_damping.Init()

        self._pub_walking = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self._pub_walking.Init()

        sub = ChannelSubscriber("rt/lowstate", LowState_)
        sub.Init(self._on_state, 10)
        log.info("DDS publishers ready on interface %s", interface)

        # Wait for first state message
        log.info("Waiting for robot state...")
        deadline = time.time() + 5.0
        while self._state is None and time.time() < deadline:
            time.sleep(0.1)
        if self._state is None:
            log.warning("No robot state after 5s — damping mode_machine will default to 0")
        else:
            log.info("Robot state received")

    def _on_state(self, msg: LowState_):
        self._state = msg

    def publish_cmd(self, mode: int, positions: list, velocities: list):
        """Build a LowCmd_ and publish it on the correct topic."""
        cmd = unitree_hg_msg_dds__LowCmd_()
        walking = mode == 1

        if not walking:
            cmd.mode_pr = 0
            cmd.mode_machine = self._state.mode_machine if self._state else 0
        else:
            cmd.motor_cmd[WEIGHT_JOINT].q = 1.0

        for i, name in enumerate(UPPER_BODY_JOINTS):
            if walking and name in WALKING_EXCLUDE:
                continue
            idx = G1_JOINT_INDEX[name]
            motor = cmd.motor_cmd[idx]
            motor.mode = 1
            motor.q    = positions[i]
            motor.dq   = velocities[i]
            motor.tau  = 0.0
            motor.kp   = KP
            motor.kd   = KD

        cmd.crc = self._crc.Crc(cmd)
        pub = self._pub_walking if walking else self._pub_damping
        pub.Write(cmd)

    def release_walking_mode(self, last_positions: list):
        """Ramp arm_sdk weight 1→0 so loco controller reclaims arms smoothly."""
        log.info("Releasing walking mode — ramping weight to 0...")
        for step in range(WEIGHT_RAMP_STEPS, -1, -1):
            cmd = unitree_hg_msg_dds__LowCmd_()
            cmd.motor_cmd[WEIGHT_JOINT].q = step / WEIGHT_RAMP_STEPS
            for i, name in enumerate(UPPER_BODY_JOINTS):
                if name in WALKING_EXCLUDE:
                    continue
                idx = G1_JOINT_INDEX[name]
                motor = cmd.motor_cmd[idx]
                motor.q   = last_positions[i]
                motor.dq  = 0.0
                motor.tau = 0.0
                motor.kp  = KP
                motor.kd  = KD
            cmd.crc = self._crc.Crc(cmd)
            self._pub_walking.Write(cmd)
            time.sleep(CONTROL_DT)
        log.info("Walking mode released")

# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------

def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from sock, or raise ConnectionError."""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("client disconnected")
        buf += chunk
    return buf


def handle_client(conn: socket.socket, bridge: DDSBridge):
    conn.settimeout(0.5)  # 500ms — detect PC dropout
    last_positions = None
    last_mode = 0
    msg_count = 0
    timeout_count = 0

    while True:
        try:
            type_byte = recv_exact(conn, 1)
        except socket.timeout:
            timeout_count += 1
            if timeout_count % 10 == 1:
                log.debug("Timeout #%d (msgs so far: %d)", timeout_count, msg_count)
            continue
        except ConnectionError:
            log.info("Client disconnected")
            break

        msg_type = type_byte[0]
        msg_count += 1
        if msg_count <= 3 or msg_count % 1000 == 0:
            log.info("msg #%d: type=0x%02x", msg_count, msg_type)

        try:
            if msg_type == MOTOR_CMD:
                payload = recv_exact(conn, MOTOR_CMD_SIZE - 1)
                mode, positions, velocities = unpack_motor_cmd(type_byte + payload)
                bridge.publish_cmd(mode, positions, velocities)
                last_positions = positions
                last_mode = mode

            elif msg_type == STOP:
                payload = recv_exact(conn, STOP_SIZE - 1)
                mode = unpack_stop(type_byte + payload)
                if mode == 1 and last_positions is not None:
                    bridge.release_walking_mode(last_positions)
                log.info("Stop received (mode=%d)", mode)

            elif msg_type == HEARTBEAT:
                pass  # keepalive

            else:
                log.warning("Unknown message type: 0x%02x", msg_type)

        except ConnectionError:
            log.info("Client disconnected mid-message")
            break


def serve(port: int, bridge: DDSBridge):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    log.info("Listening on 0.0.0.0:%d", port)

    while True:
        conn, addr = srv.accept()
        log.info("Client connected: %s:%d", *addr)
        try:
            handle_client(conn, bridge)
        finally:
            conn.close()
            log.info("Connection closed, waiting for next client...")


def main():
    parser = argparse.ArgumentParser(description="G1 WiFi animation relay")
    parser.add_argument("--interface", default="eth0",
                        help="Network interface to MCU (default: eth0)")
    parser.add_argument("--port", type=int, default=PORT,
                        help=f"TCP listen port (default: {PORT})")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    bridge = DDSBridge(args.interface)
    serve(args.port, bridge)


if __name__ == "__main__":
    main()
