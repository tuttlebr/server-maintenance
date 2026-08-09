ROMED6U-2L2T
User Manual
Version 1.0
Published October 2020
Copyright©2020 ASRock Rack INC. All rights reserved.

---

Version 1.10 
Published Dec. 2024
Copyright©2024 ASRock Rack Inc. All rights reserved.
Copyright Notice:
No part of this documentation may be reproduced, transcribed, transmitted, or translated 
in any language, in any form or by any means, except duplication of documentation by the 
purchaser for backup purpose, without written consent of ASRock Rack Inc.
Products and corporate names appearing in this documentation may or may not be 
registered trademarks or copyrights of their respective companies, and are used only for 
identification or explanation and to the owners' benefit, without intent to infringe.
Disclaimer:
Specifications and information contained in this documentation are furnished for 
informational use only and subject to change without notice, and should not be 
constructed as a commitment by ASRock Rack. ASRock Rack assumes no responsibility 
for any errors or omissions that may appear in this documentation. 
With respect to the contents of this documentation, ASRock Rack does not provide 
warranty of any kind, either expressed or implied, including but not limited to the implied 
warranties or conditions of merchantability or fitness for a particular purpose.
In no event shall ASRock Rack, its directors, officers, employees, or agents be liable for 
any indirect, special, incidental, or consequential damages (including damages for loss of 
profits, loss of business, loss of data, interruption of business and the like), even if ASRock 
Rack has been advised of the possibility of such damages arising from any defect or error 
in the documentation or product.
This device complies with Part 15 of the FCC Rules. Operation is subject to the following 
two conditions: 
(1) this device may not cause harmful interference, and 
(2) this device must accept any interference received, including interference that 
may cause undesired operation.
CALIFORNIA, USA ONLY
The Lithium battery adopted on this motherboard contains Perchlorate, a toxic substance 
controlled in Perchlorate Best Management Practices (BMP) regulations passed by the 
California Legislature. When you discard the Lithium battery in California, USA, please 
follow the related regulations in advance.
"Perchlorate Material-special handling may apply, see www.dtsc.ca.gov/hazardouswaste/
perchlorate"
ASRock Rack's Website: www.ASRockRack.com

---

Contact Information
If you need to contact ASRock Rack or want to know more about ASRock Rack, you're 
welcome to visit ASRock Rack's website at www.ASRockRack.com; or you may contact 
your dealer for further information. 
ASRock Rack Incorporation
6F., No.37, Sec. 2, Jhongyang S. Rd., Beitou District,
Taipei City 112, Taiwan (R.O.C.)

---

Contents
Chapter 1 Introduction 1
1.1 Package Contents 1
1.2 Specifications 2
1.3 Unique Features 5
1.4 Motherboard Layout 6
1.5 Onboard LED Indicators 10
1.6 I/O Panel 11
1.7 Block Diagram 13
Chapter 2 Installation 14
2.1 Screw Holes 14
2.2 Pre-installation Precautions 14
2.3 Installing the CPU 15
2.4 Installation of Memory Modules (DIMM) 19
2.5 Expansion Slots (PCI Express Slots) 21
2.6 Onboard Headers and Connectors 22
2.7 ATX PSU / DC-IN Power Connections 29
2.8 Unit Identification purpose LED/Switch 30
2.9 Driver Installation Guide 30
2.10 M.2_SSD (NGFF) Module Installation Guide 31
Chapter 3 UEFI Setup Utility 32
3.1 Introduction 32
3.1.1 UEFI Menu Bar 32
3.1.2 Navigation Keys 33

---

3.2 Main Screen 34
3.3 Advanced Screen 35
3.3.1 CPU Configuration 36
3.3.2 Chipset Configuration 37
3.3.3 Storage Configuration 40
3.3.4 ACPI Configuration 41
3.3.5 USB Configuration 42
3.3.6 Super IO Configuration 43
3.3.7 Serial Port Console Redirection 44
3.3.8 H/W Monitor 47
3.3.9 PCI Subsystem Settings 48
3.3.10 AMD CBS 49
3.3.11 AMD PBS 50
3.3.12 PSP Firmware Versions 51
3.3.13 Instant Flash 52
3.4 Server Mgmt 53
3.4.1 System Event Log 54
3.4.2 BMC Network Configuration 55
3.4.2 BMC Tools 57
3.5 Security 58
3.5.1 Key Management 59
3.6 Boot Screen 62
3.6.1 CSM Parameters 64
3.7 Event Logs 66

---

3.8 Exit Screen 68
Chapter 4 Software Support 69
4.1 Install Operating System 69
4.2 Support CD Information 69
4.2.1 Running The Support CD 69
4.2.2 Drivers Menu 69
4.2.3 Utilities Menu 69
4.2.4 Contact Information 69
Chapter 5 Troubleshooting 70
5.1 Troubleshooting Procedures 70
5.2 Technical Support Procedures 72
5.3 Returning Merchandise for Service 72

---

ROMED6U-2L2T
1
English
Chapter 1 Introduction
Thank you for purchasing ASRock Rack ROMED6U-2L2T motherboard, a reliable 
motherboard produced under ASRock Rack's consistently stringent quality control. 
It delivers excellent performance with robust design conforming to ASRock Rack's 
commitment to quality and endurance.
In this manual, chapter 1 and 2 contains introduction of the motherboard and stepby-step guide to the hardware installation. Chapter 3 and 4 contains the configuration 
guide to BIOS setup and information of the Support CD. 
1.1 Package Contents
• ASRock Rack ROMED6U-2L2T Motherboard 
(microATX Form Factor: 9.6-in x 9.6-in, 24.4 cm x 24.4 cm)
• Quick Installation Guide
• 1 x I/O Shield 
• 2 x Screws for M.2 Sockets
• 1 x SATA3 Cable (60cm) 
• 1 x Mini SAS HD to 4 SATA Cable (60cm)
• 1 x ATX 4P to 24P Power Cable (8cm)
• 1 x SATA Power Cable (80cm)
If any items are missing or appear damaged, contact your authorized dealer.
Because the motherboard specifications and the BIOS software might be updated, the content of this manual will be subject to change without notice. In case any modifications of 
this manual occur, the updated version will be available on ASRock Rack website without 
further notice. You may find the latest memory and CPU support lists on ASRock Rack 
website as well. ASRock Rack's Website: www.ASRockRack.com
If you require technical support related to this motherboard, please visit our website for 
specific information about the model you are using. 
http://www.asrockrack.com/support/

---

2 
English
1.2 Specifications
ROMED6U-2L2T
MB Physical Status
Form Factor microATX
Dimension 9.6'' x 9.6'' (24.4 cm x 24.4 cm)
Processor System
CPU AMD EPYC™ 7002 Series Processor
Socket Single Socket SP3 (LGA4094)
Chipset N/A
Thermal Design 
Power
280W
System Memory
Type - Six Channel DDR4 memory technology
- Supports DDR4 RDIMM, LRDIMM and NVDIMM
DIMM Size Per 
DIMM
- RDIMM: 64GB, 32GB, 16GB, 8GB 
- LRDIMM: 128GB, 64GB, 32GB 
- NVDIMM: 32GB
DIMM Frequency - RDIMM: 3200MHz 
- LRDIMM: 2666MHz 
- NVDIMM: 2666MHz
Voltage 1.2V
Expansion Slot 
PCIe 4.0 x 16 PCIE7: Gen4 x16 link
PCIE6: Gen4 x16 link
PCIE5: Gen4 x16 link
PCIE4: Gen4 x16 link
Storage
Slimline SLIM1: PCIe Gen4 x8 (Support SATA ) SLIM2: PCIe Gen4 x8 
(Support SATA ) SLIM3: PCIe Gen4 x8
SATA 2x 7Pin SATA3 , 12 x SATA3 6.0 Gb/s (from mini SAS HD , 
Gen3)
M.2 Slot 2 (M2_1:2280, M2_2:2260 Support SATA x1 or PCIE x4)
Ethernet
Interface 10G by Intel X710-AT2 ; 1000 /100 /10 Mbps by Intel i210 
LAN Controller - 2 x RJ45 10G base-T by Intel® X710-AT2
- 1 x RJ45 1G base-T by Intel® I210-AT2
- 1 x RJ45 Dedicated IPMI LAN port by RTL8211E
- Supports Wake-On-LAN
- Supports Energy Effcient Ethernet 802.3az
- Supports Dual LAN with Teaming function
- Supports PXE
- LAN1 supports NCSI

---

