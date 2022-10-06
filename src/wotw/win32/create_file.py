from pathlib import Path
import ctypes
from ctypes import windll, wintypes
from enum import IntFlag, IntEnum
from typing import Any, Optional

# https://learn.microsoft.com/en-us/windows/win32/secauthz/access-mask

NULL: int = 0


class GenericAccessRights(IntFlag):
    GENERIC_ALL = 0x10000000
    GENERIC_EXECUTE = 0x20000000
    GENERIC_WRITE = 0x40000000
    GENERIC_READ = 0x80000000


class StandardAccessRights(IntFlag):
    STANDARD_RIGHTS_ALL = 0x001F0000
    STANDARD_RIGHTS_EXECUTE = 0x00020000
    STANDARD_RIGHTS_READ = 0x00020000
    STANDARD_RIGHTS_REQUIRED = 0x000F0000
    STANDARD_RIGHTS_WRITE = 0x00020000


class FileDirAccessRights(IntFlag):
    # Directory
    FILE_LIST_DIRECTORY = 0x00000001
    FILE_ADD_FILE = 0x00000002
    FILE_ADD_SUBDIRECTORY = 0x00000004
    FILE_TRAVERSE = 0x00000020
    FILE_DELETE_CHILD = 0x00000040

    # File
    FILE_READ_DATA = 0x00000001
    FILE_APPEND_DATA = 0x00000004
    FILE_READ_EA = 0x00000008
    FILE_EXECUTE = 0x00000020
    FILE_READ_ATTRIBUTES = 0x00000080
    FILE_WRITE_ATTRIBUTES = 0x00000100
    FILE_WRITE_EA = 0x00000010

    # File/Directory
    FILE_WRITE_DATA = 0x00000002

    # Pipe
    FILE_CREATE_PIPE_INSTANCE = 0x00000004


class FileShareMode(IntFlag):
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004


class FileCreationDisposition(IntEnum):
    CREATE_NEW = 1
    CREATE_ALWAYS = 2
    OPEN_EXISTING = 3
    OPEN_ALWAYS = 4
    TRUNCATE_EXISTING = 5


class FileAttributes(IntFlag):
    FILE_ATTRIBUTE_ARCHIVE = 0x00000020
    FILE_ATTRIBUTE_ENCRYPTED = 0x00004000
    FILE_ATTRIBUTE_HIDDEN = 0x0000002
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    FILE_ATTRIBUTE_OFFLINE = 0x00001000
    FILE_ATTRIBUTE_READONLY = 0x00000001
    FILE_ATTRIBUTE_SYSTEM = 0x00000004
    FILE_ATTRIBUTE_TEMPORARY = 0x00000100
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_DELETE_ON_CLOSE = 0x04000000
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FILE_FLAG_OPEN_NO_RECALL = 0x00100000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_FLAG_OVERLAPPED = 0x40000000
    FILE_FLAG_POSIX_SEMANTICS = 0x01000000
    FILE_FLAG_RANDOM_ACCESS = 0x10000000
    FILE_FLAG_SESSION_AWARE = 0x00800000
    FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
    FILE_FLAG_WRITE_THROUGH = 0x80000000


class SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", ctypes.c_bool),
    ]


def create_file(
    path: Path,
    access: GenericAccessRights,
    share_mode: FileShareMode,
    security_attrs: Any = NULL,
    creation_disposition: FileCreationDisposition = FileCreationDisposition.OPEN_EXISTING,
    flags: FileAttributes = FileAttributes.FILE_FLAG_BACKUP_SEMANTICS,
    template: Optional[wintypes.HANDLE] = None,
):
    CreateFileW = windll.kernel32.CreateFileW
    CreateFileW.argtypes = (
        wintypes.LPCWSTR,  # LPCWSTR               lpFileName
        wintypes.DWORD,  # DWORD                 dwDesiredAccess
        wintypes.DWORD,  # DWORD                 dwShareMode
        wintypes.LPVOID,  # LPSECURITY_ATTRIBUTES lpSecurityAttributes
        wintypes.DWORD,  # DWORD                 dwCreationDisposition
        wintypes.DWORD,  # DWORD                 dwFlagsAndAttributes
        wintypes.HANDLE,  # HANDLE                hTemplateFile
    )
    CreateFileW.restype = wintypes.HANDLE

    lpSecurityAttributes = ctypes.byref(security_attrs) if security_attrs else NULL
    hTemplateFile = template if template else NULL

    return CreateFileW(
        str(path),
        access,
        share_mode,
        lpSecurityAttributes,
        creation_disposition,
        flags,
        hTemplateFile,
    )
