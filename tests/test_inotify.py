from pathlib import Path
from wotw.inotify import watch, InotifyEvent, InotifyMasks


def test_inotify_watch():
    watch_for = (
        InotifyMasks.IN_CLOSE_WRITE | InotifyMasks.IN_DELETE | InotifyMasks.IN_MOVE
    )

    def event_handler(event: InotifyEvent, dir: Path):
        # if event.mask & watch_for:
        print(f"Got event {event.events} on file {event.filename} in {dir}")

    p1 = Path("~/tmp/b").expanduser()
    p2 = Path("~/tmp/a").expanduser()

    print()
    watch([p1, p2], event_handler, watch_for)


if __name__ == "__main__":
    test_inotify_watch()


"""
Touch new file ->
    Subfile was created
    File was opened
    Metadata changed
    Writable file was closed

Touch existing ->
    File was opened
    Metadata changed
    Writable file was closed

Edit new file ->
    Subfile was created
    File was opened
    File was modified
    Writable file was closed

Edit existing file ->
    File was accessed
    Unwritable file closed
    File was modified

    File was opened
    File was modified
    Writable file was closed

Delete file ->
    Subfile was deleted
"""