ROMED6U-2L2T
3
English
Management
BMC Controller ASPEED AST2500
IPMI Dedicated 
GLAN
1 x Realtek RTL8211E for dedicated management GLAN
Features Watch Dog
NMI
Graphics
Controller ASPEED AST2500
VRAM DDR4 256MB
Rear Panel I/O
VGA Port 1 x D-Sub
USB 3.2 Gen1 Port 2
LAN Port - 4+1 RJ45 Gigabit Ethernet LAN port
- LAN Ports with LED (ACT/LINK LED and SPEED LED)
UID 1
Internal Connector
Auxiliary Panel 
Header
1 (includes chassis intrusion, location button & LED, and front 
LAN LED)
TPMS Header 1
IPMB Header 1
Fan Header 6 Fans x 4-pin
ATX Power 1 x (8-pin) + 1 x (8-pin) + 1 x (4-pin)
SATA Power 1 x (4-pin)
USB 3.2 Gen1 
Header
1 (supports 2 USB 3.2 Gen1 ports)
M.2 2 (M2_1:2280 , M2_2:2260 Support SATA x1 or PCIE x4)
Slimline 3 (SLIM1 / SLIM2: PCIEx8 or SATA Gen3 x8; SLIM3: PCIEx8)
MiniSAS HD 2 (MSAS_HD0: SATA Gen3 x8, MSAS_HD1: SATA Gen3 x4)
Smbus from BMC 1 
PSU SMB 1 
NMI button 1
SGPIO Header 3
Thermal Sensor 
Header 
1
Speaker(4pin) 1 
ClearCMOS 1 (short pad)
CPU_HSBP1 1
Front LAN LED 1
OH/FanFail LED 6 (only Fan Fail LED)
COM Header 1
Panel Header 1
System BIOS
BIOS Type 32MB AMI UEFI Legal BIOS

---

4 
English
BIOS Features - Plug and Play (PnP)
- ACPI 2.0 Compliance Wake Up Events
- SMBIOS 2.8 Support
- ASRock Rack Instant Flash
Hardware Monitor
Temperature - CPU Temperature Sensing
- MB/Card side/TR1 Temperature Sensing
Fan - Fan Tachometer
- CPU Quiet Fan (Allow CPU Fan Speed Auto-Adjust by CPU 
 Temperature)
- Fan Multi-Speed Control
Voltage Voltage Monitoring: +12V, +5V, +3.3V, CPU Vcore, DRAM, 
+BAT, 3VSB, 5VSB
Support OS
OS Microsoft® Windows®
- Server 2016 (64 bit)
- Server 2019 (64 bit)
Linux® 
- RedHat Enterprise Linux Server 8.0 (64 bit) / 7.6 (64 bit)
- CentOs 8.0 (64 bit) / 7.6 ( 64 bit)
- SUSE SLES 15.1 (64 bit) / 12.4 (64 bit)
- UBuntu 18.04.3 (64 bit) / 16.04.6 (64 bit)
- CITRIX Hypervisor 8.1.0
Virtual
- VMWare ESXi 6.5 u3 / 6.7 u3
- vSphere 6.5 u3 / 6.7 u3
* Please refer to our website for the latest OS support list.
Environment
Temperature Operation temperature: 10°C ~ 35°C / Non operation 
temperature: -40°C ~ 70°C
 NOTE: Please refer to our website for the latest specifications.
This motherboard supports Wake from on Board LAN. To use this function, please make 
sure that the "Wake on Magic Packet from power off state" is enabled in Device Manager 
> Intel® Ethernet Connection > Power Management. And the "PCI Devices Power On" is 
enabled in UEFI SETUP UTILITY > Advanced > ACPI Configuration. After that, onboard 
LAN1&4 can wake up S5 under OS.
If you install Intel® LAN utility or Marvell SATA utility, this motherboard may fail Windows® Hardware Quality Lab (WHQL) certification tests. If you install the drivers only, it 
will pass the WHQL tests.

---

ROMED6U-2L2T
5
English
1.3 Unique Features
ASRock Rack Instant Flash is a BIOS flash utility embedded in Flash ROM. This convenient BIOS update tool allows you to update system BIOS without entering operating systems first like MS-DOS or Windows®
. With this utility, you can press the <F6> 
key during the POST or the <F2> key to enter into the BIOS setup menu to access 
ASRock Rack Instant Flash. Just launch this tool and save the new BIOS file to your 
USB flash drive, floppy disk or hard drive, then you can update your BIOS only in a 
few clicks without preparing an additional floppy diskette or other complicated flash 
utility. Please be noted that the USB flash drive or hard drive must use FAT32/16/12 
file system.

---

6 
English
1.4 Motherboard Layout
24.4cm (9.6 in)
VGA1
DDR4_G1 (64 bit, 288-pin module)
DDR4_H1 (64 bit, 288-pin module)
ATX12V2
USB 3.2 Gen1
T: USB2
B: USB1
IPMI_LAN
LAN3
UID1
PCIE7 M2_1
NUT80
HDLED RESET
PLED PWRBTN
PANEL1
1
1
SPEAKER1
1
T R1
1
IPMB_1
1
ASPEED
AST2500
ATX12V1
BMC
ROM
LGA4094
Socket SP3
PSU_SMB1 1
LAN4
DDR4_D1 (64 bit, 288-pin module)
DDR4_C1 (64 bit, 288-pin module)
FAN4
BATTERY1
ATX4PIN1
SATA_PWR1
PWM_CFG1
NMI_BTN1
24.4Cm (9.6 in)
1 2 3 4 5 6 8
9
10
11
12
13
14
15
16
17
28 27 26 24 23
CLRMOS1
25
DDR4_E1 (64 bit, 288-pin module)
DDR4_A1 (64 bit, 288-pin module)
PCIE6
PCIE5
PCIE4
LAN1
LAN2
FAN1 FAN2 FAN3
FAN5
FAN6
SLIM3
SLIM2
SLIM1
MSAS_HD0
MSAS_HD1
Super
I/O
Intel
X710-AT2
Intel
I210-AT2
Intel
I210-AT2
1
SATA_SGPIO3 1
SATA_SGPIO2 1
SATA_SGPIO1
1
USB3_3_4 LED_LAN3_4
1
COM1 TPMS1
1
1
AUX_PANEL1 BMC_SMB1
ROMED6U-2L2T
BIOS
ROM
7
18
19
20
21
38 37 36 35 34 33 32 31 30 29 22
CPU_HSBP1
SATA0
SATA1
Top View

---

ROMED6U-2L2T
7
English
39 M2_2
NUT60_2
Bottom View

---

8 
English
No. Description
1 ATX 12V Power Connector (ATX12V2)
2 ATX 12V Power Connector (ATX12V1)
3 ATX 4-PIN Power Connector (ATX4PIN1)**
4 PSU SMBus Header (PSU_SMB1)
5 PWM Configuration Header (PWM_CFG1)
6 System Fan Connector (FAN1)
7 System Fan Connector (FAN2)
8 System Fan Connector (FAN3)
9 System Fan Connector (FAN4)
10 System Fan Connector (FAN5)
11 System Fan Connector (FAN6)
12 3 x 288-pin DDR4 DIMM Slots (DDR4_E1, DDR4_G1, DDR4_H1)*
13 3 x 288-pin DDR4 DIMM Slots (DDR4_A1, DDR4_C1, DDR4_D1)*
14 SATA Power Connector (DC-IN Mode) (SATAPWR1)**
15 M.2 Socket (M2_1) (Type 2280)
16 Slimline NVMe Connector (SLIM3)
17 Slimline NVMe Connector (SLIM2)
18 Slimline NVMe Connector (SLIM1) (Right-Angled)
19 SATA3 Connector (SATA1) 
20 Mini-SAS HD Connector (MSAS_HD0) (Right-Angled)
21 Mini-SAS HD Connector (MSAS_HD1) (Right-Angled)
22 Speaker Header (SPEAKER1)
23 System Panel Header (PANEL1)
24 Backplane PCI Express Hot-Plug Connector (CPU1_HSBP1)
25 SATA SGPIO Connector (SATA_SGPIO3)
26 SATA SGPIO Connector (SATA_SGPIO2)
27 SATA SGPIO Connector (SATA_SGPIO1)
28 SATA3 Connector (SATA0) 
29 Front LAN LED Connector (LED_LAN3_4)
30 USB 3.2 Gen1 Header (USB3_3_4) (Right-Angled)
31 Clear CMOS Pad (CLRMOS1)
32 COM Port Header (COM1)
33 TPMS Header (TPMS1)

---

9
No. Description
34 Thermal Sensor Header (TR1)
35 Auxiliary Panel Header (AUX_PANEL1) 
36 BMC SMBus Header (BMC_SMB1)
37 Intelligent Platform Management Bus Header (IPMB_1)
38 Non Maskable Interrupt Button (NMI_BTN1)
39 M.2 Socket (M2_2) (Type 2260)
*For DIMM installation and configuration instructions, please see p.19 (Installation of Memory Modules 
(DIMM)) for more details. 
**Caution: Misconnection between the ATX4PIN1 and the SATA_PWR1 connectors may permanently damage 
the motherboard.

