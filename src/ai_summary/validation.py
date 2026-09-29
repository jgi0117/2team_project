"""공통 키, 시점과 수치 검사. 기존 공통 데이터 계약을 변경하지 않는다."""

import numpy as np
import pandas as pd


def timestamp(value):
    at = pd.Timestamp(value)
    if pd.isna(at) or at.tzinfo is not None:
        raise ValueError("Expected a timezone-naive timestamp")
    return at


def frame_with_keys(frame, required, keys):
    missing = set(required) - set(frame)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    result = frame.copy()
    if result[list(keys)].isna().any().any():
        raise ValueError("Missing row keys")
    result["as_of"] = pd.to_datetime(result["as_of"], errors="raise")
    if (not pd.api.types.is_datetime64_any_dtype(result.as_of)
            or result.as_of.isna().any() or result.as_of.dt.tz is not None):
        raise ValueError("Expected timezone-naive timestamps")
    ids = pd.to_numeric(result.machineID, errors="raise")
    if (~np.isfinite(ids) | ids.le(0) | ids.mod(1).ne(0)).any():
        raise ValueError("machineID must be a positive integer")
    result["machineID"] = ids.astype(int)
    if result.duplicated(list(keys)).any():
        raise ValueError(f"Duplicate keys: {keys}")
    return result


def numeric(frame, column, *, minimum=None, maximum=None, nullable=False):
    values = pd.to_numeric(frame[column], errors="raise")
    present = values.dropna() if nullable else values
    if not np.isfinite(present).all():
        raise ValueError(f"Invalid {column}")
    if minimum is not None and present.lt(minimum).any():
        raise ValueError(f"{column} below {minimum}")
    if maximum is not None and present.gt(maximum).any():
        raise ValueError(f"{column} above {maximum}")
    frame[column] = values


def boolean_values(values):
    flags = values.astype(str).str.lower()
    if not flags.isin(["true", "false", "1", "0", "1.0", "0.0"]).all():
        raise ValueError("Invalid boolean values")
    return flags.isin(["true", "1", "1.0"])
