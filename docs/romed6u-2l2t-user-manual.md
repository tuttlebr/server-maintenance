# ASRock Rack ROMED6U-2L2T User Manual

| Document field | Value |
|---|---|
| Product | ASRock Rack ROMED6U-2L2T motherboard |
| Cover edition | Version 1.0, published October 2020 |
| Legal-page revision | Version 1.10, published December 2024 |
| Copyright notices | Cover: Copyright © 2020 ASRock Rack INC. All rights reserved.<br>Legal page: Copyright © 2024 ASRock Rack Inc. All rights reserved. |
| Language | English |

> **Markdown edition.** This edition was reconstructed from the official PDF supplied by the user. Repeated page headers, footers, language tabs, and printed page numbers have been removed. Printed page references have been replaced with links to the relevant sections. Obvious extraction artifacts have been corrected, while technical names, values, and option descriptions have been preserved. Figures are retained as portable image assets where the PDF layout carries information that text alone cannot represent faithfully.

## Copyright Notice

No part of this documentation may be reproduced, transcribed, transmitted, or translated in any language, in any form or by any means, except duplication of documentation by the purchaser for backup purpose, without written consent of ASRock Rack Inc.

Products and corporate names appearing in this documentation may or may not be registered trademarks or copyrights of their respective companies, and are used only for identification or explanation and to the owners’ benefit, without intent to infringe.

### Disclaimer

Specifications and information contained in this documentation are furnished for informational use only and subject to change without notice, and should not be construed as a commitment by ASRock Rack. ASRock Rack assumes no responsibility for any errors or omissions that may appear in this documentation.

With respect to the contents of this documentation, ASRock Rack does not provide warranty of any kind, either expressed or implied, including but not limited to the implied warranties or conditions of merchantability or fitness for a particular purpose.

In no event shall ASRock Rack, its directors, officers, employees, or agents be liable for any indirect, special, incidental, or consequential damages (including damages for loss of profits, loss of business, loss of data, interruption of business, and the like), even if ASRock Rack has been advised of the possibility of such damages arising from any defect or error in the documentation or product.

This device complies with Part 15 of the FCC Rules. Operation is subject to the following two conditions:

1. This device may not cause harmful interference.
2. This device must accept any interference received, including interference that may cause undesired operation.

### California, USA Only

The lithium battery adopted on this motherboard contains perchlorate, a toxic substance controlled in Perchlorate Best Management Practices (BMP) regulations passed by the California Legislature. When you discard the lithium battery in California, USA, follow the related regulations in advance.

“Perchlorate Material - special handling may apply.” See <https://www.dtsc.ca.gov/hazardouswaste/perchlorate>.

ASRock Rack website: <https://www.asrockrack.com>

## Contact Information

If you need to contact ASRock Rack or want to know more about ASRock Rack, visit the ASRock Rack website or contact your dealer.

**ASRock Rack Incorporation**  
6F., No. 37, Sec. 2, Jhongyang S. Rd., Beitou District,  
Taipei City 112, Taiwan (R.O.C.)

## Contents

