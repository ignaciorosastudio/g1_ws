# Running G1 Animations

## Environment setup

Two env configs are provided. Source the correct one for your use case:

```bash
# For anything involving the robot (live or dry-run with robot connected):
source ~/g1_ws/setup_robot_env.sh

# For local testing only (RViz, dry-run without robot):
source ~/g1_ws/setup_local_env.sh
```

Both set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, `ROS_DOMAIN_ID=0`, and the
appropriate `CYCLONEDDS_URI`. The robot env pins CycloneDDS to `enp46s0`
(robot ethernet); the local env auto-selects interfaces for intra-machine comms.

> **Both terminals must source the same env** for the CLI to discover the node.

---

## Launch options

A single launch file covers all use cases:

```bash
ros2 launch g1_animation robot_deploy.launch.py [args]
```

| Intent | Command |
|---|---|
| Preview in RViz (default) | `ros2 launch g1_animation robot_deploy.launch.py` |
| Preview, manual pose sliders | `ros2 launch g1_animation robot_deploy.launch.py use_gui:=true` |
| Preview, no RViz | `ros2 launch g1_animation robot_deploy.launch.py rviz:=false` |
| Deploy to robot (damping) | `ros2 launch g1_animation robot_deploy.launch.py dry_run:=false` |
| Deploy to robot (walking) | `ros2 launch g1_animation robot_deploy.launch.py dry_run:=false mode:=walking` |
| Deploy + loop animations | `ros2 launch g1_animation robot_deploy.launch.py dry_run:=false loop:=true` |
| Deploy via WiFi relay | `ros2 launch g1_animation robot_deploy.launch.py transport:=wifi dry_run:=false mode:=walking` |

RViz is always available — `robot_publisher` publishes `/joint_states` in both
dry-run and live mode, so you can monitor commanded positions at all times.

---

## Mode 1 — Damping (robot static)

The robot must be powered on in **Debug/Damping mode**. The animation node owns
all upper-body joints directly via `rt/lowcmd`.

### Step 1 — Launch the node

```bash
source ~/g1_ws/setup_robot_env.sh
ros2 launch g1_animation robot_deploy.launch.py \
  network_interface:=enp46s0 \
  mode:=damping \
  dry_run:=false \
  loop:=false
```

The node starts **idle** — it holds position and waits for a play command.

### Step 2 — Control via CLI

In a second terminal (same env sourced):

```bash
source ~/g1_ws/setup_robot_env.sh
ros2 run g1_animation animation_cli
```

```
Waiting for animation node...
Connected. Available clips: arms, cross, hands, neutral, reach, twist, typing, wave
Commands: <clip_name> | stop | list | speed <value> | quit

animation> wave          # play clip
animation> speed 0.5     # slow to half speed
animation> speed 1.0     # restore normal speed
animation> stop          # blend to neutral over 1.5s, then idle
animation> list          # re-discover available clips
animation> quit
```

### Step 3 — Shutdown

Press **Ctrl+C** on the animation node. The robot is left at the last
commanded position. Switch back to Sport mode before attempting locomotion.

---

## Mode 2 — Walking (animations while walking)

The robot is controlled by **g1pilot's locomotion stack**. The animation node
sends arm commands via `rt/arm_sdk`, blended on top of the loco controller
using a weight register (`motor_cmd[29].q = 1.0`).

**The waist joints (yaw, roll, pitch) are intentionally excluded** — they are
left to the loco controller for balance compensation during locomotion.

> **The robot must be in normal Sport mode, NOT Debug/Damping mode.**
> Debug mode disables the onboard sport service. Verify comms by checking that
> `loco_client` reports a real FSM ID (e.g. `1`) rather than `None`.

> **Only Regular walking mode (R1+X on the controller) supports `rt/arm_sdk`
> arm override. Running mode (R2+A) does not.**

---

### Step 1 — Start the locomotion stack

```bash
source ~/g1_ws/setup_robot_env.sh
ros2 launch g1pilot navigation_launcher.launch.py interface:=enp46s0
```

The node starts in **Damp** mode and prints FSM ID/Mode every second.
If you see `FSM ID: None, Mode: None` — DDS env vars are missing or the robot
is in Debug mode. Re-source the env and check the robot mode before continuing.

---

### Step 2 — Trigger balance stand

Balance stand is **not automatic**. In a separate terminal:

```bash
source ~/g1_ws/setup_robot_env.sh
ros2 topic pub --once /g1pilot/start_balancing std_msgs/msg/Bool "data: true"
```

Or press **R1** on the joystick. Wait for the loco_client log to show:

```
Starting balancing procedure...
Balancing procedure completed.
```

The robot should now be standing upright with the sport service active.

---

### Step 3 — Start walking (optional)

Use the joystick or loco_client RPC to begin walking before launching
animations. Animations can also be triggered while the robot stands still.

---

### Step 4 — Launch the animation node

```bash
source ~/g1_ws/setup_robot_env.sh
ros2 launch g1_animation robot_deploy.launch.py \
  network_interface:=enp46s0 \
  mode:=walking \
  dry_run:=false \
  loop:=false
```

