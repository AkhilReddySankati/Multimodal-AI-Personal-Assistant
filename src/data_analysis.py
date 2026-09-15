"""
CSV / Excel analysis.

Fix vs the original: describe().to_dict() and corr().to_dict() return numpy
scalars (np.float64), and sample rows can contain NaN / Timestamp objects.
None of those are JSON-serialisable, so the agent crashed when it tried to
send the analysis back to Gemini as a function response. Everything is now
converted to plain Python types.
"""

import math
import os

import numpy as np
import pandas as pd


# ============================================================
# JSON-SAFE CONVERSION
# ============================================================

def to_native(value):
    """Convert numpy / pandas values into plain JSON-safe Python types."""

    if value is None:
        return None

    if isinstance(value, dict):
        return {str(key): to_native(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_native(item) for item in value]

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value

    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)

    if value is pd.NaT:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    return str(value)


# ============================================================
# LOAD
# ============================================================

def load_dataset(file_path):
    """Load a CSV or Excel dataset."""

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":
        return pd.read_csv(file_path)

    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)

    raise ValueError(
        f"Unsupported dataset format: {extension}. Use CSV or Excel."
    )


# ============================================================
# FULL ANALYSIS
# ============================================================

def analyze_dataset(file_path):
    """Return a structured, JSON-safe summary of a dataset."""

    df = load_dataset(file_path)

    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()

    result = {
        "file_name": os.path.basename(file_path),
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": [str(column) for column in df.columns],
        "data_types": {
            str(column): str(dtype)
            for column, dtype in df.dtypes.items()
        },
        "missing_values": {
            str(column): int(value)
            for column, value in df.isnull().sum().items()
            if value > 0
        },
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_columns": [str(c) for c in numeric_columns],
        "categorical_columns": [str(c) for c in categorical_columns],
    }

    if numeric_columns:
        result["statistics"] = to_native(
            df[numeric_columns].describe().round(2).to_dict()
        )
    else:
        result["statistics"] = {}

    if len(numeric_columns) >= 2:
        result["correlation"] = to_native(
            df[numeric_columns].corr(numeric_only=True).round(3).to_dict()
        )
    else:
        result["correlation"] = {}

    result["sample_rows"] = to_native(
        df.head(5).where(pd.notnull(df.head(5)), None).to_dict(
            orient="records"
        )
    )

    return result


# ============================================================
# INDIVIDUAL HELPERS
# ============================================================

def get_missing_values(file_path):

    df = load_dataset(file_path)

    return {
        str(column): int(value)
        for column, value in df.isnull().sum().items()
        if value > 0
    }


def get_descriptive_statistics(file_path):

    numeric_df = load_dataset(file_path).select_dtypes(include="number")

    if numeric_df.empty:
        return {}

    return to_native(numeric_df.describe().round(2).to_dict())


def get_correlations(file_path):

    numeric_df = load_dataset(file_path).select_dtypes(include="number")

    if numeric_df.shape[1] < 2:
        return {}

    return to_native(numeric_df.corr(numeric_only=True).round(3).to_dict())


def get_categorical_summary(file_path):

    df = load_dataset(file_path)

    categorical_columns = df.select_dtypes(
        include=["object", "category"]
    ).columns

    return {
        str(column): to_native(
            df[column].value_counts(dropna=False).head(10).to_dict()
        )
        for column in categorical_columns
    }
