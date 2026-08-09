# Reachy Mini Wi‑Fi Owner’s Manual

**Model:** Reachy Mini (Wireless / Wi‑Fi edition)  
**Prepared from:** Pollen Robotics and Hugging Face documentation  
**Reviewed:** 2026-08-09  
**Status:** Community-prepared operating manual; use the official documentation and hardware instructions when they conflict with this document.

> **Scope:** This manual covers the autonomous Reachy Mini Wireless, powered by its Raspberry Pi Compute Module 4 and internal battery. It does not describe the Reachy Mini Lite except where a comparison prevents confusion.

> **Important:** Reachy Mini is a moving electromechanical device with exposed gears, linkages, cables, batteries, and powered electronics. Keep fingers, hair, clothing, tools, and loose objects away from moving parts. Supervise children and pets. Stop the robot before inspecting, adjusting, or repairing it.

---

## Contents

1. [Quick start](#1-quick-start)
2. [Safety and operating rules](#2-safety-and-operating-rules)
3. [What you own](#3-what-you-own)
4. [Hardware reference](#4-hardware-reference)
5. [Assembly and first inspection](#5-assembly-and-first-inspection)
6. [Power, battery, and shutdown](#6-power-battery-and-shutdown)
7. [Wi‑Fi and network operation](#7-wi-fi-and-network-operation)
8. [Reachy Mini Control](#8-reachy-mini-control)
9. [Apps](#9-apps)
10. [Python SDK](#10-python-sdk)
11. [Motion and control reference](#11-motion-and-control-reference)
12. [Camera, microphones, speaker, and IMU](#12-camera-microphones-speaker-and-imu)
13. [Maintenance](#13-maintenance)
14. [Troubleshooting](#14-troubleshooting)
15. [Expert mode](#15-expert-mode)
16. [Reference tables and commands](#16-reference-tables-and-commands)
17. [Official sources](#17-official-sources)

---

## 1. Quick start

### 1.1 Assemble the robot

1. Unpack every box and inspect the parts.
2. Follow the printed assembly booklet together with the [interactive digital assembly guide](https://huggingface.co/spaces/pollen-robotics/Reachy_Mini_Assembly_Guide).
3. Use the [full assembly video](https://www.youtube.com/watch?v=WeKKdnuXca4) when cable routing or motor-arm alignment is unclear.
4. Expect about 2–3 hours for assembly. Depending on experience, the process can take 1.5–4 hours.
5. Spare screws and cables may remain after assembly. This is normal.
6. Before powering on, check that:
   - every motor cable is fully seated;
   - no cable is pinched or stretched;
   - the head can move through its range without pulling the internal USB cable;
   - the head-board boot switch is in **DEBUG**, not **DOWNLOAD**;
   - the supplied 7 V / 5 A power supply is connected.

### 1.2 Connect to Wi‑Fi

1. Power on Reachy Mini.
2. Install **Reachy Mini Control** from the [official download page](https://hf.co/reachy-mini/#/download).
3. Open the app.
4. Select **First time connecting…** or **First time WiFi setup**.
5. Follow the wizard. It will ask you to join the robot’s temporary Wi‑Fi access point, then select and configure your normal Wi‑Fi network.
6. Connect your computer to the same normal network as the robot.
7. Use Reachy Mini Control to connect.

The factory access point is normally:

| Item | Value |
|---|---|
| SSID | `reachy-mini-ap` |
| Password | `reachy-mini` |
| Host name after normal Wi‑Fi setup | `reachy-mini.local` |
| Daemon port | `8000` |
| SSH user | `pollen` |
| Factory SSH password | `root` |

Treat the factory SSH password as a setup credential. Change or protect access to the robot if you place it on a shared or untrusted network.

### 1.3 Update before use

1. Connect in Reachy Mini Control.
2. Open **Settings**.
3. Open **System Updates**.
4. Install the available update.
5. Restart the robot and your computer after the update.
6. For a Wireless robot, verify the image with:

```bash
ssh pollen@reachy-mini.local
reachyminios_check
```

### 1.4 Run a first motion

Install the SDK on your computer, activate its virtual environment, and run this test only after the robot is stable on a clear surface:

```python
from reachy_mini import ReachyMini

with ReachyMini() as mini:
    print("Connected to Reachy Mini")
    mini.goto_target(antennas=[0.5, -0.5], duration=0.5)
    mini.goto_target(antennas=[-0.5, 0.5], duration=0.5)
    mini.goto_target(antennas=[0, 0], duration=0.5)
```

Save it as `hello.py` and run:

```bash
python hello.py
```

If the robot does not respond, stop testing and use [Troubleshooting](#14-troubleshooting).

### 1.5 Normal shutdown

1. Stop the active app or Python program.
2. Wait for motion and audio to stop.
3. Press **OFF**.
4. Wait at least five seconds before pressing **ON** again.

Do not unplug power while motors are moving or while the system is writing an update.

---

## 2. Safety and operating rules

### 2.1 Before every session

- Put the robot on a stable, level surface.
- Keep the head and antennas clear of walls, cups, cables, and hands.
- Keep the power cable away from moving joints.
- Confirm that no motor LED is blinking red.
- Confirm that the robot is not in an unknown or partially powered state.
- Keep a clear path for the full head and body motion.
- Test new code at low speed and with short motions.

### 2.2 During motion

- Do not hold a powered joint by force.
- Do not block the Stewart-platform rods or antenna arms.
- Do not add a load to the head, antennas, or body.
- Stop the app if the robot squeaks, shakes violently, stalls, heats excessively, or moves unpredictably.
- If a motor reports an overload or electrical-shock error, turn the robot off before touching cables.

### 2.3 Power and battery

The Wireless model uses a LiFePO4 battery with a battery-management system. The published battery specification is **6.4 V, 2,000 mAh, 12.8 Wh**. The power board provides protection against overcharge, over-discharge, over-current, short circuit, and excessive temperature.

The documented input range is **6.8–7.6 V**. The troubleshooting guide specifies a **7 V / 5 A** supply for operation. Use the supplied or manufacturer-approved supply. The internal USB-C port is an output/data port and **does not charge the robot**.

The software does not expose an exact battery percentage. The LED indicates low-battery state by changing approximately from green to orange to red.

### 2.4 Servicing rules

Before opening the robot, removing a cable, changing a motor, or removing the battery:

1. Stop all applications.
2. Press **OFF**.
3. Disconnect external power.
4. Confirm that the green power LED is off.
5. Wait for capacitors and motors to de-energize.

Never work on the robot while it is powered. Do not short battery contacts. Do not puncture, crush, heat, or modify the battery pack.

### 2.5 Motion limits

The SDK and daemon clamp out-of-range commands to safe poses. Do not rely on clamping as a substitute for collision checking.

The published documentation contains a body-yaw discrepancy: one page lists ±180°, while the Core Concepts page lists ±160°. Use the more conservative **±160°** in application design until your installed software reports otherwise. The other documented limits are:

| Axis | Conservative application limit |
|---|---:|
| Head pitch | −40° to +40° |
| Head roll | −40° to +40° |
| Head yaw | −180° to +180° |
| Body yaw | −160° to +160° |
| Head/body yaw difference | no more than 65° |

---

## 3. What you own

The Wireless edition is a self-contained robot. The Raspberry Pi runs the daemon and can run installed apps without a laptop. A laptop or desktop is still useful for setup, updates, development, and remote control.

### 3.1 Wireless versus Lite

| Feature | Reachy Mini Wireless | Reachy Mini Lite |
|---|---|---|
| Controller | Raspberry Pi CM4 inside robot | External computer over USB |
| Normal control path | Wi‑Fi or Ethernet adapter | USB |
| Battery | Internal LiFePO4 battery | Model-dependent external power arrangement |
| Daemon | Starts on the robot at boot | Runs on the connected computer |
| SSH | Available on robot | Not the normal control path |
| IMU | Available | Not available according to SDK docs |
| USB-C | Does not provide a normal laptop robot link or charging | Different model behavior |

Do not expect a USB-C cable from a Wireless robot to behave like the Lite’s USB connection.

### 3.2 Software layers

```text
Your Python app / Reachy Mini Control / web app
                    │
              SDK or REST API
                    │
        Reachy Mini daemon on CM4
                    │
 motors · camera · microphone array · speaker · IMU
```

The daemon owns the hardware and safety checks. Your application sends targets and reads state. Only one managed Reachy Mini app can control the robot at a time.

---

## 4. Hardware reference

### 4.1 Physical specifications

| Item | Specification |
|---|---|
| Dimensions | 30 × 20 × 15.5 cm, extended |
| Mass | 1.475 kg |
| Materials | ABS, polycarbonate, aluminium, steel |
| Head degrees of freedom | 6: 3 rotations and 3 translations |
| Body | 1 rotation |
| Antennas | 1 rotation each |
| Input voltage | 6.8–7.6 V |
| Camera | 120° wide angle, 12 MP, autofocus |
| Audio | Four-microphone array and speaker |
| Controller | Raspberry Pi Compute Module 4, Wireless version |

### 4.2 Actuators

| Location | Motor |
|---|---|
| Body/base | 1 × custom Dynamixel XC330-M288-PG |
| Antennas | 2 × Dynamixel XL330-M077-T |
| Stewart platform | 6 × Dynamixel XL330-M288-T |

The motor scan should normally find the expected motor chain at **1,000,000 baud**. The troubleshooting documentation lists IDs 10–18, but one example includes ID 16 while another list omits it. Verify the expected set against your installed hardware configuration and Testbench app rather than assuming a missing ID is always a fault.

### 4.3 Camera

- Raspberry Pi Camera Module 3 wide-angle variant.
- Sony IMX708 sensor.
- 12 MP.
- Autofocus.
- CSI connection to the CM4.

### 4.4 Audio

- Four PDM MEMS microphones.
- Seeed Studio reSpeaker XMOS XVF3800 audio processor.
- 16 kHz maximum microphone sample rate in the hardware datasheet.
- Acoustic echo cancellation is enabled by default.
- 5 W speaker at 4 Ω.

### 4.5 Controller and connectivity

The CM4 includes:

- Wi‑Fi dual-band 2.4/5 GHz.
- 4 GB RAM.
- 16 GB flash.
- USB-C output/data connection.
- TTL Dynamixel connection.
- CSI camera connection.
- Microphone-array connection.

### 4.6 Battery

- LiFePO4 chemistry.
- 6.4 V nominal.
- 2,000 mAh.
- 12.8 Wh.
- Integrated protective battery-management features.
- Exact charge percentage is not available through the current software interface.

---

## 5. Assembly and first inspection

### 5.1 Assembly priorities

Cable routing and motor-arm orientation cause many first-start failures. During assembly:

- Follow the cable lengths and motor positions in the assembly guide.
- Leave enough USB cable slack inside the head for the maximum head height.
- Do not force an FPC connector.
- Keep FPC contacts oriented as shown in the assembly guide.
- Align the marks on a motor horn and arm when the guide specifies alignment.
- Tighten fasteners securely without crushing plastic or binding a joint.

### 5.2 First inspection checklist

With the robot off:

- Check the central motor connection first.
- Check every 3-wire motor cable.
- Check the black/red power cable.
- Check the microphone FPC cable orientation.
- Check the head-board switch: **DEBUG** for normal boot.
- Move the head gently by hand only when motors are unpowered.
- Check that the rods and spherical joints move freely.

With the robot on:

- Confirm that the Wi‑Fi access point or normal network connection appears.
- Confirm that no motor blinks red.
- Confirm that all motors are detected.
- Test antennas before testing a large head motion.
- Run `reachyminios_check` after software installation or recovery.

### 5.3 Microphone FPC orientation

Silence or all-zero audio often means the microphone cable is upside down.

- For a white-and-blue cable, verify the blue side orientation in the assembly guide.
- For a black cable, the side marked **Main Board** should face up as shown in the troubleshooting guide.
- If orientation is correct and audio still fails, inspect or replace the cable.

---

## 6. Power, battery, and shutdown

### 6.1 Starting

1. Place the robot on a clear surface.
2. Connect the approved power supply if available.
3. Press **ON**.
4. Wait for the system and daemon to finish starting.
5. Connect Reachy Mini Control or wait for the normal Wi‑Fi link.

The daemon normally starts automatically on the Wireless robot. You do not normally start it manually.

### 6.2 Restarting

For a normal restart:

1. Stop the running app or script.
2. Press **OFF**.
3. Wait five seconds.
4. Press **ON**.

This restart procedure is the first fix recommended by the official troubleshooting guide.

### 6.3 Emergency stop behavior

If the robot moves unexpectedly:

1. Press **OFF** immediately.
2. Disconnect power after motion stops.
3. Do not restart until you identify the cause.
4. Check app ownership, motor errors, cables, and the last command sent.

### 6.4 Motor modes

| SDK operation | Behavior | Use |
|---|---|---|
| `enable_motors()` | Stiff; holds position | Normal powered operation |
| `disable_motors()` | Limp; no holding torque | Safe manual repositioning when stopped |
| `make_motors_compliant()` or gravity compensation | Powered but soft | Teaching by demonstration; supported kinematics only |

Use compliant mode only while holding the robot securely and keeping the motion slow.

---

## 7. Wi‑Fi and network operation

### 7.1 Recommended network

Use a private network where the computer and robot can communicate directly. Avoid guest, hotel, and conference networks with client isolation.

A phone hotspot is a useful diagnostic network: connect both the robot and computer to the hotspot.

For installations that need a wired link, a USB-C-to-Ethernet adapter and Ethernet cable can replace Wi‑Fi. The USB-C port itself is not a normal laptop control link.

### 7.2 Find the robot

Try these in order:

1. Reachy Mini Control discovery.
2. `reachy-mini.local` through mDNS.
3. The router’s DHCP client list.
4. The robot’s IP address from the control app.
5. A subnet scan, adjusted to your LAN prefix:

```bash
for i in $(seq 1 254); do
  curl -sf --connect-timeout 0.3 \
    "http://192.168.1.${i}:8000/api/daemon/status" \
    >/dev/null 2>&1 && echo "Found: 192.168.1.${i}"
done
```

Use the scan only on a network you own or administer.

### 7.3 Check the daemon

Open the API documentation:

```text
http://reachy-mini.local:8000/docs
```

The daemon status endpoint is:

```text
http://reachy-mini.local:8000/api/daemon/status
```

A successful HTTP response confirms network reachability. It does not prove that every motor or sensor is healthy.

### 7.4 SSH

```bash
ssh pollen@reachy-mini.local
# password: root
```

If mDNS fails, replace `reachy-mini.local` with the robot’s IP address.

Useful first checks:

```bash
reachyminios_check
systemctl status reachy-mini-daemon
journalctl -u reachy-mini-daemon -n 100 --no-pager
```

### 7.5 VPN and local discovery

If you put the robot behind a VPN, preserve local access. The troubleshooting guide recommends excluding the local LAN from VPN routing and allowing these local ports:

| Port | Use |
|---:|---|
| 22 | SSH |
| 8000 | Reachy Mini daemon |
| 5353 TCP/UDP | mDNS and local discovery |

Restart the daemon after changing VPN routing:

```bash
sudo systemctl restart reachy-mini-daemon
```

---

## 8. Reachy Mini Control

Reachy Mini Control is the normal desktop interface for setup and daily use.

### 8.1 Main functions

- Discover and connect to the robot.
- View robot status.
- Control the head and antennas.
- Play built-in expressions.
- Configure Wi‑Fi.
- Install, start, and stop apps.
- Install system updates.
- Open environment and diagnostic settings.

### 8.2 App ownership

When an app is running, it controls the robot. Stop the app before running a separate Python script. Only one managed app can run at a time.

### 8.3 Environment recovery

The control app provides environment reset options mainly for Lite and Simulation local environments:

- **Reset apps environment:** Recreates `apps_venv`. Reinstall apps afterward.
- **Full Environment Reset:** Deletes and re-downloads the Python interpreter and both virtual environments.

Use the smaller reset first. Do not delete the Wireless robot’s environments unless you are following a documented recovery procedure.

---

## 9. Apps

Reachy Mini apps are Python behaviors packaged for the Hugging Face Spaces ecosystem.

### 9.1 Install and run an app

1. Open the Applications tab in Reachy Mini Control.
2. Select **Discover Apps**.
3. Choose a compatible app.
4. Select **Install**.
5. Select **Start**.
6. Select **Stop** before starting another app or script.

### 9.2 Wireless app location

Installed Wireless apps use the shared environment:

```text
/venvs/apps_venv/
```

### 9.3 Diagnose an app that exits

Test imports directly in the Wireless environment:

```bash
ssh pollen@reachy-mini.local
/venvs/apps_venv/bin/python3 -c \
  'from my_app.main import MyApp'
```

If the import fails, install the missing dependency in the app environment or correct the app package. Also inspect daemon logs:

```bash
journalctl -u reachy-mini-daemon -f
```

### 9.4 Build an app

Use the assistant CLI. Do not hand-build the package layout unless you understand Python entry points and Hugging Face Space metadata.

```bash
uv pip install reachy-mini
reachy-mini-app-assistant create my_app_name /path/to/destination
```

To publish during creation:

```bash
reachy-mini-app-assistant create my_app_name /path/to/destination --publish
```

Validate the generated app:

```bash
reachy-mini-app-assistant check /path/to/my_app
```

A minimal app must extend `ReachyMiniApp`, implement `run()`, poll `stop_event`, and call `wrapped_run()` from its `__main__` block. The generated project is the safest starting point.

### 9.5 App lifecycle

The daemon:

1. Starts the app as a Python subprocess.
2. Supplies a connected `ReachyMini` instance and stop event.
3. Sends `SIGINT` when the app stops.
4. Returns the robot to its default position after exit.

Design every app to stop cleanly. Release audio and other resources in `finally` blocks.

### 9.6 Offline app deployment

For a Wireless robot with no internet access:

```bash
scp -r /path/to/my_app pollen@reachy-mini.local:/tmp/my_app
ssh pollen@reachy-mini.local \
  "/venvs/apps_venv/bin/pip install /tmp/my_app"
```

Restart the app after code changes.

---

## 10. Python SDK

### 10.1 Supported development platforms

The current installation guide supports Linux, macOS, and Windows. It documents Python **3.10–3.12** and recommends Python 3.12.

### 10.2 Install the SDK

Install `uv`, Python 3.12, Git, and Git LFS according to your operating system. On Linux, initialize Git LFS:

```bash
git lfs install
```

Create and activate an isolated environment:

```bash
uv venv reachy_mini_env --python 3.12
source reachy_mini_env/bin/activate
```

On Windows, activate the equivalent `Scripts\\activate` environment.

Install the SDK:

```bash
uv pip install reachy-mini
```

For simulation:

```bash
uv pip install "reachy-mini[mujoco]"
```

The Wireless robot already includes its daemon. Install the SDK on your computer for remote control, or run it in the robot’s app environment for local execution.

### 10.3 Wireless local execution

```bash
ssh pollen@reachy-mini.local
source /venvs/apps_venv/bin/activate
python
```

Then use the normal constructor:

```python
from reachy_mini import ReachyMini

with ReachyMini() as mini:
    print(mini.state)
```

Local execution reduces network latency but has less CPU power and no normal graphical desktop.

### 10.4 Connection modes

The SDK normally detects local versus network operation:

```python
from reachy_mini import ReachyMini

with ReachyMini() as mini:
    pass
```

Force a mode only when needed:

```python
ReachyMini(connection_mode="localhost_only")
ReachyMini(connection_mode="network")
```

### 10.5 Simulation

Start the daemon without hardware:

```bash
# Linux and Windows
reachy-mini-daemon --sim

# macOS
mjpython -m reachy_mini.daemon.app.main --sim
```

Open `http://localhost:8000/docs` to verify the daemon. Use `media_backend="no_media"` when testing control logic without camera or audio.

---

## 11. Motion and control reference

### 11.1 Targets

`goto_target()` interpolates smoothly over time. Use it for gestures and normal actions.

```python
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
import numpy as np

with ReachyMini() as mini:
    mini.goto_target(
        head=create_head_pose(z=10, mm=True),
        antennas=np.deg2rad([45, 45]),
        body_yaw=np.deg2rad(30),
        duration=2.0,
        method="minjerk",
    )
```

Supported interpolation methods documented by the SDK include:

- `linear`
- `minjerk`
- `ease_in_out`
- `cartoon`

`set_target()` applies a target immediately. Use it for high-frequency control, such as teleoperation or generated trajectories.

### 11.2 Angles and units

- SDK antenna and body values use radians in the examples.
- `create_head_pose()` can accept degrees when `degrees=True`.
- Use `mm=True` when specifying head translation in millimetres.
- Use explicit conversions instead of relying on memory.

### 11.3 Coordinate frames

- **Head frame:** Located at the base of the head. Use it for head poses.
- **World frame:** Fixed to the robot base. Use it for `look_at_world()`.

### 11.4 Look-at control

```python
mini.look_at_image(x, y)       # image coordinates; (0, 0) is top-left
mini.look_at_world(x, y, z)    # coordinates in the robot/world frame
```

### 11.5 Tracking

```python
with ReachyMini() as mini:
    mini.start_head_tracking()
    face = mini.get_tracked_face()
    mini.stop_head_tracking()
```

The tracked face result includes detection state, normalized coordinates, and roll. Good lighting improves tracking. Set a tracking weight when blending tracking with application motion; `1.0` gives tracking full control and `0.0` pauses its influence.

### 11.6 Recording and replay

```python
with ReachyMini() as mini:
    mini.start_recording()
    # Move the robot or send targets.
    recorded_data = mini.stop_recording()
```

Use the SDK’s `RecordedMoves` support or the [Reachy Mini dances library](https://github.com/pollen-robotics/reachy_mini_dances_library) for replayable moves.

### 11.7 Control-loop health

A healthy motor loop is approximately **50 Hz**, or a period near **20 ms**. Check status through the SDK or:

```bash
curl http://reachy-mini.local:8000/api/daemon/status
```

Heavy CPU load and, for Lite, USB latency can slow the loop. On Wireless, high latency can also affect remote commands, but the motor loop remains on the robot.

---

## 12. Camera, microphones, speaker, and IMU

### 12.1 Media ownership

The daemon owns the physical camera and audio hardware.

- `LOCAL`: same machine as daemon; local IPC video and local GStreamer audio.
- `WEBRTC`: remote client; camera and audio stream over WebRTC.
- `NO_MEDIA`: daemon releases camera and audio for direct access by another library.
- `default`: selects the suitable backend automatically.

### 12.2 Camera from Python

```python
from reachy_mini import ReachyMini

with ReachyMini(media_backend="default") as mini:
    frame = mini.media.get_frame()
    # NumPy array: (height, width, 3), uint8, BGR order
```

### 12.3 Camera diagnostics over SSH

```bash
rpicam-hello --list
rpicam-still -t 1 -r -o test.jpg --width 4608 --height 2592
scp pollen@reachy-mini.local:/home/pollen/test.jpg .
```

To test autofocus manually:

```bash
rpicam-still -t 1 -r -o near.jpg \
  --width 4608 --height 2592 \
  --autofocus-mode manual --lens-position 0

rpicam-still -t 1 -r -o far.jpg \
  --width 4608 --height 2592 \
  --autofocus-mode manual --lens-position 1000
```

The daemon uses GStreamer `libcamerasrc`. Inspect its available properties with:

```bash
gst-inspect-1.0 libcamerasrc
```

If the camera cannot focus, check for a blocked lens. The troubleshooting guide says the camera is held by four screws; loosen them only very slightly, about one-eighth of a turn, if the physical mount is obstructing focus.

### 12.4 Audio from Python

```python
from reachy_mini import ReachyMini
import time

with ReachyMini(media_backend="default") as mini:
    mini.media.start_recording()
    mini.media.start_playing()

    sample = mini.media.get_audio_sample()
    mini.media.push_audio_sample(sample)
    time.sleep(len(sample) / mini.media.get_output_audio_samplerate())

    doa, speech = mini.media.get_DoA()
    print("DoA:", doa, "speech:", speech)

    mini.media.stop_recording()
    mini.media.stop_playing()
```

Documented audio details:

- Input is a NumPy `float32` array shaped `(samples, 2)`.
- Output accepts `(samples, 1)` or `(samples, 2)` as `float32`.
- Use the SDK methods to read the actual sample rates and channel counts.
- `push_audio_sample()` is non-blocking. Wait for playback when timing matters.

### 12.5 Direction of arrival

The microphone array can estimate sound direction. The SDK documentation defines 0 radians as left, π/2 as front/back, and π as right. The array’s physical layout places mic 0 near the robot’s right antenna and mic 3 near its left antenna.

### 12.6 Direct camera/audio access

Release daemon media before opening the devices directly:

```python
from reachy_mini import ReachyMini
import cv2

with ReachyMini(media_backend="no_media") as mini:
    cap = cv2.VideoCapture(0)
    ok, frame = cap.read()
    cap.release()
    mini.goto_target(antennas=[0.3, -0.3], duration=0.5)
```

Alternatively:

```python
mini.release_media()
# Use OpenCV, sounddevice, or another direct-access library.
mini.acquire_media()
```

The context manager reacquires media when it exits. Do not let two programs open the camera or audio device at the same time.

### 12.7 Advanced audio controls

On the robot, the audio card appears as `Pollen Robotics Reachy Mini Audio`. Use `alsamixer` to inspect it. The official guidance recommends leaving controls at 100% except PCM output, which you can adjust.

Read a parameter:

```bash
python src/reachy_mini/media/audio_control_utils.py PP_MIN_NS
```

Write a parameter only when you understand the XVF3800 control:

```bash
python src/reachy_mini/media/audio_control_utils.py PP_MIN_NS --values 0
```

Remote Wireless access is available through the daemon API:

```bash
curl http://reachy-mini.local:8000/api/audio/config/parameter/AUDIO_MGR_MIC_GAIN

curl -X POST http://reachy-mini.local:8000/api/audio/config/apply \
  -H 'Content-Type: application/json' \
  -d '{"config": [{"name": "AUDIO_MGR_MIC_GAIN", "values": [1.0]}], "verify": true}'
```

### 12.8 GStreamer audio tests

Run these on the machine that owns the audio board. For Wireless, that is the robot. Stop other audio users first.

```bash
# Record
 gst-launch-1.0 -e alsasrc device="reachymini_audio_src" ! \
   audioconvert ! audioresample ! wavenc ! filesink location=test.wav

# Play the recording
 gst-launch-1.0 filesrc location=test.wav ! wavparse ! \
   audioconvert ! alsasink device=reachymini_audio_sink

# Play a test tone
 gst-launch-1.0 audiotestsrc wave="pink-noise" ! audioconvert ! \
   audioresample ! alsasink device=reachymini_audio_sink
```

If Linux playback is too quiet, inspect `alsamixer`, set `PCM1` to 100%, and adjust `PCM` for the desired output level.

### 12.9 IMU

The IMU is available on Wireless models:

```python
with ReachyMini() as mini:
    imu = mini.imu
    accel_x, accel_y, accel_z = imu["accelerometer"]
    gyro_x, gyro_y, gyro_z = imu["gyroscope"]
    quat_w, quat_x, quat_y, quat_z = imu["quaternion"]
    temperature = imu["temperature"]
```

---

## 13. Maintenance

### 13.1 Routine care

- Keep camera glass and microphone openings clean and dry.
- Keep ventilation openings clear.
- Inspect cables for cuts, crushed insulation, and loose connectors.
- Check that the head moves without squeaking or binding.
- Remove dust from around spherical joints.
- Store the robot powered off in a dry, moderate environment.
- Do not use solvents on plastic or electronics.

### 13.2 Spherical-joint maintenance

Dark dust around the rods or high-pitched squeaking indicates that the ball joints may need cleaning and grease.

Tools listed by the official guide:

- PH1 screwdriver and cross socket.
- Degreaser, such as WD-40.
- Grease, such as NSK LR3.
- Soft cloth.
- Small plastic tool for applying grease.

Procedure:

1. Power off, unplug, and remove the top shell using the assembly guide in reverse.
2. Work on one rod at a time.
3. Remove the nut and screw at the motor-arm end.
4. Remove the screw at the neck end.
5. Clean all dirt from the spherical joint with degreaser and a soft cloth.
6. Apply grease over the complete sphere surface.
7. Rotate the sphere repeatedly to distribute grease.
8. Remove excess grease.
9. Reassemble the rod.
10. Repeat for each rod, then replace the shell, head, and antennas.

Do not mix rods or force a joint. If a joint is damaged, contact support.

### 13.3 Battery removal

Battery removal is a service operation. Follow the official troubleshooting guide and disconnect all power first.

The documented outline is:

1. Confirm the green LED is off.
2. Remove the three bottom screws.
3. Pull the foot out slightly.
4. Unplug the battery connector.
5. Lift the battery carefully; adhesive may resist removal.
6. Reassemble in reverse order without pinching cables.

Do not perform this operation unless you are comfortable working on battery-powered electronics.

### 13.4 Microphone FPC replacement

Replacement cable specifications:

- FFC/FPC flat-flex cable.
- 12 pins.
- 0.5 mm pitch.
- Type A, contacts on the same side.
- Approximately 150 mm length.

Procedure summary:

1. Power off and unplug the robot.
2. Open the head using the assembly guide.
3. Disconnect the cable from the head board.
4. Peel the rubber isolation case gently from both sides.
5. Remove the black tape and disconnect the cable from the microphone board.
6. Install the replacement cable in the same orientation.
7. Refit the isolation case and reconnect the head board.
8. Reassemble the head and test audio.

---

## 14. Troubleshooting

### 14.1 First response for almost any fault

1. Stop the app.
2. Update Reachy Mini Control, the robot, or the SDK.
3. Press **OFF**.
4. Wait five seconds.
5. Press **ON**.
6. Restart the computer.
7. Run `reachyminios_check` on Wireless.

### 14.2 Symptom-to-action table

| Symptom | First checks |
|---|---|
| Robot does not move at first startup | Confirm 7 V / 5 A supply, power cables, motor cables, and daemon connection |
| Temporary Wi‑Fi AP does not appear | Confirm head-board switch is **DEBUG**, not **DOWNLOAD**; reflash only if needed |
| `reachy-mini.local` fails | Use Control discovery, router DHCP list, IP address, hotspot, or subnet scan |
| Computer and robot both have Wi‑Fi but cannot communicate | Client isolation; use a phone hotspot or wired Ethernet adapter |
| Wireless robot does not work over laptop USB-C | Expected; use Wi‑Fi, SSH, or USB-C Ethernet adapter |
| Microphone is silent or returns zeros | Check FPC orientation, connector seating, and cable damage |
| Speaker volume is low on Linux | Use `alsamixer`; set PCM1 to 100% and adjust PCM |
| Camera is dark on Lite | Adjust exposure with a camera tool; this is mainly a Lite issue |
| Camera cannot focus | Check lens obstruction and camera mount; inspect autofocus with `rpicam-still` |
| Antenna shakes near vertical | Offset the target by about 10°; avoid unstable exact vertical position |
| Head squeaks | Clean and regrease spherical joints |
| Motor blinks red | Power off; inspect cables, overload, motor order, and motor configuration |
| Motor reports electrical shock | Inspect power and motor cables for damage or shorts; stop using the robot |
| App silently exits | Test imports in `apps_venv`, inspect daemon logs, and check dependencies |
| App install fails on Windows | Check symlink permissions and try `HF_HUB_DISABLE_SYMLINKS_WARNING=1` |
| Motion looks shaky | Check daemon status for a control-loop period near 20 ms; reduce CPU load |
| Simulation reports circular buffer overrun | Use `ReachyMini(media_backend="no_media")` if video is not needed |

### 14.3 Wireless AP missing

1. Power off.
2. Inspect the head-board switch.
3. Set it to **DEBUG** for normal boot.
4. Disconnect any flashing cable.
5. Power on again.
6. If the AP still does not appear, run `reachyminios_check` if SSH is possible.
7. Reflash the OS only after ordinary checks fail.

### 14.4 Wi‑Fi reset through Bluetooth

Use the official Reachy Mini Control Bluetooth console first. If unavailable, use a Bluetooth-capable browser or nRF Connect.

In nRF Connect:

1. Scan for `ReachyMini`.
2. Connect.
3. Open **Unknown Service**.
4. Use **WRITE** to send commands.
5. Read responses in the **READ** area.
6. Send the PIN before any command.

The PIN is the last five digits of the robot serial number. If the serial ends in `00018`, send `PIN_00018`.

| Command | ASCII hex |
|---|---|
| `STATUS` | `535441545553` |
| `PIN_00018` | `50494E5F3030303138` |
| `CMD_HOTSPOT` | `434D445F484F5453504F54` |
| `CMD_RESTART_DAEMON` | `434D445F524553544152545F4441454D4F4E` |
| `CMD_SOFTWARE_RESET` | `434D445F534F4654574152455F5245534554` |

`CMD_SOFTWARE_RESET` reinstalls or restores software and can make the robot unreachable for about five minutes. Use it only when you intend that recovery action.

### 14.5 Motor diagnosis

Use the [Reachy Mini Testbench app](https://huggingface.co/spaces/pollen-robotics/reachy_mini_testbench).

1. Power on the robot.
2. In Reachy Mini Control, turn off the motor backend or daemon as instructed by the Testbench workflow.
3. Open Testbench.
4. Select **Scan Motors**.
5. If all motors appear, select **Check all motors**.
6. If a motor has the wrong ID or baud rate, use the motor-reflash section and the correct preset.
7. Reconnect and restart the daemon.

If successive motors are missing, check cable continuity between the foot power board and the chain. If all motors are missing, inspect the first/central motor connection. If one motor is missing, inspect that motor’s cable and connector first.

If a motor blinks red and is unusually hard to turn while powered off, it may be damaged. Update and reboot once. Contact support if the fault remains.

### 14.6 Motor shaking

Antenna shaking near 0° is associated with gearbox backlash and unstable equilibrium. The recommended first fix is to offset the antenna by a few degrees, typically about 10°.

Advanced PID tuning is possible, but values vary by robot. The troubleshooting guide suggests trying lower P, around 180, on motors 10, 17, and 18, then increasing D to around 10 if needed. Treat these values as test starting points, not universal settings. Record the original configuration before changing it.

### 14.7 Daemon and app logs

```bash
systemctl status reachy-mini-daemon
journalctl -u reachy-mini-daemon -n 200 --no-pager
journalctl -u reachy-mini-daemon -f
```

Restart only after stopping any local test daemon:

```bash
sudo systemctl restart reachy-mini-daemon
```

Wait about 30 seconds before starting an app if the daemon was in a bad state.

---

## 15. Expert mode

> **Use this section only when normal updates, restarts, cable checks, and the official troubleshooting workflow do not solve the problem. Back up application code first. An incorrect command can erase the robot or leave it unbootable.**

### 15.1 Inspect the operating system

```bash
ssh pollen@reachy-mini.local
reachyminios_check
systemctl status reachy-mini-daemon
journalctl -u reachy-mini-daemon -f
```

Use the daemon’s API and logs before modifying installed packages.

### 15.2 Install the daemon from a branch

This is for developers and testers, not normal owners.

#### Local development mode

```bash
ssh pollen@reachy-mini.local
cd /home/pollen
git clone -b <branch-name> https://github.com/pollen-robotics/reachy_mini.git
cd reachy_mini
uv venv --python /venvs/mini_daemon/bin/python .venv
source .venv/bin/activate
uv sync --extra gstreamer --extra wireless-version
sudo systemctl stop reachy-mini-daemon
reachy-mini-daemon --wireless-version
```

The system service starts again after reboot. Stop it again before running the local daemon.

#### System-wide branch installation

```bash
ssh pollen@reachy-mini.local
source /venvs/mini_daemon/bin/activate
pip install --no-cache-dir --force-reinstall \
  "reachy_mini[gstreamer,wireless-version] @ \
   git+https://github.com/pollen-robotics/reachy_mini.git@<branch-name>"
sudo systemctl restart reachy-mini-daemon
pip show reachy-mini | grep Version
```

The official guide uses `pip` here because of a documented `git lfs` issue with `uv pip install`.

Monitor the result:

```bash
journalctl -u reachy-mini-daemon -f
```

#### Rollback

Use the Bluetooth `CMD_SOFTWARE_RESET` procedure to restore the factory daemon, then follow the [Reset Guide](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/reset).

### 15.3 Development workflows

#### VS Code Remote SSH

Use the Remote - SSH extension and connect to:

```text
pollen@reachy-mini.local
```

#### Clone on the robot and edit remotely

```bash
ssh pollen@reachy-mini.local
cd /home/pollen
git clone https://github.com/YOUR_USER/YOUR_APP.git
```

Mount it locally from your computer:

```bash
mkdir -p ~/wireless_dev
sshfs pollen@reachy-mini.local:/home/pollen/YOUR_APP \
  ~/wireless_dev \
  -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3
```

Install and run on the robot:

```bash
cd /home/pollen/YOUR_APP
/venvs/apps_venv/bin/pip install -e .
/venvs/apps_venv/bin/python -m YOUR_MODULE.main
```

Unmount on Linux:

```bash
fusermount -u ~/wireless_dev
```

#### Rsync source to the robot

```bash
rsync -avz /path/to/your_app/src/your_app/ \
  pollen@reachy-mini.local:/venvs/apps_venv/lib/python3.12/site-packages/your_app/
```

Add `--delete` only when you intend to remove remote files.

#### Important mount-point rule

A repository often contains:

```text
your_app/src/your_app/main.py
```

`site-packages` expects the inner package directory:

```text
your_app/main.py
```

Mount or copy only the inner package directory. Mounting the entire repository over `site-packages` can make imports fail.

### 15.4 Reflash the CM4 OS

Reflashing is a factory reset. It can erase network configuration, installed apps, local code, and custom changes.

#### Obtain the image

Download the current ReachyMiniOS image and `.bmap` file from:

<https://github.com/pollen-robotics/reachy-mini-os/releases>

#### Install tools

- Install `rpiboot` using the Raspberry Pi USB boot instructions.
- Linux: install `bmap-tools`.
- Windows: use Raspberry Pi Imager or the documented RPiBoot mass-storage workflow.

Linux:

```bash
sudo apt install bmap-tools
```

#### Put the CM4 into mass-storage mode

1. Shut down the robot completely.
2. Start `rpiboot` and keep its terminal open:

```bash
sudo ./rpiboot -d mass-storage-gadget64
```

3. Set the head PCB switch to **DOWNLOAD (SW1)**.
4. Connect the cable shown as **USB2** in the official guide.
5. Power on the robot.
6. Wait for the CM4 eMMC to appear as a mass-storage device.

#### Identify and unmount the eMMC

Check carefully. Do not guess the device name.

```bash
lsblk
```

If `bootfs` and `rootfs` are mounted, unmount those exact partitions:

```bash
sudo umount /media/<username>/bootfs
sudo umount /media/<username>/rootfs
```

#### Flash

Replace the placeholders with the exact downloaded filenames and device. A wrong device path can destroy another disk.

```bash
sudo bmaptool copy <reachy_mini_os>.zip \
  --bmap <reachy_mini_os>.bmap /dev/sda
```

#### Restore normal boot

1. Power off.
2. Move the switch back to **DEBUG**.
3. Disconnect USB2.
4. Power on.
5. Join `reachy-mini-ap` with password `reachy-mini`.
6. SSH to the robot:

```bash
ssh pollen@reachy-mini.local
reachyminios_check
```

A successful check reports:

```text
Image validation PASSED
```

### 15.5 Linux GStreamer and WebRTC

Linux remote media requires manual GStreamer setup. The official guide requires GStreamer 1.22 or later and uses Rust to build the WebRTC plugin.

Ubuntu/Debian package set:

```bash
sudo apt-get update
sudo apt-get install \
  libgstreamer-plugins-bad1.0-dev \
  libgstreamer-plugins-base1.0-dev \
  libgstreamer1.0-dev \
  libglib2.0-dev \
  libssl-dev \
  libgirepository1.0-dev \
  libcairo2-dev \
  libportaudio2 \
  libnice10 \
  gstreamer1.0-plugins-good \
  gstreamer1.0-alsa \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-nice \
  python3-gi \
  python3-gi-cairo
```

For Ubuntu 22.04, verify the version and install a newer GStreamer source if needed:

```bash
pkg-config --modversion gstreamer-1.0
```

Install Rust:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

Build the WebRTC plugin:

```bash
git clone https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git
cd gst-plugins-rs
git checkout 0.14.5
cargo install cargo-c
sudo mkdir -p /opt/gst-plugins-rs
sudo chown "$USER" /opt/gst-plugins-rs
cargo cinstall -p gst-plugin-webrtc \
  --prefix=/opt/gst-plugins-rs --release
```

For x86-64 Linux:

```bash
echo 'export GST_PLUGIN_PATH=/opt/gst-plugins-rs/lib/x86_64-linux-gnu:$GST_PLUGIN_PATH' >> ~/.bashrc
source ~/.bashrc
```

For ARM64, replace `x86_64-linux-gnu` with `aarch64-linux-gnu`.

Verify:

```bash
sudo apt install gstreamer1.0-tools
gst-launch-1.0 --version
gst-inspect-1.0 webrtcsrc
python -c "import gi"
```

Do not build or replace media plugins on the robot unless you understand the daemon’s architecture and have a recovery path.

---

## 16. Reference tables and commands

### 16.1 Common paths

| Path | Purpose |
|---|---|
| `/venvs/apps_venv/` | Wireless app environment |
| `/venvs/mini_daemon/` | Wireless daemon environment |
| `/home/pollen/` | Default user home |
| `http://reachy-mini.local:8000/docs` | Wireless Swagger UI |
| `http://reachy-mini.local:8000/openapi.json` | Wireless OpenAPI schema |

### 16.2 Common commands

```bash
# Connect
ssh pollen@reachy-mini.local

# Validate image and system
reachyminios_check

# Service status
systemctl status reachy-mini-daemon

# Follow daemon logs
journalctl -u reachy-mini-daemon -f

# Restart service
sudo systemctl restart reachy-mini-daemon

# API status
curl http://reachy-mini.local:8000/api/daemon/status

# State
curl http://reachy-mini.local:8000/api/state/full

# Scan camera
rpicam-hello --list
```

### 16.3 REST API overview

The daemon serves HTTP and WebSocket APIs under `/api`:

| Category | Prefix | Purpose |
|---|---|---|
| Apps | `/api/apps` | List, install, start, and stop apps |
| Daemon | `/api/daemon` | Daemon status and control |
| State | `/api/state` | Head, body, antenna, and DoA state |
| Move | `/api/move` | Targets and recorded moves |
| Motors | `/api/motors` | Motor status and control mode |
| Kinematics | `/api/kinematics` | IK, URDF, and mesh data |
| Volume | `/api/volume` | Speaker and microphone volume |
| HF auth | `/api/hf-auth` | Hugging Face authentication |

Use the live Swagger UI at `/docs` as the authoritative endpoint and schema reference for your installed version.

Example WebSocket state stream:

```javascript
const ws = new WebSocket(
  "ws://reachy-mini.local:8000/api/state/ws/full"
);

ws.onmessage = (event) => {
  const state = JSON.parse(event.data);
  console.log(state);
};
```

### 16.4 Support information to collect

Before contacting support, record:

- Robot serial number.
- Installed Reachy Mini Control version.
- Robot software or image version.
- Operating system and SDK version.
- Exact command or app that failed.
- `reachyminios_check` output.
- Relevant `journalctl` output.
- Photos of damaged cables, connectors, motor LEDs, or packaging.
- Order or invoice number for hardware claims.

Contact Pollen Robotics through the current support channel. The troubleshooting guide lists `sales@pollen-robotics.com` for missing, damaged, warranty, and shipping issues, and links to the [Pollen Robotics Discord](https://discord.gg/Y7FgMqHsub) for community help.

---

## 17. Official sources

Use these pages for updates, diagrams, firmware, and procedures:

- [Wireless setup guide](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/get_started)
- [Hardware datasheet](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/hardware)
- [Usage guide](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/usage)
- [Advanced media controls](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/media_advanced_controls)
- [Bluetooth reset guide](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/reset)
- [Daemon branch installation](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/install_daemon_from_branch)
- [Wireless development workflow](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/development_workflow)
- [CM4 OS reflash guide](https://huggingface.co/docs/reachy_mini/en/platforms/reachy_mini/reflash_the_rpi_ISO)
- [Troubleshooting and FAQ](https://huggingface.co/docs/reachy_mini/en/troubleshooting)
- [Motor diagnosis](https://huggingface.co/docs/reachy_mini/en/troubleshooting/motors_diagnosis)
- [Microphone FPC replacement](https://huggingface.co/docs/reachy_mini/en/troubleshooting/change_mic_fpc_cable)
- [Spherical-joint maintenance](https://huggingface.co/docs/reachy_mini/en/troubleshooting/spherical_joints_maintenance)
- [SDK installation](https://huggingface.co/docs/reachy_mini/en/SDK/installation)
- [SDK quickstart](https://huggingface.co/docs/reachy_mini/en/SDK/quickstart)
- [Python SDK reference](https://huggingface.co/docs/reachy_mini/en/SDK/python-sdk)
- [Core concepts](https://huggingface.co/docs/reachy_mini/en/SDK/core-concept)
- [Media architecture](https://huggingface.co/docs/reachy_mini/en/SDK/media-architecture)
- [App development](https://huggingface.co/docs/reachy_mini/en/SDK/apps)
- [REST API](https://huggingface.co/docs/reachy_mini/en/API/rest-api)
- [GStreamer installation](https://huggingface.co/docs/reachy_mini/en/SDK/gstreamer-installation)

### Document notes

This manual consolidates the published pages above into an owner-oriented workflow. It adds organization, checklists, safety cautions, and cross-references. It does not replace the paper assembly instructions, manufacturer support, or the documentation shipped with a later software release.