The node starts **idle** and immediately takes arm control (`weight=1.0`).
The loco controller retains full control of the legs and waist.

---

### Step 5 — Control via CLI

In a separate terminal (same env):

```bash
source ~/g1_ws/setup_robot_env.sh
ros2 run g1_animation animation_cli
```

```
animation> wave       # right-arm wave while walking
animation> arms       # bilateral arm wave
animation> stop       # blend arms back to neutral
animation> speed 0.8  # slow clips slightly for smoother motion while walking
```

---

### Step 6 — Shutdown

Press **Ctrl+C** on the animation node. It ramps the arm weight from `1.0→0`
over ~1 second, smoothly returning arm control to the loco controller.
Then shut down the loco stack.

---

## Mode 3 — WiFi (animations over WiFi via Orin relay)

When the PC is connected to the robot over WiFi instead of Ethernet, DDS
cannot reach the MCU directly (addresses are embedded in DDS payloads and
NAT cannot rewrite them). A lightweight relay on the Orin bridges the gap:
the PC sends struct-packed motor commands over TCP, and the Orin forwards
them to the MCU via DDS on its internal eth0 network.

This mode works with both damping and walking, and is fully compatible with
the Unitree Explore app for locomotion.

### Orin relay installation (one-time setup)

The relay runs on the G1's Orin (Jetson) companion computer. It needs
Python 3.8+, `unitree_sdk2py`, and two relay scripts. The Orin runs
Ubuntu 20.04 aarch64 — all steps below run over SSH.

#### 1. SSH into the Orin

Over WiFi:

```bash
ssh unitree@192.168.0.123
```

Or over Ethernet:

```bash
ssh unitree@192.168.123.164
```

Default password is `123` (Unitree factory default).

#### 2. Check Python

```bash
python3 --version
```

Ubuntu 20.04 ships with Python 3.8. Anything 3.8+ works.

#### 3. Install pip (if missing)

```bash
python3 -m pip --version
```

If pip is not installed:

```bash
sudo apt update && sudo apt install -y python3-pip
```

#### 4. Install unitree_sdk2py

```bash
pip3 install unitree_sdk2py==1.0.1
```

This pulls in `cyclonedds` and `numpy` automatically. If the install
fails (e.g. no pre-built wheel for aarch64), use the fallback below.

**Fallback — copy from PC:**

On your PC, find where the packages are installed:

```bash
python3 -c "import unitree_sdk2py; print(unitree_sdk2py.__path__[0])"
python3 -c "import cyclonedds; print(cyclonedds.__path__[0])"
```

Then copy them to the Orin:

```bash
# From your PC
scp -r /usr/local/lib/python3.10/dist-packages/unitree_sdk2py unitree@192.168.0.123:~/
scp -r ~/.local/lib/python3.10/site-packages/cyclonedds unitree@192.168.0.123:~/
```

On the Orin, move them into the Python path:

```bash
sudo mv ~/unitree_sdk2py /usr/local/lib/python3.8/dist-packages/
sudo mv ~/cyclonedds /usr/local/lib/python3.8/dist-packages/
```

> Adjust the Python version in the path if the Orin has a different version.

#### 5. Verify the SDK

```bash
python3 -c "from unitree_sdk2py.core.channel import ChannelPublisher; print('OK')"
```

You should see `OK`. If you get an import error about `cyclonedds`,
install it separately: `pip3 install cyclonedds==0.10.2`.

#### 6. Copy the relay scripts

From your PC:

```bash
scp ~/g1_ws/src/g1_animation/g1_animation/wifi_relay_server.py unitree@192.168.0.123:~/
scp ~/g1_ws/src/g1_animation/g1_animation/wifi_relay_protocol.py unitree@192.168.0.123:~/
```

#### 7. Test-run the relay

```bash
python3 ~/wifi_relay_server.py --interface eth0
```

You should see:

```
[relay] INFO: DDS publishers ready on interface eth0
[relay] INFO: Waiting for robot state...
[relay] INFO: Robot state received
[relay] INFO: Listening on 0.0.0.0:9870
```

If the robot is off or not in the right mode, the "robot state" line will
show a warning instead — that's fine, the relay still works.

Press Ctrl+C to stop. The relay is now installed and ready.

> **Updating the relay:** After code changes, just re-run the two `scp`
> commands in step 6 and restart the relay.

---

### Step 1 — Start the relay on the Orin

SSH into the Orin and run the relay server:

```bash
ssh unitree@192.168.0.123
python3 ~/wifi_relay_server.py --interface eth0
```

The relay listens on TCP port 9870. It creates DDS publishers for both
`rt/lowcmd` and `rt/arm_sdk` and waits for a connection.

### Step 2 — Launch the animation node on the PC

```bash
source ~/g1_ws/setup_local_env.sh
ros2 launch g1_animation robot_deploy.launch.py \
  transport:=wifi \
  mode:=walking \
  dry_run:=false \
  loop:=false
```

