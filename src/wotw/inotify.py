"""Inotify directory watcher

Adapted from https://gist.github.com/quiver/3609972
Bit mask info from https://github.com/torvalds/linux/blob/master/include/uapi/linux/inotify.h
and https://man7.org/linux/man-pages/man7/inotify.7.html
"""
import ctypes
import ctypes.util
import os
import queue
import select
import struct
from pathlib import Path
from queue import Queue
from typing import Callable, NamedTuple
from enum import IntFlag

POLL_INTERVAL = 1  # in seconds


class inotify_event_struct(ctypes.Structure):
    """
    Structure representation of the inotify_event structure
    (used in buffer size calculations)::
        struct inotify_event {
            __s32 wd;            # watch descriptor
            __u32 mask;          # watch mask
            __u32 cookie;        # cookie to synchronize two events
            __u32 len;           # length (including nulls) of name
            char  name[0];       # stub for possible name
        };
    """

    _fields_ = [
        ("wd", ctypes.c_int),
        ("mask", ctypes.c_uint32),
        ("cookie", ctypes.c_uint32),
        ("len", ctypes.c_uint32),
        ("name", ctypes.c_char_p),
    ]


class InotifyEvent(NamedTuple):
    wd: int
    mask: int
    cookie: int
    len: int
    filename: str
    events: list[str]


EVENT_SIZE = ctypes.sizeof(inotify_event_struct)
EVENT_BUFFER_SIZE = 1024 * (EVENT_SIZE + 16)

WatchID = int
PathBytes = bytes
InotifyEventHandler = Callable[[InotifyEvent, str], None]

# region bit masks
class InotifyMasks(IntFlag):
    IN_ACCESS = 0x00000001  # File was accessed
    IN_MODIFY = 0x00000002  # File was modified
    IN_ATTRIB = 0x00000004  # Metadata changed
    IN_CLOSE_WRITE = 0x00000008  # Writtable file was closed
    IN_CLOSE_NOWRITE = 0x00000010  # Unwrittable file closed
    IN_OPEN = 0x00000020  # File was opened
    IN_MOVED_FROM = 0x00000040  # File was moved from X
    IN_MOVED_TO = 0x00000080  # File was moved to Y
    IN_CREATE = 0x00000100  # Subfile was created
    IN_DELETE = 0x00000200  # Subfile was deleted
    IN_DELETE_SELF = 0x00000400  # Self was deleted
    IN_MOVE_SELF = 0x00000800  # Self was moved
    # the following are legal events.  they are sent as needed to any watch
    IN_UNMOUNT = 0x00002000  # Backing fs was unmounted
    IN_Q_OVERFLOW = 0x00004000  # Event queued overflowed
    IN_IGNORED = 0x00008000  # File was ignored
    # special flags
    IN_ONLYDIR = 0x01000000  # only watch the path if it is a directory
    IN_DONT_FOLLOW = 0x02000000  # don't follow a sym link
    IN_EXCL_UNLINK = 0x04000000  # exclude events on unlinked objects
    IN_MASK_CREATE = 0x10000000  # only create watches
    IN_MASK_ADD = 0x20000000  # add to the mask of an already existing watch
    IN_ISDIR = 0x40000000  # event occurred against dir
    IN_ONESHOT = 0x80000000  # only send event once

    # helper events
    IN_CLOSE = IN_CLOSE_WRITE | IN_CLOSE_NOWRITE  # close
    IN_MOVE = IN_MOVED_FROM | IN_MOVED_TO  # moves

    # All of the events - we build the list by hand so that we can add flags in
    # the future and not break backward compatibility.  Apps will get only the
    # events that they originally wanted.  Be sure to add new events here!
    IN_ALL_EVENTS = (
        IN_ACCESS
        | IN_MODIFY
        | IN_ATTRIB
        | IN_CLOSE_WRITE
        | IN_CLOSE_NOWRITE
        | IN_OPEN
        | IN_MOVED_FROM
        | IN_MOVED_TO
        | IN_DELETE
        | IN_CREATE
        | IN_DELETE_SELF
        | IN_MOVE_SELF
    )


