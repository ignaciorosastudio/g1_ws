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

NEUTRAL = [0.0, 0.0, 0.0, 0.2, 0.0, 0.0, -0.3, 0.0, 0.0, 0.0,0.2, 0.0, 0.0, -0.3, 0.0, 0.0, 0.0]

HANDS_UP = [

    # Neutral
    {"time": 0.0, "positions": NEUTRAL},

    # Raise arms half way
    {'time': 2, 'positions': [0.0, 0.0, 0.0, -0.0003, 1.8222, 1.6326, 0.0985, 0.0, 0.0, 0.0, -0.0003, -1.7773, -1.4169, -0.0004, 0.0, 0.0, 0.0]},
        
    # Hold
    {'time': 4, 'positions': [0.0, 0.0, 0.0, -0.0003, 1.8222, 1.6326, 0.0985, 0.0, 0.0, 0.0, -0.0003, -1.7773, -1.4169, -0.0004, 0.0, 0.0, 0.0]},
        
    # Return to neutral
    {"time": 6, "positions": NEUTRAL},

]

WAVE_ARMS = [
    {"time": 0.0, "positions": NEUTRAL},
    {'time': 1.0, 'positions': [0.0, 0.0, 0.0, -0.0003, 0.4672, 0.4927, -0.3636, 0.116, 0.0381, 0.8356, -0.3787, -0.4445, -0.6158, -0.0004, -0.0233, -0.247, -0.7598]},
    {'time': 1.5, 'positions': [0.0, 0.0, 0.0, -0.684, 0.6027, 0.7393, -0.5851, 0.116, 0.0381, 0.8356, -0.7854, -0.4445, -0.6158, -0.308, -0.0233, -0.247, -0.7598]},
    {'time': 2.0, 'positions': [0.0, 0.0, 0.0, -0.684, 0.6027, 0.7393, 0.1171, 0.116, 0.0759, 0.8356, -0.8193, -0.4445, -0.6158, 0.1541, -0.0233, -0.247, -0.7598]},
    {'time': 2.5, 'positions': [0.0, 0.0, 0.0, -0.684, 0.6027, 0.7393, -0.5851, 0.116, 0.0381, 0.8356, -0.7854, -0.4445, -0.6158, -0.308, -0.0233, -0.247, -0.7598]},
    {'time': 3.0, 'positions': [0.0, 0.0, 0.0, -0.684, 0.6027, 0.7393, 0.1171, 0.116, 0.0759, 0.8356, -0.8193, -0.4445, -0.6158, 0.1541, -0.0233, -0.247, -0.7598]},
    {"time": 4.0, "positions": NEUTRAL},
]

# Right arm wave: raise arm, oscillate wrist pitch to wave
WAVE_RIGHT = [
    {"time": 0.0, "positions": NEUTRAL},
    # Raise right arm: shoulder roll out, elbow bent up
    {"time": 1.5, "positions": [0.0, 0.0, 0.0,  0.2,  0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, -1.2, 0.0,  1.5, 0.0,  0.0, 0.0]},
    # Wave 1 — wrist pitch forward
    {"time": 2.0, "positions": [0.0, 0.0, 0.0,  0.2,  0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, -1.2, 0.0,  1.5, 0.0,  0.6, 0.0]},
    # Wave 2 — wrist pitch back
    {"time": 2.5, "positions": [0.0, 0.0, 0.0,  0.2,  0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, -1.2, 0.0,  1.5, 0.0, -0.6, 0.0]},
    # Wave 3
    {"time": 3.0, "positions": [0.0, 0.0, 0.0,  0.2,  0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, -1.2, 0.0,  1.5, 0.0,  0.6, 0.0]},
    # Wave 4
    {"time": 3.5, "positions": [0.0, 0.0, 0.0,  0.2,  0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, -1.2, 0.0,  1.5, 0.0, -0.6, 0.0]},
    # Return to neutral
    {"time": 5.0, "positions": NEUTRAL},
]

