# G1 EDU+ upper body joint names (29 DOF arms + waist)
# Adjust to match your URDF joint names exactly
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

# Keyframe format: {"time": seconds, "positions": [joint values in radians]}
# Positions must match UPPER_BODY_JOINTS order

WAVE_ANIMATION = [

    # Neutral
    {"time": 0.0, "positions": [
        0.0,  0.0,  0.0,   # base + waist
        0.2,  0.0,  0.0, -0.3,   # left arm relaxed
        0.0,  0.0,  0.0,
        0.2,  0.0,  0.0, -0.3,   # right arm relaxed
        0.0,  0.0,  0.0
    ]},

    # Raise arms half way
    {'time': 0.2, 'positions': [0.0, 0.0, 0.0, -0.0003, 1.8222, 1.6326, 0.0985, 0.0, 0.0, 0.0, -0.0003, -1.7773, -1.4169, -0.0004, 0.0, 0.0, 0.0]},
    
    # Raise arms fully
    {'time': 0.4, 'positions': [0.0, 0.0, 0.0, -0.0003, 2.2515, 1.6326, 0.7639, 0.0, 0.0, 0.0, -0.0003, -2.2515, -1.4169, 0.7454, 0.0, 0.0, 0.0]},

    # Raise arms half way
    {'time': 0.6, 'positions': [0.0, 0.0, 0.0, -0.0003, 1.8222, 1.6326, 0.0985, 0.0, 0.0, 0.0, -0.0003, -1.7773, -1.4169, -0.0004, 0.0, 0.0, 0.0]},
    
    # Raise arms fully
    {'time': 0.7, 'positions': [0.0, 0.0, 0.0, -0.0003, 2.2515, 1.6326, 0.7639, 0.0, 0.0, 0.0, -0.0003, -2.2515, -1.4169, 0.7454, 0.0, 0.0, 0.0]},

    # Raise arms half way
    {'time': 0.8, 'positions': [0.0, 0.0, 0.0, -0.0003, 1.8222, 1.6326, 0.0985, 0.0, 0.0, 0.0, -0.0003, -1.7773, -1.4169, -0.0004, 0.0, 0.0, 0.0]},
    
    # Return to neutral
    {"time": 0.9, "positions": [
        0.0,  0.0,  0.0,
        0.2,  0.0,  0.0, -0.3,
        0.0,  0.0,  0.0,
        0.2,  0.0,  0.0, -0.3,
        0.0,  0.0,  0.0
    ]},
]
