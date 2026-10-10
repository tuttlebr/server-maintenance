#!/usr/bin/env python3
"""Prune only unused images/build cache. Never delete containers or volumes."""
import json
import shutil
import subprocess
import sys


def execute(argv, timeout=600):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return result.returncode, (result.stdout if result.returncode == 0 else result.stdout + result.stderr).strip()[-16000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def cleanup(run=execute, which=shutil.which):
    steps = []
    available = 0
    mutation_started = False

    def record(label, argv):
        nonlocal mutation_started
        mutation_started = True
        rc, output = run(argv)
        steps.append({'label': label, 'status': 'success' if rc == 0 else 'failed', 'output': output})
        return rc

    if which('docker'):
        rc, output = run(['docker', 'info'], timeout=30)
        if rc == 0:
            available += 1
            record('Docker unused images', ['docker', 'image', 'prune', '--all', '--force'])
            record('Docker build cache', ['docker', 'builder', 'prune', '--all', '--force'])
        else:
            steps.append({'label': 'Docker', 'status': 'failed', 'output': 'Docker is installed but its daemon is unavailable. ' + output})
    else:
        steps.append({'label': 'Docker', 'status': 'skipped', 'output': 'Docker is not installed.'})

    if which('nerdctl'):
        rc, output = run(['nerdctl', 'namespace', 'ls', '--quiet'], timeout=30)
        if rc == 0:
            available += 1
            for namespace in sorted(set(output.splitlines())):
                namespace = namespace.strip()
                if not namespace:
                    continue
                # Docker owns this namespace; prune through its daemon only.
                if namespace == 'moby':
                    steps.append({'label': 'containerd / moby', 'status': 'skipped', 'output': 'Docker manages this namespace.'})
                    continue
                record('containerd / ' + namespace, ['nerdctl', '--namespace', namespace, 'image', 'prune', '--all', '--force'])
            # Build cache belongs to BuildKit, not individual containerd namespaces.
            if which('buildctl'):
                build_rc, build_output = run(['buildctl', 'debug', 'workers'], timeout=30)
                if build_rc == 0:
                    record('containerd build cache', ['nerdctl', 'builder', 'prune', '--all', '--force'])
                else:
                    steps.append({'label': 'containerd build cache', 'status': 'skipped', 'output': 'BuildKit is unavailable; image cleanup completed. ' + build_output})
            else:
                steps.append({'label': 'containerd build cache', 'status': 'skipped', 'output': 'buildctl is not installed; BuildKit cache was not checked.'})
        else:
            steps.append({'label': 'containerd', 'status': 'failed', 'output': 'Cannot reach containerd through nerdctl. ' + output})
    else:
        steps.append({'label': 'containerd', 'status': 'skipped', 'output': 'nerdctl is not installed.'})

    success = available > 0 and not any(step['status'] == 'failed' for step in steps)
    return {'steps': steps, 'success': success, 'mutation_started': mutation_started, 'summary': 'Unused images and available build cache cleared.' if success else 'Cleanup is incomplete. Review runtime results.'}


if __name__ == '__main__':
    report = cleanup()
    print(json.dumps(report))
    sys.exit(0 if report['success'] else 1)
