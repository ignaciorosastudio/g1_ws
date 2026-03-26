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

# Registry — add new clips here, they become available as service commands
ANIMATIONS = {
    "hands":    HANDS_UP,
    "arms":    WAVE_ARMS,
    "neutral": [{"time": 0.0, "positions": NEUTRAL},
                {"time": 0.5, "positions": NEUTRAL}],
}