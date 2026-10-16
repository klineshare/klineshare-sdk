"""Convert API payloads to pandas DataFrame when available."""

from __future__ import annotations

from typing import Any, Optional


def to_dataframe(data: Any) -> Any:
    """Return a DataFrame for list-of-dicts / dict-of-lists; otherwise return ``data``."""
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover
        return data

    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, list):
        if not data:
            return pd.DataFrame()
        if isinstance(data[0], dict):
            return pd.DataFrame(data)
        return pd.DataFrame({'value': data})
    if isinstance(data, dict):
        # common pattern: {field: [..], ...} column orientation
        if data and all(isinstance(v, list) for v in data.values()):
            try:
                return pd.DataFrame(data)
            except ValueError:
                pass
    return data


def maybe_frame(data: Any, *, as_dataframe: Optional[bool]) -> Any:
    if as_dataframe is False:
        return data
    if as_dataframe is True:
        return to_dataframe(data)
    # default: prefer DataFrame when pandas is installed
    try:
        import pandas  # noqa: F401
    except ImportError:
        return data
    if isinstance(data, list) and (not data or isinstance(data[0], dict)):
        return to_dataframe(data)
    return data
