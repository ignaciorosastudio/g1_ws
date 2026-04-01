# Running G1 Animations

## Prerequisites

Both modes require:
```bash
export G1_INTERFACE=enp46s0          # your ethernet interface to the robot
export CYCLONEDDS_URI=$(pwd)/config/cyclonedds.xml
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

---

## Mode 1 — Damping (robot static)

The robot must be powered on in **Debug/Damping mode**. The animation node owns all
upper-body joints directly via `rt/lowcmd`.

```bash
ros2 launch g1_animation robot_deploy.launch.py \
  network_interface:=$G1_INTERFACE \
  mode:=damping \
  dry_run:=false \
  loop:=false \
  animation:=wave
```

---

## Mode 2 — Walking (animations while walking)

The robot is controlled by **g1pilot's locomotion stack**. The animation node
sends only arm/waist commands via `rt/arm_sdk`, which are blended on top of
the loco controller's natural arm swing.

> **The robot must be in normal Sport mode, NOT in Debug/Damping mode.**
> Debug mode disables the onboard sport service that `loco_client` relies on.
> If you have been using damping mode, switch the robot back to sport mode
> (typically **L2 + A** on the controller, or power cycle without entering debug)
> before proceeding. You can verify comms are working if `loco_client` reports
> a real `FSM ID` (e.g. `1` or `4`) rather than `None`.

> **Only Regular walking mode (R1+X on the controller) supports `rt/arm_sdk`
> arm override. Running mode (R2+A) does not.**

### Step 1 — Start the locomotion stack

In a separate terminal (all three env vars must be set):
```bash
export G1_INTERFACE=enp46s0
export CYCLONEDDS_URI=<path_to_ws>/config/cyclonedds.xml
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

cd ~/g1_ws && colcon build --packages-select g1_animation
source ~/g1_ws/setup_robot_env.sh
ros2 launch g1pilot navigation_launcher.launch.py \
  interface:=$G1_INTERFACE
```

The node starts in **Damp** mode and prints the current FSM ID/Mode.
If you see `FSM ID: None, Mode: None`, the DDS env vars are likely missing —
check `echo $CYCLONEDDS_URI` and re-source before relaunching.

### Step 2 — Trigger Balance Stand

Balance stand is **not automatic**. Trigger it in a third terminal:
```bash
ros2 topic pub --once /g1pilot/start_balancing std_msgs/msg/Bool "data: true"
```

Alternatively, press **R1 (button 4)** on the joystick if one is connected.

Watch the `loco_client` logs for:
```
Starting balancing procedure...
Balancing procedure completed.
```
Wait for both lines before proceeding.

### Step 3 — Launch the animation node

In a second terminal (same env vars):
```bash
cd ~/g1_ws && colcon build --packages-select g1_animation
source ~/g1_ws/setup_robot_env.sh
ros2 launch g1_animation robot_deploy.launch.py \
  network_interface:=$G1_INTERFACE \
  mode:=walking \
  dry_run:=false \
  loop:=true \
  animation:=hands
```

### Step 4 — Shutdown

Press **Ctrl+C** on the animation node. It will ramp the arm weight from 1→0
over ~1 second before exiting, smoothly returning arm control to the loco
controller. Then shut down the loco stack.

---

## Debugging

# Check joint_states are publishing at ~50 Hz
ros2 topic hz /joint_states

# Inspect a message
ros2 topic echo /joint_states --once

# See all active topics
ros2 topic list

---

## Recording

Capture a single pose
python3 ~/g1_ws/scripts/read_pose.py enp46s0

---

Record a series of poses
python3 ~/g1_ws/scripts/record_poses.py enp46s0 --spacing 0.5 --name NEW_ANIMATION
```
A typical recording session looks like this:
```
[0 captured] > p               ← preview current positions
[0 captured] >                 ← Enter to capture as "pose_1"
[1 captured] > l arms raised   ← capture with label "arms raised"
[2 captured] > d               ← discard if you moved wrong
[2 captured] > l arms down     ← capture return pose
[3 captured] > q               ← finish and print output

The output is paste-ready into keyframes.py, and is also saved to /tmp/new_animation_recorded.py as a backup. The --spacing flag sets the time gap between each captured keyframe — use 0.5 for fast animations, 1.5 for slow deliberate ones. You can always hand-edit the timestamps after pasting.

## Parameters

| Parameter           | Default    | Description                                      |
|---------------------|------------|--------------------------------------------------|
| `network_interface` | `enp3s0`   | Ethernet interface to the robot                  |
| `mode`              | `damping`  | `damping` (static) or `walking` (loco active)    |
| `animation`         | `hands`    | Animation clip to play                           |
| `loop`              | `true`     | Loop the animation                               |
| `dry_run`           | `true`     | Print commands only, do not send to robot        |