---

10 
English
1.5 Onboard LED Indicators
DDR4_G1 (64 bit, 288-pin module)
DDR4_H1 (64 bit, 288-pin module)
LGA4094
Socket SP3
1
DDR4_D1 (64 bit, 288-pin module)
DDR4_C1 (64 bit, 288-pin module)
28 27 26 25 24 23 22 2120 19 18
DDR4_E1 (64 bit, 288-pin module)
DDR4_A1 (64 bit, 288-pin module)
ROMED6U-2L2T
1 2 3
4
6
5
7
8
No. Item Status Description
1 FAN_LED1 Red FAN1 failed
2 FAN_LED2 Red FAN2 failed
3 FAN_LED3 Red FAN3 failed
4 FAN_LED4 Red FAN4 failed
5 FAN_LED5 Red FAN5 failed
6 FAN_LED6 Red FAN6 failed
7 BMC_LED1 Green BMC heartbeat LED
8 SB_PWR1 Green STB PWR ready

---

ROMED6U-2L2T
11
English
1.6 I/O Panel
2
3
1 6 7
8
4
5
No. Description No. Description
1 UID Switch (UID1) 5 1G LAN RJ-45 Port (LAN4)**
2 USB 3.2 Gen1 Ports (USB3_1_2) 6 VGA Port (VGA1)
3 LAN RJ-45 Port (IPMI_LAN1)* 7 10G LAN RJ-45 Port (LAN1)**
4 1G LAN RJ-45 Port (LAN3)** 8 10G LAN RJ-45 Port (LAN2)**
*There are two LED next to the LAN port. Please refer to the table below for the LAN port 
LED indications. 
Dedicated IPMI LAN Port LED Indications
Activity / Link LED Speed LED
Status Description Status Description
Off No Link Off 10M bps connection or no 
link
Blinking Yellow Data Activity Yellow 100M bps connection
On Link Green 1Gbps connection
ACT/LINK LED
SPEED LED
LAN Port

---

12 
English
**There are two LEDs on each LAN port. Please refer to the table below for the LAN port 
LED indications.
1G LAN Port (LAN3, LAN4) LED Indications 
Activity / Link LED Speed LED
Status Description Status Description
Off No Link Off 10Mbps connection or 
no link
Blinking Green Data Activity Yellow 100Mbps connection
On Link Green 1Gbps connection
10G LAN Port (LAN1, LAN2) LED Indications 
Activity / Link LED Speed LED
Status Description Status Description
Off No Link Off 100Mbps connection or 
no link
Blinking Yellow Data Activity Yellow 1Gbps connection
On Link Green 10Gbps connection
ACT/LINK LED
SPEED LED
LAN Port
SPEED LED
ACT/LINK LED

---

ROMED6U-2L2T
13
English
1.7 Block Diagram
55
44
33
22
11
D DC CB BA A
R/LRDIMM
6 DIMM Slots
1 x DDR4 LRDIMM/RDIMM
AMD Family 17h Processor
DDR4 DDR4 DDR4CPU 
PCI-E
AMD EPYC 700x
Port G3.0~7Port G1Port G0
10/100/1GRTL8211EREALTEK
PHY
DDR4 DDR4 DDR4 1 x DDR4 LRDIMM/RDIMM 1 x DDR4 LRDIMM/RDIMM 1 x DDR4 LRDIMM/RDIMM
PCIe Gen4 x16
PCI-E
x8
0~7Port P0.
Port P2
(512MB)DDR4 DRAM
BMC
AST2500
Ethernet
10/100/1000
Video
DAC
VRAMBMC &
PCI-Express
USB
1.1 &
2.0 LPC
MAC2 SPI
(512Mb)SPI FLASH
PCI-E Gen3 
x1
LPC PCIE Gen3 x 1
LPC
USB
USB2.0 x 2
TPM 2.0
PCI-E
P1.12
PCIE Gen3 x 1
Port G2.0~3
x16
1 x DDR4 LRDIMM/RDIMM1 x DDR4 LRDIMM/RDIMM
NCSI
USB 3.2 USB3.2 GEN1
F_USB1
NCT6779SIO
Ethernet
10/100/1000
MAC1
SLIM3
Port G3.8~15
PCIe Gen4 x8
8~15Port P0.
Slimline Conn.
x8
PCIE Gen4 x 16
SLIM1
Slimline Conn.
PCIe Gen4 x4 *2orSATA Gen3 x 8
2. NVMe*21. SATA*8Support:
SATA Gen3 x 2
PCIe Gen4 x16
PCIE Gen4 x 16
PCIE7PCIE6
PCIE4PCIE5
SATA 7Pin
PCIe Gen4 x4
M2_1
M.2 Socket
2. PCIE1. SATASupport:
MSAS_HD0 Mini SAS HD
SATA GEN3 x8
Port P3
PCI-E
x16
PCI-E
x8
0~7Port P1.
x4
8~11Port P1.
x1 x1
 13Port P1
 14Port P1
SLIM2
Slimline Conn.
PCIe Gen4 x4 *2orSATA Gen3 x 8
2. NVMe*21. SATA*8Support:
PCIE Gen3 x 4
X710-AT2INTEL
10G
I210 AT2*2INTEL
1G
PCIE Gen3 x 1
R/LRDIMMR/LRDIMM
R/LRDIMMR/LRDIMMR/LRDIMM
SATA_0_7 use SGPIO_3SATA_8_11 , SATA12 , SATA13 use SGPIO_2SLIM2 use SGPIO_1SLIM1 use SGPIO_0SATA SGPIO Configuration
Port G2.8~15Port G2.4~7
M2_2
M.2 SocketMSAS_HD1 Mini SAS HD
SATA GEN3 x4
Resistance Option
Size Project Name Rev
Date: Sheet of
Title :
Engineer:
C
1 127 Thursday, November 26, 2020
Asrockrack
000-BLOCK
R1.00 ROMED6U-2L2T
Eric Hu
<Variant Name>
Size Project Name Rev
Date: Sheet of
Title :
Engineer:
C
1 127 Thursday, November 26, 2020
Asrockrack
000-BLOCK
R1.00 ROMED6U-2L2T
Eric Hu
<Variant Name>
Size Project Name Rev
Date: Sheet of
Title :
Engineer:
C
1 127 Thursday, November 26, 2020
Asrockrack
000-BLOCK
R1.00 ROMED6U-2L2T
Eric Hu
<Variant Name>

---

14 
English
Chapter 2 Installation
This is a microATX form factor (9.6'' x 9.6'', 24.4 cm x 24.4 cm) motherboard. Before 
you install the motherboard, study the configuration of your chassis to ensure that the 
motherboard fits into it.
2.1 Screw Holes
Place screws into the holes indicated by circles to secure the motherboard to the chassis.
2.2 Pre-installation Precautions
Take note of the following precautions before you install motherboard components or 
change any motherboard settings.
1. Unplug the power cord from the wall socket before touching any components.
2. To avoid damaging the motherboard's components due to static electricity, NEVER 
place your motherboard directly on the carpet or the like. Also remember to use a 
grounded wrist strap or touch a safety grounded object before you handle the components. 
3. Hold components by the edges and do not touch the ICs. 
4. Whenever you uninstall any component, place it on a grounded anti-static pad or in 
the bag that comes with the component.
5. When placing screws into the screw holes to secure the motherboard to the chassis, 
please do not over-tighten the screws! Doing so may damage the motherboard. 
Make sure to unplug the power cord before installing or removing the motherboard. Failure 
to do so may cause physical injuries to you and damages to motherboard components.
Do not over-tighten the screws! Doing so may damage the motherboard.
Before you install or remove any component, ensure that the power is switched off or the 
power cord is detached from the power supply. Failure to do so may cause severe damage to 
the motherboard, peripherals, and/or components.

---

ROMED6U-2L2T
15
English
2.3 Installing the CPU
1. Before you insert the CPU into the socket, please check if the PnP cap is on the socket, 
if the CPU surface is unclean, or if there are any bent pins in the socket. Do not force to 
insert the CPU into the socket if above situation is found. Otherwise, the CPU will be 
seriously damaged. 
2. Unplug all power cables before installing the CPU.
1
2

---

16 
English
3
4

---

ROMED6U-2L2T
17
English
Please make sure that the carrier
frame with CPU is closely attached to 
the rail frame while inserting it.
5
6
Install the carrier frame with CPU. Don't separate them.
Carrier Frame with CPU
Rail Frame

