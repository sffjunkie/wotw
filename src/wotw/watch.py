from pathlib import Path
from typing import Generator

from wotw import inotify


def subdirs(path: Path) -> Generator[str, None, None]:
    """Walk a path and return all files found"""
    for entry in Path(path).iterdir():
        if entry.is_dir():
            yield str(entry)
            yield from subdirs(entry)


def watch(directory: Path, event_handler: inotify.InotifyEventHandler):
    dirs = list(subdirs(directory))
    print(dirs)
