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

SMOKING = [
    # pose_1
    {'time': 0.0, 'positions': [-0.0933, 0.0000, 0.0000, -0.1021, 0.1762, 0.0004, -0.3790, -0.2218, 0.0000, 0.0000, -0.0358, 0.0359, 0.1022, 1.1311, -0.0229, 0.0000, 0.0000]},
    # pose_2
    {'time': 0.5, 'positions': [-0.0917, 0.0000, 0.0000, -0.1830, 0.5504, -0.3922, -0.5112, -0.8413, 0.0000, 0.0000, -0.0355, 0.0351, 0.1021, 1.1313, -0.0229, 0.0000, 0.0000]},
    # pose_3
    {'time': 1.0, 'positions': [-0.0908, 0.0000, 0.0000, -0.4822, 0.3122, -0.4668, -1.0808, -1.0406, 0.0000, 0.0000, -0.0355, 0.0342, 0.1020, 1.1314, -0.0229, 0.0000, 0.0000]},
    # pose_4
    {'time': 1.5, 'positions': [-0.0938, 0.0000, 0.0000, -0.2773, 0.1766, 0.0428, -0.5437, -1.0663, 0.0000, 0.0000, -0.0359, 0.0346, 0.1021, 1.1312, -0.0229, 0.0000, 0.0000]},
    # pose_5
    {'time': 2.0, 'positions': [-0.0948, 0.0000, 0.0000, -0.0004, 0.1996, 0.1947, -0.5437, -1.0652, 0.0000, 0.0000, -0.0361, 0.0346, 0.1021, 1.1311, -0.0229, 0.0000, 0.0000]},
    # pose_6
    {'time': 2.5, 'positions': [-0.0913, 0.0000, 0.0000, -0.2760, 0.1360, -0.7044, -1.0808, -1.0456, 0.0000, 0.0000, -0.0356, 0.0339, 0.1021, 1.1314, -0.0229, 0.0000, 0.0000]},
    # pose_7
    {'time': 3.0, 'positions': [-0.0943, 0.0000, 0.0000, -0.1415, 0.2523, 0.0307, -0.3906, -0.8015, 0.0000, 0.0000, -0.0361, 0.0343, 0.1021, 1.1311, -0.0229, 0.0000, 0.0000]},
]

BOMBO = [
    # pose_1
    {'time': 0.0, 'positions': [-0.1211, 0.0000, 0.0000, 0.1872, 0.0069, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, 0.1320, -0.1608, 0.0857, 0.9776, -0.4939, 0.0000, 0.0000]},
    # pose_2
    {'time': 0.5, 'positions': [-0.1205, 0.0000, 0.0000, 0.1872, 0.0069, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, 0.0034, -0.1365, 0.7685, 0.5837, -0.4893, 0.0000, 0.0000]},
    # pose_3
    {'time': 1.0, 'positions': [-0.1206, 0.0000, 0.0000, 0.1872, 0.0069, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, 0.0027, -0.1165, 0.8262, 0.1304, -0.4767, 0.0000, 0.0000]},
    # pose_4
    {'time': 1.5, 'positions': [-0.1212, 0.0000, 0.0000, 0.1873, 0.0069, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, 0.0034, -0.0613, 0.4715, -0.0867, -0.4750, 0.0000, 0.0000]},
    # pose_5
    {'time': 2.0, 'positions': [-0.1211, 0.0000, 0.0000, 0.1872, 0.0069, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, 0.0056, -0.0072, 0.0850, -0.3603, -0.4511, 0.0000, 0.0000]},
    # pose_6
    {'time': 2.5, 'positions': [-0.1203, 0.0000, 0.0000, 0.1872, 0.0068, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, 0.0051, -0.1077, 0.0842, 0.3471, -0.4553, 0.0000, 0.0000]},
    # pose_7
    {'time': 3.0, 'positions': [-0.1204, 0.0000, 0.0000, 0.1871, 0.0068, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, -0.0623, -0.0813, 0.1024, -0.4017, -0.4543, 0.0000, 0.0000]},
    # pose_8
    {'time': 3.5, 'positions': [-0.1202, 0.0000, 0.0000, 0.1871, 0.0068, 0.0633, 0.8780, 0.6106, 0.0000, 0.0000, 0.0042, -0.1248, 0.1138, 0.5793, -0.4555, 0.0000, 0.0000]},
    # pose_9
    {'time': 4.0, 'positions': [-0.1206, 0.0000, 0.0000, 0.1871, 0.0069, 0.0634, 0.8779, 0.6106, 0.0000, 0.0000, -0.0719, -0.0839, 0.1221, -0.5184, -0.4544, 0.0000, 0.0000]},
    # pose_10
    {'time': 4.5, 'positions': [-0.1203, 0.0000, 0.0000, 0.1871, 0.0068, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, -0.0562, -0.1295, 0.1000, 0.5053, -0.4597, 0.0000, 0.0000]},
    # pose_11
    {'time': 5.0, 'positions': [-0.1210, 0.0000, 0.0000, 0.1873, 0.0069, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, -0.0740, -0.1154, 0.0991, -0.4001, -0.4547, 0.0000, 0.0000]},
    # pose_12
    {'time': 5.5, 'positions': [-0.1198, 0.0000, 0.0000, 0.1871, 0.0068, 0.0633, 0.8780, 0.6106, 0.0000, 0.0000, -0.0359, -0.1257, -0.0089, 0.6624, -0.4593, 0.0000, 0.0000]},
    # pose_13
    {'time': 6.0, 'positions': [-0.1200, 0.0000, 0.0000, 0.1871, 0.0068, 0.0634, 0.8780, 0.6106, 0.0000, 0.0000, -0.0193, -0.0079, 0.6511, 0.9574, -0.4970, 0.0000, 0.0000]},
]

# Interpolation modes:
#   "linear"      — plain lerp; sharp corners at each keyframe. Good for mechanical/repetitive motion.
#   "smoothstep"  — ease-in/out lerp within each segment; still has corners but feels softer.
#   "catmull_rom" — smooth spline through keyframes + smoothstep easing. Best for organic motion.

# Registry — add new clips here, they become available as service commands
ANIMATIONS = {
    "hands":   {"keyframes": HANDS_UP,       "interp": "linear"},
    "arms":    {"keyframes": WAVE_ARMS,      "interp": "catmull_rom"},
    "wave":    {"keyframes": WAVE_RIGHT,     "interp": "catmull_rom"},
    "reach":   {"keyframes": REACH_FORWARD,  "interp": "catmull_rom"},
    "twist":   {"keyframes": TWIST,          "interp": "catmull_rom"},
    "cross":   {"keyframes": CROSS,          "interp": "catmull_rom"},
    "typing":  {"keyframes": TYPING,         "interp": "linear"},
    "smoking": {"keyframes": SMOKING,        "interp": "linear"},
    "bombo":   {"keyframes": BOMBO,          "interp": "linear"},
    "neutral": {"keyframes": [{"time": 0.0, "positions": NEUTRAL},
                               {"time": 0.5, "positions": NEUTRAL}],
                "interp": "linear"},
}