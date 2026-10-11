#!/usr/bin/python3
"""Inventory mounted, capacity-backed filesystems on a managed Linux host."""

import argparse
import grp
import json
import os
import pwd
import subprocess
import sys


MIB = 1024 * 1024
VIRTUAL_FILESYSTEMS = frozenset(
    (
        "autofs",
        "binfmt_misc",
        "bpf",
        "cgroup",
        "cgroup2",
        "configfs",
        "debugfs",
        "devpts",
        "devtmpfs",
        "efivarfs",
        "fuse.lxcfs",
        "fuse.portal",
        "fuse.snapfuse",
        "fusectl",
        "hugetlbfs",
        "mqueue",
        "nsfs",
        "overlay",
        "proc",
        "pstore",
        "ramfs",
        "rpc_pipefs",
        "securityfs",
        "selinuxfs",
        "squashfs",
        "sysfs",
        "tmpfs",
        "tracefs",
    )
)
NFS_FILESYSTEMS = frozenset(("nfs", "nfs4"))
SMB_FILESYSTEMS = frozenset(("cifs", "smb", "smb2", "smb3"))
NETWORK_FILESYSTEMS = frozenset(
    (
        "9p",
        "afs",
        "ceph",
        "fuse.ceph",
        "fuse.gcsfuse",
        "fuse.glusterfs",
        "fuse.rclone",
        "fuse.s3fs",
        "fuse.sshfs",
        "glusterfs",
        "gpfs",
        "lustre",
        "orangefs",
        "panfs",
        "pvfs2",
    )
)
SKIP_TARGETS = frozenset(("/boot", "/boot/efi"))
SKIP_TREES = (
    "/dev",
    "/proc",
    "/run",
    "/snap",
    "/sys",
    "/var/lib/containerd",
    "/var/lib/docker",
    "/var/lib/kubelet",
)


def _run(argv, timeout):
    try:
        return subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            # JetPack 4's system Python is 3.6; the text alias requires 3.7.
            universal_newlines=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _unescape_mount_field(value):
    for encoded, decoded in (
        ("\\040", " "),
        ("\\011", "\t"),
        ("\\012", "\n"),
        ("\\134", "\\"),
    ):
        value = value.replace(encoded, decoded)
    return value


def _normalized_mount(entry):
    return {
        "target": str(entry.get("target") or ""),
        "source": str(entry.get("source") or ""),
        "fstype": str(entry.get("fstype") or "").lower(),
        "options": str(entry.get("options") or ""),
        "major_minor": str(
            entry.get("major_minor")
            or entry.get("maj:min")
            or entry.get("maj_min")
            or entry.get("majmin")
            or ""
        ),
    }


def _flatten_findmnt(entries):
    flattened = []
    for entry in entries or []:
        flattened.append(_normalized_mount(entry))
        flattened.extend(_flatten_findmnt(entry.get("children")))
    return flattened


def _mounts_from_findmnt():
    result = _run(
        [
            "findmnt",
            "--json",
            "--bytes",
            "--list",
            "--output",
            "TARGET,SOURCE,FSTYPE,OPTIONS,MAJ:MIN",
        ],
        20,
    )
    if not result or result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        return _flatten_findmnt(json.loads(result.stdout).get("filesystems", []))
    except (TypeError, ValueError):
        return []


def _mounts_from_proc(path="/proc/self/mountinfo"):
    mounts = []
    try:
        with open(path, "r", encoding="utf-8") as mountinfo:
            lines = mountinfo.readlines()
    except OSError:
        return mounts

    for line in lines:
        before, separator, after = line.rstrip("\n").partition(" - ")
        if not separator:
            continue
        left = before.split()
        right = after.split()
        if len(left) < 6 or len(right) < 2:
            continue
        mounts.append(
            {
                "target": _unescape_mount_field(left[4]),
                "source": _unescape_mount_field(right[1]),
                "fstype": right[0].lower(),
                "options": ",".join((left[5], right[2] if len(right) > 2 else "")),
                "major_minor": left[2],
            }
        )
    return mounts


def discover_mounts():
    mounts = _mounts_from_findmnt()
    return mounts if mounts else _mounts_from_proc()


def _under_tree(target, tree):
    return target == tree or target.startswith(tree + "/")


def _is_relevant_mount(mount):
    target = mount["target"]
    if not target.startswith("/") or target in SKIP_TARGETS:
        return False
    if any(_under_tree(target, tree) for tree in SKIP_TREES):
        return False
    return mount["fstype"] not in VIRTUAL_FILESYSTEMS


def _network_source(source):
    source = source.rstrip("/")
    if source.startswith("//"):
        return source.lower()
    if ":" in source and not source.startswith("/"):
        host, path = source.split(":", 1)
        return host.lower() + ":" + path
    return source


