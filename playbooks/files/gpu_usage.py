#!/usr/bin/python3
"""Read a GPU/process snapshot; only report owners supported by local evidence.

Uses the XML query documented at https://docs.nvidia.com/deploy/nvidia-smi/.
Keep compatibility with Python 3.6 on older managed nodes.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import pwd
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def run(argv, timeout=10):
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("{}: {}".format(argv[0], exc))
    if result.returncode:
        raise RuntimeError("{}: {}".format(argv[0], result.stderr.strip() or result.stdout.strip() or "query failed"))
    return result.stdout


def number(value):
    match = re.match(r"^\s*(\d+(?:\.\d+)?)(?:\s|$)", value or "")
    return float(match.group(1)) if match else None


def container_context(container_id):
    """Container hints are distinct from the observed host process owner."""
    info = {"container_id": container_id, "source": "container", "container_name": "",
            "pod_name": "", "namespace": "", "workload_owner": ""}
    for command in (["docker", "inspect", container_id], ["crictl", "inspect", container_id]):
        try:
            payload = json.loads(run(command, timeout=3))
            if command[0] == "docker":
                item = payload[0]
                labels = item.get("Config", {}).get("Labels") or {}
                name = item.get("Name", "").lstrip("/")
            else:
                item = payload["status"]
                labels = item.get("labels") or {}
                name = (item.get("metadata") or {}).get("name", "")
            info.update({"source": "docker" if command[0] == "docker" else "containerd",
                         "container_name": name,
                         "pod_name": labels.get("io.kubernetes.pod.name", ""),
                         "namespace": labels.get("io.kubernetes.pod.namespace", ""),
                         "workload_owner": next((labels[k] for k in ("user", "owner", "JUPYTER_USER", "com.nvidia.run.as") if labels.get(k)), "")})
            if info["pod_name"]:
                info["source"] = "kubernetes"
            break
        except (RuntimeError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            continue
    return info


def process_context(pid, cache, proc_root="/proc"):
    base = os.path.join(proc_root, str(pid))
    info = {"user": "unknown", "uid": None, "source": "bare-metal", "owner_status": "unavailable"}
    try:
        with open(os.path.join(base, "status")) as handle:
            status = handle.read()
        uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
        info["uid"] = int(uid_line.split()[2])  # effective UID, not login/session inference
        try:
            info["user"] = pwd.getpwuid(info["uid"]).pw_name
        except KeyError:
            info["user"] = str(info["uid"])
        info["owner_status"] = "observed"
    except (OSError, ValueError, IndexError, StopIteration):
        pass  # Processes can exit between the driver snapshot and /proc reads.
    try:
        info["executable"] = os.readlink(os.path.join(base, "exe"))
    except OSError:
        pass
    try:
        with open(os.path.join(base, "cgroup")) as handle:
            match = re.search(r"(?<![a-f0-9])([a-f0-9]{64})(?![a-f0-9])", handle.read())
        if match:
            cid = match.group(1)
            if cid not in cache:
                cache[cid] = container_context(cid)
            info.update(cache[cid])
    except OSError:
        pass
    return info


def build_report(xml, hostname, platform="unknown", resolve=None):
    root = ET.fromstring(xml)
    gpus, users, cache, contexts = [], {}, {}, {}
    resolve = resolve or (lambda pid: process_context(pid, cache))
    for index, node in enumerate(root.findall("gpu")):
        util = number(node.findtext("utilization/gpu_util"))
        total = number(node.findtext("fb_memory_usage/total"))
        used = number(node.findtext("fb_memory_usage/used"))
        uuid = node.findtext("uuid") or node.get("id") or str(index)
        procs = node.find("processes")
        known = procs is not None and (not (procs.text or "").strip() or bool(procs.findall("process_info")))
        processes = []
        for proc in node.findall("processes/process_info"):
            raw_pid = proc.findtext("pid") or ""
            if not raw_pid.isdigit():
                known = False
                continue
            pid = int(raw_pid)
            if pid not in contexts:
                contexts[pid] = resolve(pid)
            processes.append({
                "pid": pid, "process_name": proc.findtext("process_name") or "unknown",
                "process_type": proc.findtext("type") or "unknown", "gpu_uuid": uuid,
                "gpu_memory_mb": number(proc.findtext("used_memory")),
                "gpu_instance_id": proc.findtext("gpu_instance_id"),
                "compute_instance_id": proc.findtext("compute_instance_id"), **contexts[pid],
            })
        if util is not None and util > 0:
            state = "active"
        elif processes:
            state = "idle_reserved" if util == 0 else "in_use"
        elif not known or util is None:
            state = "unknown"
        elif used and used > 0:
            state = "allocated"
        else:
            state = "free"
        gpus.append({
            "index": index, "uuid": uuid, "name": node.findtext("product_name") or "Unknown GPU",
            "utilization_pct": util, "memory_total_mb": total, "memory_used_mb": used,
            "memory_supported": total is not None and used is not None,
            "processes_known": known, "processes": processes, "status": state,
            "mig_mode": node.findtext("mig_mode/current_mig") or "N/A",
        })
        for user in {proc["user"] for proc in processes}:
            stats = users.setdefault(user, {"gpu_count": 0, "process_count": 0, "total_memory_mb": 0, "memory_complete": True})
            owned = [proc for proc in processes if proc["user"] == user]
            stats["gpu_count"] += 1
            stats["process_count"] += len(owned)
            stats["total_memory_mb"] += sum(proc["gpu_memory_mb"] or 0 for proc in owned)
            stats["memory_complete"] &= all(proc["gpu_memory_mb"] is not None for proc in owned)
    if not gpus:
        raise ValueError("nvidia-smi did not return any GPU records")
    notes = ["Snapshot only. Utilization is per GPU; process memory and effective Linux owners are reported separately.",
             "Container owner labels are hints, not verified people. Unknown owners may indicate exited processes or restricted /proc access."]
    if any(gpu["utilization_pct"] is None for gpu in gpus):
        notes.append("Some utilization readings are unavailable, including on MIG devices. Unavailable is not zero.")
    if any(not gpu["processes_known"] for gpu in gpus):
        notes.append("Some GPU process lists are unavailable; those GPUs are not assumed to be free.")
    if platform == "dgx_spark":
        notes.append("DGX Spark uses unified system memory; framebuffer and process memory readings may be unavailable.")
    return {"schema_version": 1, "report_type": "gpu", "hostname": hostname,
            "timestamp": datetime.now(timezone.utc).isoformat(), "platform": platform,
            "memory_architecture": "UMA" if platform == "dgx_spark" else "discrete",
            "notes": notes, "total_gpus": len(gpus), "gpus": gpus,
            "active_gpus": sum(gpu["status"] == "active" for gpu in gpus),
            "idle_gpus": sum(gpu["status"] == "idle_reserved" for gpu in gpus),
            "free_gpus": sum(gpu["status"] == "free" for gpu in gpus),
            "user_summary": [dict(user=user, **stats) for user, stats in sorted(users.items())]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--platform", default="unknown")
    args = parser.parse_args()
    print(json.dumps(build_report(run(["nvidia-smi", "-q", "-x"], timeout=30), args.hostname, args.platform)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("GPU inspection failed: {}".format(exc), file=sys.stderr)
        sys.exit(1)