---

18 
English
7
8

---

ROMED6U-2L2T
19
English
2.4 Installation of Memory Modules (DIMM)
This motherboard provides six 288-pin DDR4 (Double Data Rate 4) DIMM slots in two 
groups, and supports Six Channel Memory Technology. 
A1 C1 D1 E1 G1 H1
1 DIMM #
2 DIMMS # #
4 DIMMS # # # #
6 DIMMS # # # # # #
1. It is not allowed to install a DDR, DDR2 or DDR3 memory module into a DDR4 slot; 
otherwise, this motherboard and DIMM may be damaged.
2. For dual channel configuration, you always need to install identical (the same brand, 
speed, size and chip-type) DDR4 DIMM pairs. 
3. It is unable to activate Dual Channel Memory Technology with only one or three memory 
module installed.
4. Some DDR4 1GB double-sided DIMMs with 16 chips may not work on this motherboard. 
It is not recommended to install them on this motherboard.

---

20 
English
The DIMM only fits in one correct orientation. It will cause permanent damage to the 
motherboard and the DIMM if you force the DIMM into the slot at incorrect orientation.
1
2
3

---

ROMED6U-2L2T
21
English
2.5 Expansion Slots (PCI Express Slots)
There is 4 PCI Express slot on this motherboard.
PCIE slots: 
PCIE7, PCIE6, PCIE5 and PCIE4 (PCIE 4.0 x16 slot, from CPU) are used for PCI Express 
x16 lane width cards. 
Slot Generation Mechanical Electrical Source
PCIE7 4.0 x16 x16 CPU
PCIE6 4.0 x16 x16 CPU
PCIE5 4.0 x16 x16 CPU
PCIE4 4.0 x16 x16 CPU
Installing an expansion card
Step 1. Before installing an expansion card, please make sure that the power 
supply is switched off or the power cord is unplugged. Please read the 
documentation of the expansion card and make necessary hardware 
settings for the card before you start the installation.
Step 2. Remove the system unit cover (if your motherboard is already installed 
in a chassis).
Step 3. Remove the bracket facing the slot that you intend to use. Keep the 
screws for later use.
Step 4. Align the card connector with the slot and press firmly until the card is 
completely seated on the slot.
Step 5. Fasten the card to the chassis with screws.
Step 6. Replace the system cover.

---

22 
English
2.6 Onboard Headers and Connectors
System Panel Header
(9-pin PANEL1)
(see p.6, No. 23)
GND
RESET#
PWRBTN#
PLEDPLED+
GND
HDLEDHDLED+
1
GND
Connect the power switch, 
reset switch and system status 
indicator on the chassis to this 
header according to the pin 
assignments. Particularly note 
the positive and negative pins 
before connecting the cables.
PWRBTN (Power Switch):
Connect to the power switch on the chassis front panel. You may configure the way to turn 
off your system using the power switch.
RESET (Reset Switch):
Connect to the reset switch on the chassis front panel. Press the reset switch to restart the 
computer if the computer freezes and fails to perform a normal restart.
PLED (System Power LED):
Connect to the power status indicator on the chassis front panel. The LED is on when the 
system is operating. The LED is off when the system is in S4 sleep state or powered off (S5).
HDLED (Hard Drive Activity LED):
Connect to the hard drive activity LED on the chassis front panel. The LED is on when the 
hard drive is reading or writing data.
The front panel design may differ by chassis. A front panel module mainly consists of power 
switch, reset switch, power LED, hard drive activity LED, speaker and etc. When connecting your chassis front panel module to this header, make sure the wire assignments and the 
pin assignments are matched correctly.
Onboard headers and connectors are NOT jumpers. Do NOT place jumper caps over these 
headers and connectors. Placing jumper caps over the headers and connectors will cause 
permanent damage to the motherboard.

---

ROMED6U-2L2T
23
English
Auxiliary Panel Header
(18-pin AUX PANEL1) 
(see p.6, No. 35)
GND
SMB_Aler
SMB_CLK
t
CASEOPEN
1
SMB_DATA
+3VSB
LAN1_LINK
LED_PWR
LED_PWR
LAN2_LINK
+5VSB
GND
GND
LOCATORLED1+
LOCATORLED1-
LOCATORBTN#
LOCATORLED2+
LOCATORLED2-
A B
C D
This header supports multiple 
functions on the front panel, 
including the front panel SMB, 
internet status indicator and 
chassis intrusion pin.
Serial ATA3 Connectors
(SATA0) 
(see p.6, No. 28)
(SATA1) 
(see p.6, No. 19) SA TA0
SA TA1 These two SATA3 connectors 
support SATA data cables for 
internal storage devices with 
up to 6.0 Gb/s data transfer 
rate. 
A. Front panel SMBus connecting pin (6-1 pin FPSMB) 
This header allows you to connect SMBus (System Management Bus) equipment. It can 
be used for communication between peripheral equipment in the system, which has slower 
transmission rates, and power management equipment. 
B. Internet status indicator (2-pin LAN1_LED, LAN2_LED) 
These two 2-pin headers allow you to use the Gigabit internet indicator cable to connect 
to the LAN status indicator. When this indicator flickers, it means that the internet is properly connected.
C. Chassis intrusion pin (2-pin CHASSIS) 
This header is provided for host computer chassis with chassis intrusion detection designs. 
In addition, it must also work with external detection equipment, such as a chassis intrusion detection sensor or a microswitch. When this function is activated, if any chassis 
component movement occurs, the sensor will immediately detect it and send a signal to this 
header, and the system will then record this chassis intrusion event. The default setting is 
set to the CASEOPEN and GND pin; this function is off.
D. Locator LED (4-pin LOCATOR)
This header is for the locator switch and LED on the front panel.
E. System Fault LED (2-pin LOCATOR)
This header is for the Fault LED on the system.

---

24 
English
1
Dummy
GND
GND
Vbus
GND
GND
IntA_PA_SSRX+
Vbus
IntA_PA_D+
IntA_PA_DIntA_PA_SSTX+
IntA_PA_SSTXIntA_PA_SSRXIntA_PB_SSRXIntA_PB_SSRX+
IntA_PB_SSTXIntA_PB_SSTX+
IntA_PB_DIntA_PB_D+
USB 3.2 Gen1 Header
Right-Angled:
(19-pin USB3_3_4)
(see p.6, No. 30)
Besides two default USB 3.2 
Gen1 ports on the I/O panel, 
there is one USB 3.2 Gen1 
header on this motherboard. 
This USB 3.2 Gen1 header can 
support two USB 3.2 Gen1 
ports.
Chassis Speaker Header
(4-pin SPEAKER1)
(see p.6, No. 22)
1
+5V
DUMMY
DUMMY
SPEAKER Please connect the chassis 
speaker to this header.
System Fan Connectors
(4-pin FAN1)
(see p.6, No. 6)
(4-pin FAN2)
(see p.6, No. 7)
(4-pin FAN3)
(see p.6, No. 8)
(4-pin FAN4)
(see p.6, No. 6)
(4-pin FAN5)
(see p.6, No. 7)
(4-pin FAN6)
(see p.6, No. 8)
FAN_SPEED
FAN_SPEED_CONTROL
FAN_VOLTAGE
GND
4 3 2 1 Please connect the fan cables to 
the fan connectors and match 
the black wire to the ground 
pin. All fans supports Fan 
Control.
Mini-SAS HD Connectors
Right-Angled:
(MSAS_HD0)
(see p.6, No. 20)
(MSAS_HD1)
(see p.6, No. 21)
MSAS_HD0
MSAS_HD1
These connectors 
support MiniSAS-toSATA data cables for 
internal storage devices 
with up to 6.0 Gb/s data 
transfer rate.

---

ROMED6U-2L2T
25
English
Slimline NVMe 
Connectors
Right-Angled:
(SLIM1)
(see p.6, No. 18)
Vertical:
(SLIM2)
(see p.6, No. 17)
(SLIM3)
(see p.6, No. 16)
S LIM 3
S LIM 2
S LIM 1
These connectors are used for 
the NVME PCIE devices.
Serial Port Header
(9-pin COM1)
(see p.6, No. 32)
CCTS#1
RRTS#1
DDSR#1
DDTR#1
RRXD1
GND
TTXD1
DDCD#1
1
RRI#1
This COM header supports a 
serial port module.
ATX 4-PIN Power 
Connector
(4-pin ATX4PIN1 
(ATX 24pin-to-4pin))
(see p.6, No. 3)
The motherboard provides one 
4-pin power/signal connector 
which is a required input for 
ATX power source.
When using ATX power, it is 
necessary to use a 24pin-to4pin power cable to connect 
between the 24pin power 
connector of PSU and the 
ATX4PIN1 connector on the 
motherboard for power supply 
and signal communication.
For DC-IN 12V application, 
it is not necessary to use this 
ATX 4-PIN power connector.
*Caution: Misconnection between 
the ATX4PIN1 and the SATA_PWR1 
connectors may permanently damage 
the motherboard.
1 2
3 4
ATX_PWROK
PSON#
GND
ATX_+5VSB

