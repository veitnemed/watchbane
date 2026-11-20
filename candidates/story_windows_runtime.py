"""Redacted, opt-in observation of selected DLLs in frozen Windows QA."""

from __future__ import annotations

import ntpath
import sys


_DLL_NAMES = (
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
)


def _normalized(path):
    if not path:
        return None
    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[8:]
    elif path.startswith("\\\\?\\"):
        path = path[4:]
    normalized = ntpath.normcase(ntpath.normpath(path))
    drive, _ = ntpath.splitdrive(normalized)
    return normalized if drive and ntpath.isabs(normalized) else None


def _inside(path, parent):
    if not parent:
        return False
    try:
        return ntpath.commonpath((path, parent)) == parent and path != parent
    except ValueError:
        return False


def _origin(path, bundle, windows):
    normalized = _normalized(path)
    if normalized is None:
        return "unresolved"
    if _inside(normalized, _normalized(bundle)):
        return "bundle"
    if _inside(normalized, _normalized(windows)):
        return "windows"
    return "other"


def _observe():
    import ctypes
    from ctypes import wintypes

    # Resolve only OS inspection calls. Never load a candidate DLL by name.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel.GetModuleHandleW
    handle.argtypes = (wintypes.LPCWSTR,)
    handle.restype = wintypes.HMODULE
    filename = kernel.GetModuleFileNameW
    filename.argtypes = (wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD)
    filename.restype = wintypes.DWORD
    windows_dir = kernel.GetWindowsDirectoryW
    windows_dir.argtypes = (wintypes.LPWSTR, wintypes.UINT)
    windows_dir.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    size = windows_dir(buffer, len(buffer))
    windows = buffer.value if 0 < size < len(buffer) else None
    bundle = getattr(sys, "_MEIPASS", None)
    origins = {}
    for name in _DLL_NAMES:
        loaded = handle(name)
        if not loaded:
            origins[name] = "not_observed"
            continue
        size = filename(loaded, buffer, len(buffer))
        origins[name] = _origin(buffer.value, bundle, windows) if 0 < size < len(buffer) else "unresolved"
    return origins


def frozen_windows_msvc_observation():
    """Report only basename/location categories, never resolved filesystem paths."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return None
    try:
        return _observe()
    except (OSError, AttributeError, TypeError, ValueError):
        # Diagnostics must not turn a working inference run into a false failure.
        return dict.fromkeys(_DLL_NAMES, "unresolved")
