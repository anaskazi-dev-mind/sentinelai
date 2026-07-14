"""
data_generator.py
------------------
Generates a realistic, labeled synthetic dataset of security events for
training all 10 ML modules.

Why synthetic data (and why that's the right, honest choice here):
Real intrusion-detection datasets require live network capture, which
isn't available in a training/coursework setting. Instead, we generate
data from a *known* underlying risk function with injected noise -- this
is a standard, legitimate technique for prototyping and benchmarking ML
pipelines before real production data is available, and is explicitly
documented as such (see README.md -> "Dataset" section for the report).

Each event has:
  - 9 numeric features (used by every classifier/regressor/clustering model)
  - a human-readable log message (used by the chatbot / log monitor UI)
  - a multiclass severity label: normal / suspicious / critical
  - a binary label: normal (0) vs anomalous (1)
  - a continuous risk_score (0-100), used as the regression target
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42

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

KNOWN_DEVICES = ["WKSTN-01", "WKSTN-02", "SRV-DB-PRIMARY", "LAPTOP-ADMIN"]
UNKNOWN_DEVICE_LABELS = ["UNKNOWN-HOST", "EXT-192.168.77.14", "EXT-10.0.9.201"]

SENSITIVE_FILES = [
    "/data/finance/payroll_2026.xlsx",
    "/etc/shadow",
    "/data/hr/employee_records.db",
    "/var/backups/customer_pii.csv",
    "/data/finance/tax_filings_2025.pdf",
]
ROUTINE_FILES = [
    "/home/user/reports/Q3_summary.pdf",
    "/home/user/notes/meeting_minutes.docx",
    "/var/log/app/access.log",
    "/home/user/downloads/invoice_1042.pdf",
    "/tmp/build_cache/output.json",
]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sample_event(rng: np.random.Generator, category: str) -> dict:
    """
    Draws one event's raw features from a distribution appropriate to its
    intended category. The category *biases* the draw but does not fix the
    label outright -- the label is derived afterward from the noisy risk
    score, so classes overlap realistically instead of being trivially
    separable.
    """
    if category == "normal":
        hour = rng.integers(8, 19)
        failed_logins = rng.poisson(0.2)
        transfer_mb = rng.gamma(2, 15)
        file_access = rng.poisson(4)
        net_conn = rng.poisson(3)
        distinct_files = rng.poisson(2)
        known_device = 1

    elif category == "suspicious":
        hour = rng.integers(0, 23)
        failed_logins = rng.poisson(2.5)
        transfer_mb = rng.gamma(3, 60)
        file_access = rng.poisson(15)
        net_conn = rng.poisson(8)
        distinct_files = rng.poisson(6)
        known_device = rng.choice([0, 1], p=[0.4, 0.6])

    else:  # critical
        hour = rng.integers(0, 23)
        failed_logins = rng.poisson(6)
        transfer_mb = rng.gamma(4, 150)
        file_access = rng.poisson(35)
        net_conn = rng.poisson(15)
        distinct_files = rng.poisson(14)
        known_device = rng.choice([0, 1], p=[0.75, 0.25])

    is_after_hours = 1 if (hour < 7 or hour > 20) else 0
    cpu_spike = _clip(
        rng.normal(30, 20), 0, 100
    )  # mostly noise, weak signal on purpose

    return {
        "hour_of_day": int(hour),
        "failed_login_attempts": int(_clip(failed_logins, 0, 20)),
        "data_transfer_mb": round(float(_clip(transfer_mb, 0, 1000)), 2),
        "file_access_count": int(_clip(file_access, 0, 100)),
        "network_connections": int(_clip(net_conn, 0, 50)),
        "distinct_files_touched": int(_clip(distinct_files, 0, 30)),
        "is_after_hours": int(is_after_hours),
        "is_known_device": int(known_device),
        "cpu_spike_percent": round(cpu_spike, 1),
    }


def _compute_risk_score(row: dict, rng: np.random.Generator) -> float:
    """
    The single source of truth for 'how risky is this event'. Both the
    classification labels (normal/suspicious/critical) AND the regression
    target (risk_score) are derived from this, so the models stay
    consistent with each other -- exactly like a real scoring system.
    """
    raw = (
        row["failed_login_attempts"] * 4.5
        + (row["data_transfer_mb"] / 1000) * 28
        + row["file_access_count"] * 0.55
        + row["network_connections"] * 1.3
        + row["distinct_files_touched"] * 1.1
        + row["is_after_hours"] * 14
        + (1 - row["is_known_device"]) * 18
    )
    noisy = raw + rng.normal(0, 6)  # measurement noise -- makes regression non-trivial
    return round(_clip(noisy, 0, 100), 2)


def _severity_from_risk(risk_score: float) -> str:
    if risk_score < 28:
        return "normal"
    if risk_score < 60:
        return "suspicious"
    return "critical"


def _build_message(
    row: dict, severity: str, rng: np.random.Generator
) -> tuple[str, str, str | None]:
    """Returns (source, raw_message, file_path)."""
    device = (
        rng.choice(KNOWN_DEVICES)
        if row["is_known_device"]
        else rng.choice(UNKNOWN_DEVICE_LABELS)
    )

    if rng.random() < 0.5:
        # file-activity style event
        file_path = rng.choice(
            SENSITIVE_FILES if severity != "normal" else ROUTINE_FILES
        )
        msg = (
            f"File access: {file_path} touched {row['distinct_files_touched']} related files "
            f"by {device} at hour {row['hour_of_day']:02d}:00 "
            f"({row['data_transfer_mb']}MB transferred)."
        )
        return "file_scan", msg, str(file_path)

    # log-line style event
    msg = (
        f"Login node {device}: {row['failed_login_attempts']} failed attempts, "
        f"{row['network_connections']} active connections, "
        f"{row['file_access_count']} file operations in session "
        f"(after-hours={'yes' if row['is_after_hours'] else 'no'})."
    )
    return "log_monitor", msg, None


def generate_synthetic_events(n: int = 3000, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    category_choices = rng.choice(
        ["normal", "suspicious", "critical"], size=n, p=[0.65, 0.24, 0.11]
    )

    records = []
    for category in category_choices:
        row = _sample_event(rng, category)
        risk_score = _compute_risk_score(row, rng)
        severity = _severity_from_risk(risk_score)
        source, message, file_path = _build_message(row, severity, rng)

        records.append(
            {
                **row,
                "risk_score": risk_score,
                "severity": severity,
                "is_anomalous": 0 if severity == "normal" else 1,
                "source": source,
                "raw_message": message,
                "file_path": file_path,
            }
        )

    df = pd.DataFrame(records)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)  # shuffle


def save_dataset(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    dataset = generate_synthetic_events(n=3000)
    out_path = save_dataset(
        dataset, Path(__file__).parent / "data" / "synthetic_events.csv"
    )
    print(f"Generated {len(dataset)} events -> {out_path}")
    print(dataset["severity"].value_counts(normalize=True).round(3))
