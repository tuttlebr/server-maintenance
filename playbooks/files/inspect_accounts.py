#!/usr/bin/env python3
"""Read public account attributes and sudo policy; never read password hashes."""
import grp
import json
import pathlib
import pwd
import re
import subprocess
import sys

names = json.loads(sys.argv[1])
if not names:
    names = [p.pw_name for p in pwd.getpwall() if 1000 <= p.pw_uid < 60000 and p.pw_shell not in ('/bin/false', '/usr/sbin/nologin', '/sbin/nologin')]
reports = []
for name in sorted(set(names))[:500]:
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', name):
        raise ValueError('Unsafe username')
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        reports.append(dict(username=name, present=False, groups=[], managed_sudo=False))
        continue
    groups = {g.gr_name for g in grp.getgrall() if name in g.gr_mem or g.gr_gid == account.pw_gid}
    # This flag means precisely the Fleet-managed NOPASSWD grant exists.
    rule = pathlib.Path('/etc/sudoers.d') / name
    managed = rule.is_file() and f'{name} ALL=(ALL) NOPASSWD:ALL' in rule.read_text().splitlines()
    try:
        policy = subprocess.run(['sudo', '-n', '-l', '-U', name], capture_output=True, text=True, timeout=10)
        evidence = (policy.stdout + policy.stderr)[:16384]
    except (OSError, subprocess.TimeoutExpired):
        evidence = 'Sudo policy could not be read. Effective privileges are unknown.'
    reports.append(dict(username=name, present=True, groups=sorted(groups), shell=account.pw_shell, managed_sudo=managed, sudo_policy=evidence))
print(json.dumps(reports))
