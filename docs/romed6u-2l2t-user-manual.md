# ASRock Rack ROMED6U-2L2T

## User Manual

**Version:** 1.0  
**Published:** October 2020  
**Copyright:** © 2020 ASRock Rack Inc. All rights reserved.

> **Editing note**
> This Markdown edition removes printed page headers, footers, and page numbers. The table of contents uses links to section headings instead of fixed page numbers. Obvious PDF-to-text artifacts were repaired, lists were normalized, and structured data was converted into tables. Product names, connector names, menu names, and technical values were retained.

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
  - [3.2 Main Screen](#32-main-screen)
  - [3.3 Advanced Screen](#33-advanced-screen)
  - [3.4 Server Mgmt](#34-server-mgmt)
  - [3.5 Security](#35-security)
  - [3.6 Boot Screen](#36-boot-screen)
  - [3.7 Event Logs](#37-event-logs)
  - [3.8 Exit Screen](#38-exit-screen)
- [Chapter 4: Software Support](#chapter-4-software-support)
  - [4.1 Install Operating System](#41-install-operating-system)
  - [4.2 Support CD Information](#42-support-cd-information)
- [Chapter 5: Troubleshooting](#chapter-5-troubleshooting)
  - [5.1 Troubleshooting Procedures](#51-troubleshooting-procedures)
  - [5.2 Technical Support Procedures](#52-technical-support-procedures)
  - [5.3 Returning Merchandise for Service](#53-returning-merchandise-for-service)

---

# Chapter 1: Introduction

Thank you for purchasing the ASRock Rack ROMED6U-2L2T motherboard. It is produced under ASRock Rack's stringent quality control and is designed for reliable performance and endurance.

This manual covers:

- Motherboard introduction and hardware installation.
- UEFI setup and configuration.
- Support CD information.

## 1.1 Package Contents

- ASRock Rack ROMED6U-2L2T motherboard
  - microATX form factor: 9.6 in × 9.6 in (24.4 cm × 24.4 cm)
- Quick Installation Guide
- 1 × I/O shield
- 2 × screws for M.2 sockets
- 1 × SATA3 cable, 60 cm
- 1 × Mini-SAS HD-to-4-SATA cable, 60 cm
- 1 × ATX 4-pin-to-24-pin power cable, 8 cm
- 1 × SATA power cable, 80 cm

If any items are missing or damaged, contact your authorized dealer.

Motherboard specifications and BIOS software may be updated without notice. If this manual is modified, the updated version will be available on the ASRock Rack website. The website also provides the latest memory and CPU support lists.

- Website: <http://www.asrockrack.com>
- Technical support: <http://www.asrockrack.com/support/>

## 1.2 Specifications

### Motherboard and processor

| Category | Specification |
|---|---|
| Form factor | microATX |
| Dimensions | 9.6 in × 9.6 in (24.4 cm × 24.4 cm) |
| CPU | AMD EPYC™ 7002 Series Processor |
| Socket | Single Socket SP3 (LGA4094) |
| Chipset | N/A |
| Thermal design power | 280 W |

### System memory

| Item | Specification |
|---|---|
| Memory technology | Six-channel DDR4 |
| Supported memory | DDR4 RDIMM, LRDIMM, and NVDIMM |
| RDIMM sizes | 64 GB, 32 GB, 16 GB, 8 GB per DIMM |
| LRDIMM sizes | 128 GB, 64 GB, 32 GB per DIMM |
| NVDIMM size | 32 GB per DIMM |
| RDIMM frequency | 3200 MHz |
| LRDIMM frequency | 2666 MHz |
| NVDIMM frequency | 2666 MHz |
| Voltage | 1.2 V |

### Expansion and storage

| Category | Specification |
|---|---|
| PCIe slots | PCIE7, PCIE6, PCIE5, and PCIE4: PCIe 4.0 ×16 links |
| Slimline connectors | SLIM1: PCIe Gen4 ×8, supports SATA; SLIM2: PCIe Gen4 ×8, supports SATA; SLIM3: PCIe Gen4 ×8 |
| SATA connectors | 2 × 7-pin SATA3; 12 × SATA3 at 6.0 Gb/s from Mini-SAS HD, Gen3 |
| M.2 sockets | 2: M2_1, Type 2280; M2_2, Type 2260. Each supports SATA ×1 or PCIe ×4 |

### Ethernet

| Item | Specification |
|---|---|
| 10GbE controller | Intel® X710-AT2 |
| 1GbE controller | Intel® I210-AT2 |
| 10GbE ports | 2 × RJ45 10GBASE-T |
| 1GbE port | 1 × RJ45 1GBASE-T |
| Dedicated management port | 1 × RJ45 dedicated IPMI LAN port using Realtek RTL8211E |
| Other features | Wake-on-LAN; Energy Efficient Ethernet 802.3az; dual LAN teaming; PXE |
| LAN1 | Supports NCSI |

### Management and graphics

| Category | Specification |
|---|---|
| BMC controller | ASPEED AST2500 |
| Dedicated IPMI GLAN | 1 × Realtek RTL8211E |
| Management features | Watchdog; NMI |
| Graphics controller | ASPEED AST2500 |
| VRAM | DDR4, 256 MB |

### Rear-panel I/O

| Item | Quantity or specification |
|---|---|
| VGA | 1 × D-Sub |
| USB 3.2 Gen1 | 2 ports |
| LAN | 4 + 1 RJ45 Ethernet ports |
| LAN indicators | ACT/LINK LED and SPEED LED on LAN ports |
| UID | 1 |

### Internal connectors and headers

| Connector or header | Quantity or specification |
|---|---|
| Auxiliary panel header | 1; includes chassis intrusion, location button and LED, and front LAN LED |
| TPMS header | 1 |
| IPMB header | 1 |
| Fan headers | 6 × 4-pin |
| ATX power | 1 × 8-pin, 1 × 8-pin, and 1 × 4-pin |
| SATA power | 1 × 4-pin |
| USB 3.2 Gen1 header | 1; supports 2 USB 3.2 Gen1 ports |
| M.2 | 2: M2_1 Type 2280 and M2_2 Type 2260; SATA ×1 or PCIe ×4 |
| Slimline | 3: SLIM1 and SLIM2 support PCIe ×8 or SATA Gen3 ×8; SLIM3 supports PCIe ×8 |
| Mini-SAS HD | 2: MSAS_HD0 supports SATA Gen3 ×8; MSAS_HD1 supports SATA Gen3 ×4 |
| SMBus from BMC | 1 |
| PSU SMB | 1 |
| NMI button | 1 |
| SGPIO headers | 3 |
| Thermal sensor header | 1 |
| Speaker | 1 × 4-pin |
| Clear CMOS | 1 short pad |
| CPU_HSBP1 | 1 |
| Front LAN LED | 1 |
| OH/FanFail LEDs | 6; fan-fail LED only |
| COM header | 1 |
| Panel header | 1 |

### BIOS, hardware monitoring, and supported operating systems

| Category | Specification |
|---|---|
| BIOS type | 32 MB AMI UEFI Legal BIOS |
| BIOS features | Plug and Play (PnP); ACPI 2.0 compliance; SMBIOS 2.8; ASRock Rack Instant Flash |
| Temperature monitoring | CPU temperature; motherboard/card-side/TR1 temperature |
| Fan monitoring | Fan tachometer; CPU Quiet Fan; fan multi-speed control |
| Voltage monitoring | +12 V, +5 V, +3.3 V, CPU Vcore, DRAM, +BAT, 3VSB, 5VSB |
| Windows | Windows Server 2016 and 2019, 64-bit |
| Red Hat Enterprise Linux Server | 8.0 and 7.6, 64-bit |
| CentOS | 8.0 and 7.6, 64-bit |
| SUSE SLES | 15.1 and 12.4, 64-bit |
| Ubuntu | 18.04.3 and 16.04.6, 64-bit |
| Citrix | Citrix Hypervisor 8.1.0 |
| VMware | ESXi 6.5 U3 and 6.7 U3; vSphere 6.5 U3 and 6.7 U3 |

> Refer to the ASRock Rack website for the latest operating-system support list.

### Environment

| Condition | Range |
|---|---|
| Operating temperature | 10°C to 35°C |
| Non-operating temperature | −40°C to 70°C |

> **Wake-on-LAN note**
> This motherboard supports wake from onboard LAN. Enable **Wake on Magic Packet from power off state** in **Device Manager > Intel® Ethernet Connection > Power Management**. Also enable **PCI Devices Power On** in **UEFI SETUP UTILITY > Advanced > ACPI Configuration**. Onboard LAN1 and LAN4 can then wake the system from S5 under the operating system.
>
> Installing the Intel® LAN utility or Marvell SATA utility may cause the motherboard to fail Windows® Hardware Quality Labs (WHQL) certification tests. Installing only the drivers passes the WHQL tests.

## 1.3 Unique Features

### ASRock Rack Instant Flash

ASRock Rack Instant Flash is a BIOS flash utility embedded in the flash ROM. It updates the system BIOS without first entering MS-DOS or Windows®.

To use Instant Flash:

1. Press **F6** during POST, or press **F2** to enter the UEFI setup menu.
2. Open **ASRock Rack Instant Flash**.
3. Save the new BIOS file to a USB flash drive, floppy disk, or hard drive.
4. Launch the utility and follow the on-screen instructions.

The USB flash drive or hard drive must use a FAT32, FAT16, or FAT12 file system.

## 1.4 Motherboard Layout

The manual includes top-view and bottom-view motherboard diagrams. The following tables provide the connector legend in a searchable format.

### Board dimensions

- Form factor: microATX
- Dimensions: 24.4 cm × 24.4 cm (9.6 in × 9.6 in)
- CPU socket: LGA4094 Socket SP3
- DIMM slots: DDR4_A1, DDR4_C1, DDR4_D1, DDR4_E1, DDR4_G1, DDR4_H1

### Connector and component legend

| No. | Description |
|---:|---|
| 1 | ATX 12V power connector (ATX12V2) |
| 2 | ATX 12V power connector (ATX12V1) |
| 3 | ATX 4-pin power connector (ATX4PIN1)** |
| 4 | PSU SMBus header (PSU_SMB1) |
| 5 | PWM configuration header (PWM_CFG1) |
| 6 | System fan connector (FAN1) |
| 7 | System fan connector (FAN2) |
| 8 | System fan connector (FAN3) |
| 9 | System fan connector (FAN4) |
| 10 | System fan connector (FAN5) |
| 11 | System fan connector (FAN6) |
| 12 | Three 288-pin DDR4 DIMM slots: DDR4_E1, DDR4_G1, DDR4_H1* |
| 13 | Three 288-pin DDR4 DIMM slots: DDR4_A1, DDR4_C1, DDR4_D1* |
| 14 | SATA power connector, DC-IN mode (SATA_PWR1)** |
| 15 | M.2 socket M2_1, Type 2280 |
| 16 | Slimline NVMe connector (SLIM3) |
| 17 | Slimline NVMe connector (SLIM2) |
| 18 | Slimline NVMe connector (SLIM1), right-angled |
| 19 | SATA3 connector (SATA1) |
| 20 | Mini-SAS HD connector (MSAS_HD0), right-angled |
| 21 | Mini-SAS HD connector (MSAS_HD1), right-angled |
| 22 | Speaker header (SPEAKER1) |
| 23 | System panel header (PANEL1) |
| 24 | Backplane PCI Express hot-plug connector (CPU1_HSBP1) |
| 25 | SATA SGPIO connector (SATA_SGPIO3) |
| 26 | SATA SGPIO connector (SATA_SGPIO2) |
| 27 | SATA SGPIO connector (SATA_SGPIO1) |
| 28 | SATA3 connector (SATA0) |
| 29 | Front LAN LED connector (LED_LAN3_4) |
| 30 | USB 3.2 Gen1 header (USB3_3_4), right-angled |
| 31 | Clear CMOS pad (CLRMOS1) |
| 32 | COM port header (COM1) |
| 33 | TPMS header (TPMS1) |
| 34 | Thermal sensor header (TR1) |
| 35 | Auxiliary panel header (AUX_PANEL1) |
| 36 | BMC SMBus header (BMC_SMB1) |
| 37 | Intelligent Platform Management Bus header (IPMB_1) |
| 38 | Non-Maskable Interrupt button (NMI_BTN1) |
| 39 | M.2 socket M2_2, Type 2260 |

\* See [Installation of Memory Modules (DIMM)](#24-installation-of-memory-modules-dimm) for DIMM installation and configuration instructions.  
\*\* Misconnection between **ATX4PIN1** and **SATA_PWR1** may permanently damage the motherboard.

## 1.5 Onboard LED Indicators

| No. | Item | Status | Description |
|---:|---|---|---|
| 1 | FAN_LED1 | Red | FAN1 failed |
| 2 | FAN_LED2 | Red | FAN2 failed |
| 3 | FAN_LED3 | Red | FAN3 failed |
| 4 | FAN_LED4 | Red | FAN4 failed |
| 5 | FAN_LED5 | Red | FAN5 failed |
| 6 | FAN_LED6 | Red | FAN6 failed |
| 7 | BMC_LED1 | Green | BMC heartbeat LED |
| 8 | SB_PWR1 | Green | Standby power ready |

## 1.6 I/O Panel

| No. | Description |
|---:|---|
| 1 | UID switch (UID1) |
| 2 | USB 3.2 Gen1 ports (USB3_1_2) |
| 3 | LAN RJ45 port (IPMI_LAN1)* |
| 4 | 1GbE LAN RJ45 port (LAN3)** |
| 5 | 1GbE LAN RJ45 port (LAN4)** |
| 6 | VGA port (VGA1) |
| 7 | 10GbE LAN RJ45 port (LAN1)** |
| 8 | 10GbE LAN RJ45 port (LAN2)** |

### Dedicated IPMI LAN port LED indications

| Activity/Link LED status | Description | Speed LED status | Description |
|---|---|---|---|
| Off | No link | Off | 10 Mbps connection or no link |
| Blinking yellow | Data activity | Yellow | 100 Mbps connection |
| On | Link | Green | 1 Gbps connection |

### 1GbE LAN port LED indications: LAN3 and LAN4

| Activity/Link LED status | Description | Speed LED status | Description |
|---|---|---|---|
| Off | No link | Off | 10 Mbps connection or no link |
| Blinking green | Data activity | Yellow | 100 Mbps connection |
| On | Link | Green | 1 Gbps connection |

### 10GbE LAN port LED indications: LAN1 and LAN2

| Activity/Link LED status | Description | Speed LED status | Description |
|---|---|---|---|
| Off | No link | Off | 100 Mbps connection or no link |
| Blinking yellow | Data activity | Yellow | 1 Gbps connection |
| On | Link | Green | 10 Gbps connection |

\* The dedicated IPMI LAN port has two LEDs.  
\*\* Each LAN port has two LEDs.

## 1.7 Block Diagram

The source manual contains a graphical block diagram. Its main signal and device relationships are summarized below.

| Area | Connections and devices |
|---|---|
| CPU and memory | AMD EPYC 7002-series processor with six DDR4 LRDIMM/RDIMM channels: A1, C1, D1, E1, G1, and H1 |
| PCIe from CPU | PCIE4, PCIE5, PCIE6, and PCIE7: PCIe Gen4 ×16 |
| Slimline | SLIM1 and SLIM2: PCIe Gen4 ×8 or SATA Gen3 ×8; SLIM3: PCIe Gen4 ×8 |
| M.2 | M2_1 and M2_2: SATA or PCIe Gen4 ×4, subject to board routing and configuration |
| SATA | SATA0 and SATA1: SATA Gen3; MSAS_HD0: SATA Gen3 ×8; MSAS_HD1: SATA Gen3 ×4 |
| Networking | Intel X710-AT2 for 10GbE; two Intel I210-AT2 controllers for 1GbE; Realtek RTL8211E for dedicated management LAN |
| Management | ASPEED AST2500 BMC with DDR4 DRAM, video, USB, LPC, and SPI flash interfaces |
| Other interfaces | TPM 2.0, NCSI, USB 3.2 Gen1, USB 2.0, LPC, SPI, and SGPIO |

The source diagram also shows the following SGPIO associations:

- SATA0–SATA7 use SATA_SGPIO3.
- SATA8–SATA11, SATA12, and SATA13 use SATA_SGPIO2.
- SLIM2 uses SATA_SGPIO1.
- SLIM1 uses SATA_SGPIO0.

---

# Chapter 2: Installation

This motherboard uses a microATX form factor measuring 9.6 in × 9.6 in (24.4 cm × 24.4 cm). Before installation, confirm that the chassis supports the motherboard.

## 2.1 Screw Holes

Place screws in the holes marked by circles to secure the motherboard to the chassis.

## 2.2 Pre-installation Precautions

Follow these precautions before installing motherboard components or changing motherboard settings:

1. Unplug the power cord from the wall socket before touching any component.
2. To prevent static-electricity damage, never place the motherboard directly on carpet or a similar surface. Use a grounded wrist strap or touch a safety-grounded object before handling components.
3. Hold components by their edges. Do not touch the ICs.
4. When removing a component, place it on a grounded anti-static pad or in its supplied anti-static bag.
5. Place screws in the mounting holes without over-tightening them. Over-tightening can damage the motherboard.

> **Safety warning**
> Switch off the power or detach the power cord before installing or removing any component. Failure to do so can cause serious injury or damage to the motherboard, peripherals, or components.

## 2.3 Installing the CPU

1. Before inserting the CPU, check that:
   - The PnP cap is installed on the socket.
   - The CPU surface is clean.
   - The socket has no bent pins.
2. Do not force the CPU into the socket if any problem is found. Otherwise, the CPU can be seriously damaged.
3. Unplug all power cables before installing the CPU.
4. Follow the numbered installation illustrations in the manual.
5. Install the carrier frame with the CPU. Do not separate them.
6. While inserting the carrier frame with the CPU, keep it closely attached to the rail frame.

**Terminology in the installation illustration:**

- **Carrier Frame with CPU**
- **Rail Frame**

## 2.4 Installation of Memory Modules (DIMM)

This motherboard provides six 288-pin DDR4 DIMM slots in two groups and supports six-channel memory technology.

### DIMM population guide

| Number of DIMMs | Slots shown in the source table |
|---:|---|
| 1 | A1 |
| 2 | A1, C1 |
| 4 | A1, C1, D1, E1 |
| 6 | A1, C1, D1, E1, G1, H1 |

### Memory precautions

1. Do not install DDR, DDR2, or DDR3 memory in a DDR4 slot. This can damage the motherboard and DIMM.
2. For dual-channel configuration, install identical DDR4 DIMM pairs. Use the same brand, speed, size, and chip type.
3. Dual-channel memory technology cannot be activated with only one or three memory modules installed.
4. Some 1 GB, double-sided DDR4 DIMMs with 16 chips may not work. ASRock Rack does not recommend installing them.

The DIMM fits in only one orientation. Forcing a DIMM into a slot in the wrong orientation can permanently damage the motherboard and DIMM.

## 2.5 Expansion Slots (PCI Express Slots)

The motherboard provides four PCI Express slots. PCIE7, PCIE6, PCIE5, and PCIE4 are PCIe 4.0 ×16 slots connected to the CPU.

| Slot | Generation | Mechanical width | Electrical width | Source |
|---|---:|---:|---:|---|
| PCIE7 | 4.0 | ×16 | ×16 | CPU |
| PCIE6 | 4.0 | ×16 | ×16 | CPU |
| PCIE5 | 4.0 | ×16 | ×16 | CPU |
| PCIE4 | 4.0 | ×16 | ×16 | CPU |

### Installing an expansion card

1. Switch off the power supply or unplug the power cord.
2. Read the expansion-card documentation and set the required hardware options.
3. Remove the system-unit cover if the motherboard is installed in a chassis.
4. Remove the bracket for the slot you intend to use. Keep the screw.
5. Align the card connector with the slot and press firmly until the card is fully seated.
6. Secure the card to the chassis with the screw.
7. Replace the system cover.

## 2.6 Onboard Headers and Connectors

> **Important:** Onboard headers and connectors are not jumpers. Do not place jumper caps over them. Doing so can permanently damage the motherboard.

### System Panel Header: 9-pin PANEL1

**Board reference:** Layout item 23.

| Signal | Signal | Signal |
|---|---|---|
| GND | RESET# | PWRBTN# |
| PLED− | PLED+ | GND |
| HDLED− | HDLED+ | GND |

Connect the chassis power switch, reset switch, and system-status indicators according to the pin assignments. Check positive and negative pins before connecting cables.

- **PWRBTN:** Connect to the chassis power switch. The power-switch behavior can be configured in the firmware.
- **RESET:** Connect to the chassis reset switch. Press it to restart a system that has frozen.
- **PLED:** Connect to the chassis power LED. The LED is on when the system operates and off in S4 or S5.
- **HDLED:** Connect to the chassis storage-activity LED. The LED is on during drive read or write activity.

Chassis front-panel layouts vary. Match the wire assignments to the header pin assignments.

### Auxiliary Panel Header: 18-pin AUX_PANEL1

**Board reference:** Layout item 35.

This header supports multiple front-panel functions, including front-panel SMBus, Internet-status indicators, chassis intrusion, and locator controls.

| Function | Description |
|---|---|
| A. Front-panel SMBus | 6-1 pin FPSMB connection for SMBus equipment and power-management equipment |
| B. Internet-status indicators | 2-pin LAN1_LED and LAN2_LED headers for LAN status cables |
| C. Chassis intrusion | 2-pin CHASSIS connection for a chassis intrusion sensor or microswitch; default is CASEOPEN and GND, which disables the function |
| D. Locator LED | 4-pin LOCATOR connection for the front-panel locator switch and LED |
| E. System fault LED | 2-pin LOCATOR connection for the system fault LED |

The source pin labels include `SMB_ALERT`, `SMB_CLK`, `SMB_DATA`, `CASEOPEN`, `+3VSB`, `LAN1_LINK`, `LAN2_LINK`, `LED_PWR`, `+5VSB`, `LOCATORLED1+`, `LOCATORLED1−`, `LOCATORBTN#`, `LOCATORLED2+`, and `LOCATORLED2−`.

### Serial ATA3 Connectors: SATA0 and SATA1

**Board references:** SATA0 is layout item 28; SATA1 is layout item 19.

These SATA3 connectors support SATA data cables for internal storage devices at up to 6.0 Gb/s.

### USB 3.2 Gen1 Header: 19-pin USB3_3_4

**Board reference:** Layout item 30. Right-angled connector.

In addition to the two rear-panel USB 3.2 Gen1 ports, this header supports two USB 3.2 Gen1 ports.

### Chassis Speaker Header: 4-pin SPEAKER1

**Board reference:** Layout item 22.

Connect the chassis speaker to this header.

| Pin signal | Pin signal |
|---|---|
| +5 V | DUMMY |
| DUMMY | SPEAKER |

### System Fan Connectors: FAN1–FAN6

**Board references:** FAN1–FAN6 are layout items 6–11.

Connect fan cables with the black wire on the ground pin. All fan headers support fan control.

| Pin | Signal |
|---:|---|
| 1 | GND |
| 2 | FAN_VOLTAGE |
| 3 | FAN_SPEED_CONTROL |
| 4 | FAN_SPEED |

### Mini-SAS HD Connectors: MSAS_HD0 and MSAS_HD1

**Board references:** MSAS_HD0 is layout item 20; MSAS_HD1 is layout item 21. Both are right-angled.

These connectors support Mini-SAS-to-SATA data cables for internal storage devices at up to 6.0 Gb/s.

### Slimline NVMe Connectors: SLIM1–SLIM3

**Board references:** SLIM1 is layout item 18; SLIM2 is item 17; SLIM3 is item 16.

- SLIM1: right-angled
- SLIM2: vertical
- SLIM3: vertical

These connectors are used for NVMe PCIe devices.

### Serial Port Header: 9-pin COM1

**Board reference:** Layout item 32.

This header supports a serial-port module.

| Signal | Signal |
|---|---|
| CCTS#1 | RRTS#1 |
| DDSR#1 | DDTR#1 |
| RRXD1 | GND |
| TTXD1 | DDCD#1 |
| RRI#1 | — |

### ATX 4-pin Power Connector: ATX4PIN1

**Board reference:** Layout item 3. ATX 24-pin-to-4-pin connection.

The motherboard provides one 4-pin power/signal connector. It is required for an ATX power source.

When using ATX power, use a 24-pin-to-4-pin power cable between the PSU 24-pin connector and **ATX4PIN1**. This provides power and signal communication.

For a 12 V DC-IN application, do not use this ATX 4-pin connector.

| Pin | Signal |
|---:|---|
| 1 | GND |
| 2 | GND |
| 3 | ATX_PWROK |
| 4 | PSON# |

> **Caution:** Misconnection between **ATX4PIN1** and **SATA_PWR1** may permanently damage the motherboard.

### SATA Power Connector (DC-IN Mode): 4-pin SATA_PWR1

**Board reference:** Layout item 14.

When using DC-IN mode without a SATA power supply, connect a SATA power cable between this connector and the SATA hard drive.

| Pin | Signal |
|---:|---|
| 1 | +5 V |
| 2 | GND |
| 3 | +12 V |
| 4 | GND |

> **Caution:** Misconnection between **ATX4PIN1** and **SATA_PWR1** may permanently damage the motherboard.

### ATX 12 V Power Connectors: ATX12V1 and ATX12V2

**Board references:** ATX12V1 is layout item 2; ATX12V2 is layout item 1.

The motherboard provides two 8-pin 12 V power connectors. They are required for either a 12 V DC-IN source or an ATX +12 V source.

When using ATX power, use a 24-pin-to-4-pin cable between the PSU 24-pin connector and **ATX4PIN1** for power and signal communication.

| Pin signal | Pin signal |
|---|---|
| 12 V | GND |
| 12 V | GND |
| 12 V | GND |
| 12 V | GND |

### Clear CMOS Pads: CLRMOS1

**Board reference:** Layout item 31.

To clear CMOS data, remove the CMOS battery and short the Clear CMOS pad.

### Front LAN LED Header: 4-pin LED_LAN3_4

**Board reference:** Layout item 29.

This connector is used for the front LAN status indicator.

| Pin signal | Pin signal |
|---|---|
| LAN4_LINK | LED_PWR |
| LED_PWR | LAN3_LINK |

### TPMS Header: 17-pin TPMS1

**Board reference:** Layout item 33.

This connector supports a Trusted Platform Module (TPM), which can securely store keys, digital certificates, passwords, and data. A TPM can also enhance network security, protect digital identities, and help ensure platform integrity.

The source pin labels include `GND`, `SMB_DATA_MAIN`, `LAD0`–`LAD3`, `SERIRQ#`, `PCICLK`, `PCIRST#`, `+3V`, `+3VSB`, `S_PWRDWN#`, and `LFRAME#`.

### PSU SMBus Header: 5-pin PSU_SMB1

**Board reference:** Layout item 4.

PSU SMBus monitors the power supply, fan, and system temperature.

| Pin signal | Pin signal |
|---|---|
| +3 V | GND |
| ALERT | SMBCLK |
| SMBDATA | — |

### Intelligent Platform Management Bus Header: 4-pin IPMB_1

**Board reference:** Layout item 37.

This connector provides a cabled baseboard or front-panel connection for value-added features and third-party add-in cards, such as emergency-management cards that use IPMB.

| Pin signal |
|---|
| IPMB_SDA |
| IPMB_SCL |
| No connect |
| GND |

### Thermal Sensor Header: 3-pin TR1

**Board reference:** Layout item 34.

Connect the thermal-sensor cable to pins 1–2 or 2–3. Connect the other end to the device whose temperature you want to monitor.

### Non-Maskable Interrupt Button Header: NMI_BTN1

**Board reference:** Layout item 38.

Connect an NMI device to this header.

| Pin signal | Pin signal |
|---|---|
| CONTROL | GND |

### Serial General Purpose Input/Output Headers: SATA_SGPIO1–3

**Board references:** SATA_SGPIO1 is layout item 27; SATA_SGPIO2 is item 26; SATA_SGPIO3 is item 25.

These headers support the serial link interface for onboard SATA connections.

| Pin signal |
|---|
| SLOAD |
| SCLOCK |
| GND |
| GND |
| SDATAOUT |

### Baseboard Management Controller SMBus Header: 5-pin BMC_SMB1

**Board reference:** Layout item 36.

This header is used for SMBus devices.

| Pin signal |
|---|
| BMC_SMB_PRESENT_1_N |
| Power |
| BMC_SMBCLK |
| GND |
| BMC_SMBDATA |

### PWM Configuration Header: 3-pin PWM_CFG1

**Board reference:** Layout item 5.

This header is used for PWM configuration.

| Pin signal |
|---|
| GND |
| SMB_DATA_VSB |
| SMB_CLK_VSB |

### CPU HP-SMBus Connector: 5-pin CPU1_HSBP1

**Board reference:** Layout item 24.

This header supports the hot-plug feature for hard drives on the backplane.

| Pin signal |
|---|
| +3 V |
| GND |
| P0_HP_ALERT_L |
| CPU_HP_SDA |
| CPU_HP_SCL |

## 2.7 ATX PSU / DC-IN Power Connections

The motherboard supports both +12 V DC and ATX power input.

| Connector | DC-IN | ATX PSU |
|---|:---:|:---:|
| 12 V 8-pin | Yes | Yes |
| ATX 4-pin | No | Yes, using the bundled ATX 24-pin-to-4-pin converter cable |

The connection diagrams in the source manual show these configurations:

- **DC-IN:** 12 V 8-pin connected; ATX 4-pin not used.
- **ATX PSU:** 12 V 8-pin connected; ATX 4-pin connected through the 24-pin-to-4-pin converter cable.

To connect the bundled converter cable, make sure that the latch and socket are aligned in the correct direction.

## 2.8 Unit Identification Purpose LED/Switch

The UID button helps locate a server in a rack.

When the UID button on the front or rear panel is pressed, the front and rear blue UID LEDs turn on. Press the UID button again to turn them off.

## 2.9 Driver Installation Guide

1. Insert the support CD into the optical drive.
2. The support CD detects the system and lists compatible drivers.
3. Install required drivers from top to bottom in the listed order.

Installing the drivers in order helps them work correctly.

## 2.10 M.2 SSD (NGFF) Module Installation Guide

M.2, also called Next Generation Form Factor (NGFF), is a compact card-edge connector intended to replace mPCIe and mSATA. The M.2 Socket 3 supports either:

- A SATA3 6.0 Gb/s module.
- A PCI Express module up to Gen4 ×4, or 64 Gb/s.

### Installing an M.2 SSD module

1. Prepare an M.2 SSD module and the screw.
2. Gently insert the module into the M.2 slot. It fits in only one orientation.
3. Align the module with the selected nut position, such as **NUT1** or **NUT2**.
4. Tighten the screw with a screwdriver to secure the module.
5. Do not over-tighten the screw. This may damage the module.

The source illustration specifies a 20° insertion angle.

### M.2 SSD module support list

For the latest M.2 SSD module support list, visit <http://www.asrockrack.com>.

---

# Chapter 3: UEFI Setup Utility

## 3.1 Introduction

The UEFI chip stores the UEFI SETUP UTILITY. Press **F2** or **Del** during the Power-On Self-Test (POST) to enter it. If you do not enter setup, POST continues its test routines.

To enter the utility after POST, restart the system with **Ctrl + Alt + Delete**, the chassis reset button, or a complete power cycle.

### 3.1.1 UEFI Menu Bar

| Menu item | Purpose |
|---|---|
| Main | Set system time and date |
| Advanced | Configure advanced UEFI features |
| Server Mgmt | Manage the server |
| Security | Configure security features |
| Boot | Set the default device used to locate and load the operating system |
| Event Logs | Configure event logs |
| Exit | Exit the current screen or the UEFI SETUP UTILITY |

Use the left and right arrow keys to select a menu item. Press **Enter** to open its sub-screen.

UEFI software is updated regularly. The screens and descriptions in this manual are for reference and may not exactly match the system display.

### 3.1.2 Navigation Keys

| Key | Function |
|---|---|
| Left Arrow / Right Arrow | Move the cursor left or right to select screens |
| Up Arrow / Down Arrow | Move the cursor up or down to select items |
| `+` / `−` | Change the selected option |
| **Tab** | Switch to the next function |
| **Enter** | Open the selected screen |
| **Page Up** | Go to the previous page |
| **Page Down** | Go to the next page |
| **Home** | Go to the top of the screen |
| **End** | Go to the bottom of the screen |
| **F1** | Display the General Help screen |
| **F7** | Discard changes and exit the UEFI SETUP UTILITY |
| **F9** | Load optimal default values |
| **F10** | Save changes and exit the UEFI SETUP UTILITY |
| **F12** | Print screen |
| **Esc** | Jump to the Exit screen or exit the current screen |

## 3.2 Main Screen

The Main screen appears after entering the UEFI SETUP UTILITY. It displays a system overview and allows you to set the system time and date.

## 3.3 Advanced Screen

> **Warning:** Incorrect values in this section may cause the system to malfunction.

The Advanced screen includes:

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

### 3.3.1 CPU Configuration

| Setting | Description |
|---|---|
| SVM Mode | Enable or disable CPU virtualization |
| Node 0 Information | View memory information for Node 0 |

### 3.3.2 Chipset Configuration

| Setting | Description |
|---|---|
| OnBrd/Ext VGA Select | Select onboard or external VGA support |
| Onboard LAN1 | Enable or disable onboard LAN1 |
| Onboard LAN2 | Enable or disable onboard LAN2 |
| Onboard LAN3 | Enable or disable onboard LAN3 |
| Onboard LAN4 | Enable or disable onboard LAN4 |
| SLIM1 Mode | Configure SLIM1 mode |
| SLIM2 Mode | Configure SLIM2 mode |
| SLIM1 Link Width | Select SLIM1 link width; default is `x16` |
| SLIM2 Link Width | Select SLIM2 link width; default is `x16` |
| SLIM3 Link Width | Select SLIM3 link width; default is `x16` |
| PCIE4 Link Width | Select PCIE4 link width; default is `x16` |
| PCIE5 Link Width | Select PCIE5 link width; default is `x16` |
| PCIE6 Link Width | Select PCIE6 link width; default is `x16` |
| PCIE7 Link Width | Select PCIE7 link width; default is `x16` |
| SLIM1 Link Speed | Select SLIM1 link speed; default is `Auto` |
| SLIM2 Link Speed | Select SLIM2 link speed; default is `Auto` |
| SLIM3 Link Speed | Select SLIM3 link speed; default is `Auto` |
| PCIE4 Link Speed | Select PCIE4 link speed; default is `Auto` |
| PCIE5 Link Speed | Select PCIE5 link speed; default is `Auto` |
| PCIE6 Link Speed | Select PCIE6 link speed; default is `Auto` |
| PCIE7 Link Speed | Select PCIE7 link speed; default is `Auto` |
| Onboard Debug Port LED | Enable or disable the onboard Dr. Debug LED |
| Restore AC Power Loss | Set the power state after a power failure. `Power Off` keeps the system off; `Power On` starts boot when power returns |
| Restore AC Power Current State | Restore the current AC power state |

### 3.3.3 Storage Configuration

| Setting | Description |
|---|---|
| SATA Hot Plug | Enable or disable the SATA hot-plug function |

### 3.3.4 ACPI Configuration

| Setting | Description |
|---|---|
| PCIE Devices Power On | Allow a PCIe device to wake the system and enable Wake-on-LAN |
| RTC Alarm Power On | Enable or disable powering on the system by the real-time clock alarm |

### 3.3.5 USB Configuration

| Setting | Description |
|---|---|
| Legacy USB Support | Enable or disable legacy USB-device support; default is `Enabled` |

### 3.3.6 Super IO Configuration

| Setting | Description |
|---|---|
| Serial Port 1 Configuration | Set parameters for Serial Port 1 (COM1) |
| Serial Port | Enable or disable the serial port |
| Serial Port Address | Select an optimal setting for the Super I/O device |
| SOL Configuration | Set parameters for SOL |
| SOL Port | Set SOL port parameters |

### 3.3.7 Serial Port Console Redirection

#### COM1 / SOL

| Setting | Description |
|---|---|
| Console Redirection | Enable or disable console redirection. When enabled, select the COM port used for redirection. |
| Console Redirection Settings | Configure how the system and connected host exchange information. Use compatible settings on both systems. |
| Terminal Type | Select the terminal emulation type. The manual recommends `VT-UTF8`. |

| Option | Description |
|---|---|
| VT100 | ASCII character set |
| VT100+ | Extended VT100 with color and function-key support |
| VT-UTF8 | Uses UTF-8 encoding to map Unicode characters to one or more bytes |
| ANSI | Extended ASCII character set |

| Setting | Description |
|---|---|
| Bits Per Second | Select 9600, 19200, 38400, 57600, or 115200. Use the same speed on the host and client. Lower speeds may help on long or noisy lines. |
| Data Bits | Select 7 or 8 bits |
| Parity | Select None, Even, Odd, Mark, or Space |
| Stop Bits | Select 1 or 2 stop bits. Use 2 for slower devices. |
| Flow Control | Select None or Hardware RTS/CTS |
| VT-UTF8 Combo Key Support | Enable or disable VT-UTF8 combo-key support for ANSI/VT100 terminals |
| Recorder Mode | Enable or disable capture of terminal data and transmission as text messages |
| Resolution 100×31 | Enable or disable extended terminal-resolution support |
| Putty Keypad | Select function-key and keypad behavior for PuTTY |

#### Legacy Console Redirection

| Setting | Description |
|---|---|
| Legacy Console Redirection Settings | Configure the exchange of information between the system and connected host |
| Redirection COM Port | Select the COM port used to display legacy OS and legacy OPROM messages |
| Resolution | Set the number of rows and columns supported by the legacy OS redirection |
| Redirect After POST | `Bootloader` disables legacy console redirection before booting a legacy OS. `Always Enable` keeps it enabled. The default is `Always Enable`. |

#### Serial Port for Out-of-Band Management / Windows EMS

| Setting | Description |
|---|---|
| Console Redirection | Enable or disable console redirection and select the COM port |
| Console Redirection Settings | Configure information exchange between the system and connected host |
| Out-of-Band Mgmt Port | Microsoft Windows Emergency Management Services (EMS) supports remote management of Windows Server through a serial port |
| Terminal Type | Select terminal emulation; the manual recommends `VT-UTF8` |
| Bits Per Second | Select 9600, 19200, 57600, or 115200 |
| Flow Control | Select None, Hardware RTS/CTS, or Software Xon/Xoff |
| Data Bits | Configure data bits |
| Parity | Configure parity |
| Stop Bits | Configure stop bits |

### 3.3.8 H/W Monitor

This screen monitors CPU temperature, motherboard temperature, CPU fan speed, chassis fan speed, and critical voltages.

| Setting | Description |
|---|---|
| Watch Dog Timer | Enable or disable the watchdog timer; default is `Disabled` |

### 3.3.9 PCI Subsystem Settings

| Setting | Description |
|---|---|
| Above 4G Decoding | Enable or disable decoding of 64-bit-capable PCIe devices in the address space above 4 GB, if supported |
| SR-IOV Support | Enable or disable Single Root I/O Virtualization for SR-IOV-capable PCIe devices |

### 3.3.10 AMD CBS

| Setting | Description |
|---|---|
| CPU Common Options | Configure CPU common options |
| DF Common Options | Configure Data Fabric common options |
| UMC Common Options | Configure UMC common options |
| NBIO Common Options | Configure NBIO common options |
| FCH Common Options | Configure FCH common options |
| SoC Miscellaneous Control | Configure SoC miscellaneous-control options |

### 3.3.11 AMD PBS

| Setting | Description |
|---|---|
| RAS | Configure AMD CPM RAS-related settings |

### 3.3.12 PSP Firmware Versions

The PSP Firmware Versions screen displays version information for:

- PSP Recovery BL
- PSP BootLoader
- SMU FW
- ABL
- APCB
- APDB
- APPB

### 3.3.13 Instant Flash

Instant Flash is a UEFI flash utility embedded in the flash ROM. It updates the system UEFI without first entering MS-DOS or Windows®.

1. Save the new UEFI file to a FAT32, FAT16, or FAT12 USB flash drive, floppy disk, or hard drive.
2. Launch Instant Flash.
3. Select the correct UEFI file and review its information.
4. Start the update.
5. Reboot after the update completes.

## 3.4 Server Mgmt

| Setting | Description |
|---|---|
| Wait For BMC | Wait for a BMC response for a specified timeout. The BMC starts with BIOS during AC power-on and takes about 90 seconds to initialize the host-to-BMC interfaces. |
| Inventory Support | Run the system inventory function. Enabling this option adds time to system boot. |

### 3.4.1 System Event Log

| Setting | Description |
|---|---|
| SEL Components | Enable or disable event logging for error and progress codes during boot |
| Erase SEL | Select options for erasing the SEL |
| When SEL is Full | Select the response when the SEL is full |
| Log EFI Status Codes | Disable EFI status-code logging, log only error codes, log only progress codes, or log both |

### 3.4.2 BMC Network Configuration

> **Warning:** When `DHCP` or `Static` is selected, do not modify BMC network settings on the IPMI web page.

| Setting | Description |
|---|---|
| LAN Channel (Failover) | Configure the LAN channel failover setting |
| Manual Setting IPMI LAN | If `No`, DHCP assigns the address. If `Yes`, enter a static address; changes take effect after reboot. Default is `No`. |
| Configuration Address Source | Select `Static` or `DHCP` for BMC network parameters |
| Static | Enter the IP address, subnet mask, and gateway address in BIOS |
| DHCP | The network DHCP server assigns the IP address, subnet mask, and gateway address |
| IPv6 Support | Enable or disable LAN1 IPv6 support |
| Manual Setting IPMI LAN (IPv6) | Configure IPv6 parameters statically or dynamically. `Unspecified` leaves BMC network parameters unchanged during BIOS initialization. |
| IPv6 Index | Set the selector for a static IP; range is 0–15 |

The default IPMI web-interface login information in the source manual is:

- **Username:** `admin`
- **Password:** `admin`

For remote-control setup and IPMI management instructions, see the IPMI Configuration User Guide or visit <http://www.asrockrack.com/support/ipmi.asp>.

### 3.4.3 BMC Tools

> The source contents list labels this section as `3.4.2 BMC Tools`. It duplicates the preceding section number. This Markdown edition uses `3.4.3` so each section has a unique heading.

| Setting | Description |
|---|---|
| Load BMC Default Settings | Load the BMC default settings |
| KCS control | Select the KCS interface state after POST. `Enabled` keeps the KCS interface active; `Disabled` disables it after POST. |

## 3.5 Security

This screen sets or changes the supervisor and user passwords. A user password can also be cleared.

| Setting | Description |
|---|---|
| Supervisor Password | Set or change the administrator password. Only the administrator can change UEFI settings. Leave blank and press **Enter** to remove it. |
| User Password | Set or change the user password. Users cannot change UEFI settings. Leave blank and press **Enter** to remove it. |
| Secure Boot | Enable or disable Secure Boot Control; default is `Disabled`. Secure Boot supports Windows Server 2012 R2 and later. |
| Secure Boot Mode | Select `Standard` or `Custom`. Custom mode permits Secure Boot variables to be configured without authentication. |

### 3.5.1 Key Management

This screen allows expert users to modify Secure Boot policy variables without full authentication.

| Setting | Description |
|---|---|
| Factory Key Provision | Install factory-default Secure Boot keys after platform reset while the system is in Setup mode |
| Install Default Secure Boot Keys | Install default Secure Boot keys when using Secure Boot for the first time |
| Enroll EFI Image | Allow an image to run in Secure Boot mode by enrolling its SHA-256 hash in the Authorized Signature Database (`db`) |
| Restore DB defaults | Restore the `db` variable to factory defaults |

The following key databases support enrolling factory defaults or loading certificates from a file:

- **Platform Key (PK)**
- **Key Exchange Keys (KEK)**
- **Authorized Signatures (`db`)**
- **Forbidden Signatures (`dbx`)**
- **Authorized TimeStamps (`dbt`)**
- **OS Recovery Signatures**

Supported enrollment sources include:

1. Public Key Certificate in:
   - `EFI_SIGNATURE_LIST`
   - `EFI_CERT_X509` (DER)
   - `EFI_CERT_RSA2048` (binary)
   - `EFI_CERT_SHAXXX`
2. Authenticated UEFI variable
3. EFI PE/COFF image using SHA-256

Key-source options shown in the source manual include `Default`, `External`, `Mixed`, and, for the relevant key database, `Test`.

## 3.6 Boot Screen

This screen displays available devices and configures boot settings and priority.

| Setting | Description |
|---|---|
| Boot Option #1 | Set the system boot order |
| Boot Option Filter | Control Legacy/UEFI ROM priority |
| Boot From Onboard LAN | Enable or disable boot from onboard LAN |
| Setup Prompt Timeout | Set the number of seconds to wait for the UEFI setup utility |
| Bootup Num-Lock | Enable or disable Numeric Lock after boot |
| Boot Beep | Enable or disable the boot beep; a buzzer is required |
| Full Screen Logo | Enable or disable the OEM logo; default is `Enabled` |
| AddOn ROM Display | Show or hide AddOn ROM information during boot. Options are `Enabled` and `Disabled`; default is `Enabled`. |

### 3.6.1 CSM Parameters

| Setting | Description |
|---|---|
| CSM | Enable the Compatibility Support Module. Do not disable it unless running a WHCK test. With Windows Server 2012 R2 or later in 64-bit UEFI mode, and with all devices supporting UEFI, disabling CSM may improve boot speed. |
| Launch Video OpROM Policy | Select `UEFI only`, `Legacy only`, or `Do not launch` |
| SLIM1-1 Slot OpROM | Select the storage or network Option ROM policy. In `Auto`, the default is disabled with an NVMe device and Legacy with other devices. Video Option ROM policy is unavailable. |
| SLIM2-1 Slot OpROM | Same policy behavior as SLIM1-1 |
| SLIM2-2 Slot OpROM | Same policy behavior as SLIM1-1 |
| SLIM3-1 OpROM | Same policy behavior as SLIM1-1 |
| SLIM3-2 Slot OpROM | Same policy behavior as SLIM1-1 |
| M2_1 Slot OpROM | Same policy behavior as SLIM1-1 |
| M2_2 Slot OpROM | Same policy behavior as SLIM1-1 |
| PCIE4 Slot OpROM | Same policy behavior as SLIM1-1 |
| PCIE5 Slot OpROM | Same policy behavior as SLIM1-1 |
| PCIE6 Slot OpROM | Same policy behavior as SLIM1-1 |
| PCIE7 Slot OpROM | Same policy behavior as SLIM1-1 |

## 3.7 Event Logs

### Change SMBIOS Event Log Settings

This screen configures SMBIOS event logging.

| Setting | Description |
|---|---|
| SMBIOS Event Log | Enable or disable all SMBIOS event-logging features during boot |
| Erase Event Log | Options are `No`, `Yes, Next reset`, and `Yes, Every reset`. Selecting `Yes` erases all logged events. |
| When Log is Full | Select `Do Nothing` or `Erase Immediately` |
| Log System Boot Event | Enable or disable logging of system boot events |
| MECI (Multiple Event Count Increment) | Set the increment value for the multiple-event counter; valid range is 1–255 |
| METW (Multiple Event Time Window) | Set the minutes between duplicate entries that use a multiple-event counter; range is 0–99 minutes |
| Log EFI Status Code | Enable or disable logging of EFI status codes as OEM-reserved type E0, if not already converted to legacy |
| Convert EFI Status Codes to Standard SMBIOS Type | Enable or disable conversion of EFI status codes to standard SMBIOS types. Not all codes may translate. |
| View SMBIOS Event Log | Press **Enter** to view SMBIOS event-log records |

Changed values do not take effect until the computer restarts.

## 3.8 Exit Screen

| Option | Description |
|---|---|
| Save Changes and Exit | Save configuration changes and exit. Press **F10** or select `Yes`. |
| Discard Changes and Exit | Exit without saving changes. Press **Esc** or select `Yes`. |
| Discard Changes | Discard all changes. Press **F7** or select `Yes`. |
| Load UEFI Defaults | Load default values for all setup questions. Press **F9**. |
| Boot Override | Select an available device and boot from it. |

---

# Chapter 4: Software Support

## 4.1 Install Operating System

The motherboard supports various Microsoft® Windows® Server and Linux operating systems. Motherboard settings and hardware options vary, so use this chapter as a general reference. See the operating-system documentation for details.

## 4.2 Support CD Information

The supplied support CD contains drivers and utilities that enhance the motherboard's features.

### 4.2.1 Running the Support CD

1. Insert the CD into the CD-ROM drive.
2. If `AUTORUN` is enabled, the main menu opens automatically.
3. If the menu does not open, locate and double-click `ASRSetup.exe` in the support CD root folder.

### 4.2.2 Drivers Menu

The Drivers Menu lists available device drivers when the system detects installed devices. Install the required drivers to activate the devices.

### 4.2.3 Utilities Menu

The Utilities Menu lists supported motherboard applications. Select an application and follow the installation wizard.

### 4.2.4 Contact Information

Visit <http://www.asrockrack.com> for more information. You can also contact your dealer.

---

# Chapter 5: Troubleshooting

## 5.1 Troubleshooting Procedures

Follow these procedures to troubleshoot the system.

### Initial checks

1. Disconnect the power cable. Confirm that the PWR LED is off.
2. Unplug all cables and connectors. Remove all add-on cards.
3. Confirm that jumpers use their default settings.
4. Confirm that no short circuit exists between the motherboard and chassis.
5. Install a CPU and fan on the motherboard.
6. Connect the chassis speaker and power LED.

### If there is no power

1. Confirm that no short circuit exists between the motherboard and chassis.
2. Confirm that jumpers use their default settings.
3. Check the power-supply 115 V/230 V switch.
4. Check that the motherboard battery provides approximately 3 VDC. Replace it if necessary.

### If there is no video

1. Reconnect the monitor cables and power cord.
2. Check for memory errors.

### If there are memory errors

1. Confirm that the DIMM modules are fully seated.
2. Use recommended DDR4 RDIMMs, LRDIMMs, or NVDIMMs.
3. If more than one DIMM is installed, use identical modules with the same brand, speed, size, and chip type.
4. Test different DIMMs in different slots to identify faulty modules or slots.
5. Check the power-supply 115 V/230 V switch.

### If system setup configurations cannot be saved

1. Check that the motherboard battery provides approximately 3 VDC. Replace it if necessary.
2. Confirm that the power supply provides adequate and stable power.

### Other problems

Search for relevant keywords on the ASRock Rack FAQ page: <http://www.asrockrack.com/support>.

> **Safety warning**
> Always unplug the power cord before adding, removing, or changing hardware. Failure to do so can cause injury or damage to motherboard components.

## 5.2 Technical Support Procedures

If the troubleshooting procedures do not solve the problem, contact ASRock Rack technical support with:

1. Contact information.
2. Model name, BIOS version, and problem type.
3. System configuration.
4. Problem description.

Technical support: <http://www.asrockrack.com/support/tsd.asp>

## 5.3 Returning Merchandise for Service

For warranty service, provide the receipt or a copy of the invoice showing the purchase date.

1. Contact your vendor or visit the RMA website at <http://event.asrockrack.com/tsd.asp> to obtain a Returned Merchandise Authorization (RMA) number.
2. Display the RMA number on the outside of the shipping carton.
3. Ship or hand-carry the motherboard to the manufacturer. Prepay shipping when required.
4. Shipping and handling charges apply to orders mailed after service is complete.

The warranty does not cover damage caused during shipping or by alteration, misuse, abuse, or improper maintenance.

Contact your distributor first for product-related problems during the warranty period.
