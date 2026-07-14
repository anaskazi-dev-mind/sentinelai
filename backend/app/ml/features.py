"""
features.py
------------
Single source of truth for feature engineering, shared by both:
  - train_models.py  (training on the synthetic dataset)
  - predict.py        (live inference on real incoming events)

Keeping this logic in one place guarantees train-time and inference-time
features are computed identically -- a very common real-world ML bug is
"training/serving skew," where the two drift apart and the model quietly
degrades. Centralizing it here prevents that class of bug entirely.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "hour_of_day",
    "failed_login_attempts",
    "data_transfer_mb",
    "file_access_count",
    "network_connections",
    "distinct_files_touched",
    "is_after_hours",
    "is_known_device",
    "cpu_spike_percent",
]

KNOWN_DEVICES = {"WKSTN-01", "WKSTN-02", "SRV-DB-PRIMARY", "LAPTOP-ADMIN"}

SCALER_FILENAME = "feature_scaler.joblib"

# Default used for the one feature (cpu_spike_percent) that can't be
# recovered from a plain-text log line -- it's intentionally a weak,
# noisy signal in the model (see data_generator.py), so a neutral default
# doesn't meaningfully distort predictions.
DEFAULT_CPU_SPIKE = 30.0


# =====================================================================
# DataFrame -> matrix (used at training time on the full synthetic set)
# =====================================================================


def build_feature_matrix(df: pd.DataFrame) -> np.ndarray:
    missing = [col for col in FEATURE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing required feature columns: {missing}")
    return df[FEATURE_COLUMNS].to_numpy(dtype=float)


class FeatureScaler:
    """Thin wrapper around StandardScaler with save/load, so every model
    (KNN, SVM, ANN etc.) consumes features on the same standardized scale."""

    def __init__(self) -> None:
        self._scaler = StandardScaler()
        self._fitted = False

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        self._fitted = True
        return self._scaler.fit_transform(X)

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError(
                "FeatureScaler must be fit (or loaded) before calling transform()."
            )
        return self._scaler.transform(X)

    def save(self, path: str) -> None:
        joblib.dump(self._scaler, path)

    def load(self, path: str) -> "FeatureScaler":
        self._scaler = joblib.load(path)
        self._fitted = True
        return self


# =====================================================================
# Raw event -> feature dict (used at inference time on a live log line)
# =====================================================================

_FAILED_LOGIN_RE = re.compile(r"(\d+)\s+failed attempts", re.IGNORECASE)
_TRANSFER_MB_RE = re.compile(r"([\d.]+)\s*MB transferred", re.IGNORECASE)
_NET_CONN_RE = re.compile(r"(\d+)\s+active connections", re.IGNORECASE)
_FILE_OPS_RE = re.compile(r"(\d+)\s+file operations", re.IGNORECASE)
_DISTINCT_FILES_RE = re.compile(r"touched\s+(\d+)\s+related files", re.IGNORECASE)
_DEVICE_RE = re.compile(
    r"(WKSTN-\d+|SRV-[A-Z0-9-]+|LAPTOP-[A-Z]+|UNKNOWN-HOST|EXT-[\d.]+)"
)


def extract_features_from_event(
    raw_message: str,
    file_path: str | None = None,
    timestamp: datetime | None = None,
) -> dict:
    """
    Heuristically parses a real incoming log line / file-activity message
    into the same 9 numeric features the models were trained on.

    This is regex-based rather than a full NLP pipeline deliberately --
    it matches the structured log format produced by
    services/log_ingestion_service.py, which is a realistic assumption
    for a log-monitoring tool (most production log parsers, e.g. Splunk's
    field extraction, are also pattern-based for known log formats).
    """
    timestamp = timestamp or datetime.now(timezone.utc)

    def _find_int(pattern: re.Pattern, default: int = 0) -> int:
        match = pattern.search(raw_message)
        return int(match.group(1)) if match else default

    def _find_float(pattern: re.Pattern, default: float = 0.0) -> float:
        match = pattern.search(raw_message)
        return float(match.group(1)) if match else default

    device_match = _DEVICE_RE.search(raw_message)
    device = device_match.group(1) if device_match else None
    is_known_device = 1 if device in KNOWN_DEVICES else 0

    hour = timestamp.hour
    is_after_hours = 1 if (hour < 7 or hour > 20) else 0

    file_ops = _find_int(_FILE_OPS_RE)
    distinct_files = _find_int(_DISTINCT_FILES_RE)

    return {
        "hour_of_day": hour,
        "failed_login_attempts": _find_int(_FAILED_LOGIN_RE),
        "data_transfer_mb": _find_float(_TRANSFER_MB_RE),
        "file_access_count": file_ops if file_ops else distinct_files,
        "network_connections": _find_int(_NET_CONN_RE),
        "distinct_files_touched": (
            distinct_files if distinct_files else (1 if file_path else 0)
        ),
        "is_after_hours": is_after_hours,
        "is_known_device": is_known_device,
        "cpu_spike_percent": DEFAULT_CPU_SPIKE,
    }


def feature_dict_to_vector(feature_dict: dict) -> np.ndarray:
    return np.array([[feature_dict[col] for col in FEATURE_COLUMNS]], dtype=float)
