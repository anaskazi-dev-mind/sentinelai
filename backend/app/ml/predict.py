"""
predict.py
----------
Loads the artifacts saved by train_models.py and runs live inference on
a real incoming event (a log line or file-activity message).

Design choices worth knowing for your viva:
  - All model artifacts are loaded ONCE and cached (module-level singleton),
    not reloaded on every request -- reloading a model per API call is a
    common beginner mistake that tanks performance in production.
  - The production severity prediction comes from whichever classifier
    train_models.py determined was best (by macro-F1).
  - The human-readable "explanation" always comes from the Decision Tree
    specifically, even if it wasn't the best-performing model -- because
    it's the one classifier whose reasoning can be read out as plain
    if/else rules. This mirrors a real practice: pairing a strong
    black-box model with an interpretable companion model purely for
    explainability.
  - risk_score is the average of the KNN Regressor and Linear Regression
    predictions (simple ensemble averaging), which reduces variance
    compared to trusting a single regressor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

from app.ml.features import (
    FEATURE_COLUMNS,
    FeatureScaler,
    extract_features_from_event,
    feature_dict_to_vector,
)

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"

SEVERITY_LABELS = ["normal", "suspicious", "critical"]


@dataclass
class PredictionResult:
    severity: str
    risk_score: float
    cluster_id: int
    model_used: str
    explanation: str


class _ModelRegistry:
    """Holds every trained artifact in memory after the first load."""

    def __init__(self) -> None:
        if not MODEL_DIR.exists() or not (MODEL_DIR / "best_classifier.txt").exists():
            raise FileNotFoundError(
                "No trained models found. Run `python -m app.ml.train_models` first "
                f"(expected artifacts in {MODEL_DIR})."
            )

        self.scaler = FeatureScaler().load(str(MODEL_DIR / "feature_scaler.joblib"))

        self.best_classifier_name = (
            (MODEL_DIR / "best_classifier.txt").read_text().strip()
        )
        self.best_classifier = joblib.load(
            MODEL_DIR / f"{self.best_classifier_name}.joblib"
        )

        # Always load the decision tree separately -- used for explanations
        # regardless of which model is "best".
        self.decision_tree = joblib.load(MODEL_DIR / "decision_tree.joblib")

        self.knn_regressor = joblib.load(MODEL_DIR / "knn_regressor.joblib")
        self.linear_regression = joblib.load(MODEL_DIR / "linear_regression.joblib")

        self.kmeans = joblib.load(MODEL_DIR / "kmeans.joblib")


@lru_cache
def _get_registry() -> _ModelRegistry:
    """Cached so all artifacts are read from disk exactly once per process."""
    return _ModelRegistry()


def _explain_with_decision_tree(
    registry: _ModelRegistry, scaled_sample: np.ndarray, raw_features: dict
) -> str:
    """
    Walks the decision path the Decision Tree took for this specific sample
    and renders it as a plain-English rule trail, using the original
    (unscaled) feature units so it's human-readable.
    """
    tree_model = registry.decision_tree
    tree = tree_model.tree_

    node_indicator = tree_model.decision_path(scaled_sample)
    leaf_id = tree_model.apply(scaled_sample)[0]
    path_nodes = node_indicator.indices[
        node_indicator.indptr[0] : node_indicator.indptr[1]
    ]

    scale_ = registry.scaler._scaler.scale_
    mean_ = registry.scaler._scaler.mean_

    reasons: list[str] = []
    for node_id in path_nodes:
        if node_id == leaf_id:
            continue  # leaf carries the final label, not a rule

        feat_idx = tree.feature[node_id]
        feat_name = FEATURE_COLUMNS[feat_idx]
        raw_value = raw_features[feat_name]

        # Convert this node's scaled split threshold back to the original unit
        raw_threshold = tree.threshold[node_id] * scale_[feat_idx] + mean_[feat_idx]
        went_left = scaled_sample[0][feat_idx] <= tree.threshold[node_id]
        comparator = "<=" if went_left else ">"

        readable_name = feat_name.replace("_", " ")
        reasons.append(
            f"{readable_name} {comparator} {raw_threshold:.1f} (actual: {raw_value})"
        )

        if len(reasons) >= 3:  # top 3 splits closest to the root are the most decisive
            break

    if not reasons:
        return "Classified based on overall feature pattern (no single dominant rule)."
    return "Flagged because: " + "; ".join(reasons) + "."


def predict_event(
    raw_message: str,
    file_path: str | None = None,
    timestamp: datetime | None = None,
) -> PredictionResult:
    registry = _get_registry()

    raw_features = extract_features_from_event(raw_message, file_path, timestamp)
    raw_vector = feature_dict_to_vector(raw_features)
    scaled_vector = registry.scaler.transform(raw_vector)

    # ----- Severity: production classifier (best by macro-F1) -----
    severity = str(registry.best_classifier.predict(scaled_vector)[0])

    # ----- Risk score: ensemble average of two regressors -----
    knn_score = float(registry.knn_regressor.predict(scaled_vector)[0])
    linear_score = float(registry.linear_regression.predict(scaled_vector)[0])
    risk_score = round(float(np.clip((knn_score + linear_score) / 2, 0, 100)), 2)

    # ----- Cluster: which behavioral group this event resembles -----
    cluster_id = int(registry.kmeans.predict(scaled_vector)[0])

    # ----- Explanation: always from the interpretable Decision Tree -----
    explanation = _explain_with_decision_tree(registry, scaled_vector, raw_features)

    return PredictionResult(
        severity=severity,
        risk_score=risk_score,
        cluster_id=cluster_id,
        model_used=registry.best_classifier_name,
        explanation=explanation,
    )


def get_cluster_labels_for_dataset(X_scaled: np.ndarray) -> np.ndarray:
    """Used by the /events cluster-summary endpoint to label historical events."""
    return _get_registry().kmeans.predict(X_scaled)