---

26 
English
SATA Power Connector 
(DC-IN Mode)
(4-pin SATA_PWR1)
(see p.6, No. 14)
1 2
3 4
+5V
GND
+12V
GND
Please use a SATA power cable
to connect this SATA Power
Connector and your SATA
HDD for supplying power
from the motherboard, when
using DC-IN mode without
SATA power supply.
*Caution: Misconnection between 
the ATX4PIN1 and the SATA_PWR1 
connectors may permanently damage 
the motherboard.
ATX 12V Power 
Connectors
(8-pin ATX12V1)
(see p.6, No. 2)
(8-pin ATX12V2)
(see p.6, No. 1)
4
8
1
5
12V
GND The motherboard provides two 
8-pin 12V power connectors 
which are required input for 
either DC-IN 12V or ATX 
+12V power source.
When using ATX power, it is 
necessary to use a 24pin-to4pin power cable to connect 
between the 24pin power 
connector of PSU and the 
ATX4PIN1 connector on the 
motherboard for power supply 
and signal communication.
Clear CMOS Pads
(CLRMOS1)
(see p.6, No. 31)
This allows you to clear the 
data in CMOS. To clear CMOS, 
take out the CMOS battery and 
short the Clear CMOS Pad.
Front LAN LED Header 
(4-pin LED_LAN3_4)
(see p.5, No. 29)
1
LAN4_LINK
LED_PWR
LED_PWR
LAN3_LINK
This 4-pin connector is used 
for the front LAN status 
indicator.

---

ROMED6U-2L2T
27
English
TPMS Header
(17-pin TPMS1)
(see p.6, No. 33) 1 GND SMB_DATA_MAIN GN LAD1 LAD2
D
S_PWRDWN#
SERIRQ#
GND
PCICLK
PCIRST#
+3
LAD3
V
+3VS
LAD0
B
GND
LFRAME# SMB_CLK_MAIN
This connector supports 
Trusted Platform Module 
(TPM) system, which can 
securely store keys, digital 
certificates, passwords, and 
data. A TPM system also helps 
enhance network security, 
protects digital identities, and 
ensures platform integrity.
PSU SMBus Header
(5-pin PSU_SMB1)
(see p.6, No. 4)
+3V
1
GND
ALERT
SMBCLK
SMBDATA
PSU SMBus monitors the 
status of the power supply, fan 
and system temperature.
Intelligent Platform 
Management Bus Header
(4-pin IPMB_1)
(see p.6, No. 37)
IPMB_SDA
IPMB_SCL
No Connect
GND
This 4-pin connector is used 
to provide a cabled base-board 
or front panel connection for 
value added features and 3rdparty add-in cards, such as 
Emergency Management cards, 
that provide management 
features using the IPMB.
Thermal Sensor Header
(3-pin TR1)
(see p.6, No. 34) 1
TR1 TR1
GND
Please connect the thermal 
sensor cable to either pin 1-2 
or pin 2-3 and the other end to 
the device which you wish to 
monitor its temperature.
Non Maskable Interrupt 
Button Header
(NMI_BTN1)
(see p.6, No. 38)
1
CONTROL
GND Please connect a NMI device
to this header.

---

28 
English
Serial General Purpose 
Input/Output Headers
(7-pin SATA_SGPIO1)
(see p.6, No. 27)
(7-pin SATA_SGPIO2)
(see p.6, No. 26)
(7-pin SATA_SGPIO3)
(see p.6, No. 25)
1
SLOAD
SCLOCK
GND
GND
SDATAOUT
These headers support Serial 
Link interface for onboard 
SATA connections. 
Baseboard Management 
Controller SMBus Header
(5-pin BMC_SMB1)
(see p.6, No. 36)
BMC_SMB_PRESENT_1_N
Power
BMC_SMBCLK
GND
BMC_SMBDATA
1
The header is used for the SM 
BUS devices.
PWM Configuration 
Header
(3-pin PWM_CFG1)
(see p.6, No. 5)
GND
SMB_DATA_VSB
SMB_CLK_VSB
1
This header is used for PWM 
configurations.
CPU HP-SMBus Connector
(5-pin CPU1_HSBP1)
(see p.6, No. 24)
1
+3V
GND
P0_HP_ALERT_L
CPU_HP_SDA
CPU_HP_SCL
This header is used for the hot 
plug feature of HDDs on the 
backplane.

---

ROMED6U-2L2T
29
English
2.7 ATX PSU / DC-IN Power Connections
This motherboard supports both +12V DC and ATX power input. Please refer to the 
table below for the required connections between the motherboard and the power 
supply.
Connector DC-IN ATX PSU
12V 8pin O O
ATX 4pin X
O
(with the bundled ATX 
24pin-to-4pin converter cable)
PSU
12V 8pin ATX 4pin
(via a 24pin-to-4pin 
Converter Cable)
PSU
12V 8pin
DC-IN ATX PSU
The following diagram illustrates how to connect the bundled ATX 24pin-to-4pin 
converter cable.
24pin-to-4pin
Converter Cable
* Make sure the latch and the socket 
 are aligned in the right direction.

---

30 
English
2.8 Unit Identification purpose LED/Switch
With the UID button, You are able to locate the server you're working on from behind 
a rack of servers.
Unit Identification 
purpose LED/Switch
(UID1)
When the UID button on the 
front or rear panel is pressed, 
the front/rear UID blue LED 
indicator will be truned on. 
Press the UID button again to 
turn off the indicator.
2.9 Driver Installation Guide
To install the drivers to your system, please insert the support CD to your optical 
drive first. Then, the drivers compatible to your system can be auto-detected and listed 
on the support CD driver page. Please follow the order from top to bottom to install 
those required drivers. Therefore, the drivers you install can work properly.

---

ROMED6U-2L2T
31
English
2.10 M.2_SSD (NGFF) Module Installation Guide 
The M.2, also known as the Next Generation Form Factor (NGFF), is a small size and 
versatile card edge connector that aims to replace mPCIe and mSATA. This M.2_SSD 
(NGFF) Socket 3 can accommodate a SATA3 6.0 Gb/s module or a PCI Express module up 
to Gen4 x4 (64 Gb/s) only. 
Installing the M.2_SSD (NGFF) Module
Step 1
Prepare a M.2_SSD (NGFF) module 
and the screw.
20o
Step 2
Gently insert the M.2 (NGFF) SSD 
module into the M.2 slot. Please 
be aware that the M.2 (NGFF) SSD 
module only fits in one orientation.
NUT2 NUT1
Step 3
Tighten the screw with a screwdriver 
to secure the module into place. 
Please do not overtighten the screw as 
this might damage the module.
M.2_SSD (NGFF) Module Support List
For the latest updates of M.2_SSD (NFGG) module support list, please visit our website for 
details: http://www.asrockrack.com

---

32 
English
Chapter 3 UEFI Setup Utility
3.1 Introduction
This section explains how to use the UEFI SETUP UTILITY to configure your system. The 
UEFI chip on the motherboard stores the UEFI SETUP UTILITY. You may run the UEFI 
SETUP UTILITY when you start up the computer. Please press <F2> or <Del> during the 
Power-On-Self-Test (POST) to enter the UEFI SETUP UTILITY; otherwise, POST will 
continue with its test routines.
If you wish to enter the UEFI SETUP UTILITY after POST, restart the system by pressing 
<Ctrl> + <Alt> + <Delete>, or by pressing the reset button on the system chassis. You may 
also restart by turning the system off and then back on.
3.1.1 UEFI Menu Bar
The top of the screen has a menu bar with the following selections: 
Item Description
Main To set up the system time/date information
Advanced To set up the advanced UEFI features
Server Mgmt To manage the server
Security To set up the security features
Boot To set up the default system device to locate and load the 
Operating System
Event Logs For event log configuration
Exit To exit the current screen or the UEFI SETUP UTILITY
Use < > key or < > key to choose among the selections on the menu bar, and 
then press <Enter> to get into the sub screen. 
Because the UEFI software is constantly being updated, the following UEFI setup screens 
and descriptions are for reference purpose only, and they may not exactly match what you 
see on your screen.

---

