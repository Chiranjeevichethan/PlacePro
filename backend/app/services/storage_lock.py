"""Cooperative JSON update locks for threads and processes sharing local storage."""

import errno
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path


class StorageLockTimeout(TimeoutError):
    pass


_registry_guard = threading.Lock()
_thread_locks = {}
_held = threading.local()


def _try_lock(handle):
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle):
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def record_transaction(directory, record_id, timeout=10):
    """Serialize a validated record's entire read/modify/write operation.

    The caller validates record_id before using it in a path. Nested operations
    on the same record/thread reuse the OS lock. Lock files are retained; removing
    one while another process holds it would break mutual exclusion.
    """
    key = os.path.normcase(os.path.realpath(os.path.join(directory, f"{record_id}.json")))
    with _registry_guard:
        thread_lock = _thread_locks.setdefault(key, threading.RLock())
    if not thread_lock.acquire(timeout=timeout):
        raise StorageLockTimeout(f"Timed out waiting for record '{record_id}'.")
    try:
        held = getattr(_held, "keys", None)
        if held is None:
            held = _held.keys = set()
        if key in held:
            yield
            return

        lock_dir = Path(directory) / ".locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        with (lock_dir / f"{record_id}.lock").open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                try:
                    _try_lock(handle)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        raise
                    if time.monotonic() >= deadline:
                        raise StorageLockTimeout(
                            f"Timed out waiting for record '{record_id}'."
                        ) from exc
                    time.sleep(0.01)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                _unlock(handle)
    finally:
        thread_lock.release()
