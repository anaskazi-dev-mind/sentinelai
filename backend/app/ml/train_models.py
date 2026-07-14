"""
train_models.py
----------------
Trains ALL 10 ML course modules on the synthetic security-event dataset,
benchmarks the classifiers against each other on a held-out test set, and
persists every trained artifact to disk for use by predict.py.

Run directly:
    python -m app.ml.train_models

Modules trained here (mapped 1:1 to the SBT training curriculum):
    1. KNN Classification        -> severity (normal/suspicious/critical)
    2. KNN Regression             -> risk_score
    3. Linear Regression          -> risk_score
    4. Logistic Regression (bin)  -> is_anomalous
    5. Logistic Regression (mc)   -> severity
    6. Decision Tree              -> severity (also used for explanations)
    7. Artificial Neural Network  -> severity (MLPClassifier)
    8. Support Vector Machine     -> severity
    9. K-Means Clustering         -> unsupervised behavior groups
   10. Random Forest              -> severity (production classifier)

The best-performing severity classifier (by macro-F1) is selected and
marked as the "production" model that predict.py loads by default --
this model-comparison step is a standard applied-ML practice, and its
output (benchmark_report.json) doubles as honest evidence for the
report's Outcomes chapter.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from app.ml.data_generator import generate_synthetic_events, save_dataset
from app.ml.features import FeatureScaler, FEATURE_COLUMNS, build_feature_matrix

ML_DIR = Path(__file__).resolve().parent
DATA_PATH = ML_DIR / "data" / "synthetic_events.csv"
MODEL_DIR = ML_DIR / "saved_models"
RANDOM_STATE = 42


def load_or_generate_dataset() -> pd.DataFrame:
    if DATA_PATH.exists():
        return pd.read_csv(DATA_PATH)
    df = generate_synthetic_events(n=3000)
    save_dataset(df, DATA_PATH)
    return df


def prepare_data(df: pd.DataFrame) -> dict:
    X = build_feature_matrix(df)
    y_severity = df["severity"].to_numpy()
    y_binary = df["is_anomalous"].to_numpy()
    y_risk = df["risk_score"].to_numpy()

    # Single split shared across every model, so all 10 are compared/used
    # on the exact same train/test partition -- required for a fair benchmark.
    indices = np.arange(len(df))
    idx_train, idx_test = train_test_split(
        indices, test_size=0.2, random_state=RANDOM_STATE, stratify=y_severity
    )

    scaler = FeatureScaler()
    X_train_scaled = scaler.fit_transform(X[idx_train])
    X_test_scaled = scaler.transform(X[idx_test])

    return {
        "scaler": scaler,
        "X_all_scaled": scaler.transform(X),  # for KMeans, fit on everything
        "X_train": X_train_scaled,
        "X_test": X_test_scaled,
        "y_severity_train": y_severity[idx_train],
        "y_severity_test": y_severity[idx_test],
        "y_binary_train": y_binary[idx_train],
        "y_binary_test": y_binary[idx_test],
        "y_risk_train": y_risk[idx_train],
        "y_risk_test": y_risk[idx_test],
    }


# =====================================================================
# 1, 5, 6, 7, 8, 10 -- Severity classifiers (compared head-to-head)
# =====================================================================


def train_classifiers(X_train: np.ndarray, y_train: np.ndarray) -> dict:
    models = {
        "knn": KNeighborsClassifier(n_neighbors=7, weights="distance"),
        "logistic_multiclass": LogisticRegression(
            max_iter=1000, multi_class="multinomial", random_state=RANDOM_STATE
        ),
        "decision_tree": DecisionTreeClassifier(
            max_depth=6, min_samples_leaf=10, random_state=RANDOM_STATE
        ),
        "ann": MLPClassifier(
            hidden_layer_sizes=(32, 16), max_iter=800, random_state=RANDOM_STATE
        ),
        "svm": SVC(kernel="rbf", C=2.0, probability=True, random_state=RANDOM_STATE),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=10, random_state=RANDOM_STATE
        ),
    }
    for name, model in models.items():
        model.fit(X_train, y_train)
    return models


def evaluate_classifiers(models: dict, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    report = {}
    for name, model in models.items():
        preds = model.predict(X_test)
        report[name] = {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "f1_macro": round(float(f1_score(y_test, preds, average="macro")), 4),
        }
    return report


# =====================================================================
# 4 -- Logistic Regression (Binary Classification)
# =====================================================================


def train_binary_logistic(
    X_train: np.ndarray, y_train: np.ndarray
) -> LogisticRegression:
    model = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    model.fit(X_train, y_train)
    return model


# =====================================================================
# 2, 3 -- Regressors (risk_score prediction)
# =====================================================================


def train_regressors(X_train: np.ndarray, y_train: np.ndarray) -> dict:
    knn_reg = KNeighborsRegressor(n_neighbors=7, weights="distance").fit(
        X_train, y_train
    )
    lin_reg = LinearRegression().fit(X_train, y_train)
    return {"knn_regressor": knn_reg, "linear_regression": lin_reg}


def evaluate_regressors(models: dict, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    report = {}
    for name, model in models.items():
        preds = model.predict(X_test)
        report[name] = {
            "mae": round(float(mean_absolute_error(y_test, preds)), 3),
            "r2": round(float(r2_score(y_test, preds)), 4),
        }
    return report


# =====================================================================
# 9 -- K-Means Clustering (unsupervised behavior grouping)
# =====================================================================


def train_kmeans(X_all: np.ndarray, n_clusters: int = 4) -> KMeans:
    model = KMeans(n_clusters=n_clusters, n_init=10, random_state=RANDOM_STATE)
    model.fit(X_all)
    return model


# =====================================================================
# Orchestration
# =====================================================================


def main() -> None:
    start = time.time()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading dataset...")
    df = load_or_generate_dataset()
    data = prepare_data(df)

    print(
        "Training severity classifiers (KNN, Logistic-MC, Decision Tree, ANN, SVM, Random Forest)..."
    )
    classifiers = train_classifiers(data["X_train"], data["y_severity_train"])
    classifier_report = evaluate_classifiers(
        classifiers, data["X_test"], data["y_severity_test"]
    )

    best_name = max(
        classifier_report, key=lambda name: classifier_report[name]["f1_macro"]
    )
    print(f"Best classifier by macro-F1: {best_name}  ({classifier_report[best_name]})")

    print("Training binary Logistic Regression (anomaly vs normal)...")
    binary_logistic = train_binary_logistic(data["X_train"], data["y_binary_train"])
    binary_preds = binary_logistic.predict(data["X_test"])
    binary_report = {
        "accuracy": round(
            float(accuracy_score(data["y_binary_test"], binary_preds)), 4
        ),
        "f1": round(float(f1_score(data["y_binary_test"], binary_preds)), 4),
    }

    print("Training regressors (KNN Regression, Linear Regression) for risk_score...")
    regressors = train_regressors(data["X_train"], data["y_risk_train"])
    regressor_report = evaluate_regressors(
        regressors, data["X_test"], data["y_risk_test"]
    )

    print("Training K-Means clustering on full feature space...")
    kmeans = train_kmeans(data["X_all_scaled"], n_clusters=4)

    print("Saving all model artifacts...")
    data["scaler"].save(str(MODEL_DIR / "feature_scaler.joblib"))
    for name, model in classifiers.items():
        joblib.dump(model, MODEL_DIR / f"{name}.joblib")
    joblib.dump(binary_logistic, MODEL_DIR / "logistic_binary.joblib")
    for name, model in regressors.items():
        joblib.dump(
            model,
            (
                MODEL_DIR / f"{name.replace('_regressor', '')}_regressor.joblib"
                if False
                else f"{name}.joblib"
            ),
        )
    joblib.dump(kmeans, MODEL_DIR / "kmeans.joblib")

    (MODEL_DIR / "best_classifier.txt").write_text(best_name)

    benchmark_report = {
        "feature_columns": FEATURE_COLUMNS,
        "dataset_size": len(df),
        "train_size": len(data["y_severity_train"]),
        "test_size": len(data["y_severity_test"]),
        "severity_classifiers": classifier_report,
        "best_classifier": best_name,
        "binary_logistic_regression": binary_report,
        "regressors_risk_score": regressor_report,
        "kmeans_clusters": kmeans.n_clusters,
        "kmeans_inertia": round(float(kmeans.inertia_), 2),
    }
    with open(MODEL_DIR / "benchmark_report.json", "w") as f:
        json.dump(benchmark_report, f, indent=2)

    elapsed = round(time.time() - start, 2)
    print(f"\nDone in {elapsed}s. Artifacts saved to: {MODEL_DIR}")
    print(json.dumps(benchmark_report, indent=2))


if __name__ == "__main__":
    main()
