"""An OS-owned scheduler lease released by the OS even after a process crash."""
import os
from contextlib import contextmanager


@contextmanager
def single_instance(root):
    stream=(root/'worker.lock').open('a+b')
    stream.seek(0)
    if os.fstat(stream.fileno()).st_size==0:stream.write(b'0');stream.flush()
    stream.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError('Another studio worker owns this data root; use one backend worker')
    try:yield
    finally:stream.close()
