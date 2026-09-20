"""Keep Ansible's process group tied to the executor's lifetime via an EOF pipe."""
import os
import signal
import subprocess
import sys
import threading


def main():
    parent_fd = int(sys.argv[1])
    child = subprocess.Popen(sys.argv[2:], start_new_session=True, close_fds=True)
    stopped = threading.Event()

    def stop(*_):
        if stopped.is_set():
            return
        stopped.set()
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        def force_stop():
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        timer = threading.Timer(5, force_stop)
        timer.daemon = True
        timer.start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def watch_parent():
        try:
            while os.read(parent_fd, 1):
                pass
        finally:
            stop()
            os.close(parent_fd)

    threading.Thread(target=watch_parent, daemon=True).start()
    code = child.wait()
    # A exited leader can leave SSH descendants behind. Always reap its group.
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    sys.exit(main())