ROMED6U-2L2T
33
English
3.1.2 Navigation Keys
Please check the following table for the function description of each navigation key. 
Navigation Key(s) Function Description
 / Moves cursor left or right to select Screens
 / Moves cursor up or down to select items
 + / - To change option for the selected items
<Tab> Switch to next function
<Enter> To bring up the selected screen
<PGUP> Go to the previous page
<PGDN> Go to the next page
<HOME> Go to the top of the screen
<END> Go to the bottom of the screen
<F1> To display the General Help Screen 
<F7> Discard changes and exit the UEFI SETUP UTILITY
<F9> Load optimal default values for all the settings
<F10> Save changes and exit the UEFI SETUP UTILITY
<F12> Print screen
<ESC> Jump to the Exit Screen or exit the current screen

---

34 
English
3.2 Main Screen
Once you enter the UEFI SETUP UTILITY, the Main screen will appear and display the 
system overview. The Main screen provides system overview information and allows you 
to set the system time and date.

---

ROMED6U-2L2T
35
English
Setting wrong values in this section may cause the system to malfunction.
3.3 Advanced Screen
In this section, you may set the configurations for the following items: CPU Configuration, 
Chipset Configuration, Storage Configuration, ACPI Configuration, USB Configuration, 
Super IO Configuration, Serial Port Console Redirection, H/W Monitor, PCI Subsystem 
Settings, AMD CBS, AMD PBS, PSP Firmware Versions and Instant Flash.

---

36 
English
3.3.1 CPU Configuration
SVM Mode
Enable or disable CPU Virtualization.
Node 0 Information
View Memory Information related to Node 0.

---

ROMED6U-2L2T
37
English
3.3.2 Chipset Configuration
OnBrd/Ext VGA Select
Select between onboard or external VGA support.
Onboard LAN1
This allows you to enable or disable the Onboard LAN1 feature.
Onboard LAN2
This allows you to enable or disable the Onboard LAN2 feature.
Onboard LAN3
This allows you to enable or disable the Onboard LAN3 feature.
Onboard LAN4
This allows you to enable or disable the Onboard LAN4 feature.
SLIM1 Mode
This allows you configure SLIM1 Mode settings.
SLIM2 Mode
This allows you configure SLIM2 Mode settings.

---

38 
English
SLIM1 Link Width
This allows you to select SLIM1 Link Width. The default value is [x16].
SLIM2 Link Width
This allows you to select SLIM2 Link Width. The default value is [x16].
SLIM3 Link Width
This allows you to select SLIM3 Link Width. The default value is [x16].
PCIE4 Link Width
This allows you to select PCIE4 Link Width. The default value is [x16].
PCIE5 Link Width
This allows you to select PCIE5 Link Width. The default value is [x16].
PCIE6 Link Width
This allows you to select PCIE6 Link Width. The default value is [x16].
PCIE7 Link Width
This allows you to select PCIE7 Link Width. The default value is [x16].
SLIM1 Link Speed
This allows you to select SLIM1 Link Speed. The default value is [Auto].
SLIM2 Link Speed
This allows you to select SLIM2 Link Speed. The default value is [Auto].
SLIM3 Link Speed
This allows you to select SLIM3 Link Speed. The default value is [Auto].
PCIE4 Link Speed
This allows you to select PCIE4 Link Speed. The default value is [Auto].
PCIE5 Link Speed
This allows you to select PCIE5 Link Speed. The default value is [Auto].
PCIE6 Link Speed
This allows you to select PCIE6 Link Speed. The default value is [Auto].
PCIE7 Link Speed
This allows you to select PCIE7 Link Speed. The default value is [Auto].

---

ROMED6U-2L2T
39
English
Onboard Debug Port LED
Enable or disable the onboard Dr. Debug LED.
Restore AC Power Loss
This allows you to set the power state after a power failure. If [Power Off] is selected, the 
power will remain off when the power recovers. If [Power On] is selected, the system will 
start to boot up when the power recovers.
Restore AC Power Current State
This allows you to restore AC Power Current State.

---

40 
English
3.3.3 Storage Configuration
SATA Hot Plug
Enable/disable the SATA Hot Plug Function.

---

ROMED6U-2L2T
41
English
3.3.4 ACPI Configuration
PCIE Devices Power On
Allow the system to be waked up by a PCIE device and enable wake on LAN. 
RTC Alarm Power On
Use this item to enable or disable RTC (Real Time Clock) to power on the system.

---

42 
English
3.3.5 USB Configuration
Legacy USB Support
Use this option to enable or disable legacy support for USB devices. The default value is 
[Enabled].

---

ROMED6U-2L2T
43
English
3.3.6 Super IO Configuration
Serial Port 1 Configuration
Use this item to set parameters of Serial Port 1 (COM1).
Serial Port
Use this item to enable or disable the serial port.
Serial Port Address
Use this item to select an optimal setting for Super IO device.
SOL Configuration
Use this item to set parameters of SOL.
SOL Port
Use this item to set parameters of SOL.
Serial Port Address
Use this item to select an optimal setting for Super IO device.

---

44 
English
3.3.7 Serial Port Console Redirection
COM1 / SOL
Console Redirection
Use this option to enable or disable Console Redirection. If this item is set to Enabled, you 
can select a COM Port to be used for Console Redirection.
Console Redirection Settings
Use this option to configure Console Redirection Settings, and specify how your computer 
and the host computer to which you are connected exchange information. Both computers 
should have the same or compatible settings.
Terminal Type
Use this item to select the preferred terminal emulation type for out-of-band management.
It is recommended to select [VT-UTF8].
Option Description
VT100 ASCII character set
VT100+ Extended VT100 that supports color and function keys
VT-UTF8 UTF8 encoding is used to map Unicode chars onto 1 or more bytes
ANSI Extended ASCII character set

---

ROMED6U-2L2T
45
English
Bits Per Second
Use this item to select the serial port transmission speed. The speed used in the host 
computer and the client computer must be the same. Long or noisy lines may require lower 
transmission speed. The options include [9600], [19200], [38400], [57600] and [115200].
Data Bits
Use this item to set the data transmission size. The options include [7] and [8] (Bits).
Parity
Use this item to select the parity bit. The options include [None], [Even], [Odd], [Mark] and 
[Space].
Stop Bits
The item indicates the end of a serial data packet. The standard setting is [1] Stop Bit. Select 
[2] Stop Bits for slower devices.
Flow Control
Use this item to set the flow control to prevent data loss from buffer overflow. When 
sending data, if the receiving buffers are full, a "stop" signal can be sent to stop the data 
flow. Once the buffers are empty, a "start" signal can be sent to restart the flow. Hardware 
flow uses two wires to send start/stop signals. The options include [None] and [Hardware 
RTS/CTS].
VT-UTF8 Combo Key Support
Use this item to enable or disable the VT-UTF8 Combo Key Support for ANSI/VT100 
terminals.
Recorder Mode
Use this item to enable or disable Recorder Mode to capture terminal data and send it as 
text messages.
Resolution 100x31
Use this item to enable or disable extended terminal resolution support.
Putty Keypad
Use this item to select Function Key and Keypad on Putty.
Legacy Console Redirection
Legacy Console Redirection Settings
Use this option to configure Legacy Console Redirection Settings, and specify how your 
computer and the host computer to which you are connected exchange information.
Redirection COM Port
Select a COM port to display redirection of Legacy OS and Legacy OPROM Messages.
Resolution
On Legacy OS, the Number of Rows and Columns supported redirection.

---

46 
English
Redirect After POST
When Bootloader is selected, then Legacy Console Redirection is disabled before booting 
to legacy OS. When Always Enable is selected, then Legacy Console Redirection is enabled 
for legacy OS. Default setting for this option is set to Always Enable.
Serial Port for Out-of-Band Management/Windows Emergency 
Management Services (EMS)
Console Redirection
Use this option to enable or disable Console Redirection. If this item is set to Enabled, you 
can select a COM Port to be used for Console Redirection.
Console Redirection Settings
Use this option to configure Console Redirection Settings, and specify how your computer 
and the host computer to which you are connected exchange information.
Out-of-Band Mgmt Port
Microsof t Windows Emergency Management Services (EMS) allows for remote 
management of a Windows Server OS through a serial port.
Terminal Type
Use this item to select the preferred terminal emulation type for out-of-band management.
It is recommended to select [VT-UTF8].
Option Description
VT100 ASCII character set
VT100+ Extended VT100 that supports color and function keys
VT-UTF8 UTF8 encoding is used to map Unicode chars onto 1 or more bytes
ANSI Extended ASCII character set
Bits Per Second
Use this item to select the serial port transmission speed. The speed used in the host 
computer and the client computer must be the same. Long or noisy lines may require lower 
transmission speed. The options include [9600], [19200], [57600] and [115200].
Flow Control
Use this item to set the flow control to prevent data loss from buffer overflow. When 
sending data, if the receiving buffers are full, a "stop" signal can be sent to stop the data 
flow. Once the buffers are empty, a "start" signal can be sent to restart the flow. Hardware 
flow uses two wires to send start/stop signals. The options include [None], [Hardware RTS/
CTS], and [Software Xon/Xoff].
Data Bits
Parity
Stop Bits