def _basic_storage_type(mount):
    fstype = mount["fstype"]
    source = mount["source"]
    if fstype in NFS_FILESYSTEMS:
        return "nfs"
    if fstype in SMB_FILESYSTEMS or source.startswith("//"):
        return "smb"
    if fstype in NETWORK_FILESYSTEMS:
        return "network"
    return "local"


def _filesystem_id(mount):
    storage_type = _basic_storage_type(mount)
    if storage_type in ("nfs", "smb", "network"):
        return "{}:{}:{}".format(
            storage_type, mount["fstype"], _network_source(mount["source"])
        )
    if mount["major_minor"]:
        return "device:" + mount["major_minor"]
    return "source:{}:{}".format(mount["fstype"], mount["source"])


def _device_source(source):
    return source.split("[", 1)[0]


def _block_stack(source):
    device = _device_source(source)
    if not device.startswith("/dev/"):
        return []
    result = _run(["lsblk", "--inverse", "--noheadings", "--output", "TYPE,TRAN", device], 10)
    if not result or result.returncode != 0:
        return []
    return [line.lower().split() for line in result.stdout.splitlines() if line.strip()]


def classify_storage(mount):
    storage_type = _basic_storage_type(mount)
    if storage_type != "local":
        return storage_type

    source = _device_source(mount["source"])
    if source.startswith("/dev/md"):
        return "raid"
    if source.startswith("/dev/rbd") or source.startswith("/dev/drbd"):
        return "network"

    stack = _block_stack(source)
    if any(columns and columns[0].startswith("raid") for columns in stack):
        return "raid"
    if any("iscsi" in columns[1:] for columns in stack):
        return "iscsi"
    return "local"


def _mount_rank(mount):
    options = set(mount["options"].split(","))
    return (
        1 if options.intersection(("bind", "rbind")) else 0,
        mount["target"].count("/"),
        len(mount["target"]),
        mount["target"],
    )


def filesystem_usage(target):
    result = _run(
        ["df", "-B1", "--output=size,used,avail,pcent", "--", target], 20
    )
    portable_output = False
    if not result or result.returncode != 0:
        result = _run(["df", "-Pk", "--", target], 20)
        portable_output = True
    if not result or result.returncode != 0:
        return None

    for line in reversed(result.stdout.splitlines()):
        columns = line.split()
        if portable_output:
            usage_column = 4
            if len(columns) < 6 or not columns[usage_column].endswith("%"):
                continue
        elif len(columns) < 4 or not columns[-1].endswith("%"):
            continue
        try:
            if portable_output:
                total = int(columns[1]) * 1024
                used = int(columns[2]) * 1024
                available = int(columns[3]) * 1024
                use_pct = int(columns[4].rstrip("%"))
            else:
                total = int(columns[-4])
                used = int(columns[-3])
                available = int(columns[-2])
                use_pct = int(columns[-1].rstrip("%"))
        except ValueError:
            continue
        return {
            "total_mb": (total + MIB - 1) // MIB,
            "used_mb": (used + MIB - 1) // MIB,
            "avail_mb": available // MIB,
            "use_pct": use_pct,
        }
    return None


def _owner(path):
    try:
        stat_result = os.lstat(path)
    except OSError:
        return None, None, None
    try:
        username = pwd.getpwuid(stat_result.st_uid).pw_name
    except KeyError:
        username = str(stat_result.st_uid)
    try:
        groupname = grp.getgrgid(stat_result.st_gid).gr_name
    except KeyError:
        groupname = str(stat_result.st_gid)
    return username, stat_result.st_uid, groupname


def scan_top_level_entries(target):
    result = _run(["du", "-amx", "--max-depth=1", "--", target], 120)
    if not result or result.returncode not in (0, 1):
        return []

    entries = []
    seen_paths = set()
    for line in result.stdout.splitlines():
        size, separator, path = line.partition("\t")
        if not separator:
            columns = line.split(None, 1)
            if len(columns) != 2:
                continue
            size, path = columns
        path = path.rstrip("/") or "/"
        if path == (target.rstrip("/") or "/") or path in seen_paths:
            continue
        try:
            size_mb = int(size)
        except ValueError:
            continue
        seen_paths.add(path)
        username, uid, groupname = _owner(path)
        entries.append(
            {
                "size_mb": size_mb,
                "name": os.path.basename(path) or path,
                "path": path,
                "owner_user": username,
                "owner_uid": uid,
                "owner_group": groupname,
                "kind": "directory" if os.path.isdir(path) else "file",
            }
        )
    entries.sort(key=lambda entry: (-entry["size_mb"], entry["path"]))
    return entries[:20]


