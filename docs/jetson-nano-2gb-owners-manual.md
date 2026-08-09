# NVIDIA Jetson Nano 2GB Developer Kit
## Practical Owner's Manual

**Revision:** 1.0  
**Prepared:** 2026-08-09  
**Applies to:** Jetson Nano 2GB Developer Kit, kit part number **P3541**, using Jetson module **P3448-0003** and reference carrier board **P3542-0000**.

> This is an independent practical manual. It consolidates NVIDIA's official hardware, setup, and software documentation into one operating reference. It does not replace NVIDIA's licenses, safety notices, release notes, or board-specific documentation.

---

## Contents

1. [Important status information](#1-important-status-information)
2. [What you have](#2-what-you-have)
3. [Safety and handling](#3-safety-and-handling)
4. [Hardware overview](#4-hardware-overview)
5. [Before you power on](#5-before-you-power-on)
6. [Install the operating system](#6-install-the-operating-system)
7. [First boot](#7-first-boot)
8. [Headless operation](#8-headless-operation)
9. [Connectors and interfaces](#9-connectors-and-interfaces)
10. [40-pin expansion header](#10-40-pin-expansion-header)
11. [Power and thermal management](#11-power-and-thermal-management)
12. [Networking](#12-networking)
13. [Camera installation](#13-camera-installation)
14. [Useful software commands](#14-useful-software-commands)
15. [GPIO, I2C, SPI, UART, I2S, and PWM](#15-gpio-i2c-spi-uart-i2s-and-pwm)
16. [Reflash and recovery](#16-reflash-and-recovery)
17. [Storage, swap, and backups](#17-storage-swap-and-backups)
18. [Maintenance and reliability](#18-maintenance-and-reliability)
19. [Troubleshooting](#19-troubleshooting)
20. [Practical limits](#20-practical-limits)
21. [Official references](#21-official-references)

---

# 1. Important status information

The Jetson Nano 2GB Developer Kit has reached **End of Life (EOL)**. NVIDIA no longer sells it. JetPack 4.x is the supported software family for this hardware, and **JetPack 4.6.6 with Jetson Linux R32.7.6 is the final JetPack 4 release**.

Treat this board as an educational, experimental, and legacy development system:

- Do not expose it directly to the public Internet.
- Do not use it as a security-sensitive server without additional isolation and maintenance.
- Keep a local copy of the software image, packages, source code, and working SD card.
- Expect modern packages, containers, certificates, and cloud services to stop supporting its old software stack.
- Prefer an isolated VLAN, private lab network, or offline workflow for long-term use.

The developer kit is a reference development platform. It is not a production product. NVIDIA distinguishes it from production Jetson modules and does not provide a production lifecycle for developer kits.

## Recommended software baseline

For a new installation, use the matching Jetson Nano 2GB image from NVIDIA's JetPack archive. The practical baseline is:

- **JetPack:** 4.6.6
- **Jetson Linux / L4T:** R32.7.6
- **Kernel family:** Linux 4.9 with NVIDIA changes
- **CUDA family:** CUDA 10.2 in the R32 software line
- **Target board name for host flashing:** `jetson-nano-2gb-devkit`

Do not mix a Jetson Nano 4GB image with the 2GB kit. Use the image or board configuration specifically marked for **Jetson Nano 2GB**.

---

# 2. What you have

## 2.1 Kit variants

NVIDIA shipped two common kit part numbers:

| Kit part number | Wireless adapter | Extension cable |
|---|---:|---:|
| `945-13541-0000-000` | Included | Included |
| `945-13541-0001-000` | Not included | Not included |

The carrier board is otherwise the same reference design for this manual.

## 2.2 Included hardware

A kit normally contains:

- Jetson Nano 2GB module attached to the reference carrier board
- Quick Start and support information
- 802.11ac USB wireless adapter and extension cable, where supplied

## 2.3 Items you must supply

Prepare these items before setup:

- UHS-I microSD card, **32 GB minimum**
- **64 GB or larger** card recommended
- High-endurance microSD card recommended for swap, logging, or frequent writes
- Reliable USB-C power supply rated for **5 V at 3 A**
- USB-C cable suitable for 3 A at 5 V
- HDMI display and HDMI cable
- USB keyboard and mouse
- Computer with Internet access and an SD card reader or writer

The microSD card is the boot device and the main storage device. The 2 GB RAM limit makes swap useful for many AI workloads, so storage endurance matters.

---

# 3. Safety and handling

Read these rules before connecting power.

## 3.1 Electrical safety

- Use **5 V DC only** at the USB-C power connector.
- Use a supply that can deliver **3 A continuously**.
- The board does not use USB-C Power Delivery negotiation. A USB-C supply must provide the required 5 V output without relying on a higher-voltage PD mode.
- Do not power through the Micro-USB connector. That connector is for device mode and recovery.
- Do not connect USB-C power and external 5 V power through the 40-pin header at the same time.
- Treat every 40-pin signal as a **3.3 V signal**. Do not connect 5 V logic directly.
- Turn power off before inserting or removing a camera cable, fan, jumper, or header wiring.
- Check polarity before using a battery, regulator, or external 5 V supply.

## 3.2 Mechanical and thermal safety

- Place the carrier board on a non-conductive surface. The underside has exposed contacts and pins that can short on metal or conductive material.
- The heatsink can become hot. Do not touch it during operation or immediately after shutdown.
- Keep airflow around the heatsink and the carrier board.
- Do not cover the heatsink or place the board inside a sealed enclosure without a thermal plan.
- Do not force the microSD card, camera latch, SO-DIMM connector, or header pins.
- Ground yourself before handling the board in a dry environment.

## 3.3 Data safety

- A failed or worn microSD card can prevent boot and can corrupt the root filesystem.
- Shut down Linux before removing power when possible.
- Avoid unnecessary swap and high-rate logging on low-endurance cards.
- Keep at least one known-good spare card and a tested backup.

---

# 4. Hardware overview

## 4.1 Processing and storage

| Feature | Jetson Nano 2GB Developer Kit |
|---|---|
| Module | P3448-0003 |
| Carrier board | P3542-0000 |
| CPU | Quad-core 64-bit Arm Cortex-A57, up to about 1.43 GHz in the NVIDIA software configuration |
| GPU | 128-core NVIDIA Maxwell GPU |
| Stated compute performance | About 472 GFLOPS |
| Memory | 2 GB LPDDR4 |
| Boot firmware storage | Built-in QSPI-NOR on the module |
| Main storage | Removable microSD card |
| Display | HDMI output |
| Wired network | Gigabit Ethernet, RJ45 |
| Wireless network | Supported USB wireless adapter; included on some kit variants |
| Camera | One MIPI CSI-2 camera connector |
| USB host | One USB 3.0 Type-A port and two USB 2.0 Type-A ports |
| USB device/recovery | One Micro-USB 2.0 connector |
| Expansion | 40-pin header with GPIO, I2C, SPI, UART, I2S, power, and ground |
| Fan | Optional 5 V 3-pin or 4-pin fan at J7 |
| Form factor | Approximately 80 mm × 100 mm for the complete developer kit |

The 2 GB module is not the same as the original 4 GB Jetson Nano module. The 2 GB kit uses a different module and carrier-board combination.

## 4.2 Connector map

The silkscreen designators below match NVIDIA's documentation.

| Designator | Connector or feature | Function |
|---|---|---|
| `DS1` | Power LED | Lights when the kit is powered |
| `J1` | SO-DIMM connector | Jetson module connection; the module is pre-installed |
| `J2` | USB-C | 5 V power input |
| `J3` | RJ45 | Gigabit Ethernet |
| `J4` | HDMI | Display output |
| `J5` | MIPI CSI-2 | Camera input |
| `J6` | 40-pin header | Power, ground, GPIO, I2C, SPI, UART, I2S, and PWM-capable signals |
| `J7` | 4-pin fan header | 5 V fan power, tachometer, and PWM |
| `J8` | Coin-cell socket | Optional battery socket |
| `J9` | USB 3.0 Type-A | Host port; up to 1 A total power delivery |
| `J10` | Two stacked USB 2.0 Type-A ports | Host-only ports |
| `J11` | Optional 2×4 button header | Alternate power, reset, recovery, and auto-power-on control |
| `J12` | 1×12 button header | Power LED, UART, power, reset, recovery, and auto-power-on control |
| `J13` | Micro-USB 2.0 | Device mode, serial setup, and recovery flashing |

The product page contains labeled front and bottom images. See the references at the end of this manual if you need a visual orientation guide.

---

# 5. Before you power on

Use this checklist:

- [ ] The board is on a non-conductive surface.
- [ ] The microSD card contains a Jetson Nano 2GB image.
- [ ] The microSD card is inserted into the slot on the underside of the module.
- [ ] HDMI is connected if you will use the desktop setup.
- [ ] Keyboard and mouse are connected to the USB 2.0 ports.
- [ ] Ethernet or the supported wireless adapter is available if you need networking.
- [ ] The power supply provides 5 V at 3 A.
- [ ] No 5 V signal is connected to the 40-pin header.
- [ ] You are not using the Micro-USB connector as a power input.
- [ ] There is airflow around the heatsink.

Connect power last. The board powers on automatically when the correct USB-C power is connected, unless auto-power-on has been disabled through the button header.

---

# 6. Install the operating system

The recommended method is the official prebuilt SD card image. Use host flashing only when you need to update QSPI firmware, customize the root filesystem, or recover a board that does not boot normally.

## 6.1 Download the image

1. Open NVIDIA's [Jetson Nano 2GB Getting Started page](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-2gb-devkit).
2. Follow its link to the Jetson Nano 2GB SD card image.
3. Prefer the image associated with JetPack 4.6.6 / L4T R32.7.6.
4. Record the downloaded filename and verify its checksum if NVIDIA provides one.

NVIDIA may change the download interface. Use the JetPack Archive if the direct image link is no longer visible.

## 6.2 Write the image with Etcher

Etcher is the safest general method on Windows, macOS, and Linux.

1. Install and open Etcher from its official source.
2. Select the downloaded Jetson Nano 2GB image.
3. Insert the microSD card into the host computer.
4. Select the correct removable drive.
5. Confirm the capacity and device name. This step matters because flashing destroys the selected drive.
6. Start the flash operation.
7. Allow Etcher to validate the result.
8. Eject the card through the operating system.
9. Remove the card from the host.

Your host operating system may report that it cannot read one or more partitions after flashing. Do not reformat the card. Eject it and use it in the Jetson.

## 6.3 Linux command-line method

Use this only if you are comfortable identifying block devices.

1. Insert the microSD card.
2. Identify it with `lsblk`.
3. Confirm the device by size, model, and connection. Use the whole device, such as `/dev/sdX`, not a partition such as `/dev/sdX1`.
4. Unmount its partitions.
5. Write the image.

Example:

```bash
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS
sudo umount /dev/sdX1 2>/dev/null || true
sudo umount /dev/sdX2 2>/dev/null || true
unzip -p ~/Downloads/jetson_nano_devkit_sd_card.zip \
  | sudo dd of=/dev/sdX bs=1M status=progress conv=fsync
sync
sudo eject /dev/sdX
```

Replace `/dev/sdX` with the actual microSD device. **Never copy this command unchanged.** A wrong device name can destroy another disk.

For a compressed image with a different filename, substitute that filename. If the image is already uncompressed, use `dd if=...` instead of `unzip -p ...`.

## 6.4 macOS command-line method

First list external disks before inserting the card:

```bash
diskutil list external | fgrep '/dev/disk'
```

Insert the card, run the command again, and identify the newly added disk. Then unmount and write to the raw device:

```bash
sudo diskutil unmountDisk /dev/diskN
/usr/bin/unzip -p ~/Downloads/jetson_nano_devkit_sd_card.zip \
  | sudo /bin/dd of=/dev/rdiskN bs=1m
sync
sudo diskutil eject /dev/diskN
```

Replace `diskN` with the actual microSD device. Confirm it by capacity before running the command.

---

# 7. First boot

## 7.1 Desktop setup

1. Insert the prepared microSD card into the underside slot.
2. Place the kit on a non-conductive surface.
3. Connect the HDMI display.
4. Connect the keyboard and mouse to the USB 2.0 ports.
5. Connect Ethernet if desired.
6. Connect the USB-C power supply.
7. Wait for the first-boot setup screen.

The first boot can take longer than later boots.

## 7.2 Complete the first-boot wizard

The wizard asks you to:

1. Review and accept the NVIDIA software license.
2. Select the language.
3. Select the keyboard layout.
4. Select the time zone.
5. Create your normal user account.
6. Set a strong password.
7. Set the hostname.
8. Configure wireless networking if required.
9. Set the APP partition size. Use the maximum suggested size unless you have a specific reason not to.
10. Create a swap file if you will run AI, computer-vision, or other memory-heavy software.

The desktop uses a lightweight LXDE/Openbox environment. This is intentional. The 2 GB system does not have much memory for a full modern desktop.

## 7.3 After login

Open a terminal and record the initial state:

```bash
cat /etc/nv_tegra_release
uname -a
lsblk -f
free -h
df -h
```

Then update only from repositories that still support your chosen legacy release. Do not assume that a current Ubuntu mirror will continue to serve every old package.

A reasonable initial setup is:

```bash
sudo apt update
sudo apt full-upgrade
sudo reboot
```

If `apt update` reports expired metadata, missing Release files, or unavailable Ubuntu 18.04 repositories, stop. Use the relevant Ubuntu archive or a maintained local mirror. Do not bypass repository signature checks.

---

# 8. Headless operation

Headless operation uses the Micro-USB connector for USB device mode and the board's serial console during first setup.

## 8.1 Connection

1. Insert the prepared microSD card.
2. Place the board on a non-conductive surface.
3. Connect a USB-A-to-Micro-B cable from the host computer to `J13`.
4. Connect the 5 V, 3 A USB-C supply to `J2`.
5. Wait about one minute.
6. Open the serial device on the host.

The Micro-USB cable does not power the board. It provides the USB device connection.

## 8.2 Windows and PuTTY

1. Open Device Manager.
2. Expand **Ports (COM & LPT)**.
3. Find the new USB serial device.
4. Check its hardware IDs if several devices are present. NVIDIA identifies the recovery serial device with USB vendor ID `0955` and product ID `7020` during the documented setup flow.
5. Open PuTTY.
6. Select **Serial**.
7. Enter the COM port.
8. Set the speed to `115200`.
9. Open the session.

## 8.3 macOS

Before connecting the board:

```bash
ls /dev/cu.usbmodem*
```

Connect the board and run the command again. Then use the newly appearing device:

```bash
sudo screen /dev/cu.usbmodemXXXX 115200
```

Exit `screen` with `Ctrl-A`, then `K`, then confirm with `Y`.

## 8.4 Linux

Before and after connecting the board, inspect the kernel log:

```bash
dmesg | grep --color 'tty'
```

The device commonly appears as `/dev/ttyACM0`.

```bash
sudo apt install screen
sudo screen /dev/ttyACM0 115200
```

Exit `screen` with `Ctrl-A`, then `K`, then confirm with `Y`.

If the setup screen does not appear, press the space bar once.

## 8.5 After first setup

After creating the user, connect through Ethernet or Wi-Fi and use SSH:

```bash
ssh your-user@jetson-hostname-or-ip
```

For a legacy device, prefer SSH keys and disable password authentication after confirming key access. Keep the serial connection available for recovery.

---

# 9. Connectors and interfaces

## 9.1 USB

| Port | Role | Notes |
|---|---|---|
| `J9` | USB 3.0 host | Single unstacked Type-A port; up to 1 A total power delivery |
| `J10` | USB 2.0 host | Two stacked Type-A ports; host mode only |
| `J13` | USB 2.0 device/recovery | Micro-B; use for serial/device mode and host flashing |

Use `J9` for the supplied wireless adapter when possible. NVIDIA recommends the extension cable to reduce interference between the adapter and the board.

The Type-A ports are not intended to charge external devices. A powered USB hub is preferable when using several high-current peripherals.

## 9.2 HDMI

`J4` provides HDMI display output. Connect the display before power-on if you want the first-boot wizard to use the graphical interface.

If there is no display, use the serial console. Do not assume a black screen means that Linux failed to boot.

## 9.3 Ethernet

`J3` is a Gigabit Ethernet port. The port LEDs provide a quick link check:

- Green indicates an active Gigabit link. It is off with no link or a link below Gigabit speed.
- Amber flickers when traffic is present.

A wired connection is the best choice for first setup, package installation, and recovery work.

## 9.4 Wireless and Bluetooth

Use a Linux-supported USB adapter. For best performance:

- Use the USB 3.0 port.
- Use the supplied extension cable when available.
- Keep the radio away from the board and high-speed digital cables.
- Prefer Ethernet for flashing and large package downloads.

The supplied adapter and the adapters in NVIDIA's supported component list are the safest starting points. Other adapters may work if a compatible driver exists in the installed Jetson Linux release.

## 9.5 Coin-cell socket

`J8` is an optional coin-cell socket. Use only the battery type specified for the carrier-board design. Remove power before installing or replacing it.

---

# 10. 40-pin expansion header

The expansion header is `J6`. Pin 1 is marked on the carrier board. Verify orientation against the silkscreen before wiring.

## 10.1 Electrical rules

- Signal levels are 3.3 V.
- Do not apply 5 V to a signal pin.
- The two 3.3 V pins and two 5 V pins are always powered when the board is powered. They are not software-switched.
- The I2C lines have 2.2 kΩ pull-ups to 3.3 V.
- Most non-I2C signals pass through TXB0108 level shifters. This affects signal direction, drive strength, pull-ups, and some peripheral designs.
- Use a proper level shifter or interface board for external 5 V systems.
- Do not connect motor coils, relays, LEDs with no resistor, or other loads directly to GPIO pins.

## 10.2 Complete J6 pinout

The legacy Linux GPIO numbers below are those shown in NVIDIA's Jetson Nano 2GB reference pinout. Prefer signal names with Jetson-IO, Jetson.GPIO, or `gpiofind` instead of hard-coding these numbers in new software.

| Pin | SoC signal | Legacy Linux GPIO | Default function | Alternate function | Electrical role |
|---:|---|---:|---|---|---|
| 1 | — | — | 3.3 VDC | — | Power |
| 2 | — | — | 5 VDC | — | Power |
| 3 | `PJ.03` | 75 | `I2C1_SDA` | GPIO | Signal |
| 4 | — | — | 5 VDC | — | Power |
| 5 | `PJ.02` | 74 | `I2C1_SCL` | GPIO | Signal |
| 6 | — | — | GND | — | Ground |
| 7 | `PBB.00` | 216 | GPIO | `AUD_CLK` | Signal |
| 8 | `PG.00` | 48 | `UART1_TXD` | GPIO | Signal |
| 9 | — | — | GND | — | Ground |
| 10 | `PG.01` | 49 | `UART1_RXD` | GPIO | Signal |
| 11 | `PG.02` | 50 | GPIO | `UART1_RTS` | Signal |
| 12 | `PJ.07` | 79 | GPIO | `I2S0_SCLK` | Signal |
| 13 | `PB.06` | 14 | GPIO | `SPI1_SCK` | Signal |
| 14 | — | — | GND | — | Ground |
| 15 | `PY.02` | 194 | GPIO | — | Signal |
| 16 | `PDD.00` | 232 | GPIO | `SPI1_CS1` | Signal |
| 17 | — | — | 3.3 VDC | — | Power |
| 18 | `PB.07` | 15 | GPIO | `SPI1_CS0` | Signal |
| 19 | `PC.00` | 16 | GPIO | `SPI0_MOSI` | Signal |
| 20 | — | — | GND | — | Ground |
| 21 | `PC.01` | 17 | GPIO | `SPI0_MISO` | Signal |
| 22 | `PB.05` | 13 | GPIO | `SPI1_MISO` | Signal |
| 23 | `PC.02` | 18 | GPIO | `SPI0_SCK` | Signal |
| 24 | `PC.03` | 19 | GPIO | `SPI0_CS0` | Signal |
| 25 | — | — | GND | — | Ground |
| 26 | `PC.04` | 20 | GPIO | `SPI0_CS1` | Signal |
| 27 | `PB.05` | 13 | `I2C0_SDA` | GPIO | Signal |
| 28 | `PC.02` | 18 | `I2C0_CLK` | GPIO | Signal |
| 29 | `PS.05` | 149 | GPIO | `CAM_MCLK` | Signal |
| 30 | — | — | GND | — | Ground |
| 31 | `PZ.00` | 200 | GPIO | `CAM_MCLK` | Signal |
| 32 | `PY.00` | 168 | GPIO | `PWM` | Signal |
| 33 | `PE.06` | 38 | GPIO | `PWM` | Signal |
| 34 | — | — | GND | — | Ground |
| 35 | `PJ.04` | 76 | GPIO | `I2S0_FS` | Signal |
| 36 | `PG.03` | 51 | GPIO | `UART1_CTS` | Signal |
| 37 | `PB.04` | 12 | GPIO | `SPI1_MOSI` | Signal |
| 38 | `PJ.05` | 77 | GPIO | `I2S0_DIN` | Signal |
| 39 | — | — | GND | — | Ground |
| 40 | `PJ.06` | 78 | GPIO | `I2S0_DOUT` | Signal |

### Important pinout notes

- The table shows several functions that are not enabled as the default mode. Use Jetson-IO to select a supported alternate function.
- Do not assume two signal pins with the same legacy GPIO number are interchangeable. Pin muxing and the active peripheral function still matter.
- Do not rely on a Raspberry Pi pinout diagram without checking the Jetson Nano 2GB diagram. The physical 40-pin format is similar, but the electrical and software mappings are NVIDIA-specific.

## 10.3 Jetson-IO

Use Jetson-IO to inspect and select supported header functions:

```bash
sudo /opt/nvidia/jetson-io/jetson-io.py
```

Select the required header configuration, save it, and reboot if prompted. If you change the configuration while wiring hardware, keep a written record of the selected mode.

---

# 11. Power and thermal management

## 11.1 USB-C input

Use `J2` with:

- **5 V DC nominal**
- **±5% input tolerance**
- **3 A supply capability**

The board does not negotiate USB-C Power Delivery. A supply marked only for high-voltage USB-C PD is not enough unless it also provides the required 5 V fallback output.

If the board input falls below approximately **4.25 V**, it can shut down. Voltage drop in the cable and connector is a common cause of random resets under load.

Choose a short, good-quality cable and a supply with real continuous output capability. A supply's label alone is not proof that it maintains 5 V at 3 A under load.

## 11.2 40-pin power input

The two 5 V header pins can each support up to 2.5 A according to NVIDIA's user guide. This is an alternative power path for suitable regulated external supplies.

**Never use the 40-pin 5 V input and USB-C input at the same time.**

For battery operation, use a regulated 5 V supply or a suitable USB-C power bank that remains above the board's minimum input voltage during load changes. Do not connect a raw lithium battery to the board.

## 11.3 Power modes

The NVIDIA software provides two module power modes:

- **10 W:** default performance-oriented mode
- **5 W:** lower power and lower performance mode

Check or change the active mode with:

```bash
nvpmodel -q
sudo nvpmodel -m 0
```

The exact mode number can vary with the installed configuration. Use the desktop power-mode control or `nvpmodel -q` before changing it.

The total system power includes the module, carrier board, USB devices, camera, network adapter, and fan. A 3 A supply is a supply-capability requirement, not a promise that the board always consumes 15 W.

## 11.4 Fan

`J7` supports 5 V fans:

| Pin | Function |
|---:|---|
| 1 | Ground |
| 2 | +5 V |
| 3 | Tachometer |
| 4 | PWM |

A 3-wire fan uses ground, power, and tachometer. A 4-wire fan also uses PWM. Use a standard ATX-style 5 V fan with the correct connector orientation. Only 5 V fans are supported at this header.

The carrier board fan header was not populated on some units. If you add it, solder carefully and inspect for bridges before applying power. A heatsink-compatible 40 mm fan is the usual physical choice.

To inspect thermal data and fan behavior:

```bash
tegrastats
cat /sys/devices/virtual/thermal/thermal_zone*/temp
```

Keep the heatsink clean. If the board throttles, freezes, or resets during sustained GPU work, check power and cooling before changing software.

---

# 12. Networking

## 12.1 Ethernet

Ethernet is the preferred interface for initial setup and maintenance.

Useful commands:

```bash
ip link
ip addr
ip route
ping -c 3 192.0.2.1
resolvectl status 2>/dev/null || systemd-resolve --status
```

Replace the example address with a real gateway or host on your network.

## 12.2 Wi-Fi

List devices and connections:

```bash
nmcli device
nmcli connection show
```

Connect to a network:

```bash
nmcli device wifi list
sudo nmcli device wifi connect 'SSID' password 'your-password'
```

Use the wireless adapter with the USB 3.0 port and extension cable when available.

## 12.3 Bluetooth

Bluetooth requires a supported USB Bluetooth adapter. Pair devices through the desktop or the BlueZ tools installed for the chosen JetPack image.

Bluetooth audio may require additional configuration. Use NVIDIA's archived Bluetooth audio guide rather than copying instructions for a newer Jetson release.

## 12.4 Legacy security posture

JetPack 4 uses an old kernel and old user-space base. For a safer lab deployment:

1. Put the board behind a firewall.
2. Use Ethernet on a private VLAN where possible.
3. Install only required packages.
4. Use SSH keys.
5. Disable root SSH login.
6. Disable password SSH login after testing key access.
7. Keep services bound to the private interface.
8. Do not expose the board directly to the Internet.
9. Back up configuration before upgrades.

---

# 13. Camera installation

## 13.1 Compatible camera types

`J5` is a MIPI CSI-2 camera connector. Cameras must have a driver and device-tree configuration compatible with the installed Jetson Linux release.

NVIDIA lists support for cameras including:

- Raspberry Pi Camera Module V2
- Raspberry Pi Camera Module NoIR V2
- Raspberry Pi High Quality Camera, with the Nano 2GB-specific driver package and instructions

A physically matching ribbon cable does not guarantee software compatibility.

## 13.2 Install the ribbon cable

Power off and disconnect the USB-C supply first.

1. Lift the connector latch gently.
2. Insert the ribbon cable.
3. Place the metal contacts toward the center of the developer kit.
4. Align the cable straight and fully.
5. Press the latch down with light, even pressure.
6. Inspect the cable for tilt or exposed misalignment.
7. Reconnect power.

Do not use force. A damaged camera latch or flex cable is easy to cause and difficult to repair.

## 13.3 Verify the camera

Start with NVIDIA's camera test instructions for the installed image. Common checks include:

```bash
v4l2-ctl --list-devices
v4l2-ctl --list-formats-ext -d /dev/video0
```

If the camera uses the Argus stack, use a Jetson-compatible Argus or GStreamer example from the matching JetPack documentation. A generic Linux `v4l2-ctl` test may not exercise the NVIDIA camera path.

If the camera is not detected:

- Power off and reseat the ribbon cable.
- Confirm the cable orientation.
- Confirm the camera driver matches the JetPack release.
- Check the device tree or Jetson-IO configuration.
- Test with a known-supported camera.
- Check kernel messages with `dmesg | grep -i -E 'imx|camera|csi|vi'`.

---

# 14. Useful software commands

## 14.1 Identify the installed release

```bash
cat /etc/nv_tegra_release
uname -a
cat /proc/device-tree/model; echo
cat /proc/device-tree/nvidia,dtsfilename; echo
```

The device-tree filename should identify the `p3448-0003` module and the `p3542-0000` carrier configuration.

## 14.2 Check hardware and resources

```bash
free -h
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS
df -h
lsusb
lspci
ip addr
```

## 14.3 Monitor load, temperature, and clocks

```bash
tegrastats
```

Press `Ctrl-C` to stop it.

Useful process and memory views:

```bash
top
htop 2>/dev/null || top
watch -n 2 free -h
```

## 14.4 Check CUDA and GPU visibility

If the CUDA samples are installed:

```bash
which deviceQuery
deviceQuery
```

Other useful checks:

```bash
ls -l /dev/nvhost*
gls -B 2>/dev/null | head
```

A missing sample binary does not prove that the GPU driver is missing. It may only mean that the samples were not installed.

## 14.5 Check system logs

```bash
journalctl -b -p warning
journalctl -k -b
sudo dmesg -T | tail -n 100
```

Check the previous boot after a reset:

```bash
journalctl -b -1 -p warning
```

---

# 15. GPIO, I2C, SPI, UART, I2S, and PWM

## 15.1 GPIO

Use Jetson.GPIO for Python projects. Install or verify the package supplied by the matching JetPack image rather than installing an arbitrary package from a current distribution.

Minimal example:

```python
import Jetson.GPIO as GPIO
import time

PIN = 18  # BOARD numbering: J6 pin 18
GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIN, GPIO.OUT, initial=GPIO.LOW)

try:
    GPIO.output(PIN, GPIO.HIGH)
    time.sleep(1)
finally:
    GPIO.output(PIN, GPIO.LOW)
    GPIO.cleanup()
```

Run hardware tests with the external circuit disconnected first. Use a resistor for LEDs and a transistor or driver board for loads.

For newer Linux GPIO tools, discover lines by name:

```bash
gpiofind SPI0_CS0 2>/dev/null
gpioinfo 2>/dev/null
```

The available tools and naming can vary between JetPack images.

## 15.2 I2C

The header provides two I2C interfaces. The exact `/dev/i2c-*` number depends on the enabled device-tree configuration.

List controllers:

```bash
ls -l /dev/i2c-*
sudo i2cdetect -l
```

Scan a selected bus:

```bash
sudo i2cdetect -y 1
```

Replace `1` with the bus that your hardware uses. Do not run a scan on a bus containing devices that do not tolerate the scan's probing method.

The header I2C lines are pulled up to 3.3 V with 2.2 kΩ resistors. Do not add strong pull-ups to 5 V.

## 15.3 SPI

The header exposes two SPI controller groups with chip-select signals. Enable the required function with Jetson-IO, reboot, and inspect the resulting `/dev/spidev*` devices:

```bash
ls -l /dev/spidev*
```

Use a device-tree-aware library or `spidev` only after confirming the bus, chip-select, mode, speed, and voltage.

## 15.4 UART

The 40-pin header provides UART signals. The header signal is 3.3 V logic, not RS-232 voltage.

Use a 3.3 V USB-to-TTL adapter if you need an external serial connection. Do not connect an RS-232 port directly.

Cross the signals:

- Jetson TX to external RX
- Jetson RX to external TX
- Common ground

The button header also exposes UART signals. Avoid using both paths at the same time unless you understand the pin mux and electrical connections.

## 15.5 I2S and PWM

The header exposes I2S signals and PWM-capable pins. Use Jetson-IO and the matching device-tree configuration to select them. PWM pins are signal outputs; they are not power outputs for motors or fans.

---

# 16. Reflash and recovery

There are two different recovery tasks:

1. **Replace the SD card image:** easiest; does not require a Linux host flash session.
2. **Flash QSPI or a customized image:** requires a Linux host and Force Recovery Mode.

## 16.1 Rebuild the SD card

Use the procedure in [Install the operating system](#6-install-the-operating-system). This is usually enough when:

- The root filesystem is corrupted.
- The card is worn out.
- You want a clean software installation.
- The board still reaches its boot process and does not need new QSPI firmware.

## 16.2 Force Recovery Mode with J12

For the Jetson Nano 2GB carrier board:

1. Power the board off.
2. Insert the microSD card if you will flash it as part of the procedure.
3. Place a jumper across **J12 pins 9 and 10**. These are `GND` and `Recovery Mode Button`.
4. Connect a USB-A-to-Micro-B cable from the Linux host to `J13`.
5. Connect 5 V USB-C power to `J2`.
6. The board powers on and enters Force Recovery Mode.
7. Remove the jumper after the host detects the board, or before normal boot as directed by the flash procedure.

Do not place a jumper on an unknown pair of pins. Use the J12 silkscreen and the official diagram.

## 16.3 Confirm recovery mode

On the Linux host:

```bash
lsusb
```

The Nano module should appear as an NVIDIA recovery device. NVIDIA's Jetson Linux guide identifies Jetson Nano devices with the NVIDIA USB ID family including `0955:7f21`.

If no NVIDIA device appears:

- Confirm the board has USB-C power.
- Confirm the cable supports data.
- Confirm you used `J13`, not a USB Type-A host port.
- Check the recovery jumper.
- Try another host USB port.
- Remove USB peripherals and hubs.
- Check `dmesg` on the host.

## 16.4 Flash with the Linux for Tegra package

Use a supported Linux host for the matching JetPack release. NVIDIA documents Ubuntu 16.04 and 18.04 for the older SDK Manager and L4T workflows.

Obtain the matching L4T release package and sample root filesystem from NVIDIA. Then:

```bash
tar xf Tegra210_Linux_R32.7.6_aarch64.tbz2
cd Linux_for_Tegra/rootfs
sudo tar xpf ../../Tegra_Linux_Sample-Root-Filesystem_R32.7.6_aarch64.tbz2
cd ..
sudo ./apply_binaries.sh
```

Package filenames can vary. Use the exact names downloaded from NVIDIA.

With the board in Force Recovery Mode:

```bash
sudo ./flash.sh jetson-nano-2gb-devkit mmcblk0p1
```

The operation can take about ten minutes or longer. Do not disconnect power or the USB cable during the flash.

The board should reboot when flashing completes. Follow the first-boot prompts on the HDMI display or serial console.

## 16.5 Flash only the device tree

This is an advanced operation. For the standard 2GB configuration, the device tree file is associated with the `p3448-0003` module and `p3542-0000` carrier.

The documented form is:

```bash
sudo ./flash.sh -k DTB jetson-nano-2gb-devkit mmcblk0p1
```

Only use this command after placing a deliberately built and tested DTB in the correct `Linux_for_Tegra/kernel/dtb/` directory.

## 16.6 SDK Manager

SDK Manager is an alternative host-based installation method. It is more involved than the SD card image method and requires an older supported Ubuntu host for this product generation.

Use SDK Manager when you need to:

- Flash the board from a host GUI.
- Install selected JetPack components.
- Prepare a cross-compilation host.
- Recover or update boot firmware.

For a simple working board, the SD card image is the better method.

---

# 17. Storage, swap, and backups

## 17.1 Storage layout

The Jetson Nano 2GB uses:

- QSPI-NOR for boot firmware
- microSD for the operating system and application storage

The SD card's APP partition is resized during first boot when using the official image. Select the maximum practical APP size in the first-boot wizard.

## 17.2 Swap

A swap file can prevent memory exhaustion during compilation and AI workloads. It also increases SD card writes.

Check current swap:

```bash
swapon --show
free -h
```

Create a 4 GiB swap file if you have sufficient free space:

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

For a heavily used system, consider placing swap on a reliable external storage device if the boot and software configuration supports it. Do not blindly move system partitions to unsupported media.

## 17.3 File backup

Back up project files and configuration separately from the operating system:

```bash
rsync -aHAX --delete \
  --exclude='.cache/' \
  ~/projects/ /path/to/backup/jetson-projects/
```

Back up important system configuration selectively:

```bash
sudo tar czf jetson-config-$(date +%F).tar.gz \
  /etc/NetworkManager \
  /etc/ssh \
  /etc/systemd/system \
  /boot/extlinux
```

Review the archive before storing it. Do not publish private keys or passwords.

## 17.4 Full SD card image backup

Power down the Jetson cleanly, remove the card, and attach it to a Linux host. Identify the card carefully:

```bash
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS
```

Unmount its partitions, then create an image of the whole device:

```bash
sudo dd if=/dev/sdX of=jetson-nano-2gb-backup.img \
  bs=4M status=progress conv=fsync
sha256sum jetson-nano-2gb-backup.img > jetson-nano-2gb-backup.img.sha256
```

Replace `/dev/sdX` with the actual card device. Do not image a mounted card. Store the image on a disk with enough free space.

To restore, reverse `if` and `of` only after checking the target device three times. A restore destroys the selected card.

---

# 18. Maintenance and reliability

## 18.1 Routine checks

Every few months, or before an important project:

1. Check free disk space.
2. Check the filesystem for errors during a maintenance window.
3. Inspect the card for unexpected read-only remounts.
4. Check temperatures under the expected workload.
5. Test the backup card or image.
6. Confirm the power supply and cable still work under load.
7. Clean dust from the heatsink without spinning the fan excessively.

Useful commands:

```bash
df -h
free -h
tegrastats
mount | grep -E ' / |mmcblk'
dmesg -T | grep -i -E 'mmc|I/O error|ext4|thermal|voltage|brown'
```

## 18.2 SD card replacement indicators

Replace the card if you see:

- Repeated filesystem repair messages
- `mmc` CRC or timeout errors
- Files changing to read-only unexpectedly
- Boot failures that disappear with another card
- Corrupted packages or compiler output
- Very slow writes compared with the same card on a host

Do not spend hours debugging software around a failing card.

## 18.3 Enclosures

An enclosure must provide:

- Access to USB-C, HDMI, Ethernet, and USB ports
- Clearance for the heatsink and optional fan
- A non-conductive mounting method or insulated standoffs
- Air intake and exhaust paths
- No contact with underside pins or exposed solder points

Test the enclosure at the highest expected ambient temperature and workload.

---

# 19. Troubleshooting

## 19.1 No power LED

Check, in order:

1. The USB-C supply output is 5 V.
2. The supply can provide 3 A.
3. The cable is fully inserted.
4. The connector and cable are not damaged.
5. No header wiring is shorted.
6. The board is not on a conductive surface.
7. Auto-power-on has not been disabled through J11 or J12.
8. The board is not being powered through Micro-USB.

Disconnect all USB devices and header wiring, then test with only microSD, HDMI, and USB-C power.

## 19.2 Random resets or shutdowns

The most common causes are power drop, thermal stress, or SD card failure.

- Test a known-good 5 V, 3 A supply.
- Replace the USB-C cable.
- Remove high-current USB devices.
- Use a powered USB hub.
- Check `tegrastats` and thermal readings.
- Add or test the fan.
- Check the card and kernel log for `mmc`, I/O, or voltage errors.

If the input falls below about 4.25 V, the system can shut down.

## 19.3 Black or missing HDMI display

- Connect HDMI before power-on.
- Test a known-good HDMI cable and display.
- Remove USB devices during the test.
- Wait through the first boot.
- Use the serial console to determine whether Linux booted.
- Check whether the display is receiving a signal from another device.
- Reflash the matching 2GB image if the system never reaches the login stage.

A working serial console with no HDMI output points to a display configuration or cable problem, not necessarily a dead board.

## 19.4 The board does not boot from the card

- Confirm the card was flashed with the Jetson Nano **2GB** image.
- Confirm the card is fully inserted.
- Try a known-good high-endurance card.
- Reflash the card.
- Check that the QSPI firmware and image are from a compatible JetPack release.
- Use Force Recovery Mode and host flashing if the QSPI boot firmware requires repair.

The module has QSPI-NOR boot firmware and uses the microSD card for the operating system. A damaged card and damaged QSPI are separate failure modes.

## 19.5 No USB device appears on the host

- Use `J13`, the Micro-USB connector.
- Use a data cable, not a charge-only cable.
- Apply USB-C power to `J2`.
- Confirm the recovery jumper is on J12 pins 9 and 10 when flashing.
- Remove hubs and other host USB devices.
- Check `dmesg` and `lsusb` on the host.
- Try another host port or cable.

## 19.6 Wireless adapter is missing

- Move it to `J9`, the USB 3.0 port.
- Use the extension cable.
- Check `lsusb`.
- Check `nmcli device`.
- Try Ethernet to install or repair packages.
- Confirm the adapter has a driver for the installed JetPack release.

## 19.7 Camera is not detected

- Power off and reseat the ribbon cable.
- Put the metal contacts toward the center of the board.
- Check the latch.
- Confirm the camera model and driver match JetPack.
- Use Jetson-IO if the camera requires a configuration change.
- Inspect `dmesg` for CSI, VI, and sensor errors.

## 19.8 GPIO peripheral behaves incorrectly

- Confirm the pin number and numbering scheme.
- Confirm the active Jetson-IO function.
- Confirm the peripheral uses 3.3 V logic.
- Confirm the ground connection.
- Remove external pull-ups that fight the board's I2C pull-ups.
- Check whether a TXB0108 level shifter is in the signal path.
- Test with a meter or logic analyzer before connecting the final load.

## 19.9 System is slow or runs out of memory

- Check `free -h` and `tegrastats`.
- Create swap if the workload needs it.
- Use the 10 W mode for performance if cooling and power are adequate.
- Close the desktop when operating headless.
- Reduce camera resolution, batch size, or concurrent processes.
- Use a lightweight application stack.
- Check whether the SD card is slow or failing.

## 19.10 Package installation fails

JetPack 4 and its Ubuntu base are legacy releases. Current repositories may no longer provide compatible metadata or packages.

- Confirm the installed L4T version.
- Use the correct NVIDIA JetPack archive.
- Use an appropriate Ubuntu archive or internal mirror.
- Do not mix packages from newer Jetson releases.
- Do not disable GPG signature verification.
- Pin or containerize application dependencies where practical.

---

# 20. Practical limits

The board is useful, but its limits are real:

- 2 GB RAM constrains browsers, compilers, containers, and large AI models.
- The Maxwell GPU is capable for its age but cannot run software built only for newer CUDA architectures.
- JetPack 4.6.6 is the final JetPack 4 release.
- The Linux 4.9 base is old and lacks many current kernel features and fixes.
- Modern prebuilt Python, TensorFlow, PyTorch, and container images may not support the platform.
- The microSD card is slower and less durable than modern SSD storage.
- USB power margins become tight with several peripherals.
- The developer kit is not a production deployment platform.
- The kit is not a safe Internet-facing appliance without compensating controls.

For new production designs, use a current Jetson platform. For education, robotics experiments, legacy projects, and low-cost edge prototypes, this board remains practical when its software environment is kept controlled.

---

# 21. Official references

Use the NVIDIA pages below for updates, original diagrams, release files, and legal notices.

## Primary hardware and setup documentation

- [Jetson Nano 2GB Developer Kit User Guide](https://developer.nvidia.com/embedded/learn/jetson-nano-2gb-devkit-user-guide)
- [Getting Started with Jetson Nano 2GB Developer Kit](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-2gb-devkit)
- [Jetson Download Center](https://developer.nvidia.com/embedded/downloads)
- [Jetson Nano 2GB product and lifecycle information](https://developer.nvidia.com/embedded/lifecycle)

## Software and flashing documentation

- [JetPack Archive](https://developer.nvidia.com/embedded/jetpack-archive)
- [Jetson Linux Archive](https://developer.nvidia.com/embedded/jetson-linux-archive)
- [JetPack SDK 4.6.6](https://developer.nvidia.com/jetpack-sdk-466)
- [Jetson Linux R32.7.6](https://developer.nvidia.com/embedded/linux-tegra-r3276)
- [Jetson Linux Quick Start](https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3276/Tegra%20Linux%20Driver%20Package%20Development%20Guide/quick_start.html)
- [Flashing and Booting the Target Device](https://docs.nvidia.com/jetson/l4t/Tegra%20Linux%20Driver%20Package%20Development%20Guide/flashing.html)
- [Jetson Nano Adaptation and Bring-Up](https://docs.nvidia.com/jetson/l4t/Tegra%20Linux%20Driver%20Package%20Development%20Guide/adaptation_and_bringup_nano.html)
- [Jetson Nano software features](https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3276/Tegra%20Linux%20Driver%20Package%20Development%20Guide/software_features_jetson_nano.html)

## Community and software tools

- [NVIDIA Jetson.GPIO](https://github.com/NVIDIA/jetson-gpio)
- [NVIDIA Jetson developer forums](https://forums.developer.nvidia.com/c/agx-autonomous-machines/jetson-embedded-systems/jetson-nano/76)

## Source notes

This manual was prepared from the official NVIDIA pages above. Hardware pinout, connector, power, camera, fan, and setup details are consolidated from the Jetson Nano 2GB User Guide and Getting Started Guide. Software release and flashing details are consolidated from NVIDIA's archived Jetson Linux documentation and JetPack release pages.

**Last reviewed:** 2026-08-09
