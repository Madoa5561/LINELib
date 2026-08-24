import json
import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional


_LOCKS: Dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _thread_lock(path: str) -> threading.RLock:
    absolute_path = os.path.abspath(path)
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(absolute_path, threading.RLock())


@contextmanager
def _process_lock(path: str) -> Iterator[None]:
    lock_path = f"{os.path.abspath(path)}.lock"
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lock_file = open(lock_path, "a+b")
    lock_acquired = False
    try:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        lock_acquired = True
        yield
    finally:
        active_error = sys.exc_info()[1]
        cleanup_error = None
        if lock_acquired:
            try:
                lock_file.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except Exception as error:
                cleanup_error = error
        try:
            lock_file.close()
        except Exception as error:
            if cleanup_error is None:
                cleanup_error = error
        if active_error is None and cleanup_error is not None:
            raise cleanup_error


@contextmanager
def locked_json(path: str) -> Iterator[None]:
    with _thread_lock(path):
        with _process_lock(path):
            yield


def _read_json_unlocked(path: str, *, missing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not os.path.exists(path):
        return dict(missing or {})
    if os.path.getsize(path) == 0:
        raise ValueError("JSON file is empty")
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def read_json(path: str, *, missing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with locked_json(path):
        return _read_json_unlocked(path, missing=missing)


def _write_json_unlocked(path: str, data: Dict[str, Any]) -> None:
    absolute_path = os.path.abspath(path)
    parent = os.path.dirname(absolute_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=parent or None,
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        os.replace(temporary_path, absolute_path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def write_json(path: str, data: Dict[str, Any]) -> None:
    with locked_json(path):
        _write_json_unlocked(path, data)


def update_json(
    path: str,
    update: Callable[[Dict[str, Any]], Any],
    *,
    missing: Optional[Dict[str, Any]] = None,
) -> Any:
    with locked_json(path):
        data = _read_json_unlocked(path, missing=missing)
        result = update(data)
        _write_json_unlocked(path, data)
        return result