---

ROMED6U-2L2T
47
English
3.3.8 H/W Monitor
In this section, it allows you to monitor the status of the hardware on your system, including the parameters of the CPU temperature, motherboard temperature, CPU fan speed, 
chassis fan speed, and the critical voltage.
Watch Dog Timer
This allows you to enable or disable the Watch Dog Timer. The default value is [Disabled].

---

48 
English
3.3.9 PCI Subsystem Settings
Above 4G Decoding
Enable or disable 64bit capable Devices to be decoded in Above 4G Address Space (only if
the system supports 64 bit PCI decoding).
SR-IOV Support
If system has SR-IOV capable PCIe Devices, this option Enables or Disables Single Root IO 
Virtualization Support.

---

ROMED6U-2L2T
49
English
3.3.10 AMD CBS
CPU Common Options
Use this item to configure CPU Common options.
DF Common Options
Use this item to configure DF Common options.
UMC Common Options
Use this item to configure UMC Common options.
NBIO Common Options
Use this item to configure NBIO Common options.
FCH Common Options
Use this item to configure FCH Common options.
Soc Miscellaneous Control
Use this item to configure Soc Miscellaneous Control options.

---

50 
English
3.3.11 AMD PBS
RAS
Use this item to configure AMD CPM RAS related settings.

---

ROMED6U-2L2T
51
English
3.3.12 PSP Firmware Versions
The PSP Firmware Verions displays the version information of PSP Recovery BL, PSP 
BootLoader, SMU FW, ABL, APCB, APDB, and APPB.

---

52 
English
3.3.13 Instant Flash
Instant Flash is a UEFI flash utility embedded in Flash ROM. This convenient UEFI 
update tool allows you to update system UEFI without entering operating systems 
first like MS-DOS or Windows®. Just save the new UEFI file to your USB flash drive, 
floppy disk or hard drive and launch this tool, then you can update your UEFI only 
in a few clicks without preparing an additional floppy diskette or other complicated flash utility. Please be noted that the USB flash drive or hard drive must use 
FAT32/16/12 file system. If you execute Instant Flash utility, the utility will show the 
UEFI files and their respective information. Select the proper UEFI file to update 
your UEFI, and reboot your system after the UEFI update process is completed.

---

ROMED6U-2L2T
53
English
3.4 Server Mgmt
Wait For BMC
Wait For BMC response for specified time out. BMC starts at the same time when 
BIOS starts during AC power ON. It takes around 90 seconds to initialize Host to BMC 
interfaces.
Inventory Support
This will execute inventory function for system. Enabling this item will take some time at 
system boot.

---

54 
English
3.4.1 System Event Log
SEL Components
Change this to enable ro disable event logging for error/progress codes during boot.
Erase SEL
Use this to choose options for earsing SEL.
When SEL is Full
Use this to choose options for reactions to a full SEL.
Log EFI Status Codes
Use this item to disable the logging of EFI Status Codes or log only error code or only 
progress code or both.

---

ROMED6U-2L2T
55
English
When [DHCP] or [Static] is selected, do NOT modify the BMC network settings on the 
IPMI web page.
3.4.2 BMC Network Configuration
Lan Channel (Failover)
Manual Setting IPMI LAN
If [No] is selected, the IP address is assigned by DHCP. If you prefer using a static IP 
address, toggle to [Yes], and the changes take effect after the system reboots. The default 
value is [No].
Configuration Address Source
Select to configure BMC network parameters statically or dynamically(by BIOS or BMC).
Configuration options: [Static] and [DHCP].
Static: Manually enter the IP Address, Subnet Mask and Gateway Address in the BIOS for 
BMC LAN channel configuration.
DHCP: IP address, Subnet Mask and Gateway Address are automatically assigned by the 
network's DHCP server.

---

56 
English
The default login information for the IPMI web interface is:
 Username: admin
 Password: admin
For more instructions on how to set up remote control environment and use the IPMI management platform, please refer to the IPMI Configuration User Guide or go to the Support 
website at: http://www.asrockrack.com/support/ipmi.asp 
IPV6 Support
Enable or Disable LAN1 IPV6 Support.
Manual Setting IPMI LAN(IPV6)
Select to configure LAN channel parameters statically or dynamucally(by BIOS or BMC). 
Unspecified option will not modify any BMC network parameters during BIOS phase.
IPV6 Index
Set Selector for Static IP, range: 0 to 15.

---

ROMED6U-2L2T
57
English
3.4.2 BMC Tools
Load BMC Default Settings
Use this item to load BMC default settings.
KCS control
Select the KSC interface state after POST end. If [Enabled] is selected, the BMC will 
remain KCS interface after POST stage. If [Disabled] is selected, the BMC will disable KCS 
interface after POST stage.

---

58 
English
3.5 Security
In this section, you may set or change the supervisor/user password for the system. For the 
user password, you may also clear it.
Supervisor Password
Set or change the password for the administrator account. Only the administrator 
has authority to change the settings in the UEFI Setup Utility. Leave it blank and 
press enter to remove the password.
User Password
Set or change the password for the user account. Users are unable to change the 
settings in the UEFI Setup Utility. Leave it blank and press enter to remove the 
password.
Secure Boot
Use this to enable or disable Secure Boot Control. The default value is [Disabled]. 
Enable to support Windows Server 2012 R2 or later versions Secure Boot.
Secure Boot Mode
Secure Boot mode selector: Standard/Custom. In Custom mode Secure Boot Variables can be configured without authentication.

---

ROMED6U-2L2T
59
English
3.5.1 Key Management
In this section, expert users can modify Secure Boot Policy variables without full authentication.
Factory Key Provision
Install factory default Secure Boot keys after the platform reset and while the System 
is in Setup mode.
Install Default Secure Boot Keys
Please install default secure boot keys if it's the first time you use secure boot. 
Enroll Efi Image
Allow the image to run in Secure Boot mode. Enroll SHA256 hash of the binary into 
Authorized Signature Database (db).
Restore DB defaults
Restore DB variable to factory defaults.
Platform Key(PK)
Enroll Factory Defaults or load certificates from a file: 
1. Public Key Certificate in:
a) EFI_SIGNATURE_LIST

---

60 
English
b) EFI_CERT_X509 (DER)
c) EFI_CERT_RSA2048 (bin)
d) EFI_CERT_SHAXXX
2. Authenticated UEFI Variable
3. EFI PE/COFF Image(SHA256)
Key Source: Default, External, Mixed
Key Exchange Keys
Enroll Factory Defaults or load certificates from a file: 
1. Public Key Certificate in:
a) EFI_SIGNATURE_LIST
b) EFI_CERT_X509 (DER)
c) EFI_CERT_RSA2048 (bin)
d) EFI_CERT_SHAXXX
2. Authenticated UEFI Variable
3. EFI PE/COFF Image(SHA256)
Key Source: Default, External, Mixed
Key Source: Default, External, Mixed, Test
Authorized Signatures
Enroll Factory Defaults or load certificates from a file: 
1. Public Key Certificate in:
a) EFI_SIGNATURE_LIST
b) EFI_CERT_X509 (DER)
c) EFI_CERT_RSA2048 (bin)
d) EFI_CERT_SHAXXX
2. Authenticated UEFI Variable
3. EFI PE/COFF Image(SHA256)
Key Source: Default, External, Mixed
Forbidden Signatures

---

ROMED6U-2L2T
61
English
Enroll Factory Defaults or load certificates from a file: 
1. Public Key Certificate in:
a) EFI_SIGNATURE_LIST
b) EFI_CERT_X509 (DER)
c) EFI_CERT_RSA2048 (bin)
d) EFI_CERT_SHAXXX
2. Authenticated UEFI Variable
3. EFI PE/COFF Image(SHA256)
Key Source: Default, External, Mixed
Authorized TimeStamps
Enroll Factory Defaults or load certificates from a file: 
1. Public Key Certificate in:
a) EFI_SIGNATURE_LIST
b) EFI_CERT_X509 (DER)
c) EFI_CERT_RSA2048 (bin)
d) EFI_CERT_SHAXXX
2. Authenticated UEFI Variable
3. EFI PE/COFF Image(SHA256)
Key Source: Default, External, Mixed
OsRecovery Signatures
Enroll Factory Defaults or load certificates from a file: 
1. Public Key Certificate in:
a) EFI_SIGNATURE_LIST
b) EFI_CERT_X509 (DER)
c) EFI_CERT_RSA2048 (bin)
d) EFI_CERT_SHAXXX
2. Authenticated UEFI Variable
3. EFI PE/COFF Image(SHA256)
Key Source: Default, External, Mixed