InotifyMaskNames = {
    InotifyMasks.IN_ACCESS: "File was accessed",
    InotifyMasks.IN_MODIFY: "File was modified",
    InotifyMasks.IN_ATTRIB: "Metadata changed",
    InotifyMasks.IN_CLOSE_WRITE: "File was closed and written to",
    InotifyMasks.IN_CLOSE_NOWRITE: "File was closed and not written to",
    InotifyMasks.IN_OPEN: "File was opened",
    InotifyMasks.IN_MOVED_FROM: "File was moved from X",
    InotifyMasks.IN_MOVED_TO: "File was moved to Y",
    InotifyMasks.IN_CREATE: "Subfile was created",
    InotifyMasks.IN_DELETE: "Subfile was deleted",
    InotifyMasks.IN_DELETE_SELF: "Self was deleted",
    InotifyMasks.IN_MOVE_SELF: "Self was moved",
    InotifyMasks.IN_UNMOUNT: "Backing fs was unmounted",
    InotifyMasks.IN_Q_OVERFLOW: "Event queued overflowed",
    InotifyMasks.IN_IGNORED: "File was ignored",
    InotifyMasks.IN_ONLYDIR: "Only watch the path if it is a directory",
    InotifyMasks.IN_DONT_FOLLOW: "Don't follow a sym link",
    InotifyMasks.IN_EXCL_UNLINK: "Exclude events on unlinked objects",
    InotifyMasks.IN_MASK_CREATE: "Only create watches",
    InotifyMasks.IN_MASK_ADD: "Add to the mask of an already existing watch",
    InotifyMasks.IN_ISDIR: "Event occurred against dir",
    InotifyMasks.IN_ONESHOT: "Only send event once",
}
# endregion


class WatchMask(IntFlag):
    WATCH_CREATE = InotifyMasks.IN_CREATE
    WATCH_UPDATE = InotifyMasks.IN_CLOSE_WRITE
    WATCH_DELETE = InotifyMasks.IN_DELETE


# wrap for inotify system call
libc_name = ctypes.util.find_library("c")
libc = ctypes.CDLL(libc_name, use_errno=True)
get_errno_func = ctypes.get_errno

libc.inotify_init.argtypes = []
libc.inotify_init.restype = ctypes.c_int
libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
libc.inotify_add_watch.restype = ctypes.c_int
libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
libc.inotify_rm_watch.restype = ctypes.c_int

inotify_init = libc.inotify_init
inotify_add_watch = libc.inotify_add_watch
inotify_rm_watch = libc.inotify_rm_watch


def mask_to_event_names(mask: int) -> str | list[str]:
    names = []
    masks = [2**idx for idx in range(32)]
    for item in masks:
        if mask & item > 0:
            names.append(InotifyMaskNames[item])

    return names


def close_inotify_fd(fd):
    os.close(fd)


def handle_events(
    q: queue.Queue,
    watches: dict[WatchID, PathBytes],
    event_handler: InotifyEventHandler,
):
    while not q.empty():
        event: InotifyEvent = q.get()
        dir = Path(watches[event.wd].decode("utf-8"))
        event_handler(event, dir)


def read_events(
    event_queue: queue.Queue,
    fd: int,
):
    try:
        event_buffer = os.read(fd, EVENT_BUFFER_SIZE)
    except OSError as msg:
        raise msg

    count = 0
    buffer_i = 0

    fmt = "iIII"
    s_size = struct.calcsize(fmt)
    while buffer_i < len(event_buffer):
        wd, mask, cookie, fname_len = struct.unpack(
            fmt, event_buffer[buffer_i : buffer_i + s_size]
        )
        (filename,) = struct.unpack(
            "%ds" % fname_len,
            event_buffer[buffer_i + s_size : buffer_i + s_size + fname_len],
        )

        filename = filename.rstrip(b"\0")  # remove trailing pad
        event_names = mask_to_event_names(mask)
        event = InotifyEvent(
            wd, mask, cookie, fname_len, filename.decode("utf-8"), event_names
        )
        # print("enqueue", event)
        event_queue.put(event)
        buffer_i += s_size + fname_len
        count += 1

    # print(f"{count} events queued")


def process_inotify_events(
    inotify_fd: int,
    watches: dict[WatchID, PathBytes],
    event_handler: InotifyEventHandler | None = None,
):
    event_queue = Queue()
    epoll = select.epoll()
    epoll.register(inotify_fd)

    while True:
        try:
            events = epoll.poll(POLL_INTERVAL)
            for _fileno, event in events:
                if event & select.EPOLLIN:
                    read_events(event_queue, inotify_fd)
            handle_events(event_queue, watches, event_handler)
        except KeyboardInterrupt as err:
            break


def watch(
    directories: Path | list[Path],
    event_handler: InotifyEventHandler,
    watch_for: InotifyMasks | None = None,
):
    if isinstance(directories, Path):
        directories = [directories]

    if watch_for is None:
        watch_masks = InotifyMasks.IN_ALL_EVENTS
    else:
        watch_masks = watch_for

    watches: dict[WatchID, PathBytes] = {}

    inotify_fd = inotify_init()
    if inotify_fd > 0:
        for dir in directories:
            dirstr = str(dir).encode("utf-8")
            wd = inotify_add_watch(inotify_fd, dirstr, watch_masks)
            if wd < 0:
                raise OSError(
                    f"Unable to add inotify watch. Ensure directory to watch {dirstr.decode('utf-8')} exists."
                )
            watches[wd] = dirstr
        try:
            process_inotify_events(inotify_fd, watches, event_handler)
        finally:
            inotify_rm_watch(inotify_fd, wd)
            close_inotify_fd(inotify_fd)
    else:
        raise OSError("Unable to initialize inotify")
