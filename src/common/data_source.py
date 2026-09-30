"""CSV contract shared by GE and the optional database entry point."""
import pandas as pd

_reader = None


def configure_reader(reader):
    global _reader
    _reader = reader


def read_csv(path, **kwargs):
    if _reader is not None:
        frame = _reader(path, **kwargs)
        if frame is not None:
            return frame
    return pd.read_csv(path, **kwargs)
