import ctypes
import ctypes.wintypes
from enum import IntEnum


class FileNotifyAction(IntEnum):
    FILE_ACTION_ADDED = 0x00000001
    FILE_ACTION_REMOVED = 0x00000002
    FILE_ACTION_MODIFIED = 0x00000003
    FILE_ACTION_RENAMED_OLD_NAME = 0x00000004
    FILE_ACTION_RENAMED_NEW_NAME = 0x00000005


class NotifyInfo(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", ctypes.wintypes.DWORD),
        ("Action", ctypes.wintypes.DWORD),
        ("FilenameLength", ctypes.wintypes.DWORD),
        ("Filename", ctypes.wintypes.WCHAR),
    ]
