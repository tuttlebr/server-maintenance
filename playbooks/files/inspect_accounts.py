#!/usr/bin/env python3
"""Read public account attributes and sudo policy; never read password hashes."""
import grp
import json
import pathlib
import pwd
import subprocess
import sys

def inspect_accounts(names):
    # Enumerate all accounts, including system accounts and disabled logins.
    # The 500-row mutation limit must never truncate an inventory.
    accounts = {account.pw_name: account for account in pwd.getpwall()} if not names else {}
    names = names or list(accounts)
    group_entries = grp.getgrall()
    reports = []
    for name in sorted(set(names)):
        try:
            account = accounts.get(name) or pwd.getpwnam(name)
        except KeyError:
            reports.append(dict(username=name, present=False, groups=[], managed_sudo=False))
            continue
        groups = {g.gr_name for g in group_entries if name in g.gr_mem or g.gr_gid == account.pw_gid}
        # This flag means precisely the Fleet-managed NOPASSWD grant exists.
        # NSS can return names outside the format accepted by account edits.
        managed = None
        if name not in ('.', '..') and '/' not in name:
            rule = pathlib.Path('/etc/sudoers.d') / name
            try:
                managed = rule.is_file() and f'{name} ALL=(ALL) NOPASSWD:ALL' in rule.read_text().splitlines()
            except OSError:
                pass
        try:
            policy = subprocess.run(['sudo', '-n', '-l', '-U', name], capture_output=True, text=True, timeout=10)
            evidence = (policy.stdout + policy.stderr)[:16384]
        except (OSError, subprocess.TimeoutExpired):
            evidence = 'Sudo policy could not be read. Effective privileges are unknown.'
        reports.append(dict(username=name, present=True, full_name=account.pw_gecos.split(',', 1)[0],
                            uid=account.pw_uid, home=account.pw_dir, groups=sorted(groups),
                            shell=account.pw_shell, managed_sudo=managed, sudo_policy=evidence))
    return reports


if __name__ == '__main__':
    print(json.dumps(inspect_accounts(json.loads(sys.argv[1]))))