def build_storage_inventory(mounts, scan_entries=False, min_size_mb=100):
    groups = {}
    for original in mounts:
        mount = _normalized_mount(original)
        if not _is_relevant_mount(mount):
            continue
        groups.setdefault(_filesystem_id(mount), []).append(mount)

    inventory = []
    for filesystem_id, candidates in groups.items():
        candidates.sort(key=_mount_rank)
        usage = None
        selected = candidates[0]
        for candidate in candidates:
            usage = filesystem_usage(candidate["target"])
            if usage is not None:
                selected = candidate
                break

        if usage is not None and usage["total_mb"] < min_size_mb:
            continue
        record = {
            "filesystem_id": filesystem_id,
            "mountpoint": selected["target"],
            "mountpoints": sorted(
                {candidate["target"] for candidate in candidates},
                key=lambda target: (target.count("/"), len(target), target),
            ),
            "type": classify_storage(selected),
            "fstype": selected["fstype"],
            "source": selected["source"],
            "accessible": usage is not None,
            "total_mb": 0,
            "used_mb": 0,
            "avail_mb": 0,
            "use_pct": 0,
            "entries": [],
        }
        if usage is not None:
            record.update(usage)
            if scan_entries:
                record["entries"] = scan_top_level_entries(selected["target"])
        inventory.append(record)

    inventory.sort(
        key=lambda record: (
            0 if record["mountpoint"] == "/" else 1,
            record["mountpoint"].count("/"),
            record["mountpoint"],
        )
    )
    return inventory


def read_fstab(path="/etc/fstab"):
    """Read configured mount targets, retaining escaped spaces and optional mounts."""
    entries = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 4:
                raise ValueError("Malformed fstab entry at line {}".format(number))
            source, target, fstype, options = map(_unescape_mount_field, fields[:4])
            if fstype == "swap" or target in ("none", "swap"):
                continue
            if not target.startswith("/"):
                raise ValueError("Invalid fstab mount target at line {}".format(number))
            entries.append(_normalized_mount({
                "source": source, "target": target, "fstype": fstype, "options": options,
            }))
    return entries


def build_home_fstab_inventory(mounts, fstab, home_path=None):
    """Check /home's backing filesystem and each fstab target without mounting it.

    Unlike discovery, this preserves small, virtual and duplicate/bind targets.
    Never run df on an absent mount: that would report its parent's capacity.
    """
    live = {_normalized_mount(m)["target"]: _normalized_mount(m) for m in mounts}
    home_path = home_path or os.path.realpath("/home")
    parents = [m for target, m in live.items() if target == "/" or _under_tree(home_path, target)]
    if not parents:
        raise ValueError("Could not identify the filesystem containing /home")
    home_mount = max(parents, key=lambda m: len(m["target"]))
    requests = [(home_mount["target"], None)]
    requests.extend((entry["target"], entry) for entry in fstab)
    records = []
    for target, configured in requests:
        # Merge the initial home observation with its fstab entry, if present.
        if configured and target == home_mount["target"] and not records[0].get("in_fstab"):
            record = records[0]
        else:
            actual = live.get(target)
            mounted = bool(actual and actual["fstype"] != "autofs")
            usage = filesystem_usage(target) if mounted else None
            record = {
                "mountpoint": target, "mountpoints": [target],
                "covers_home": target == home_mount["target"], "home_path": home_path,
                "in_fstab": False, "mounted": mounted, "accessible": usage is not None,
                "status": "mounted" if usage else "unavailable" if mounted else "automount_pending" if actual else "unmounted",
                "source": actual["source"] if actual else None,
                "fstype": actual["fstype"] if actual else None,
                "type": classify_storage(actual) if actual else None,
                "total_mb": None, "used_mb": None, "avail_mb": None, "use_pct": None,
                "entries": [],
            }
            if usage:
                record.update(usage)
            records.append(record)
        if configured:
            options = set(configured["options"].split(","))
            record.update({
                "in_fstab": True, "configured_source": configured["source"],
                "configured_fstype": configured["fstype"],
                "optional": "nofail" in options, "noauto": "noauto" in options,
                "automount": "x-systemd.automount" in options,
            })
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-entries", action="store_true")
    parser.add_argument("--min-size-mb", type=int, default=100)
    parser.add_argument("--home-fstab", action="store_true")
    args = parser.parse_args()
    inventory = build_home_fstab_inventory(discover_mounts(), read_fstab()) if args.home_fstab else build_storage_inventory(
        discover_mounts(),
        scan_entries=args.scan_entries,
        min_size_mb=max(0, args.min_size_mb),
    )
    print(json.dumps(inventory, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # Keep diagnostics useful without breaking every host scan.
        print("storage discovery failed: {}".format(exc), file=sys.stderr)
        print("[]")
        sys.exit(1)