The default relay address is `192.168.0.123:9870` (the Orin's WiFi IP).
Override with `relay_host:=<ip>` and `relay_port:=<port>` if needed.

> Use `setup_local_env.sh` (not `setup_robot_env.sh`) since the PC is not
> on the robot's ethernet network.

### Step 3 — Control via CLI

Same as any other mode:

```bash
source ~/g1_ws/setup_local_env.sh
ros2 run g1_animation animation_cli
```

### Step 4 — Shutdown

Press **Ctrl+C** on the PC node. If in walking mode, the PC sends a stop
message and the Orin performs the arm weight ramp-down locally (this must
happen at DDS speed, not over WiFi). Then Ctrl+C the relay on the Orin.

---

## Dry-run (no robot required)

Test the full command pipeline against RViz without touching the robot.
Use the **local env** for all terminals:

```bash
# Terminal 1 — publisher + RViz (all-in-one)
source ~/g1_ws/setup_local_env.sh
ros2 launch g1_animation robot_deploy.launch.py

# Terminal 2 — CLI
source ~/g1_ws/setup_local_env.sh
ros2 run g1_animation animation_cli
```

---

## Debugging

```bash
# Verify both nodes are visible
ros2 node list

# Check services are registered
ros2 service list | grep animation

# Check joint_states rate (~200 Hz in dry-run)
ros2 topic hz /joint_states

# Inspect commanded positions and velocities
ros2 topic echo /joint_states --field position
ros2 topic echo /joint_states --field velocity
```

---

## Recording New Clips

Two recording scripts are available. Both require the robot in **Debug/Damping mode**
and the robot env sourced.

### Pose-by-pose (keyframe recorder)

Move the robot to each pose by hand and press Enter to capture it.

```bash
source ~/g1_ws/setup_robot_env.sh
python3 ~/g1_ws/scripts/record_poses.py enp46s0
python3 ~/g1_ws/scripts/record_poses.py enp46s0 --spacing 0.5 --name my_clip
```

| Key | Action |
|---|---|
| Enter | Capture current pose |
| `l <label>` | Capture with a custom label |
| `d` | Discard last captured pose |
| `p` | Preview current joint positions |
| `q` / `done` | Finish and write output |

`--spacing` sets the time gap (seconds) between keyframes in the output. Use `0.5` for
fast animations, `1.5` for slow deliberate ones. Timestamps can always be hand-edited
afterwards.

Output is written to `~/g1_ws/clips/<name>.json` (ready to use without a rebuild).

---

### Continuous (motion-capture recorder)

Move the robot through the full motion while the script samples at a fixed rate.

```bash
source ~/g1_ws/setup_robot_env.sh
python3 ~/g1_ws/scripts/record_continuous.py enp46s0
python3 ~/g1_ws/scripts/record_continuous.py enp46s0 --interval 0.05 --name wave --interp catmull_rom
```

| Flag | Default | Description |
|---|---|---|
| `--interval` | `0.1` | Seconds between samples (0.1 → 10 fps, 0.05 → 20 fps) |
| `--name` | `my_animation` | Output filename (becomes `<name>.json`) |
| `--interp` | `linear` | Interpolation mode (`linear`, `smoothstep`, `catmull_rom`) |

Press **Enter** to start recording, **Enter** again (or **Ctrl-C**) to stop.
Output is written directly to `~/g1_ws/clips/<name>.json`.

Use `catmull_rom` for continuous motion recordings — it produces the smoothest
playback when samples are dense.

---

## Clips

Clips are loaded from `~/g1_ws/clips/*.json` at startup. Each file defines
keyframes and an interpolation mode:

```json
{
  "interp": "catmull_rom",
  "keyframes": [
    {"time": 0.0, "positions": [...]},
    {"time": 2.0, "positions": [...]}
  ]
}
```

| `interp` value | Behaviour |
|---|---|
| `linear` | Plain lerp — good for mechanical/repetitive motion |
| `smoothstep` | Ease-in/out within each segment |
| `catmull_rom` | Smooth spline through keyframes — best for organic motion |

To add a clip: drop a `.json` file into `~/g1_ws/clips/` and restart the node.
No rebuild required.

---

## Parameters

| Parameter           | Default          | Description                                       |
|---------------------|------------------|---------------------------------------------------|
| `network_interface` | `enp3s0`         | Ethernet interface to the robot                   |
| `mode`              | `damping`        | `damping` (static, rt/lowcmd) or `walking` (rt/arm_sdk) |
| `loop`              | `false`          | Loop clips when playing                           |
| `dry_run`           | `true`           | Publish /joint_states only, do not send to robot  |
| `speed`             | `1.0`            | Playback speed multiplier (settable via CLI)      |
| `transport`         | `local`          | `local` (direct DDS) or `wifi` (TCP relay via Orin) |
| `relay_host`        | `192.168.0.123`  | Orin WiFi IP (only used when transport:=wifi)     |
| `relay_port`        | `9870`           | Relay TCP port (only used when transport:=wifi)   |
