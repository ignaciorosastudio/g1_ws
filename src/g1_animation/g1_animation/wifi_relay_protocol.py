"""
WiFi relay protocol — shared constants and pack/unpack helpers.

Used by both the PC-side WifiPublisher and the Orin-side wifi_relay_server.
All messages are fixed-size, little-endian, struct-packed binary.
"""
import struct

PORT = 9870
NUM_JOINTS = 17

# Message types (first byte)
MOTOR_CMD = 0x01
STOP      = 0x02
HEARTBEAT = 0xFF

# struct formats
_MOTOR_CMD_FMT = f'<BB{NUM_JOINTS}f{NUM_JOINTS}f'  # type + mode + positions + velocities
_STOP_FMT      = '<BB'                                # type + mode

MOTOR_CMD_SIZE = struct.calcsize(_MOTOR_CMD_FMT)  # 138 bytes
STOP_SIZE      = struct.calcsize(_STOP_FMT)        # 2 bytes


def pack_motor_cmd(mode: int, positions: list, velocities: list) -> bytes:
    return struct.pack(_MOTOR_CMD_FMT, MOTOR_CMD, mode, *positions, *velocities)


def unpack_motor_cmd(data: bytes):
    """Returns (mode, positions, velocities)."""
    vals = struct.unpack(_MOTOR_CMD_FMT, data)
    # vals[0] = type byte, vals[1] = mode, vals[2:19] = positions, vals[19:36] = velocities
    mode = vals[1]
    positions = list(vals[2 : 2 + NUM_JOINTS])
    velocities = list(vals[2 + NUM_JOINTS : 2 + 2 * NUM_JOINTS])
    return mode, positions, velocities


def pack_stop(mode: int) -> bytes:
    return struct.pack(_STOP_FMT, STOP, mode)


def unpack_stop(data: bytes) -> int:
    """Returns mode."""
    return struct.unpack(_STOP_FMT, data)[1]