# Both arms pitch forward, elbows extended — tests shoulder pitch symmetry
REACH_FORWARD = [
    {"time": 0.0, "positions": NEUTRAL},
    # Arms sweep forward
    {"time": 2.0, "positions": [0.0, 0.0, 0.0, -1.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
    # Hold
    {"time": 3.0, "positions": [0.0, 0.0, 0.0, -1.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
    # Return
    {"time": 5.0, "positions": NEUTRAL},
]

# Waist yaw left then right — isolates the waist_yaw_joint
TWIST = [
    {"time": 0.0, "positions": NEUTRAL},
    # Rotate left
    {"time": 1.5, "positions": [ 1.2, 0.0, 0.0,  0.2, 0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, 0.0, 0.0, -0.3, 0.0, 0.0, 0.0]},
    # Rotate right
    {"time": 3.0, "positions": [-1.2, 0.0, 0.0,  0.2, 0.0, 0.0, -0.3, 0.0, 0.0, 0.0,  0.2, 0.0, 0.0, -0.3, 0.0, 0.0, 0.0]},
    # Return
    {"time": 4.5, "positions": NEUTRAL},
]

# Arms cross at chest — tests shoulder pitch, inward roll, and elbow flex together.
# Elbows kept at 0.6 rad (not fully bent) and pitch limited to -0.5 to avoid
# forearm-to-forearm self-collision in front of the torso.
CROSS = [
    {"time": 0.0, "positions": NEUTRAL},
    # Pitch both arms forward, roll inward, elbows lightly bent
    {"time": 2.0, "positions": [0.0, 0.0, 0.0, -0.5, -0.3, 0.0, 0.6, 0.0, 0.0, 0.0, -0.5, 0.3, 0.0, 0.6, 0.0, 0.0, 0.0]},
    # Hold
    {"time": 3.5, "positions": [0.0, 0.0, 0.0, -0.5, -0.3, 0.0, 0.6, 0.0, 0.0, 0.0, -0.5, 0.3, 0.0, 0.6, 0.0, 0.0, 0.0]},
    # Return
    {"time": 5.0, "positions": NEUTRAL},
]

TYPING = [
    {'time': 0, 'positions': NEUTRAL},
    # Roll wrists down
    {'time': 1, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, 0.0, -0.0001, 1.5545, 0.0, 0.0, -0.0003, -0.0003, 0.0, -0.0001, -1.5545, 0.0, 0.0]},
    # Lift left arm, lower right arm
    {'time': 2, 'positions': [0.0, 0.0, 0.0, -0.2774, -0.0001, -0.1539, -0.0676, 1.5545, 0.0, 0.3797, -0.0061, 0.007, 0.1539, 0.0062, -1.5545, 0.0, 0.0]},
    # Lift right arm, lower left arm
    {'time': 3, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, -0.1539, 0.0062, 1.5545, 0.0, 0.0, -0.2774, 0.007, 0.1539, -0.0676, -1.5545, 0.0, -0.3797]},
    # Lift left arm, lower right arm
    {'time': 4, 'positions': [0.0, 0.0, 0.0, -0.2774, -0.0001, -0.1539, -0.0676, 1.5545, 0.0, 0.3797, -0.0061, 0.007, 0.1539, 0.0062, -1.5545, 0.0, 0.0]},
    # Lift right arm, lower left arm
    {'time': 5, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, -0.1539, 0.0062, 1.5545, 0.0, 0.0, -0.2774, 0.007, 0.1539, -0.0676, -1.5545, 0.0, -0.3797]},
    # Lift left arm, lower right arm
    {'time': 6, 'positions': [0.0, 0.0, 0.0, -0.2774, -0.0001, -0.1539, -0.0676, 1.5545, 0.0, 0.3797, -0.0061, 0.007, 0.1539, 0.0062, -1.5545, 0.0, 0.0]},
    # Lift right arm, lower left arm
    {'time': 7, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, -0.1539, 0.0062, 1.5545, 0.0, 0.0, -0.2774, 0.007, 0.1539, -0.0676, -1.5545, 0.0, -0.3797]},
    # Lift left arm, lower right arm
    {'time': 8, 'positions': [0.0, 0.0, 0.0, -0.2774, -0.0001, -0.1539, -0.0676, 1.5545, 0.0, 0.3797, -0.0061, 0.007, 0.1539, 0.0062, -1.5545, 0.0, 0.0]},
    # Lift right arm, lower left arm
    {'time': 9, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, -0.1539, 0.0062, 1.5545, 0.0, 0.0, -0.2774, 0.007, 0.1539, -0.0676, -1.5545, 0.0, -0.3797]},
    # Lift left arm, lower right arm
    {'time': 10, 'positions': [0.0, 0.0, 0.0, -0.2774, -0.0001, -0.1539, -0.0676, 1.5545, 0.0, 0.3797, -0.0061, 0.007, 0.1539, 0.0062, -1.5545, 0.0, 0.0]},
    # Lift right arm, lower left arm
    {'time': 11, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, -0.1539, 0.0062, 1.5545, 0.0, 0.0, -0.2774, 0.007, 0.1539, -0.0676, -1.5545, 0.0, -0.3797]},
    # Lift left arm, lower right arm
    {'time': 12, 'positions': [0.0, 0.0, 0.0, -0.2774, -0.0001, -0.1539, -0.0676, 1.5545, 0.0, 0.3797, -0.0061, 0.007, 0.1539, 0.0062, -1.5545, 0.0, 0.0]},
    # Lift right arm, lower left arm
    {'time': 13, 'positions': [0.0, 0.0, 0.0, -0.0061, -0.0001, -0.1539, 0.0062, 1.5545, 0.0, 0.0, -0.2774, 0.007, 0.1539, -0.0676, -1.5545, 0.0, -0.3797]},
    {'time': 14, 'positions': NEUTRAL},
]

# Interpolation modes:
#   "linear"      — plain lerp; sharp corners at each keyframe. Good for mechanical/repetitive motion.
#   "smoothstep"  — ease-in/out lerp within each segment; still has corners but feels softer.
#   "catmull_rom" — smooth spline through keyframes + smoothstep easing. Best for organic motion.

# Registry — add new clips here, they become available as service commands
ANIMATIONS = {
    "hands":   {"keyframes": HANDS_UP,       "interp": "catmull_rom"},
    "arms":    {"keyframes": WAVE_ARMS,      "interp": "catmull_rom"},
    "wave":    {"keyframes": WAVE_RIGHT,     "interp": "catmull_rom"},
    "reach":   {"keyframes": REACH_FORWARD,  "interp": "catmull_rom"},
    "twist":   {"keyframes": TWIST,          "interp": "catmull_rom"},
    "cross":   {"keyframes": CROSS,          "interp": "catmull_rom"},
    "typing":  {"keyframes": TYPING,         "interp": "linear"},
    "neutral": {"keyframes": [{"time": 0.0, "positions": NEUTRAL},
                               {"time": 0.5, "positions": NEUTRAL}],
                "interp": "linear"},
}