- [Chapter 1: Introduction](#chapter-1-introduction)
  - [1.1 Package Contents](#11-package-contents)
  - [1.2 Specifications](#12-specifications)
  - [1.3 Unique Features](#13-unique-features)
  - [1.4 Motherboard Layout](#14-motherboard-layout)
  - [1.5 Onboard LED Indicators](#15-onboard-led-indicators)
  - [1.6 I/O Panel](#16-io-panel)
  - [1.7 Block Diagram](#17-block-diagram)
- [Chapter 2: Installation](#chapter-2-installation)
  - [2.1 Screw Holes](#21-screw-holes)
  - [2.2 Pre-installation Precautions](#22-pre-installation-precautions)
  - [2.3 Installing the CPU](#23-installing-the-cpu)
  - [2.4 Installation of Memory Modules (DIMM)](#24-installation-of-memory-modules-dimm)
  - [2.5 Expansion Slots (PCI Express Slots)](#25-expansion-slots-pci-express-slots)
  - [2.6 Onboard Headers and Connectors](#26-onboard-headers-and-connectors)
  - [2.7 ATX PSU / DC-IN Power Connections](#27-atx-psu--dc-in-power-connections)
  - [2.8 Unit Identification Purpose LED/Switch](#28-unit-identification-purpose-ledswitch)
  - [2.9 Driver Installation Guide](#29-driver-installation-guide)
  - [2.10 M.2 SSD (NGFF) Module Installation Guide](#210-m2-ssd-ngff-module-installation-guide)
- [Chapter 3: UEFI Setup Utility](#chapter-3-uefi-setup-utility)
  - [3.1 Introduction](#31-introduction)
    - [3.1.1 UEFI Menu Bar](#311-uefi-menu-bar)
    - [3.1.2 Navigation Keys](#312-navigation-keys)
  - [3.2 Main Screen](#32-main-screen)
  - [3.3 Advanced Screen](#33-advanced-screen)
    - [3.3.1 CPU Configuration](#331-cpu-configuration)
    - [3.3.2 Chipset Configuration](#332-chipset-configuration)
    - [3.3.3 Storage Configuration](#333-storage-configuration)
    - [3.3.4 ACPI Configuration](#334-acpi-configuration)
    - [3.3.5 USB Configuration](#335-usb-configuration)
    - [3.3.6 Super IO Configuration](#336-super-io-configuration)
    - [3.3.7 Serial Port Console Redirection](#337-serial-port-console-redirection)
    - [3.3.8 H/W Monitor](#338-hw-monitor)
    - [3.3.9 PCI Subsystem Settings](#339-pci-subsystem-settings)
    - [3.3.10 AMD CBS](#3310-amd-cbs)
    - [3.3.11 AMD PBS](#3311-amd-pbs)
    - [3.3.12 PSP Firmware Versions](#3312-psp-firmware-versions)
    - [3.3.13 Instant Flash](#3313-instant-flash)
  - [3.4 Server Management](#34-server-management)
    - [3.4.1 System Event Log](#341-system-event-log)
    - [3.4.2 BMC Network Configuration](#342-bmc-network-configuration)
    - [3.4.3 BMC Tools](#343-bmc-tools)
  - [3.5 Security](#35-security)
    - [3.5.1 Key Management](#351-key-management)
  - [3.6 Boot Screen](#36-boot-screen)
    - [3.6.1 CSM Parameters](#361-csm-parameters)
  - [3.7 Event Logs](#37-event-logs)
  - [3.8 Exit Screen](#38-exit-screen)
- [Chapter 4: Software Support](#chapter-4-software-support)
  - [4.1 Install Operating System](#41-install-operating-system)
  - [4.2 Support CD Information](#42-support-cd-information)
    - [4.2.1 Running the Support CD](#421-running-the-support-cd)
    - [4.2.2 Drivers Menu](#422-drivers-menu)
    - [4.2.3 Utilities Menu](#423-utilities-menu)
    - [4.2.4 Contact Information](#424-contact-information)
- [Chapter 5: Troubleshooting](#chapter-5-troubleshooting)
  - [5.1 Troubleshooting Procedures](#51-troubleshooting-procedures)
  - [5.2 Technical Support Procedures](#52-technical-support-procedures)
  - [5.3 Returning Merchandise for Service](#53-returning-merchandise-for-service)

---

## Chapter 1: Introduction

Thank you for purchasing the ASRock Rack ROMED6U-2L2T motherboard, a reliable motherboard produced under ASRock Rack's consistently stringent quality control. It delivers excellent performance with a robust design that conforms to ASRock Rack's commitment to quality and endurance.

Chapters 1 and 2 introduce the motherboard and provide a step-by-step guide to hardware installation. Chapters 3 and 4 contain the BIOS setup configuration guide and information about the Support CD.

> **Important:** The motherboard specifications and BIOS software might be updated, so the contents of this manual are subject to change without notice. Updated versions will be available on the [ASRock Rack website](https://www.asrockrack.com/) without further notice. The latest memory and CPU support lists are also available there.
>
> For technical support related to this motherboard, visit [ASRock Rack Support](http://www.asrockrack.com/support/) for model-specific information.

### 1.1 Package Contents

- ASRock Rack ROMED6U-2L2T motherboard (microATX form factor: 9.6 in x 9.6 in, 24.4 cm x 24.4 cm)
- Quick Installation Guide
- 1 x I/O shield
- 2 x screws for M.2 sockets
- 1 x SATA3 cable (60 cm)
- 1 x Mini-SAS HD to 4 SATA cable (60 cm)
- 1 x ATX 4-pin to 24-pin power cable (8 cm)
- 1 x SATA power cable (80 cm)

> **Note:** If any items are missing or appear damaged, contact your authorized dealer.

### 1.2 Specifications

#### Motherboard Physical Status

| Item | Specification |
|---|---|
| Form factor | microATX |
| Dimensions | 9.6 in x 9.6 in (24.4 cm x 24.4 cm) |

#### Processor System

| Item | Specification |
|---|---|
| CPU | AMD EPYC™ 7002 Series Processor |
| Socket | Single Socket SP3 (LGA4094) |
| Chipset | N/A |
| Thermal Design Power | 280 W |

#### System Memory

| Item | Specification |
|---|---|
| Type | Six-channel DDR4 memory technology<br>Supports DDR4 RDIMM, LRDIMM, and NVDIMM |
| DIMM size per DIMM | RDIMM: 64 GB, 32 GB, 16 GB, 8 GB<br>LRDIMM: 128 GB, 64 GB, 32 GB<br>NVDIMM: 32 GB |
| DIMM frequency | RDIMM: 3200 MHz<br>LRDIMM: 2666 MHz<br>NVDIMM: 2666 MHz |
| Voltage | 1.2 V |

#### Expansion Slots

| Item | Specification |
|---|---|
| PCIe 4.0 x16 | PCIE7: Gen4 x16 link<br>PCIE6: Gen4 x16 link<br>PCIE5: Gen4 x16 link<br>PCIE4: Gen4 x16 link |

#### Storage

| Item | Specification |
|---|---|
| Slimline | SLIM1: PCIe Gen4 x8 (supports SATA)<br>SLIM2: PCIe Gen4 x8 (supports SATA)<br>SLIM3: PCIe Gen4 x8 |
| SATA | 2 x 7-pin SATA3; 12 x SATA3 6.0 Gb/s from Mini-SAS HD (Gen3) |
| M.2 slots | 2 (M2_1: Type 2280; M2_2: Type 2260; supports SATA x1 or PCIe x4) |

#### Ethernet

| Item | Specification |
|---|---|
| Interface | 10G by Intel X710-AT2; 1000/100/10 Mbps by Intel I210 |
| LAN controller | 2 x RJ-45 10GBASE-T by Intel® X710-AT2<br>2 x RJ-45 1GBASE-T provided by two Intel® I210-AT2 controllers<br>1 x RJ-45 dedicated IPMI LAN port by RTL8211E<br>Supports Wake-on-LAN<br>Supports Energy Efficient Ethernet 802.3az<br>Supports dual LAN with teaming<br>Supports PXE<br>LAN1 supports NCSI |

> **Source clarification:** The PDF's specifications table says `1 x RJ-45 1GBASE-T by Intel I210-AT2`, while its motherboard layout, rear I/O table, and block diagram show two Intel I210-AT2 controllers and two 1G ports (LAN3 and LAN4). The breakdown above follows those three mutually consistent sections.

#### Management

| Item | Specification |
|---|---|
| BMC controller | ASPEED AST2500 |
| IPMI dedicated GLAN | 1 x Realtek RTL8211E for dedicated management GLAN |
| Features | Watchdog<br>NMI |

#### Graphics

| Item | Specification |
|---|---|
| Controller | ASPEED AST2500 |
| VRAM | DDR4 256 MB |

#### Rear Panel I/O

| Item | Specification |
|---|---|
| VGA port | 1 x D-Sub |
| USB 3.2 Gen1 ports | 2 |
| LAN ports | 2 x 10G RJ-45 data ports, 2 x 1G RJ-45 data ports, and 1 x dedicated IPMI RJ-45 port<br>LAN ports include ACT/LINK and SPEED LEDs |
| UID | 1 |

#### Internal Connectors

| Item | Specification |
|---|---|
| Auxiliary panel header | 1; includes chassis intrusion, location button and LED, and front LAN LED |
| TPMS header | 1 |
| IPMB header | 1 |
| Fan headers | 6 fans x 4-pin |
| ATX power | 2 x 8-pin + 1 x 4-pin |
| SATA power | 1 x 4-pin |
| USB 3.2 Gen1 header | 1; supports 2 USB 3.2 Gen1 ports |
| M.2 | 2 (M2_1: Type 2280; M2_2: Type 2260; supports SATA x1 or PCIe x4) |
| Slimline | 3 (SLIM1 and SLIM2: PCIe x8 or SATA Gen3 x8; SLIM3: PCIe x8) |
| Mini-SAS HD | 2 (MSAS_HD0: SATA Gen3 x8; MSAS_HD1: SATA Gen3 x4) |
| SMBus from BMC | 1 |
| PSU SMB | 1 |
| NMI button | 1 |
| SGPIO headers | 3 |
| Thermal sensor header | 1 |
| Speaker (4-pin) | 1 |
| Clear CMOS | 1 short pad |
| CPU_HSBP1 | 1 |
| Front LAN LED | 1 |
| OH/FanFail LEDs | 6; fan-fail indication only |
| COM header | 1 |
| Panel header | 1 |

#### System BIOS

| Item | Specification |
|---|---|
| BIOS type | 32 MB AMI UEFI Legal BIOS |
| BIOS features | Plug and Play (PnP)<br>ACPI 2.0-compliant wake-up events<br>SMBIOS 2.8 support<br>ASRock Rack Instant Flash |

#### Hardware Monitor

| Item | Specification |
|---|---|
| Temperature | CPU temperature sensing<br>Motherboard/card-side/TR1 temperature sensing |
| Fan | Fan tachometer<br>CPU Quiet Fan (allows automatic CPU fan-speed adjustment based on CPU temperature)<br>Fan multi-speed control |
| Voltage | Monitoring for +12 V, +5 V, +3.3 V, CPU Vcore, DRAM, +BAT, 3VSB, and 5VSB |

#### Supported Operating Systems

| Platform | Supported versions |
|---|---|
| Microsoft® Windows® | Server 2016 (64-bit)<br>Server 2019 (64-bit) |
| Linux® | Red Hat Enterprise Linux Server 8.0 (64-bit) / 7.6 (64-bit)<br>CentOS 8.0 (64-bit) / 7.6 (64-bit)<br>SUSE SLES 15.1 (64-bit) / 12.4 (64-bit)<br>Ubuntu 18.04.3 (64-bit) / 16.04.6 (64-bit)<br>Citrix Hypervisor 8.1.0 |
| Virtualization | VMware ESXi 6.5 U3 / 6.7 U3<br>vSphere 6.5 U3 / 6.7 U3 |

> **Note:** Refer to the ASRock Rack website for the latest OS support list.

#### Environment

| Item | Specification |
|---|---|
| Temperature | Operating: 10°C to 35°C<br>Non-operating: -40°C to 70°C |

> **Note:** Refer to the ASRock Rack website for the latest specifications.

> **Wake-on-LAN:** This motherboard supports wake from onboard LAN. To use this function, enable **Wake on Magic Packet from power off state** under `Device Manager > Intel® Ethernet Connection > Power Management`, then enable **PCI Devices Power On** under `UEFI Setup Utility > Advanced > ACPI Configuration`. Afterward, onboard LAN1 and LAN4 can wake the system from S5 under the operating system.

> **WHQL certification:** If you install the Intel® LAN utility or Marvell SATA utility, this motherboard may fail Windows® Hardware Quality Lab (WHQL) certification tests. Installing only the drivers allows it to pass the WHQL tests.

### 1.3 Unique Features

ASRock Rack Instant Flash is a BIOS flash utility embedded in Flash ROM. This convenient BIOS update tool lets you update the system BIOS without first entering an operating system such as MS-DOS or Windows®. Press **F6** during POST, or press **F2** to enter the BIOS setup menu and access ASRock Rack Instant Flash.

Launch the tool and save the new BIOS file to a USB flash drive, floppy disk, or hard drive. You can then update the BIOS in a few clicks without preparing an additional floppy diskette or another complicated flash utility. The USB flash drive or hard drive must use a FAT32, FAT16, or FAT12 file system.

### 1.4 Motherboard Layout

![ROMED6U-2L2T motherboard layout, top view](ROMED6U-2L2T_User_Manual.assets/motherboard-layout-top.png)

![ROMED6U-2L2T motherboard layout, bottom view](ROMED6U-2L2T_User_Manual.assets/motherboard-layout-bottom.png)

#### Top View - Text Transcription

> The original figure is a spatial motherboard drawing. The following transcription preserves its dimensions, visible labels, and numbered callouts; it does not reproduce exact physical spacing.

- **Board dimensions:** 24.4 cm (9.6 in) x 24.4 cm (9.6 in)
- **Model marking:** ROMED6U-2L2T
- **Rear I/O edge:** UID1; USB 3.2 Gen1 (`T: USB2`, `B: USB1`); IPMI_LAN; LAN3; LAN4; VGA1; LAN1; LAN2
- **Top-edge power and control:** ATX12V2; ATX12V1; ATX4PIN1; BATTERY1; PSU_SMB1; PWM_CFG1
- **Fan connectors:** FAN1, FAN2, and FAN3 along the top edge; FAN4, FAN5, and FAN6 along the right edge
- **Processor and memory:** LGA4094 Socket SP3; DDR4_H1, DDR4_G1, and DDR4_E1 above the socket; DDR4_A1, DDR4_C1, and DDR4_D1 below the socket. Each slot is labeled as a 64-bit, 288-pin module.
- **Controllers and firmware:** Intel X710-AT2; two Intel I210-AT2 controllers; ASPEED AST2500; Super I/O; BIOS ROM; BMC ROM
- **Expansion and storage:** PCIE7; PCIE6; PCIE5; PCIE4; M2_1 with NUT80; SLIM3; SLIM2; SLIM1; SATA1; SATA0; SATA_PWR1; MSAS_HD0; MSAS_HD1
- **Bottom-edge headers and controls:** NMI_BTN1; IPMB_1; BMC_SMB1; AUX_PANEL1; TR1; TPMS1; COM1; USB3_3_4; LED_LAN3_4; CLRMOS1; SATA_SGPIO1; SATA_SGPIO2; SATA_SGPIO3; SPEAKER1; PANEL1; CPU_HSBP1 (listed as CPU1_HSBP1 in the component reference). The panel drawing also labels `HDLED`, `RESET`, `PLED`, and `PWRBTN`; pin-1 markers are shown for applicable headers.

#### Bottom View - Text Transcription

The bottom view shows callout **39**, the `M2_2` socket, and its `NUT60_2` mounting point.

#### Component Reference

| No. | Description |
|---:|---|
| 1 | ATX 12 V Power Connector (ATX12V2) |
| 2 | ATX 12 V Power Connector (ATX12V1) |
| 3 | ATX 4-pin Power Connector (ATX4PIN1)[^ch1-layout-power] |
| 4 | PSU SMBus Header (PSU_SMB1) |
| 5 | PWM Configuration Header (PWM_CFG1) |
| 6 | System Fan Connector (FAN1) |
| 7 | System Fan Connector (FAN2) |
| 8 | System Fan Connector (FAN3) |
| 9 | System Fan Connector (FAN4) |
| 10 | System Fan Connector (FAN5) |
| 11 | System Fan Connector (FAN6) |
| 12 | 3 x 288-pin DDR4 DIMM Slots (DDR4_E1, DDR4_G1, DDR4_H1)[^ch1-layout-dimm] |
| 13 | 3 x 288-pin DDR4 DIMM Slots (DDR4_A1, DDR4_C1, DDR4_D1)[^ch1-layout-dimm] |
| 14 | SATA Power Connector, DC-IN Mode (`SATA_PWR1`; printed as `SATAPWR1` in the source component list)[^ch1-layout-power] |
| 15 | M.2 Socket (M2_1), Type 2280 |
| 16 | Slimline NVMe Connector (SLIM3) |
| 17 | Slimline NVMe Connector (SLIM2) |
| 18 | Slimline NVMe Connector (SLIM1), right-angled |
| 19 | SATA3 Connector (SATA1) |
| 20 | Mini-SAS HD Connector (MSAS_HD0), right-angled |
| 21 | Mini-SAS HD Connector (MSAS_HD1), right-angled |
| 22 | Speaker Header (SPEAKER1) |
| 23 | System Panel Header (PANEL1) |
| 24 | Backplane PCI Express Hot-Plug Connector (CPU1_HSBP1) |
| 25 | SATA SGPIO Connector (SATA_SGPIO3) |
| 26 | SATA SGPIO Connector (SATA_SGPIO2) |
| 27 | SATA SGPIO Connector (SATA_SGPIO1) |
| 28 | SATA3 Connector (SATA0) |
| 29 | Front LAN LED Connector (LED_LAN3_4) |
| 30 | USB 3.2 Gen1 Header (USB3_3_4), right-angled |
| 31 | Clear CMOS Pad (CLRMOS1) |
| 32 | COM Port Header (COM1) |
| 33 | TPMS Header (TPMS1) |
| 34 | Thermal Sensor Header (TR1) |
| 35 | Auxiliary Panel Header (AUX_PANEL1) |
| 36 | BMC SMBus Header (BMC_SMB1) |
| 37 | Intelligent Platform Management Bus Header (IPMB_1) |
| 38 | Non-Maskable Interrupt Button (NMI_BTN1) |
| 39 | M.2 Socket (M2_2), Type 2260 |

[^ch1-layout-dimm]: For DIMM installation and configuration instructions, see [Section 2.4, "Installation of Memory Modules (DIMM)"](#24-installation-of-memory-modules-dimm).
[^ch1-layout-power]: **Caution:** A misconnection between the ATX4PIN1 and SATA_PWR1 connectors may permanently damage the motherboard.

### 1.5 Onboard LED Indicators

![Locations of the onboard LED indicators](ROMED6U-2L2T_User_Manual.assets/onboard-led-layout.png)

#### Location Drawing - Text Transcription

> The original figure shows the eight LED locations on the motherboard. Its visible board labels are `DDR4_H1`, `DDR4_G1`, `DDR4_E1`, `DDR4_A1`, `DDR4_C1`, `DDR4_D1`, `LGA4094 Socket SP3`, and `ROMED6U-2L2T`. Callouts 1 through 6 identify the fan-failure LEDs beside FAN1 through FAN6, callout 7 identifies the BMC heartbeat LED near the lower-left edge, and callout 8 identifies the standby-power LED near the left edge.

| No. | Item | Status | Description |
|---:|---|---|---|
| 1 | FAN_LED1 | Red | FAN1 failed |
| 2 | FAN_LED2 | Red | FAN2 failed |
| 3 | FAN_LED3 | Red | FAN3 failed |
| 4 | FAN_LED4 | Red | FAN4 failed |
| 5 | FAN_LED5 | Red | FAN5 failed |
| 6 | FAN_LED6 | Red | FAN6 failed |
| 7 | BMC_LED1 | Green | BMC heartbeat LED |
| 8 | SB_PWR1 | Green | Standby power ready (`STB PWR ready`) |

### 1.6 I/O Panel

![ROMED6U-2L2T rear I/O panel](ROMED6U-2L2T_User_Manual.assets/io-panel.png)

![LAN port activity, link, and speed LED locations](ROMED6U-2L2T_User_Manual.assets/lan-led-locations.png)

#### Panel Drawing - Text Transcription

From left to right, the rear-panel drawing shows the UID switch; the IPMI LAN port above two USB ports; LAN4 above LAN3; the VGA connector; and LAN2 above LAN1.

| No. | Description |
|---:|---|
| 1 | UID Switch (UID1) |
| 2 | USB 3.2 Gen1 Ports (USB3_1_2) |
| 3 | LAN RJ-45 Port (IPMI_LAN1)[^ch1-ipmi-led] |
| 4 | 1G LAN RJ-45 Port (LAN3)[^ch1-data-led] |
| 5 | 1G LAN RJ-45 Port (LAN4)[^ch1-data-led] |
| 6 | VGA Port (VGA1) |
| 7 | 10G LAN RJ-45 Port (LAN1)[^ch1-data-led] |
| 8 | 10G LAN RJ-45 Port (LAN2)[^ch1-data-led] |

[^ch1-ipmi-led]: Two LEDs sit next to the dedicated IPMI LAN port. See the dedicated IPMI LAN port LED table below.
[^ch1-data-led]: Two LEDs sit on each 1G and 10G LAN port. See the LAN port LED tables below.

#### LAN Port LED Placement - Text Transcription

Each LAN-port drawing labels the two indicators as **ACT/LINK LED** and **SPEED LED**, with the connector labeled **LAN Port**. The dedicated IPMI drawing places ACT/LINK on the left and SPEED on the right. For the stacked 1G/10G ports, the upper port's labels appear above it and the lower port's labels appear below it, with ACT/LINK on the left and SPEED on the right.

#### Dedicated IPMI LAN Port LED Indications

| Activity/Link Status | Activity/Link Description | Speed Status | Speed Description |
|---|---|---|---|
| Off | No link | Off | 10 Mbps connection or no link |
| Blinking yellow | Data activity | Yellow | 100 Mbps connection |
| On | Link | Green | 1 Gbps connection |

#### 1G LAN Port (LAN3, LAN4) LED Indications

| Activity/Link Status | Activity/Link Description | Speed Status | Speed Description |
|---|---|---|---|
| Off | No link | Off | 10 Mbps connection or no link |
| Blinking green | Data activity | Yellow | 100 Mbps connection |
| On | Link | Green | 1 Gbps connection |

#### 10G LAN Port (LAN1, LAN2) LED Indications

| Activity/Link Status | Activity/Link Description | Speed Status | Speed Description |
|---|---|---|---|
| Off | No link | Off | 100 Mbps connection or no link |
| Blinking yellow | Data activity | Yellow | 1 Gbps connection |
| On | Link | Green | 10 Gbps connection |

### 1.7 Block Diagram

![ROMED6U-2L2T system block diagram](ROMED6U-2L2T_User_Manual.assets/block-diagram.png)

> **Text transcription:** The original block diagram uses routed lines and a landscape orientation that cannot be reproduced faithfully in plain Markdown. The tables below preserve its visible component names, CPU port labels, interface widths and generations, endpoint labels, and routing notes.

#### Processor and Memory

| Block | Diagram labels and data |
|---|---|
| Processor | `AMD Family 17h Processor`; `CPU`; `AMD EPYC 700x` |
| Memory | `6 DIMM Slots`; six instances of `1 x DDR4 LRDIMM/RDIMM`; six `R/LRDIMM` links; six CPU-side `DDR4` interfaces, with three shown on each side of the processor |

#### CPU Port and Endpoint Map

| CPU port or group | Endpoint | Link and endpoint labels |
|---|---|---|
| Port G0 | PCIE5 | PCIe Gen4 x16; `PCI Express x16 Riser Slot` |
| Port G1 | PCIE4 | PCIe Gen4 x16; `PCI Express x16 Riser Slot` |
| Port G2.0~3 | MSAS_HD1 | Mini-SAS HD; SATA Gen3 x4 |
| Port G2.4~7 | SATA 7-pin block | SATA Gen3 x2 |
| Port G2.8~15 | M2_1 and M2_2 | M.2 sockets; PCIe Gen4 x4; `support: 1. SATA 2. PCIE` |
| Port G3.0~7 | MSAS_HD0 | Mini-SAS HD; SATA Gen3 x8 |
| Port G3.8~15 | SLIM3 | Slimline connector; PCIe Gen4 x8 |
| Port P0.0~7 and Port P0.8~15 | SLIM1 | Two PCIe x8 groups; SATA Gen3 x8 or PCIe Gen4 x4 x2; `Support: 1. SATA*8 2. NVMe*2` |
| Port P2 | PCIE6 | PCIe x16; PCIe Gen4 x16; `PCI Express x16 Riser Slot` |
| Port P3 | PCIE7 | PCIe x16; PCIe Gen4 x16; `PCI Express x16 Riser Slot` |
| Port P1.0~7 | SLIM2 | PCIe x8; SATA Gen3 x8 or PCIe Gen4 x4 x2; `Support: 1. SATA*8 2. NVMe*2` |
| Port P1.8~11 | Intel X710-AT2 | PCIe x4; PCIe Gen3 x4 |
| Port P1.12 | ASPEED AST2500 | PCIe Gen3 x1 to the BMC's PCI-Express interface |
| Port P1.13 | First Intel I210-AT2 | PCIe x1; PCIe Gen3 x1 |
| Port P1.14 | Second Intel I210-AT2 | PCIe x1; PCIe Gen3 x1 |

#### SATA SGPIO Configuration

- SLIM1 uses `SGPIO_0`.
- SLIM2 uses `SGPIO_1`.
- `SATA_8_11`, `SATA12`, and `SATA13` use `SGPIO_2`.
- `SATA_0_7` uses `SGPIO_3`.

#### Network Paths

| Controller or PHY | Diagram routing and labels |
|---|---|
| Intel X710-AT2 | `10G`; two RJ-45 ports; PCIe Gen3 x4; red `NCSI` path to the AST2500 MAC2 path |
| Intel I210-AT2 x2 | `1G`; two RJ-45 ports; two PCIe Gen3 x1 links; red `Resistance Option` path to the AST2500 MAC2 path |
| Realtek RTL8211E | `10/100/1G PHY`; connected to the AST2500 `MAC1` / `Ethernet 10/100/1000` block and to the dedicated LAN-port drawing |

#### BMC and Peripheral Paths

| Source or block | Destination and visible labels |
|---|---|
| CPU USB 3.2 | `USB 3.2 GEN1` to `F_USB1` and the rear USB 3.2 port drawing |
| CPU PCIe | `PCIE Gen3 x1`, `P1.12`, to the AST2500 `PCI-Express` interface |
| CPU USB/LPC | `USB2.0 x2`; `LPC`; `TPM 2.0`; `SIO NCT6779`; AST2500 `LPC` and `USB 1.1 & 2.0` interfaces |
| ASPEED AST2500 MAC1 | `Ethernet 10/100/1000` to Realtek RTL8211E `10/100/1G PHY` and the dedicated LAN-port drawing |
| ASPEED AST2500 Video DAC | VGA connector |
| ASPEED AST2500 BMC & VRAM | DDR4 DRAM (512 MB) |
| ASPEED AST2500 BMC SPI | SPI flash (512 Mb) |
| ASPEED AST2500 MAC2 | `Ethernet 10/100/1000`; receives the diagram's red `NCSI` / `Resistance Option` routing from the Intel LAN controllers |

> **Source clarification:** The specifications table lists 256 MB of VRAM, while the block diagram labels a 512 MB DDR4 DRAM device connected to the combined `BMC & VRAM` block. The PDF does not explain whether 256 MB is a graphics allocation within that physical BMC memory, so both source values are retained.

---

## Chapter 2: Installation

The ROMED6U-2L2T is a microATX motherboard measuring 9.6 x 9.6 in
(24.4 x 24.4 cm). Before installing it, study the chassis configuration and
confirm that the motherboard will fit.

> **Warning:**
> Unplug the power cord before installing or removing the motherboard. Failure
> to do so may cause physical injury and damage motherboard components.


### 2.1 Screw Holes

Place screws into the holes indicated by circles to secure the motherboard to
the chassis.

> **Caution:**
> Do not overtighten the screws. Doing so may damage the motherboard.

### 2.2 Pre-installation Precautions

Before installing motherboard components or changing motherboard settings:

1. Unplug the power cord from the wall socket before touching any components.
2. To avoid static-electricity damage, never place the motherboard directly on
   carpet or a similar surface. Wear a grounded wrist strap or touch a safely
   grounded object before handling components.
3. Hold components by their edges. Do not touch the integrated circuits (ICs).
4. When removing a component, place it on a grounded anti-static pad or in the
   anti-static bag supplied with the component.
5. Do not overtighten the screws used to secure the motherboard to the chassis.
   Doing so may damage the motherboard.

> **Warning:**
> Before installing or removing any component, make sure that the power is
> switched off or that the power cord is disconnected from the power supply.
> Failure to do so may severely damage the motherboard, peripherals, and/or
> components.

### 2.3 Installing the CPU

![CPU installation steps, figure 1 of 4](ROMED6U-2L2T_User_Manual.assets/cpu-installation-1.png)

![CPU installation steps, figure 2 of 4](ROMED6U-2L2T_User_Manual.assets/cpu-installation-2.png)

![CPU installation steps, figure 3 of 4](ROMED6U-2L2T_User_Manual.assets/cpu-installation-3.png)

![CPU installation steps, figure 4 of 4](ROMED6U-2L2T_User_Manual.assets/cpu-installation-4.png)

> **Caution:**
> 1. Before inserting the CPU, check whether the PnP cap is still on the socket,
>    the CPU surface is unclean, or any socket pins are bent. If any of these
>    conditions exists, do not force the CPU into the socket. Otherwise, the CPU
>    may be seriously damaged.
> 2. Unplug all power cables before installing the CPU.

**Figure sequence: CPU installation (steps 1-8)**

1. Loosen the three socket screws with a screwdriver in the illustrated order:
   **A**, **B**, then **C**.
2. Lift the first hinged socket frame upward, as shown.
3. Lift the second hinged frame upward, as shown.
4. Slide the illustrated carrier assembly upward and away from the socket.
5. Insert the **carrier frame with CPU** into the **rail frame**. Make sure that
   the carrier frame with CPU stays closely attached to the rail frame while it
   is inserted.

   > **Caution:**
   > Install the carrier frame with the CPU. Do not separate them.

6. Lower the carrier and rail-frame assembly toward the socket.
7. Lower the remaining hinged socket frame.
8. Tighten the three socket screws in the illustrated order:
   **A**, **B**, then **C**.

### 2.4 Installation of Memory Modules (DIMM)

![DDR4 DIMM installation sequence](ROMED6U-2L2T_User_Manual.assets/dimm-installation.png)

The motherboard provides six 288-pin DDR4 (Double Data Rate 4) DIMM slots in
two groups and supports Six Channel Memory Technology.

#### DIMM population order

| Installed DIMMs | A1 | C1 | D1 | E1 | G1 | H1 |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 |  | ✓ |  |  |  |  |
| 2 |  | ✓ | ✓ |  |  |  |
| 4 |  | ✓ | ✓ |  | ✓ | ✓ |
| 6 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

> **Caution:**
> 1. Do not install a DDR, DDR2, or DDR3 memory module in a DDR4 slot. Doing so
>    may damage both the motherboard and the DIMM.
> 2. For a dual-channel configuration, install identical DDR4 DIMM pairs. The
>    paired modules must have the same brand, speed, size, and chip type.
> 3. Dual Channel Memory Technology cannot be activated with only one or three
>    memory modules installed.
> 4. Some double-sided 1 GB DDR4 DIMMs with 16 chips may not work on this
>    motherboard and are not recommended.

**Figure sequence: DIMM installation (steps 1-3)**

1. Open both retaining clips outward.
2. Align the DIMM notch with the keyed slot, then insert the DIMM straight down.
3. Close both retaining clips around the installed DIMM.

> **Warning:**
> A DIMM fits in only one orientation. Forcing it into the slot in the wrong
> orientation will permanently damage both the motherboard and the DIMM.

### 2.5 Expansion Slots (PCI Express Slots)

The motherboard has four PCI Express slots. PCIE7, PCIE6, PCIE5, and PCIE4 are
PCIe 4.0 x16 slots connected to the CPU and support PCI Express cards with an
x16 lane width.

| Slot | Generation | Mechanical | Electrical | Source |
|---|:---:|:---:|:---:|:---:|
| PCIE7 | 4.0 | x16 | x16 | CPU |
| PCIE6 | 4.0 | x16 | x16 | CPU |
| PCIE5 | 4.0 | x16 | x16 | CPU |
| PCIE4 | 4.0 | x16 | x16 | CPU |

#### Installing an expansion card

1. Make sure that the power supply is switched off or the power cord is
   unplugged. Read the expansion card's documentation and make any necessary
   hardware settings before starting the installation.
2. Remove the system-unit cover if the motherboard is already installed in a
   chassis.
3. Remove the bracket facing the slot you intend to use. Keep the screws for
   later use.
4. Align the card connector with the slot and press firmly until the card is
   fully seated.
5. Fasten the card to the chassis with screws.
6. Replace the system cover.

### 2.6 Onboard Headers and Connectors

> **Warning:**
> Onboard headers and connectors are **not jumpers**. Do not place jumper caps
> over them. Doing so will permanently damage the motherboard.

#### Connector index

- [System Panel Header](#system-panel-header-panel1)
- [Auxiliary Panel Header](#auxiliary-panel-header-aux_panel1)
- [Serial ATA3 Connectors](#serial-ata3-connectors-sata0-and-sata1)
- [USB 3.2 Gen1 Header](#usb-32-gen1-header-usb3_3_4)
- [Chassis Speaker Header](#chassis-speaker-header-speaker1)
- [System Fan Connectors](#system-fan-connectors-fan1-fan6)
- [Mini-SAS HD Connectors](#mini-sas-hd-connectors-msas_hd0-and-msas_hd1)
- [Slimline NVMe Connectors](#slimline-nvme-connectors-slim1-slim3)
- [Serial Port Header](#serial-port-header-com1)
- [ATX 4-pin Power Connector](#atx-4-pin-power-connector-atx4pin1)
- [SATA Power Connector](#sata-power-connector-sata_pwr1)
- [ATX 12V Power Connectors](#atx-12v-power-connectors-atx12v1-and-atx12v2)
- [Clear CMOS Pads](#clear-cmos-pads-clrmos1)
- [Front LAN LED Header](#front-lan-led-header-led_lan3_4)
- [TPMS Header](#tpms-header-tpms1)
- [PSU SMBus Header](#psu-smbus-header-psu_smb1)
- [Intelligent Platform Management Bus Header](#intelligent-platform-management-bus-header-ipmb_1)
- [Thermal Sensor Header](#thermal-sensor-header-tr1)
- [Non-Maskable Interrupt Button Header](#non-maskable-interrupt-button-header-nmi_btn1)
- [Serial General Purpose Input/Output Headers](#serial-general-purpose-inputoutput-headers-sata_sgpio1-sata_sgpio3)
- [Baseboard Management Controller SMBus Header](#baseboard-management-controller-smbus-header-bmc_smb1)
- [PWM Configuration Header](#pwm-configuration-header-pwm_cfg1)
- [CPU HP-SMBus Connector](#cpu-hp-smbus-connector-cpu1_hsbp1)

Unless otherwise noted, the pin tables below follow the pin-1 marker and
orientation printed in the source diagrams. A dash (`-`) denotes an unpopulated
position or key.

#### System Panel Header (PANEL1)

**Connector:** 9-pin `PANEL1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
23.

Connect the chassis power switch, reset switch, and system-status indicators to
this header according to the pin assignments. Pay particular attention to
positive and negative pins before connecting cables.

| Pin | Signal | Pin | Signal |
|---:|---|---:|---|
| 1 | `HDLED+` | 2 | `PLED+` |
| 3 | `HDLED-` | 4 | `PLED-` |
| 5 | `GND` | 6 | `PWRBTN#` |
| 7 | `RESET#` | 8 | `GND` |
| 9 | `GND` |  |  |

- **PWRBTN (Power Switch):** Connect to the power switch on the chassis front
  panel. You may configure how the system turns off when the power switch is
  used.
- **RESET (Reset Switch):** Connect to the reset switch on the chassis front
  panel. Press it to restart the computer if the computer freezes and cannot
  perform a normal restart.
- **PLED (System Power LED):** Connect to the power-status indicator on the
  chassis front panel. The LED is on while the system is operating. It is off
  when the system is in the S4 sleep state or powered off (S5).
- **HDLED (Hard Drive Activity LED):** Connect to the hard-drive activity LED on
  the chassis front panel. The LED is on while the hard drive is reading or
  writing data.

Front-panel designs differ by chassis. A front-panel module usually includes a
power switch, reset switch, power LED, hard-drive activity LED, speaker, and
other components. Make sure the module's wire assignments match the header's
pin assignments.

#### Auxiliary Panel Header (AUX_PANEL1)

**Connector:** 18-pin `AUX_PANEL1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
35.

This header supports several front-panel functions, including the front-panel
SMBus, internet-status indicators, and chassis-intrusion input.

The source figure shows a two-row, ten-position footprint. Pin 1 is at the
bottom-left; two positions are unpopulated. The contacts are arranged as
follows:

| Diagram row | Positions from left to right |
|---|---|
| Top | `SMB_Alert`, `SMB_CLK`, -, `GND`, `SMB_DATA`, `+3VSB`, `LAN1_LINK`, `LED_PWR`, `LED_PWR`, `LAN2_LINK` |
| Bottom | `+5VSB`, -, `CASEOPEN`, `GND`, `LOCATORLED1+`, `LOCATORLED1-`, `LOCATORBTN#`, `GND`, `LOCATORLED2-`, `LOCATORLED2+` |

The figure divides the header into these functions:

**A. Front-panel SMBus connecting pin (6-1 pin FPSMB)**

Connect SMBus (System Management Bus) equipment here. The SMBus supports
communication between slower peripheral equipment and power-management
equipment in the system.

**B. Internet-status indicators (2-pin LAN1_LED and LAN2_LED)**

These two 2-pin headers accept Gigabit internet-indicator cables for the LAN
status indicators. A flickering indicator means that the internet connection is
working properly.

**C. Chassis-intrusion pin (2-pin CHASSIS)**

This input is for a chassis with an intrusion-detection design. It must be used
with external detection equipment, such as an intrusion sensor or microswitch.
When enabled, movement of a chassis component causes the sensor to signal this
header, and the system records a chassis-intrusion event. By default,
`CASEOPEN` is connected to `GND`, so the function is off.

**D. Locator LED (4-pin LOCATOR)**

This connection is for the front-panel locator switch and LED.

**E. System Fault LED (2-pin LOCATOR)**

This connection is for the system fault LED.

#### Serial ATA3 Connectors (SATA0 and SATA1)

| Connector | Chapter 1 component reference |
|---|---|
| `SATA0` | [Item 28](#component-reference) |
| `SATA1` | [Item 19](#component-reference) |

These two SATA3 connectors accept SATA data cables for internal storage devices
and support transfer rates up to 6.0 Gb/s.

#### USB 3.2 Gen1 Header (USB3_3_4)

**Connector:** Right-angled, 19-pin `USB3_3_4`  
**Board location:** [Chapter 1 component reference](#component-reference), item
30.

In addition to the two USB 3.2 Gen1 ports on the I/O panel, the motherboard has
one USB 3.2 Gen1 header. It supports two USB 3.2 Gen1 ports.

| Pin | Signal | Pin | Signal |
|---:|---|---:|---|
| 1 | `Dummy` | 2 | `IntA_PA_D+` |
| 3 | `IntA_PB_D+` | 4 | `IntA_PA_D-` |
| 5 | `IntA_PB_D-` | 6 | `GND` |
| 7 | `GND` | 8 | `IntA_PA_SSTX+` |
| 9 | `IntA_PB_SSTX+` | 10 | `IntA_PA_SSTX-` |
| 11 | `IntA_PB_SSTX-` | 12 | `GND` |
| 13 | `GND` | 14 | `IntA_PA_SSRX+` |
| 15 | `IntA_PB_SSRX+` | 16 | `IntA_PA_SSRX-` |
| 17 | `IntA_PB_SSRX-` | 18 | `Vbus` |
| 19 | `Vbus` |  |  |

#### Chassis Speaker Header (SPEAKER1)

**Connector:** 4-pin `SPEAKER1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
22.

Connect the chassis speaker to this header.

| Pin | Signal |
|---:|---|
| 1 | `+5V` |
| 2 | `DUMMY` |
| 3 | `DUMMY` |
| 4 | `SPEAKER` |

#### System Fan Connectors (FAN1-FAN6)

| Connector | Chapter 1 component reference |
|---|---|
| 4-pin `FAN1` | [Item 6](#component-reference) |
| 4-pin `FAN2` | [Item 7](#component-reference) |
| 4-pin `FAN3` | [Item 8](#component-reference) |
| 4-pin `FAN4` | [Item 9](#component-reference) |
| 4-pin `FAN5` | [Item 10](#component-reference) |
| 4-pin `FAN6` | [Item 11](#component-reference) |

Connect fan cables to these headers and match each cable's black wire to the
ground pin. All fans support fan control.

| Pin | Signal |
|---:|---|
| 1 | `GND` |
| 2 | `FAN_VOLTAGE` |
| 3 | `FAN_SPEED` |
| 4 | `FAN_SPEED_CONTROL` |

#### Mini-SAS HD Connectors (MSAS_HD0 and MSAS_HD1)

| Connector | Orientation | Chapter 1 component reference |
|---|---|---|
| `MSAS_HD0` | Right-angled | [Item 20](#component-reference) |
| `MSAS_HD1` | Right-angled | [Item 21](#component-reference) |

These connectors accept Mini-SAS-to-SATA data cables for internal storage
devices and support transfer rates up to 6.0 Gb/s.

#### Slimline NVMe Connectors (SLIM1-SLIM3)

| Connector | Orientation | Chapter 1 component reference |
|---|---|---|
| `SLIM1` | Right-angled | [Item 18](#component-reference) |
| `SLIM2` | Vertical | [Item 17](#component-reference) |
| `SLIM3` | Vertical | [Item 16](#component-reference) |

These connectors are used for NVMe PCIe devices.

#### Serial Port Header (COM1)

**Connector:** 9-pin `COM1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
32.

This COM header supports a serial-port module.

| Pin | Signal | Pin | Signal |
|---:|---|---:|---|
| 1 | `DDCD#1` | 2 | `RRXD1` |
| 3 | `TTXD1` | 4 | `DDTR#1` |
| 5 | `GND` | 6 | `DDSR#1` |
| 7 | `RRTS#1` | 8 | `CCTS#1` |
| 9 | `RRI#1` |  |  |

#### ATX 4-pin Power Connector (ATX4PIN1)

**Connector:** 4-pin `ATX4PIN1` (ATX 24-pin-to-4-pin)  
**Board location:** [Chapter 1 component reference](#component-reference), item
3.

The motherboard provides one 4-pin power/signal connector. It is a required
input when using an ATX power source. Use the bundled 24-pin-to-4-pin power
cable between the PSU's 24-pin power connector and `ATX4PIN1` for power and
signal communication.

For a 12 V DC-IN application, this connector is not required.

| Pin | Signal |
|---:|---|
| 1 | `ATX_PWROK` |
| 2 | `GND` |
| 3 | `ATX_+5VSB` |
| 4 | `PSON#` |

> **Caution:**
> Connecting `ATX4PIN1` and `SATA_PWR1` incorrectly may permanently damage the
> motherboard.

#### SATA Power Connector (SATA_PWR1)

**Mode:** DC-IN  
**Connector:** 4-pin `SATA_PWR1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
14.

When using DC-IN mode without a SATA power supply, use a SATA power cable to
connect this motherboard connector to the SATA hard drive. This supplies drive
power from the motherboard.

| Pin | Signal |
|---:|---|
| 1 | `GND` |
| 2 | `GND` |
| 3 | `+12V` |
| 4 | `+5V` |

> **Caution:**
> Connecting `ATX4PIN1` and `SATA_PWR1` incorrectly may permanently damage the
> motherboard.

#### ATX 12V Power Connectors (ATX12V1 and ATX12V2)

| Connector | Chapter 1 component reference |
|---|---|
| 8-pin `ATX12V1` | [Item 2](#component-reference) |
| 8-pin `ATX12V2` | [Item 1](#component-reference) |

The motherboard provides two required 8-pin, 12 V power inputs for either a
12 V DC-IN source or an ATX +12 V source.

| Pins | Signal |
|---:|---|
| 1-4 | `GND` |
| 5-8 | `12V` |

When using ATX power, also connect the PSU's 24-pin connector to `ATX4PIN1`
with the bundled 24-pin-to-4-pin cable for power and signal communication.

#### Clear CMOS Pads (CLRMOS1)

**Board location:** [Chapter 1 component reference](#component-reference), item
31.

These pads allow you to clear the data in CMOS. To clear CMOS, remove the CMOS
battery and short the Clear CMOS Pad.

#### Front LAN LED Header (LED_LAN3_4)

**Connector:** 4-pin `LED_LAN3_4`  
**Board location:** [Chapter 1 component reference](#component-reference), item
29.

This connector is used for the front LAN status indicator.

| Pin | Signal |
|---:|---|
| 1 | `LAN3_LINK` |
| 2 | `LED_PWR` |
| 3 | `LED_PWR` |
| 4 | `LAN4_LINK` |

#### TPMS Header (TPMS1)

**Connector:** 17-pin `TPMS1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
33.

This connector supports a Trusted Platform Module (TPM), which can securely
store keys, digital certificates, passwords, and data. A TPM also helps enhance
network security, protect digital identities, and ensure platform integrity.

The source diagram is a two-row, nine-position footprint with one key position.
Pin 1 is at the far right of the top row.

| Diagram row | Positions from left to right |
|---|---|
| Top | `GND`, `+3VSB`, -, `LAD0`, `+3V`, `LAD3`, `PCIRST#`, `LFRAME#`, `PCICLK` (pin 1) |
| Bottom | `GND`, `SERIRQ#`, `S_PWRDWN#`, `GND`, `LAD1`, `LAD2`, `SMB_DATA_MAIN`, `SMB_CLK_MAIN`, `GND` |

#### PSU SMBus Header (PSU_SMB1)

**Connector:** 5-pin `PSU_SMB1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
4.

The PSU SMBus monitors the status of the power supply, fan, and system
temperature.

| Pin | Signal |
|---:|---|
| 1 | `SMBCLK` |
| 2 | `SMBDATA` |
| 3 | `ALERT` |
| 4 | `GND` |
| 5 | `+3V` |

#### Intelligent Platform Management Bus Header (IPMB_1)

**Connector:** 4-pin `IPMB_1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
37.

This connector provides a cabled baseboard or front-panel connection for
value-added features and third-party add-in cards, such as Emergency Management
cards, that provide management features through the IPMB.

| Diagram position, left to right | Signal |
|---:|---|
| 1 | `IPMB_SDA` |
| 2 | `GND` |
| 3 | `IPMB_SCL` |
| 4 | No Connect |

#### Thermal Sensor Header (TR1)

**Connector:** 3-pin `TR1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
34.

Connect the thermal-sensor cable to either pins 1-2 or pins 2-3, then connect
the other end to the device whose temperature you want to monitor.

| Pin | Signal |
|---:|---|
| 1 | `TR1` |
| 2 | `GND` |
| 3 | `TR1` |

#### Non-Maskable Interrupt Button Header (NMI_BTN1)

**Connector:** `NMI_BTN1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
38.

Connect an NMI device to this header.

| Pin | Signal |
|---:|---|
| 1 | `CONTROL` |
| 2 | `GND` |

#### Serial General Purpose Input/Output Headers (SATA_SGPIO1-SATA_SGPIO3)

| Connector | Chapter 1 component reference |
|---|---|
| 7-pin `SATA_SGPIO1` | [Item 27](#component-reference) |
| 7-pin `SATA_SGPIO2` | [Item 26](#component-reference) |
| 7-pin `SATA_SGPIO3` | [Item 25](#component-reference) |

These headers support the Serial Link interface for onboard SATA connections.

The source diagram is a two-row, four-position footprint with pin 1 at the
bottom-left and no contact at the bottom-right. Two contacts are not labeled in
the source figure.

| Diagram row | Positions from left to right |
|---|---|
| Top | Unlabeled, `GND`, `SLOAD`, `SCLOCK` |
| Bottom | Unlabeled (pin 1), `SDATAOUT`, `GND`, - |

#### Baseboard Management Controller SMBus Header (BMC_SMB1)

**Connector:** 5-pin `BMC_SMB1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
36.

This header is used for SMBus devices.

| Pin | Signal |
|---:|---|
| 1 | `BMC_SMBDATA` |
| 2 | `GND` |
| 3 | `BMC_SMBCLK` |
| 4 | `Power` |
| 5 | `BMC_SMB_PRESENT_1_N` |

#### PWM Configuration Header (PWM_CFG1)

**Connector:** 3-pin `PWM_CFG1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
5.

This header is used for PWM configuration.

| Pin | Signal |
|---:|---|
| 1 | `GND` |
| 2 | `SMB_DATA_VSB` |
| 3 | `SMB_CLK_VSB` |

#### CPU HP-SMBus Connector (CPU1_HSBP1)

**Connector:** 5-pin `CPU1_HSBP1`  
**Board location:** [Chapter 1 component reference](#component-reference), item
24.

This header supports the hot-plug feature for hard drives on the backplane.

| Pin | Signal |
|---:|---|
| 1 | `+3V` |
| 2 | `CPU_HP_SCL` |
| 3 | `CPU_HP_SDA` |
| 4 | `P0_HP_ALERT_L` |
| 5 | `GND` |

#### Original Connector Diagrams

![Onboard header and connector diagrams, sheet 1 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-1.png)

![Onboard header and connector diagrams, sheet 2 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-2.png)

![Onboard header and connector diagrams, sheet 3 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-3.png)

![Onboard header and connector diagrams, sheet 4 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-4.png)

![Onboard header and connector diagrams, sheet 5 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-5.png)

![Onboard header and connector diagrams, sheet 6 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-6.png)

![Onboard header and connector diagrams, sheet 7 of 7](ROMED6U-2L2T_User_Manual.assets/connector-diagrams-7.png)

### 2.7 ATX PSU / DC-IN Power Connections

![DC-IN and ATX PSU connection diagrams](ROMED6U-2L2T_User_Manual.assets/power-connections.png)

The motherboard supports both +12 V DC and ATX power input. Use the following
connections between the motherboard and the power supply.

| Connector | DC-IN | ATX PSU |
|---|:---:|:---:|
| `ATX12V1` and `ATX12V2` (8-pin) | Connect both | Connect both |
| ATX 4-pin | Do not connect | Connect with the bundled ATX 24-pin-to-4-pin converter cable |

**Figure transcription: power-source connections**

- **DC-IN:** Connect the PSU to both motherboard 12 V 8-pin inputs (`ATX12V1`
  and `ATX12V2`).
- **ATX PSU:** Connect the PSU to both motherboard 12 V 8-pin inputs. Also use
  the bundled 24-pin-to-4-pin converter cable to connect the PSU's 24-pin output
  to the motherboard's ATX 4-pin input.

**Figure transcription: bundled ATX converter cable**

1. Connect the PSU's 24-pin plug to the 24-pin socket on the bundled converter
   cable.
2. Connect the converter cable's 4-pin plug to the motherboard's ATX 4-pin
   socket.

> **Caution:**
> Make sure that the latch and socket are aligned in the correct direction.

### 2.8 Unit Identification Purpose LED/Switch

The Unit Identification (UID) button helps you locate the server you are working
on from behind a rack of servers.

**Control:** Unit Identification purpose LED/Switch (`UID1`)

Press the UID button on the front or rear panel to turn on the blue front/rear
UID LED. Press the button again to turn off the indicator.

### 2.9 Driver Installation Guide

1. Insert the support CD into the optical drive.
2. Open the support CD's driver page. Drivers compatible with the system are
   detected and listed automatically.
3. Install the required drivers in the displayed order, from top to bottom, so
   that they work properly.

### 2.10 M.2 SSD (NGFF) Module Installation Guide

![M.2 SSD module installation sequence](ROMED6U-2L2T_User_Manual.assets/m2-installation.png)

M.2, also known as Next Generation Form Factor (NGFF), is a compact and
versatile card-edge connector intended to replace mPCIe and mSATA. This M.2 SSD
(NGFF) Socket 3 supports either a SATA3 6.0 Gb/s module or a PCI Express module
up to Gen4 x4 (64 Gb/s).

#### Installing the M.2 SSD (NGFF) module

1. Prepare an M.2 SSD (NGFF) module and the screw.
2. Gently insert the M.2 SSD into the M.2 slot at the illustrated 20-degree
   angle. The module fits in only one orientation. Lower it toward the mounting
   point after it is fully inserted.
3. Tighten the screw with a screwdriver to secure the module.

> **Caution:**
> Do not overtighten the screw. Doing so may damage the module.

**Figure sequence:** Step 1 shows the module and retaining screw. Step 2 shows
the module entering the keyed socket at 20 degrees and then lowering toward the
standoff. Step 3 shows the retaining screw being installed.

#### M.2 SSD (NGFF) module support list

For the latest M.2 SSD (NGFF) module support list, visit
[ASRock Rack](http://www.asrockrack.com).

---

## Chapter 3: UEFI Setup Utility

### 3.1 Introduction

This section explains how to use the UEFI Setup Utility to configure your system. The UEFI chip on the motherboard stores the UEFI Setup Utility. You may run the utility when you start the computer. Press `F2` or `Delete` during the Power-On Self-Test (POST) to enter the UEFI Setup Utility; otherwise, POST will continue with its test routines.

To enter the UEFI Setup Utility after POST, restart the system by pressing `Ctrl` + `Alt` + `Delete`, or press the reset button on the system chassis. You may also restart by turning the system off and then back on.

> **Note:** Because the UEFI software is constantly being updated, the following UEFI setup screens and descriptions are for reference only. They may not exactly match what you see on your screen.

#### 3.1.1 UEFI Menu Bar

The top of the screen has a menu bar with the following selections:

| Item | Description |
|---|---|
| Main | Set the system time and date. |
| Advanced | Set the advanced UEFI features. |
| Server Mgmt | Manage the server. |
| Security | Set the security features. |
| Boot | Set the default system device used to locate and load the operating system. |
| Event Logs | Configure event logging. |
| Exit | Exit the current screen or the UEFI Setup Utility. |

Use the left or right arrow key to move among the menu-bar selections, then press `Enter` to open the selected subscreen.

#### 3.1.2 Navigation Keys

| Navigation key(s) | Function |
|---|---|
| Left arrow / Right arrow | Move the cursor left or right to select screens. |
| Up arrow / Down arrow | Move the cursor up or down to select items. |
| `+` / `-` | Change the option for the selected item. |
| `Tab` | Switch to the next function. |
| `Enter` | Open the selected screen. |
| `Page Up` | Go to the previous page. |
| `Page Down` | Go to the next page. |
| `Home` | Go to the top of the screen. |
| `End` | Go to the bottom of the screen. |
| `F1` | Display the General Help screen. |
| `F7` | Discard changes and exit the UEFI Setup Utility. |
| `F9` | Load optimal default values for all settings. |
| `F10` | Save changes and exit the UEFI Setup Utility. |
| `F12` | Print the screen. |
| `Esc` | Jump to the Exit screen or exit the current screen. |

### 3.2 Main Screen

![UEFI Main screen](ROMED6U-2L2T_User_Manual.assets/uefi-main-screen.png)

Once you enter the UEFI Setup Utility, the Main screen appears and displays a system overview. The Main screen also allows you to set the system time and date.

### 3.3 Advanced Screen

![UEFI Advanced screen](ROMED6U-2L2T_User_Manual.assets/uefi-advanced-screen.png)

> **Warning:** Setting incorrect values in this section may cause the system to malfunction.

In this section, you may configure the following items:

- CPU Configuration
- Chipset Configuration
- Storage Configuration
- ACPI Configuration
- USB Configuration
- Super IO Configuration
- Serial Port Console Redirection
- H/W Monitor
- PCI Subsystem Settings
- AMD CBS
- AMD PBS
- PSP Firmware Versions
- Instant Flash

#### 3.3.1 CPU Configuration

![UEFI CPU Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-cpu-configuration.png)

- **SVM Mode:** Enable or disable CPU virtualization.
- **Node 0 Information:** View memory information related to Node 0.

#### 3.3.2 Chipset Configuration

![UEFI Chipset Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-chipset-configuration.png)

- **OnBrd/Ext VGA Select:** Select onboard or external VGA support.
- **Onboard LAN1:** Enable or disable the Onboard LAN1 feature.
- **Onboard LAN2:** Enable or disable the Onboard LAN2 feature.
- **Onboard LAN3:** Enable or disable the Onboard LAN3 feature.
- **Onboard LAN4:** Enable or disable the Onboard LAN4 feature.
- **SLIM1 Mode:** Configure SLIM1 mode settings.
- **SLIM2 Mode:** Configure SLIM2 mode settings.
- **SLIM1 Link Width:** Select the SLIM1 link width. The default value is `x16`.
- **SLIM2 Link Width:** Select the SLIM2 link width. The default value is `x16`.
- **SLIM3 Link Width:** Select the SLIM3 link width. The default value is `x16`.
- **PCIE4 Link Width:** Select the PCIE4 link width. The default value is `x16`.
- **PCIE5 Link Width:** Select the PCIE5 link width. The default value is `x16`.
- **PCIE6 Link Width:** Select the PCIE6 link width. The default value is `x16`.
- **PCIE7 Link Width:** Select the PCIE7 link width. The default value is `x16`.
- **SLIM1 Link Speed:** Select the SLIM1 link speed. The default value is `Auto`.
- **SLIM2 Link Speed:** Select the SLIM2 link speed. The default value is `Auto`.
- **SLIM3 Link Speed:** Select the SLIM3 link speed. The default value is `Auto`.
- **PCIE4 Link Speed:** Select the PCIE4 link speed. The default value is `Auto`.
- **PCIE5 Link Speed:** Select the PCIE5 link speed. The default value is `Auto`.
- **PCIE6 Link Speed:** Select the PCIE6 link speed. The default value is `Auto`.
- **PCIE7 Link Speed:** Select the PCIE7 link speed. The default value is `Auto`.
- **Onboard Debug Port LED:** Enable or disable the onboard Dr. Debug LED.
- **Restore AC Power Loss:** Set the power state after a power failure. If `Power Off` is selected, the power remains off when power is restored. If `Power On` is selected, the system starts to boot when power is restored.
- **Restore AC Power Current State:** Restore the current AC power state.

#### 3.3.3 Storage Configuration

![UEFI Storage Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-storage-configuration.png)

- **SATA Hot Plug:** Enable or disable the SATA Hot Plug function.

#### 3.3.4 ACPI Configuration

![UEFI ACPI Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-acpi-configuration.png)

- **PCIE Devices Power On:** Allow a PCIe device to wake the system, and enable Wake-on-LAN.
- **RTC Alarm Power On:** Enable or disable the Real-Time Clock (RTC) alarm used to power on the system.

#### 3.3.5 USB Configuration

![UEFI USB Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-usb-configuration.png)

- **Legacy USB Support:** Enable or disable legacy support for USB devices. The default value is `Enabled`.

#### 3.3.6 Super IO Configuration

![UEFI Super IO Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-super-io-configuration.png)

**Serial Port 1 Configuration**

- **Serial Port:** Enable or disable the serial port.
- **Serial Port Address:** Select an optimal setting for the Super IO device.

**SOL Configuration**

- **SOL Port:** Set the parameters for Serial over LAN (SOL).
- **Serial Port Address:** Select an optimal setting for the Super IO device.

#### 3.3.7 Serial Port Console Redirection

![UEFI Serial Port Console Redirection screen](ROMED6U-2L2T_User_Manual.assets/uefi-serial-console-redirection.png)

The screen provides equivalent **Console Redirection** and **Console Redirection Settings** entries for both COM1 and SOL.

- **Console Redirection:** Enable or disable console redirection. When enabled, you can select a COM port to use for console redirection.
- **Console Redirection Settings:** Configure how your computer and the connected host computer exchange information. Both computers should use the same or compatible settings.

**Terminal Type**

Select the preferred terminal-emulation type for out-of-band management. `VT-UTF8` is recommended.

| Option | Description |
|---|---|
| `VT100` | ASCII character set. |
| `VT100+` | Extended VT100 with color and function-key support. |
| `VT-UTF8` | UTF-8 encoding maps Unicode characters onto one or more bytes. |
| `ANSI` | Extended ASCII character set. |

Other COM1/SOL console-redirection settings are:

- **Bits Per Second:** Select the serial-port transmission speed. The host and client computers must use the same speed. Long or noisy lines may require a lower speed. Options are `9600`, `19200`, `38400`, `57600`, and `115200`.
- **Data Bits:** Set the data-transmission size. Options are `7` and `8` bits.
- **Parity:** Select the parity bit. Options are `None`, `Even`, `Odd`, `Mark`, and `Space`.
- **Stop Bits:** Indicate the end of a serial-data packet. The standard setting is `1` stop bit. Select `2` stop bits for slower devices.
- **Flow Control:** Prevent data loss from buffer overflow. When receiving buffers are full, a stop signal can pause the data flow; when the buffers are empty, a start signal can resume it. Hardware flow control uses two wires for the start/stop signals. Options are `None` and `Hardware RTS/CTS`.
- **VT-UTF8 Combo Key Support:** Enable or disable VT-UTF8 combo-key support for ANSI/VT100 terminals.
- **Recorder Mode:** Enable or disable Recorder Mode to capture terminal data and send it as text messages.
- **Resolution 100x31:** Enable or disable extended terminal-resolution support.
- **PuTTY Keypad:** Select the function-key and keypad behavior in PuTTY.

**Legacy Console Redirection**

- **Legacy Console Redirection Settings:** Configure how your computer and the connected host computer exchange legacy console-redirection information.
- **Redirection COM Port:** Select a COM port on which to display redirection of legacy OS and legacy OPROM messages.
- **Resolution:** Set the number of rows and columns supported for redirection in a legacy OS.
- **Redirect After POST:** When `Bootloader` is selected, Legacy Console Redirection is disabled before booting to a legacy OS. When `Always Enable` is selected, Legacy Console Redirection remains enabled for a legacy OS. The default setting is `Always Enable`.

**Serial Port for Out-of-Band Management / Windows Emergency Management Services (EMS)**

- **Console Redirection:** Enable or disable console redirection. When enabled, you can select a COM port to use for console redirection.
- **Console Redirection Settings:** Configure how your computer and the connected host computer exchange information.
- **Out-of-Band Mgmt Port:** Microsoft Windows Emergency Management Services (EMS) allows remote management of a Windows Server operating system through a serial port.
- **Terminal Type:** Select the preferred terminal-emulation type for out-of-band management. `VT-UTF8` is recommended. The available terminal types are `VT100`, `VT100+`, `VT-UTF8`, and `ANSI`, as described in the table above.
- **Bits Per Second:** Select the serial-port transmission speed. The host and client computers must use the same speed. Long or noisy lines may require a lower speed. Options are `9600`, `19200`, `57600`, and `115200`.
- **Flow Control:** Prevent data loss from buffer overflow. When receiving buffers are full, a stop signal can pause the data flow; when the buffers are empty, a start signal can resume it. Hardware flow control uses two wires for the start/stop signals. Options are `None`, `Hardware RTS/CTS`, and `Software Xon/Xoff`.
- **Additional settings shown:** Data Bits, Parity, and Stop Bits.

#### 3.3.8 H/W Monitor

![UEFI hardware monitor screen](ROMED6U-2L2T_User_Manual.assets/uefi-hardware-monitor.png)

This section monitors system hardware status, including CPU temperature, motherboard temperature, CPU fan speed, chassis fan speed, and critical voltages.

- **Watch Dog Timer:** Enable or disable the Watch Dog Timer. The default value is `Disabled`.

#### 3.3.9 PCI Subsystem Settings

![UEFI PCI Subsystem Settings screen](ROMED6U-2L2T_User_Manual.assets/uefi-pci-subsystem-settings.png)

- **Above 4G Decoding:** Enable or disable decoding of 64-bit-capable devices in the address space above 4 GB. This option applies only if the system supports 64-bit PCI decoding.
- **SR-IOV Support:** If the system has SR-IOV-capable PCIe devices, enable or disable Single Root I/O Virtualization support.

#### 3.3.10 AMD CBS

![UEFI AMD CBS screen](ROMED6U-2L2T_User_Manual.assets/uefi-amd-cbs.png)

- **CPU Common Options:** Configure CPU Common options.
- **DF Common Options:** Configure DF Common options.
- **UMC Common Options:** Configure UMC Common options.
- **NBIO Common Options:** Configure NBIO Common options.
- **FCH Common Options:** Configure FCH Common options.
- **SoC Miscellaneous Control:** Configure SoC Miscellaneous Control options.

#### 3.3.11 AMD PBS

![UEFI AMD PBS screen](ROMED6U-2L2T_User_Manual.assets/uefi-amd-pbs.png)

- **RAS:** Configure settings related to AMD CPM RAS.

#### 3.3.12 PSP Firmware Versions

![UEFI PSP Firmware Versions screen](ROMED6U-2L2T_User_Manual.assets/uefi-psp-firmware-versions.png)

This screen displays version information for the PSP Recovery BL, PSP BootLoader, SMU firmware, ABL, APCB, APDB, and APPB.

#### 3.3.13 Instant Flash

Instant Flash is a UEFI flash utility embedded in flash ROM. It allows you to update the system UEFI without first entering an operating system such as MS-DOS or Windows. Save the new UEFI file to a USB flash drive, floppy disk, or hard drive, then launch this tool to update the UEFI without preparing an additional floppy diskette or other complicated flash utility.

The USB flash drive or hard drive must use the FAT32, FAT16, or FAT12 file system. When you run Instant Flash, the utility displays the available UEFI files and their information. Select the correct UEFI file, complete the update, and reboot the system.

### 3.4 Server Management

![UEFI Server Management screen](ROMED6U-2L2T_User_Manual.assets/uefi-server-management.png)

- **Wait For BMC:** Wait for the BMC to respond for the specified timeout. The BMC starts at the same time as the BIOS during AC power-on. Initializing the host-to-BMC interfaces takes approximately 90 seconds.
- **Inventory Support:** Run the system inventory function. Enabling this item increases system boot time.

#### 3.4.1 System Event Log

![UEFI System Event Log screen](ROMED6U-2L2T_User_Manual.assets/uefi-system-event-log.png)

- **SEL Components:** Enable or disable event logging for error and progress codes during boot.
- **Erase SEL:** Choose when to erase the System Event Log (SEL).
- **When SEL is Full:** Choose what the system does when the SEL is full.
- **Log EFI Status Codes:** Disable EFI status-code logging, or log only error codes, only progress codes, or both.

#### 3.4.2 BMC Network Configuration

![UEFI BMC Network Configuration screen](ROMED6U-2L2T_User_Manual.assets/uefi-bmc-network-configuration.png)

**LAN Channel (Failover)**

- **Manual Setting IPMI LAN:** If `No` is selected, DHCP assigns the IP address. To use a static IP address, select `Yes`; the changes take effect after the system reboots. The default value is `No`.
- **Configuration Address Source:** Configure BMC network parameters statically or dynamically through the BIOS or BMC. Options are `Static` and `DHCP`.
  - **Static:** Manually enter the IP address, subnet mask, and gateway address in the BIOS for the BMC LAN channel.
  - **DHCP:** The network's DHCP server automatically assigns the IP address, subnet mask, and gateway address.

> **Warning:** When `DHCP` or `Static` is selected, do not modify the BMC network settings on the IPMI web page.

The default login information for the IPMI web interface is:

- **Username:** `admin`
- **Password:** `admin`

For instructions on setting up a remote-control environment and using the IPMI management platform, see the *IPMI Configuration User Guide* or visit [ASRock Rack IPMI Support](http://www.asrockrack.com/support/ipmi.asp).

- **IPV6 Support:** Enable or disable LAN1 IPv6 support.
- **Manual Setting IPMI LAN (IPV6):** Configure LAN-channel parameters statically or dynamically through the BIOS or BMC. The `Unspecified` option does not modify any BMC network parameters during the BIOS phase.
- **IPV6 Index:** Set the selector for a static IP address. The range is `0` to `15`.

#### 3.4.3 BMC Tools

![UEFI BMC Tools screen](ROMED6U-2L2T_User_Manual.assets/uefi-bmc-tools.png)

- **Load BMC Default Settings:** Load the BMC default settings.
- **KCS Control:** Select the KCS interface state after POST ends. If `Enabled` is selected, the BMC keeps the KCS interface active after POST. If `Disabled` is selected, the BMC disables the KCS interface after POST.

### 3.5 Security

![UEFI Security screen](ROMED6U-2L2T_User_Manual.assets/uefi-security.png)

In this section, you may set or change the system's supervisor and user passwords. You may also clear the user password.

- **Supervisor Password:** Set or change the password for the administrator account. Only the administrator can change settings in the UEFI Setup Utility. To remove the password, leave the field blank and press `Enter`.
- **User Password:** Set or change the password for the user account. Users cannot change settings in the UEFI Setup Utility. To remove the password, leave the field blank and press `Enter`.
- **Secure Boot:** Enable or disable Secure Boot Control. The default value is `Disabled`. Enable this option to support Secure Boot in Windows Server 2012 R2 or later.
- **Secure Boot Mode:** Select `Standard` or `Custom`. In Custom mode, Secure Boot variables can be configured without authentication.

#### 3.5.1 Key Management

![UEFI Key Management screen](ROMED6U-2L2T_User_Manual.assets/uefi-key-management.png)

In this section, expert users can modify Secure Boot policy variables without full authentication.

- **Factory Key Provision:** Install the factory-default Secure Boot keys after the platform resets and while the system is in Setup mode.
- **Install Default Secure Boot Keys:** Install the default Secure Boot keys the first time you use Secure Boot.
- **Enroll EFI Image:** Allow an image to run in Secure Boot mode by enrolling the SHA-256 hash of the binary in the Authorized Signature Database (`db`).
- **Restore DB Defaults:** Restore the `db` variable to its factory defaults.

For each Secure Boot variable below, you can enroll the factory defaults or load certificates from a file using one of these inputs:

1. Public Key Certificate in:
   - `EFI_SIGNATURE_LIST`
   - `EFI_CERT_X509` (DER)
   - `EFI_CERT_RSA2048` (binary)
   - `EFI_CERT_SHAXXX`
2. Authenticated UEFI Variable
3. EFI PE/COFF Image (SHA-256)

The variables and key sources shown are:

- **Platform Key (PK):** Key Source: `Default`, `External`, `Mixed`.
- **Key Exchange Keys:** Key Source: `Default`, `External`, `Mixed`.
- **Authorized Signatures:** Key Source: `Default`, `External`, `Mixed`.
- **Forbidden Signatures:** Key Source: `Default`, `External`, `Mixed`.
- **Authorized TimeStamps:** Key Source: `Default`, `External`, `Mixed`.
- **OsRecovery Signatures:** Key Source: `Default`, `External`, `Mixed`.

> **Manual display note:** The manual also shows a separate `Key Source: Default, External, Mixed, Test` line between the Key Exchange Keys and Authorized Signatures blocks.

### 3.6 Boot Screen

![UEFI Boot screen](ROMED6U-2L2T_User_Manual.assets/uefi-boot-screen.png)

This section displays the available system devices and lets you configure boot settings and boot priority.

- **Boot Option #1:** Set the system boot order.
- **Boot Option Filter:** Control the priority of legacy and UEFI ROMs.
- **Boot From Onboard LAN:** Enable or disable booting from the onboard LAN.
- **Setup Prompt Timeout:** Set the number of seconds to wait for the UEFI Setup Utility prompt.
- **Bootup Num-Lock:** When set to `On`, automatically activate Num Lock after boot-up.
- **Boot Beep:** Turn the boot beep on or off. A buzzer is required.
- **Full Screen Logo:** Enable or disable the OEM logo. The default value is `Enabled`.
- **AddOn ROM Display:** Control the display of AddOn ROM information. If **Full Screen Logo** is enabled but you want to see AddOn ROM information during boot, select `Enabled`. Options are `Enabled` and `Disabled`; the default is `Enabled`.

#### 3.6.1 CSM Parameters

![UEFI CSM Parameters screen](ROMED6U-2L2T_User_Manual.assets/uefi-csm-parameters.png)

- **CSM:** Enable the Compatibility Support Module. Do not disable CSM unless you are running a WHCK test. If you use 64-bit UEFI with Windows Server 2012 R2 or later and all devices support UEFI, you may disable CSM for faster booting.
- **Launch Video OpROM Policy:** Select `UEFI Only` to run only option ROMs that support UEFI. Select `Legacy Only` to run only option ROMs that support legacy mode. Select `Do Not Launch` to run neither legacy nor UEFI option ROMs.

The following slot settings select the storage and network Option ROM policy:

- SLIM1-1 Slot OpROM
- SLIM2-1 Slot OpROM
- SLIM2-2 Slot OpROM
- SLIM3-1 OpROM
- SLIM3-2 Slot OpROM
- M2_1 Slot OpROM
- M2_2 Slot OpROM
- PCIE4 Slot OpROM
- PCIE5 Slot OpROM
- PCIE6 Slot OpROM
- PCIE7 Slot OpROM

For each setting, the `Auto` option defaults to `Disabled` with an NVMe device and `Legacy` with other devices. These settings cannot select the Video Option ROM policy.

### 3.7 Event Logs

![UEFI Event Logs screen](ROMED6U-2L2T_User_Manual.assets/uefi-event-logs.png)

**Change SMBIOS Event Log Settings** allows you to configure the SMBIOS Event Log. Opening it displays the following settings:

- **SMBIOS Event Log:** Enable or disable all SMBIOS event-logging features during system boot.
- **Erase Event Log:** Choose whether to erase logged events. Options are `No`, `Yes, Next reset`, and `Yes, Every reset`.
- **When Log is Full:** Choose what happens when the SMBIOS Event Log is full. Options are `Do Nothing` and `Erase Immediately`.
- **Log System Boot Event:** Enable or disable logging of system boot events.
- **MECI (Multiple Event Count Increment):** Enter the increment value for the multiple-event counter. The valid range is `1` to `255`.
- **METW (Multiple Event Time Window):** Specify the number of minutes that must pass between duplicate log entries that use a multiple-event counter. The valid range is `0` to `99` minutes.
- **Log EFI Status Code:** Enable or disable logging EFI status codes as OEM-reserved type E0 if they have not already been converted to legacy codes.
- **Convert EFI Status Codes to Standard SMBIOS Type:** Enable or disable conversion of EFI status codes to standard SMBIOS types. Not all codes can be translated.
- **View SMBIOS Event Log:** Press `Enter` to view the SMBIOS Event Log records.

> **Note:** Changes made in this section do not take effect until the computer restarts.

### 3.8 Exit Screen

![UEFI Exit screen](ROMED6U-2L2T_User_Manual.assets/uefi-exit-screen.png)

- **Save Changes and Exit:** Displays the message, `Save configuration changes and exit setup?` Press `F10` or select `Yes` to save changes and exit the UEFI Setup Utility.
- **Discard Changes and Exit:** Displays the message, `Discard changes and exit setup?` Press `Esc` or select `Yes` to exit the UEFI Setup Utility without saving changes.
- **Discard Changes:** Displays the message, `Discard changes?` Press `F7` or select `Yes` to discard all changes.
- **Load UEFI Defaults:** Load the default UEFI values for all setup questions. You can also press `F9`.
- **Boot Override:** Displays the available devices. Select a device to begin booting from it.

## Chapter 4: Software Support

### 4.1 Install Operating System

This motherboard supports various Microsoft Windows Server and Linux-compliant operating systems. Because motherboard settings and hardware options vary, use the setup procedures in this chapter as general reference only. Refer to your operating-system documentation for more information.

### 4.2 Support CD Information

The Support CD supplied with the motherboard contains the necessary drivers and useful utilities that enhance the motherboard's features.

#### 4.2.1 Running the Support CD

To use the Support CD, insert it into the CD-ROM drive. If `AUTORUN` is enabled, the CD automatically displays the Main Menu. If the Main Menu does not appear, locate and double-click `ASRSetup.exe` in the root folder of the Support CD.

#### 4.2.2 Drivers Menu

The Drivers Menu shows the available device drivers for hardware detected in the system. Install the necessary drivers to activate the devices.

#### 4.2.3 Utilities Menu

The Utilities Menu shows the applications supported by the motherboard. Select an item and follow the installation wizard to install it.

#### 4.2.4 Contact Information

For more information about ASRock Rack, visit the [ASRock Rack website](http://www.asrockrack.com) or contact your dealer.

## Chapter 5: Troubleshooting

### 5.1 Troubleshooting Procedures

Follow the procedures below to troubleshoot your system.

> **Warning:** Always unplug the power cord before adding, removing, or changing hardware components. Failure to do so may cause physical injury and damage to motherboard components.

1. Disconnect the power cable and confirm that the PWR LED is off.
2. Unplug all cables and connectors, and remove all add-on cards from the motherboard. Make sure the jumpers are set to their default settings.
3. Confirm that there are no short circuits between the motherboard and the chassis.
4. Install a CPU and fan on the motherboard, then connect the chassis speaker and power LED.

#### If There Is No Power

1. Confirm that there are no short circuits between the motherboard and the chassis.
2. Make sure the jumpers are set to their default settings.
3. Check the setting of the 115 V/230 V switch on the power supply.
4. Verify that the motherboard battery supplies approximately 3 VDC. Install a new battery if it does not.

#### If There Is No Video

1. Reconnect the monitor cables and power cord.
2. Check for memory errors.

#### If There Are Memory Errors

1. Verify that the DIMM modules are properly seated in their slots.
2. Use recommended DDR4 RDIMMs, LRDIMMs, and NVDIMMs.
3. If more than one DIMM module is installed, the modules should use the same brand, speed, size, and chip type.
4. Insert different DIMM modules into different slots to identify faulty modules.
5. Check the setting of the 115 V/230 V switch on the power supply.

#### Unable to Save System Setup Configurations

1. Verify that the motherboard battery supplies approximately 3 VDC. Install a new battery if it does not.
2. Confirm that the power supply provides adequate and stable power.

#### Other Problems

Search for keywords related to your problem on the [ASRock Rack FAQ and support page](http://www.asrockrack.com/support).

### 5.2 Technical Support Procedures

If you have tried the troubleshooting procedures above and the problem remains unresolved, contact ASRock Rack technical support with the following information:

1. Your contact information.
2. The model name, BIOS version, and problem type.
3. The system configuration.
4. A description of the problem.

Contact [ASRock Rack Technical Support](http://www.asrockrack.com/support/tsd.asp).

### 5.3 Returning Merchandise for Service

For warranty service, a receipt or copy of your invoice showing the purchase date is required. Contact your vendor or visit the [ASRock Rack RMA website](http://event.asrockrack.com/tsd.asp) to obtain a Returned Merchandise Authorization (RMA) number.

Display the RMA number on the outside of the shipping carton. Return the motherboard prepaid by mail or hand-carry it to the manufacturer. Shipping and handling charges apply to all orders that must be mailed when service is complete.

This warranty does not cover damage incurred during shipping or failures caused by alteration, misuse, abuse, or improper maintenance.

Contact your distributor first for any product-related problems during the warranty period.
