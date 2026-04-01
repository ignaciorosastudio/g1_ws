#!/usr/bin/env python3
"""
G1 Animation Publisher
- Idles at neutral pose
- Plays a named animation clip on demand via ROS2 service
- Loops or plays once depending on the request
- Publishes /joint_states for RViz preview
"""
import rclpy
import rclpy.duration
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from std_msgs.msg import String
from rcl_interfaces.msg import SetParametersResult

from .keyframes import UPPER_BODY_JOINTS, ANIMATIONS, NEUTRAL


class AnimationPublisher(Node):

    def __init__(self):
        super().__init__('animation_publisher')

        # --- publishers ---
        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)

        # Publishes the name of the currently playing clip (useful for monitoring)
        self.status_pub = self.create_publisher(String, '/animation/status', 10)

        # --- services (one per registered animation) ---
        self._animation_services = {}
        for name in ANIMATIONS:
            srv = self.create_service(
                Trigger,
                f'/animation/play/{name}',
                lambda req, res, n=name: self._handle_play(req, res, n),
            )
            self._animation_services[name] = srv
            self.get_logger().info(f"Registered service: /animation/play/{name}")

        # Stop service — returns to neutral immediately
        self.create_service(Trigger, '/animation/stop', self._handle_stop)

        # --- state ---
        self.declare_parameter('speed', 1.0)
        self._speed = self.get_parameter('speed').value
        self.add_on_set_parameters_callback(self._on_parameters_change)

        self._current_clip   = None      # name of playing clip
        self._keyframes      = None      # active keyframe list
        self._interp_mode    = "linear"  # set per-clip from ANIMATIONS registry
        self._start_time     = None
        self._loop           = False
        self._playing        = False

        # Start at neutral
        self._current_positions = list(NEUTRAL)

        # 50 Hz tick
        self.timer = self.create_timer(0.02, self._tick)
        self.get_logger().info("Animation publisher ready. Send a service call to play a clip.")
        self.get_logger().info("Available clips: " + ", ".join(ANIMATIONS.keys()))

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    def _on_parameters_change(self, params):
        for p in params:
            if p.name == 'speed':
                if p.value <= 0:
                    return SetParametersResult(successful=False, reason='speed must be > 0')
                if self._playing and self._start_time is not None:
                    now = self.get_clock().now()
                    old_elapsed = (now - self._start_time).nanoseconds / 1e9 * self._speed
                    self._speed = p.value
                    self._start_time = now - rclpy.duration.Duration(
                        nanoseconds=int(old_elapsed / self._speed * 1e9)
                    )
                else:
                    self._speed = p.value
                self.get_logger().info(f"Playback speed: {self._speed:.2f}x")
        return SetParametersResult(successful=True)

    def _handle_play(self, request, response, name: str):
        """Blend from current pose into the first frame of the clip, then play."""
        clip = ANIMATIONS[name]
        target_first_frame = clip["keyframes"][0]["positions"]
        blend_then_play = [
            {"time": 0.0,  "positions": list(self._current_positions)},
            {"time": 0.5, "positions": target_first_frame},
        ] + [
            {"time": kf["time"] + 0.5, "positions": kf["positions"]}
            for kf in clip["keyframes"]
        ]
        self._current_clip = name
        self._keyframes    = blend_then_play
        self._interp_mode  = clip["interp"]
        self._start_time   = self.get_clock().now()
        self._loop         = False
        self._playing      = True

        # Validate
        for i, kf in enumerate(self._keyframes):
            if len(kf["positions"]) != len(UPPER_BODY_JOINTS):
                self.get_logger().error(
                    f"[{name}] keyframe {i}: expected {len(UPPER_BODY_JOINTS)} "
                    f"positions, got {len(kf['positions'])}"
                )
                self._stop()
                break

        response.success = True
        response.message = f"Playing '{name}'"
        self.get_logger().info(response.message)
        return response

    def _handle_stop(self, request, response):
        """Stop current animation and smoothly blend back to neutral."""
        self._start_blend_to_neutral(duration=1.0)
        response.success = True
        response.message = "Stopped — blending to neutral"
        self.get_logger().info(response.message)
        return response
    
    def _start_blend_to_neutral(self, duration: float = 1.0):
        """Build a one-segment clip from current pose to neutral and play it."""
        blend_clip = [
            {"time": 0.0, "positions": list(self._current_positions)},
            {"time": duration, "positions": list(NEUTRAL)},
        ]
        self._current_clip = "blend_to_neutral"
        self._keyframes    = blend_clip
        self._start_time   = self.get_clock().now()
        self._loop         = False
        self._playing      = True

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def _start_clip(self, name: str, loop: bool = False):
        clip = ANIMATIONS[name]
        self._current_clip = name
        self._keyframes    = clip["keyframes"]
        self._interp_mode  = clip["interp"]
        self._start_time   = self.get_clock().now()
        self._loop         = loop
        self._playing      = True

        # Validate keyframe lengths up front
        for i, kf in enumerate(self._keyframes):
            if len(kf["positions"]) != len(UPPER_BODY_JOINTS):
                self.get_logger().error(
                    f"[{name}] keyframe {i}: expected {len(UPPER_BODY_JOINTS)} "
                    f"positions, got {len(kf['positions'])}"
                )
                self._stop()
                return

    def _stop(self):
        self._playing      = False
        self._current_clip = None
        self._keyframes    = None

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------

    @staticmethod
    def _catmull_rom(p0, p1, p2, p3, t):
        """
        Catmull-Rom spline interpolation between p1 and p2.
        p0 and p3 are the surrounding control points that shape the curve.
        Produces continuous velocity and acceleration through keyframes.
        """
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

        if elapsed >= total:
            if self._loop:
                elapsed = elapsed % total
            else:
                self._stop()
                return list(kfs[-1]["positions"])

        # Find segment index
        seg_idx = 0
        for i in range(len(kfs) - 1):
            if kfs[i]["time"] <= elapsed <= kfs[i + 1]["time"]:
                seg_idx = i
                break

        seg   = kfs[seg_idx + 1]["time"] - kfs[seg_idx]["time"]
        raw_t = 0.0 if seg == 0 else (elapsed - kfs[seg_idx]["time"]) / seg

        # Apply easing
        if self._interp_mode in ("smoothstep", "catmull_rom"):
            t = raw_t * raw_t * (3.0 - 2.0 * raw_t)
        else:  # linear
            t = raw_t

        if self._interp_mode == "catmull_rom":
            i0 = max(seg_idx - 1, 0)
            i1 = seg_idx
            i2 = seg_idx + 1
            i3 = min(seg_idx + 2, len(kfs) - 1)
            result = []
            for j in range(len(UPPER_BODY_JOINTS)):
                val = self._catmull_rom(
                    kfs[i0]["positions"][j],
                    kfs[i1]["positions"][j],
                    kfs[i2]["positions"][j],
                    kfs[i3]["positions"][j],
                    t,
                )
                lo = min(kfs[i1]["positions"][j], kfs[i2]["positions"][j])
                hi = max(kfs[i1]["positions"][j], kfs[i2]["positions"][j])
                result.append(max(lo, min(hi, val)))
            return result

        # linear or smoothstep — plain lerp with eased t
        return [
            kfs[seg_idx]["positions"][j] + t * (kfs[seg_idx + 1]["positions"][j] - kfs[seg_idx]["positions"][j])
            for j in range(len(UPPER_BODY_JOINTS))
        ]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _tick(self):
        if self._playing:
            elapsed = (self.get_clock().now() - self._start_time).nanoseconds / 1e9 * self._speed
            self._current_positions = self._interpolate(elapsed)

            # Publish status
            msg = String()
            msg.data = self._current_clip or "idle"
            self.status_pub.publish(msg)

        # Always publish joint states (idle = neutral, playing = interpolated)
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name         = UPPER_BODY_JOINTS
        js.position     = self._current_positions
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