---

62 
English
3.6 Boot Screen
In this section, it will display the available devices on your system for you to configure the 
boot settings and the boot priority. 
Boot Option #1
Use this item to set the system boot order.
Boot Option Filter
This option controls Legacy/UEFI ROMs priority.
Boot From Onboard LAN
Use this item to enable or disable the Boot From Onboard LAN feature.
Setup Prompt Timeout
Configure the number of seconds to wait for the UEFI setup utility.
Bootup Num-Lock
If this item is set to [On], it will automatically activate the Numeric Lock function after 
boot-up.
Boot Beep
Select whether the Boot Beep should be turned on or off when the system boots up. Please 
note that a buzzer is needed.

---

ROMED6U-2L2T
63
English
Full Screen Logo
Use this item to enable or disable OEM Logo. The default value is [Enabled].
AddOn ROM Display
Use this option to adjust AddOn ROM Display. If you enable the option "Full Screen Logo"
but you want to see the AddOn ROM information when the system boots, please select
[Enabled]. Configuration options: [Enabled] and [Disabled]. The default value is [Enabled].

---

64 
English
3.6.1 CSM Parameters
CSM
Enable to launch the Compatibility Support Module. Please do not disable unless 
you're running a WHCK test. If you are using Windows Server 2012 R2 or later versions 64-bit UEFI and all of your devices support UEFI, you may also disable CSM 
for faster boot speed.
Launch Video OpROM Policy 
Select UEFI only to run those that support UEFI option ROM only. Select Legacy only to 
run those that support legacy option ROM only. Select Do not launch to not execute both 
legacy and UEFI option ROM.
SLIM1-1 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
SLIM2-1 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
SLIM2-2 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the

---

ROMED6U-2L2T
65
English
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
SLIM3-1 OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
SLIM3-2 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
M2_1 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
M2_2 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
PCIE4 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
PCIE5 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
PCIE6 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)
PCIE7 Slot OpROM
Use this item to select slot storage and Network Option ROM policy. In Auto option, the 
default is Disabled with NVMe device, but it is Legacy with other devices. (This item can't 
select Video Option ROM policy.)

---

66 
English
3.7 Event Logs
Change Smbios Event Log Settings
This allows you to configure the Smbios Event Log Settings. 
When entering the item, you will see the followings:
Smbios Event Log
Use this item to enable or disable all features of the SMBIOS Event Logging during system 
boot.
Erase Event Log
The options include [No], [Yes, Next reset] and [Yes, Every reset]. If Yes is selected, all 
logged events will be erased.
When Log is Full
Use this item to choose options for reactions to a full Smbios Event Log. The options 
include [Do Nothing] and [Erase Immediately]. 
Log System Boot Event
Choose option to enable/disable logging of System boot event.
MECI (Multiple Event Count Increment)
Use this item to enter the increment value for the multiple event counter. The valid range is 
from 1 to 255.
METW (Multiple Event Time Window)
Use this item to specify the number of minutes which must pass between duplicate log

---

ROMED6U-2L2T
67
English
entries which utilize a multiple-event counter. The value ranges from 0 to 99 minutes.
Log EFI Status Code
Enable or disable the logging of EFI Status Codes as OEM reserved type E0 (if not already 
converted to legacy).
Convert EFI Status Codes to Standard Smbios Type
Enable or disable the converting of EFI Status Codes to Standard Smbios Types (Not all 
may be translated).
View Smbios Event Log
Press <Enter> to view the Smbios Event Log records.
All values changed here do not take effect until computer is restarted.

---

68 
English
3.8 Exit Screen
Save Changes and Exit
When you select this option, the following message "Save configuration changes and exit 
setup?" will pop-out. Press <F10> key or select [Yes] to save the changes and exit the UEFI 
SETUP UTILITY.
Discard Changes and Exit
When you select this option, the following message "Discard changes and exit setup?" will 
pop-out. Press <ESC> key or select [Yes] to exit the UEFI SETUP UTILITY without saving 
any changes.
Discard Changes
When you select this option, the following message "Discard changes?" will pop-out. Press 
<F7> key or select [Yes] to discard all changes.
Load UEFI Defaults 
Load UEFI default values for all the setup questions. F9 key can be used for this operation.
Boot Override 
These items displays the available devices. Select an item to start booting from the selected 
device.

---

ROMED6U-2L2T
69
English
Chapter 4 Software Support
4.1 Install Operating System 
This motherboard supports various Microsoft® Windows® Server / Linux compliant. 
Because motherboard settings and hardware options vary, use the setup procedures 
in this chapter for general reference only. Refer to your OS documentation for more 
information.
4.2 Support CD Information
The Support CD that came with the motherboard contains necessary drivers and useful 
utilities that enhance the motherboard's features. 
4.2.1 Running The Support CD 
To begin using the support CD, insert the CD into your CD-ROM drive. The CD 
automatically displays the Main Menu if "AUTORUN" is enabled in your computer. If the 
Main Menu does not appear automatically, locate and double click on the file "ASRSetup.
exe" from the root folder in the Support CD to display the menu.
4.2.2 Drivers Menu
The Drivers Menu shows the available device's drivers if the system detects installed 
devices. Please install the necessary drivers to activate the devices.
4.2.3 Utilities Menu
The Utilities Menu shows the application softwares that the motherboard supports. Click 
on a specific item then follow the installation wizard to install it.
4.2.4 Contact Information
If you need to contact ASRock Rack or want to know more about ASRock Rack, welcome 
to visit ASRock Rack's website at http://www.ASRockRack.com; or you may contact your 
dealer for further information.

---

70 
English
Chapter 5 Troubleshooting
5.1 Troubleshooting Procedures
Follow the procedures below to troubleshoot your system.
1. Disconnect the power cable and check whether the PWR LED is off.
2. Unplug all cables, connectors and remove all add-on cards from the motherboard. 
Make sure that the jumpers are set to default settings.
3. Confirm that there are no short circuits between the motherboard and the chassis.
4. Install a CPU and fan on the motherboard, then connect the chassis speaker and power 
LED.
If there is no power...
1. Confirm that there are no short circuits between the motherboard and the chassis.
2. Make sure that the jumpers are set to default settings.
3. Check the settings of the 115V/230V switch on the power supply.
4. Verify if the battery on the motherboard provides ~3VDC. Install a new battery if it 
does not.
If there is no video...
1. Try replugging the monitor cables and power cord.
2. Check for memory errors.
If there are memory errors...
1. Verify that the DIMM modules are properly seated in the slots.
2. Use recommended DDR4 RDIMMs, LRDIMMs and NVDIMMs.
3. If you have installed more than one DIMM modules, they should be identical with the 
same brand, speed, size and chip-type.
4. Try inserting different DIMM modules into different slots to identify faulty ones.
5. Check the settings of the 115V/230V switch on the power supply.
Always unplug the power cord before adding, removing or changing any hardware components. Failure to do so may cause physical injuries to you and damages to motherboard 
components.

---

ROMED6U-2L2T
71
English
Unable to save system setup configurations...
1. Verify if the battery on the motherboard provides ~3VDC. Install a new battery if it 
does not.
2. Confirm whether your power supply provides adaquate and stable power.
Other problems...
1. Try searching keywords related to your problem on ASRock Rack's FAQ page:
http://www.asrockrack.com/support

---

72 
English
5.2 Technical Support Procedures
If you have tried the troubleshooting procedures mentioned above and the problems 
are still unsolved, please contact ASRock Rack's technical support with the following 
information:
1. Your contact information
2. Model name, BIOS version and problem type.
3. System configuration.
4. Problem description.
You may contact ASRock Rack's technical support at:
http://www.asrockrack.com/support/tsd.asp
5.3 Returning Merchandise for Service
For warranty service, the receipt or a copy of your invoice marked with the date of 
purchase is required. By calling your vendor or going to our RMA website (http://event. 
asrockrack.com/tsd.asp) you may obtain a Returned Merchandise Authorization (RMA) 
number.
The RMA number should be displayed on the outside of the shipping carton which is 
mailed prepaid or hand-carried when you return the motherboard to the manufacturer. 
Shipping and handling charges will be applied for all orders that must be mailed when 
service is complete.
This warranty does not cover damages incurred in shipping or from failure due to 
alteration, misuse, abuse or improper maintenance of products.
Contact your distributor first for any product related problems during the warranty period.