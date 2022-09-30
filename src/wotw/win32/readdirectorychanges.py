import ctypes
import ctypes.wintypes
from enum import IntFlag
from fileinput import filename
from pathlib import Path
from typing import Any

from wotw.win32.create_file import (
    FileAttributes,
    FileCreationDisposition,
    FileDirAccessRights,
    FileShareMode,
    GenericAccessRights,
    create_file,
)
from wotw.win32.notify_info import NotifyInfo

MAX_PATH = 260
NULL: int = 0


class FileNotifyChange(IntFlag):
    FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
    FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
    FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004
    FILE_NOTIFY_CHANGE_SIZE = 0x00000008
    FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
    FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x00000020
    FILE_NOTIFY_CHANGE_CREATION = 0x00000040
    FILE_NOTIFY_CHANGE_SECURITY = 0x00000100


class DummyStructName(ctypes.Structure):
    _fields_ = [
        ("Offset", ctypes.wintypes.DWORD),
        ("OffsetHigh", ctypes.wintypes.DWORD),
    ]


class DummyUnionName(ctypes.Union):
    _fields_ = [
        ("DUMMYSTRUCTNAME", DummyStructName),
        ("Pointer", ctypes.c_void_p),
    ]


class Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.POINTER),
        ("InternalHigh", ctypes.POINTER),
        ("DUMMYUNIONNAME", DummyUnionName),
        ("hEvent", ctypes.wintypes.HANDLE),
    ]


def error_check(
    result: ctypes.wintypes.BOOL, func: Any, *arguments: Any
) -> ctypes.wintypes.BOOL:
    return result


def completion_routine(
    error_code: int, number_of_bytes_transfered: int, overlapped: ctypes.pointer
) -> None:
    ...


ReadDirectoryChangesW = ctypes.windll.kernel32.ReadDirectoryChangesW

ReadDirectoryChangesW.restype = ctypes.wintypes.BOOL
ReadDirectoryChangesW.errcheck = error_check
ReadDirectoryChangesW.argtypes = (
    ctypes.wintypes.HANDLE,  # hDirectory
    ctypes.wintypes.LPVOID,  # lpBuffer
    ctypes.wintypes.DWORD,  # nBufferLength
    ctypes.wintypes.BOOL,  # bWatchSubtree
    ctypes.wintypes.DWORD,  # dwNotifyFilter
    ctypes.POINTER(ctypes.wintypes.DWORD),  # lpBytesReturned
    ctypes.POINTER(Overlapped),  # lpOverlapped
    ctypes.POINTER,  # FileIOCompletionRoutine # lpCompletionRoutine
)


def ReadDirectoryChanges(path: Path, change_notify: int):
    dir_handle = create_file(
        path,
        access=FileDirAccessRights.FILE_LIST_DIRECTORY,
        share_mode=FileShareMode.FILE_SHARE_READ,
        creation_disposition=FileCreationDisposition.OPEN_EXISTING,
        flags=FileAttributes.FILE_FLAG_BACKUP_SEMANTICS
        # | FileAttributes.FILE_FLAG_OVERLAPPED,
    )

    buffer_size = MAX_PATH * 3
    filename_buffer = ctypes.create_unicode_buffer(size=buffer_size)
    notify_info = NotifyInfo()
    notify_info.Filename = filename_buffer
    # overlapped = Overlapped()
    bytes_returned = 0

    read_dir = ReadDirectoryChangesW(
        dir_handle,
        ctypes.POINTER(notify_info),
        ctypes.sizeof(notify_info) + buffer_size,
        True,
        change_notify,
        ctypes.POINTER(bytes_returned),
        NULL,
        # ctypes.POINTER(overlapped),
        ctypes.POINTER(completion_routine),
    )
