export const GLOSSARY = {
  fabricManager:
    "NVIDIA Fabric Manager runs on multi-GPU systems to bring up and monitor the NVLink/NVSwitch fabric that connects the GPUs. If it's inactive, GPUs can still work standalone but high-bandwidth multi-GPU jobs will fail.",

  cuda:
    "CUDA is NVIDIA's GPU compute platform. The CUDA version installed on a host must be compatible with the apps it runs (PyTorch, TensorFlow, etc.). It's tied to the GPU driver.",

  driverBranch:
    "Driver versions are grouped into branches (e.g. 570, 580). Hosts on different branches may behave differently — keep the fleet on one branch when possible.",

  unknownStatus:
    "The host hasn't been scanned recently, or the most recent scan failed. Click Scan to refresh its state.",

  offlineStatus:
    "The host did not respond to the last fleet scan. Check that it's powered on and reachable on the network.",

  onlineStatus:
    "The host responded to the most recent scan.",

  rebootRequired:
    "A package update or driver install asked Linux to reboot before the change takes effect. Typically triggered by a kernel update from apt, or a major driver upgrade.",

  raid:
    "RAID combines several physical disks into one logical volume — on DGX systems this is the /raid mount used for datasets and scratch space.",

  nicSpeed:
    "Negotiated link speed of the host's primary network card. ConnectX-7 NICs run at 400Gb; ConnectX-8 NICs at 800Gb. Lower speeds may indicate a cable or switch issue.",

  apt:
    "apt is the Ubuntu package manager. Package updates apply security and bug-fix patches; some require a reboot.",

  dockerPrune:
    "Removes stopped containers, dangling images, unused networks, and the build cache. Frees disk; doesn't affect running workloads.",

  scanFleet:
    "Connects to every host and refreshes GPU, driver, disk, network, and reboot info. Safe to run anytime.",
};
