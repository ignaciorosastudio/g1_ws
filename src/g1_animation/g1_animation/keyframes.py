import json
import os
from pathlib import Path

# G1 EDU+ upper body joint names (17 DOF)
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

# Standing default
# NEUTRAL = [
#     0.0,     # waist_yaw_joint
#     0.0,     # waist_roll_joint
#     0.0,     # waist_pitch_joint
#     0.2907,  # left_shoulder_pitch_joint
#     0.2249,  # left_shoulder_roll_joint
#     0.0003,  # left_shoulder_yaw_joint
#     0.9769,  # left_elbow_joint
#     0.1021,  # left_wrist_roll_joint
#     0.0,     # left_wrist_pitch_joint
#     0.0,     # left_wrist_yaw_joint
#     0.2939,  # right_shoulder_pitch_joint
#     -0.2376, # right_shoulder_roll_joint
#     0.0196,  # right_shoulder_yaw_joint
#     0.9779,  # right_elbow_joint
#     -0.1333, # right_wrist_roll_joint
#     0.0,     # right_wrist_pitch_joint
#     0.0,     # right_wrist_yaw_joint
# ]

#Sitting default
NEUTRAL = [0.0, 0.0, 0.0, -0.2094, -0.0001, 0.0, -0.0001, 0.0, 0.0, 0.0, -0.2094, -0.0003, 0.0, -0.0001, 0.0, 0.0, 0.0]

# Interpolation modes:
#   "linear"      — plain lerp; sharp corners at each keyframe.
#   "smoothstep"  — ease-in/out lerp within each segment.
#   "catmull_rom" — smooth spline through keyframes. Best for organic motion.

CLIPS_DIR = Path(os.environ.get("G1_CLIPS_DIR", Path.home() / "g1_ws" / "clips"))


def load_animations() -> dict:
    """Load all .json clip files from the clips/ folder into an ANIMATIONS dict."""
    animations = {}
    if not CLIPS_DIR.is_dir():
        return animations
    for path in sorted(CLIPS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            animations[path.stem] = {
                "keyframes": data["keyframes"],
                "interp":    data.get("interp", "linear"),
            }
        except Exception as e:
            print(f"[keyframes] Warning: could not load {path.name}: {e}")
    return animations


# Registry — auto-populated from clips/ folder
ANIMATIONS = load_animations()
