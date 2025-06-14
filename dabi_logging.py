# dabi_logging.py
import sys
import os
import inspect
from pathlib import Path
from datetime import datetime

class _DabiPrinter:
    def __init__(self, logfile: str | Path = "dabi.log", mode: str = "a", encoding: str = "utf-8"):
        self.logfile = Path(f"./logs/dabi_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log")
        self._handle = open(self.logfile, mode, encoding=encoding)
        self._handle.write(f"--- Log started {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")

    # Make the object itself callable → acts like a function
    def __call__(self, *args, sep: str = " ", end: str = "\n", flush: bool = False):
        caller = inspect.stack()[1]
        function = caller.function
        filename = os.path.basename(caller.filename)
        lineno = str(caller.lineno)
        msg = filename + ":" + function + ":" + lineno + ":" + sep.join(str(a) for a in args) + end

        # 1) Console
        sys.stdout.write(msg)
        if flush:
            sys.stdout.flush()

        # 2) File
        self._handle.write(msg)
        self._handle.flush()

    def close(self):
        if getattr(self, "_handle", None) and not self._handle.closed:
            try:
                self._handle.flush()
            finally:                           # always attempt to close
                self._handle.close()

    def __del__(self):
        # Called when the object is garbage-collected (not guaranteed order)
        self.close()

    # Optional: make it 'with'-able
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        self.close()

# Create a ready-to-use singleton, just import and call
dabi_print = _DabiPrinter()