#!/usr/bin/env python3
"""
AnimationCore — shared base class for AnimationPublisher and RobotPublisher.

Handles all animation logic: service registration, play/stop transitions,
interpolation (linear / smoothstep / catmull_rom), velocity/accel capping,
and the main tick loop.

Subclasses implement _send(positions, old_positions) to deliver the
computed positions to their output (JointState topic or hardware LowCmd).
"""
import time
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from std_msgs.msg import String
from rcl_interfaces.msg import SetParametersResult

from .keyframes import UPPER_BODY_JOINTS, ANIMATIONS, NEUTRAL

MAX_JOINT_VEL   = 3.0  # rad/s  — hard cap per tick
MAX_JOINT_ACCEL = 2.0  # rad/s² — must be < MAX_JOINT_VEL to have any effect at 200 Hz


class AnimationCore(Node):
    """
    Base class for animation nodes.

    Subclasses must:
      - Call super().__init__(node_name, control_dt) as the first line
      - Implement _send(positions, old_positions)
    """

    def __init__(self, node_name: str, control_dt: float):
        super().__init__(node_name)
        self.CONTROL_DT = control_dt

        # --- shared parameters ---
        self.declare_parameter('speed', 1.0)
        self.declare_parameter('loop', False)
        self._speed = self.get_parameter('speed').value
        self.add_on_set_parameters_callback(self._on_parameters_change)

        # --- shared state ---
        self._current_clip     = None
        self._keyframes        = []
        self._interp_mode      = "linear"
        self._start_time       = time.monotonic()
        self._loop             = False
        self._playing          = False
        self._queued_animation = None

        self._current_positions = list(NEUTRAL)
        self._prev_velocities   = [0.0] * len(UPPER_BODY_JOINTS)

        # --- status publisher (useful for both preview and hardware nodes) ---
        self.status_pub = self.create_publisher(String, '/animation/status', 10)

        # --- services (one per registered animation + stop) ---
        for name in ANIMATIONS:
            self.create_service(
                Trigger,
                f'/animation/play/{name}',
                lambda req, res, n=name: self._handle_play(req, res, n),
            )
        self.create_service(Trigger, '/animation/stop', self._handle_stop)

        # --- control loop ---
        self.create_timer(control_dt, self._tick)

        self.get_logger().info(f"Available clips: {', '.join(ANIMATIONS.keys())}")

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    def _on_parameters_change(self, params):
        for p in params:
            if p.name == 'speed':
                if p.value <= 0:
                    return SetParametersResult(successful=False, reason='speed must be > 0')
                if self._playing:
                    old_elapsed = (time.monotonic() - self._start_time) * self._speed
                    self._speed = p.value
                    self._start_time = time.monotonic() - old_elapsed / self._speed
                else:
                    self._speed = p.value
                self.get_logger().info(f"Playback speed: {self._speed:.2f}x")
        return SetParametersResult(successful=True)

    def _handle_play(self, request, response, name: str):
        """Queue animation and blend current → neutral first."""
        clip = ANIMATIONS[name]
        kfs  = clip["keyframes"]

        if len(kfs) < 2:
            response.success = False
            response.message = f"'{name}' has fewer than 2 keyframes"
            self.get_logger().error(response.message)
            return response

        for i, kf in enumerate(kfs):
            if len(kf["positions"]) != len(UPPER_BODY_JOINTS):
                response.success = False
                response.message = (
                    f"[{name}] keyframe {i}: expected {len(UPPER_BODY_JOINTS)} "
                    f"positions, got {len(kf['positions'])}"
                )
                self.get_logger().error(response.message)
                return response

        for i in range(1, len(kfs)):
            if kfs[i]["time"] <= kfs[i - 1]["time"]:
                response.success = False
                response.message = (
                    f"[{name}] keyframe times must be strictly increasing "
                    f"(keyframe {i}: {kfs[i]['time']} <= {kfs[i-1]['time']})"
                )
                self.get_logger().error(response.message)
                return response

        self._queued_animation = name
        self._keyframes = [
            {"time": 0.0, "positions": list(self._current_positions)},
            {"time": 1.0, "positions": list(NEUTRAL)},
        ]
        self._interp_mode = "linear"
        self._start_time  = time.monotonic()
        self._loop        = False
        self._playing     = True
        response.success = True
        response.message = f"Queued '{name}' — blending to neutral first"
        self.get_logger().info(response.message)
        return response

    def _handle_stop(self, request, response):
        self._queued_animation = None  # cancel any pending clip
        self._keyframes = [
            {"time": 0.0, "positions": list(self._current_positions)},
            {"time": 1.5, "positions": list(NEUTRAL)},
        ]
        self._interp_mode = "linear"
        self._start_time  = time.monotonic()
        self._loop        = False
        self._playing     = True
        response.success = True
        response.message = "Stopping — blending to neutral"
        self.get_logger().info(response.message)
        return response

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------

    @staticmethod
    def _catmull_rom(p0, p1, p2, p3, t):
        t2 = t * t
        t3 = t2 * t
        return (
            0.5 * (
                (2 * p1)
                + (-p0 + p2) * t
                + (2*p0 - 5*p1 + 4*p2 - p3) * t2
                + (-p0 + 3*p1 - 3*p2 + p3) * t3
            )
        )

    def _interpolate(self, elapsed: float) -> list:
        kfs   = self._keyframes
        total = kfs[-1]["time"]

        if elapsed > total:
            elapsed = elapsed % total if self._loop else total

        seg_idx = 0
        for i in range(len(kfs) - 1):
            if kfs[i]["time"] <= elapsed <= kfs[i + 1]["time"]:
                seg_idx = i
                break

        seg   = kfs[seg_idx + 1]["time"] - kfs[seg_idx]["time"]
        raw_t = 0.0 if seg == 0 else (elapsed - kfs[seg_idx]["time"]) / seg

        if self._interp_mode == "smoothstep":
            t = raw_t * raw_t * (3.0 - 2.0 * raw_t)
        else:
            t = raw_t

        if self._interp_mode == "catmull_rom":
            # Use raw t — Catmull-Rom produces its own smooth velocity profile
            # through keyframes. Pre-applying smoothstep would distort that.
            # Overshoot is intentional; the velocity limiter bounds the result.
            i0 = max(seg_idx - 1, 0)
            i1 = seg_idx
            i2 = seg_idx + 1
            i3 = min(seg_idx + 2, len(kfs) - 1)
            return [
                self._catmull_rom(
                    kfs[i0]["positions"][j],
                    kfs[i1]["positions"][j],
                    kfs[i2]["positions"][j],
                    kfs[i3]["positions"][j],
                    t,
                )
                for j in range(len(UPPER_BODY_JOINTS))
            ]

        return [
            kfs[seg_idx]["positions"][j] + t * (kfs[seg_idx + 1]["positions"][j] - kfs[seg_idx]["positions"][j])
            for j in range(len(UPPER_BODY_JOINTS))
        ]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _tick(self):
        old_positions = list(self._current_positions)

        if self._playing:
            elapsed = (time.monotonic() - self._start_time) * self._speed

            # When a non-looping clip finishes, start the queued animation or go idle
            if not self._loop and self._keyframes and elapsed >= self._keyframes[-1]["time"]:
                if self._queued_animation:
                    name = self._queued_animation
                    self._queued_animation = None
                    clip = ANIMATIONS[name]
                    self._keyframes = [
                        {"time": 0.0, "positions": list(self._current_positions)},
                        {"time": 0.5, "positions": clip["keyframes"][0]["positions"]},
                    ] + [
                        {"time": kf["time"] + 0.5, "positions": kf["positions"]}
                        for kf in clip["keyframes"]
                    ]
                    self._interp_mode  = clip["interp"]
                    self._start_time   = time.monotonic()
                    self._loop         = self.get_parameter('loop').value
                    self._current_clip = name
                    elapsed            = 0.0
                    self.get_logger().info(f"Starting '{name}'")
                else:
                    self._playing      = False
                    self._current_clip = None

            if self._playing:
                target   = self._interpolate(elapsed)
                max_step = MAX_JOINT_VEL * self.CONTROL_DT
                max_dv   = MAX_JOINT_ACCEL * self.CONTROL_DT
                positions      = []
                new_velocities = []
                for prev, tgt, prev_v in zip(self._current_positions, target, self._prev_velocities):
                    vel_capped = max(-max_step, min(max_step, tgt - prev))
                    new_v = max(prev_v - max_dv, min(prev_v + max_dv, vel_capped))
                    positions.append(prev + new_v)
                    new_velocities.append(new_v)
                self._current_positions = positions
                self._prev_velocities   = new_velocities
            else:
                # Clip just ended this tick — hold at current position
                positions = old_positions
                self._prev_velocities = [0.0] * len(UPPER_BODY_JOINTS)
        else:
            # Idle — hold position
            positions = old_positions

        # Publish status
        msg = String()
        msg.data = self._current_clip or "idle"
        self.status_pub.publish(msg)

        self._send(positions, old_positions)

    def _send(self, positions: list, old_positions: list):
        raise NotImplementedError
