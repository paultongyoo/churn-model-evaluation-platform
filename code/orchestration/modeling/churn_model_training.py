# pylint: disable=invalid-name,too-many-arguments,too-many-positional-arguments
"""
Churn Training Notebook converted to Python script.
This script trains a model to predict customer churn using XGBoost
and logs the results to MLflow.  The model is trained on a dataset of
customer churn data, and hyperparameter tuning is performed using Optuna.
The tuned model is aliased in the MLflow registry for easy retrieval
in the pipeline.
"""

import argparse
import os
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
from dotenv import load_dotenv
from mlflow import MlflowClient
from mlflow.models.signature import infer_signature
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

CUSTOMER_CHURN_DATASET = "../../../data/customer_churn_0.csv"

TARGET_COLUMN = "churn"
TARGET_PREDICTION_COLUMN = "churn_prediction"

# Tariff Plan & Age removed due to non-effect on SHAP and redundancy, respectively
#
# Per data set description, all non-Churn columns were aggregated across the 9 months
# prior to Churn column being set on month 12 (i.e. features are safe from leakage)
NUMERICAL_COLUMNS = [
    "call_failure",
    "complains",
    "subscription_length",
    "charge_amount",
    "seconds_of_use",
    "frequency_of_use",
    "frequency_of_sms",
    "distinct_called_numbers",
    "age_group",
    #'tariff_plan',
    #'age',
    "status",
    "customer_value",
]

MODEL_NAME = "XGBoostChurnModel"
MODEL_ALIAS = "staging"
MODEL_REFERENCE_DATA_FILE_NAME = "reference_data.csv"
MODEL_REFERENCE_DATA_FOLDER = "reference_data"

EXPERIMENT_NAME = "churn-model-evaluation"


def prepare_data(data_df):
    """
    Prepares the churn dataset for training by cleaning column names,
    extracting the target variable, selecting relevant features,
    and converting types.
    """
    data_to_prepare = data_df.copy()

    # Convert all column names to lowercase,
    # replace multiple spaces with a single space,
    # remove leading/trailing spaces, and replace spaces with underscores
    data_to_prepare = clean_column_names(data_to_prepare)

    # Ensure the target column is present and convert it to integer type
    if TARGET_COLUMN not in data_to_prepare.columns:
        raise ValueError(f"Target column '{TARGET_COLUMN}' not found in the dataset.")
    data_y = data_to_prepare.pop(TARGET_COLUMN).astype(int)
    data_X = data_to_prepare[NUMERICAL_COLUMNS]

    # Stops MLflow missing values warning
    data_X = data_X.astype("float64")

    return data_X, data_y


def clean_column_names(data_df):
    """
    Cleans the column names of the DataFrame by converting them to lowercase,
    replacing multiple spaces with a single space, removing leading/trailing spaces,
    and replacing spaces with underscores.
    """
    data_df.columns = (
        data_df.columns.str.lower()
        .str.replace("  ", " ")
        .str.strip()
        .str.replace(" ", "_")
    )
    return data_df


def train_model(data_X, data_y, params):
    """
    Trains an XGBoost model with the given parameters on the provided data.
    """
    model = XGBClassifier(**params, objective="binary:logistic", eval_metric="logloss")
    model.fit(data_X, data_y)
    return model


def evaluate_model(model, data_X, data_y, dataset_name, promote_model=False):
    """
    Evaluates the trained model on the provided dataset and logs the results to MLflow.
    If promote_model is True, the model training data is attached to the model version
    and promotion alias applied to allow the model to be used in downstream pipelines.
    """

    with mlflow.start_run():
        print("\nStarting MLflow Experiment Run...")
        mlflow.set_tag("dataset", dataset_name)

        y_pred = model.predict(data_X)

        print("Logging model params...")
        mlflow.log_params(model.get_params())

        print(f"Logging {dataset_name} model...")
        logged_result = mlflow.xgboost.log_model(
            model,
            name=MODEL_NAME,
            registered_model_name=MODEL_NAME,
            signature=infer_signature(data_X, y_pred),
            input_example=data_X.head(1),
            model_format="ubj",
        )

        shap_config = {
            "log_explainer": True,  # Save the explainer model
            "explainer_type": "exact",  # Use exact SHAP values (slower but precise)
            "max_error_examples": 100,  # Number of error cases to explain
            "log_model_explanations": True,  # Log individual prediction explanations
        }

        print("Executing MLflow model evaluation...")
        eval_data = data_X.copy()
        eval_data[TARGET_COLUMN] = data_y
        result = mlflow.models.evaluate(
            logged_result.model_uri,
            eval_data,
            targets=TARGET_COLUMN,
            model_type="classifier",
            evaluator_config=shap_config,
        )

        print(f"\nEvaluation Results for {dataset_name}:")
        print(f"Log Loss: {result.metrics['log_loss']:.3f}")
        print(f"Precision Score: {result.metrics['precision_score']:.3f}")
        print(f"Recall Score: {result.metrics['recall_score']:.3f}")
        print(f"Accuracy: {result.metrics['accuracy_score']:.3f}")
        print("\nSee experiment run artifacts in MLflow UI for the following plots:")
        print("* Calibration Curve")
        print("* Confusion Matrix")
        print("* Lift Curve")
        print("* Precision/Recall Curve")
        print("* Receiver Operating Characteristic (ROC) Curve")
        print("* SHAP Beeswarm")
        print("* SHAP Feature Importance")
        print("* SHAP Summary\n")

        if promote_model:
            print(
                (
                    "Attaching reference data artifact to model and "
                    f"applying promotion alias '{MODEL_ALIAS}'..."
                )
            )

            # Log the training data to MLflow and then delete it
            print("Logging reference data with model...")
            reference_data_path = MODEL_REFERENCE_DATA_FILE_NAME
            reference_df = data_X.copy()
            reference_df[TARGET_COLUMN] = data_y.to_numpy(dtype=int)
            reference_df[TARGET_PREDICTION_COLUMN] = y_pred.astype(int)
            reference_df.to_csv(reference_data_path, index=False)
            mlflow.log_artifact(
                reference_data_path, artifact_path=MODEL_REFERENCE_DATA_FOLDER
            )
            os.remove(reference_data_path)

            # Set the model alias to "staging" for easy retrieval in the pipeline
            print("Setting model alias to 'staging' in MLflow registry...\n")
            MlflowClient().set_registered_model_alias(
                MODEL_NAME, MODEL_ALIAS, logged_result.registered_model_version
            )
        else:
            print("Skipping promotion of model to MLflow registry.\n")


def tune_model_with_cv(data_X, data_y, optuna_db_conn_url):
    """
    Tunes the hyperparameters of the XGBoost model using Optuna with cross-validation.
    This function defines the objective function for Optuna, which uses stratified cross-validation
    and f1 scoring to evaluate the model's performance.

    Original wide parameter search space:
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 7),
        "gamma": trial.suggest_float("gamma", 1e-8, 5.0, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.5, 1.0),
        "colsample_bynode": trial.suggest_float("colsample_bynode", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 20.0, log=True),
        "max_delta_step": trial.suggest_int("max_delta_step", 0, 12),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 0.5, 1.0),
        "tree_method": "hist",
        "eval_metric": "logloss"
    }
    The search space has been narrowed down to the most impactful parameters
    based on previous tuning runs and feature importance analysis.

    """

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
            "learning_rate": trial.suggest_float("learning_rate", 0.001, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma": trial.suggest_float("gamma", 1e-8, 5.0, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.5, 1.0),
            "colsample_bynode": trial.suggest_float("colsample_bynode", 0.5, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 20.0, log=True),
            "max_delta_step": trial.suggest_int("max_delta_step", 0, 10),
            "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 20.0),
            "random_state": 42,  # fixed for reproducibility
        }

        model = XGBClassifier(
            **params,
            eval_metric="logloss",
            tree_method="hist",
            early_stopping_rounds=20,
        )

        scores = []
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        for train_idx, val_idx in cv.split(data_X, data_y):
            cv_X_train, X_val = data_X.iloc[train_idx], data_X.iloc[val_idx]
            cv_y_train, y_val = data_y.iloc[train_idx], data_y.iloc[val_idx]

            model.fit(cv_X_train, cv_y_train, eval_set=[(X_val, y_val)], verbose=False)

            calibrated_model = CalibratedClassifierCV(
                FrozenEstimator(model), method="sigmoid"
            )
            calibrated_model.fit(cv_X_train, cv_y_train)

            y_probs = calibrated_model.predict_proba(X_val)[:, 1]

            threshold = trial.suggest_float("threshold", 0.1, 0.9)
            y_preds = (y_probs >= threshold).astype(int)

            scores.append(f1_score(y_val, y_preds))

        return np.mean(scores)

    # Run the optimization and save trials to local Sqlite3 DB
    # (Use optuna-dashboard to analyze)
    study = optuna.create_study(
        study_name=EXPERIMENT_NAME,
        load_if_exists=True,
        direction="maximize",
        storage=optuna_db_conn_url,
    )
    study.optimize(objective, n_trials=50)

    print(f"\nBest F1 Score: {study.best_value}")

    print("\nBest hyperparameters found:")
    for key, value in study.best_params.items():
        print(f'"{key}": {value},')

    # Train final model with best hyperparameters on full dataset
    model = train_model(data_X, data_y, study.best_params)

    return model


if __name__ == "__main__":

    # Look for parameter to decide whether to deploy model to registry
    should_promote_model = True
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--nopromote", action="store_true", help="If set, skip promotion step"
    )
    args = parser.parse_args()
    if args.nopromote is True:
        print("'nopromote' arg passed - Will skip promoting model in MLflow registry.")
        should_promote_model = False

    df = pd.read_csv(CUSTOMER_CHURN_DATASET)

    # Load environment variables from .env file
    env_path = Path().resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    MLFLOW_TRACKING_URI = os.getenv(
        "MLFLOW_TRACKING_URI"
    )  # This should be set in your .env file
    print(f"MLFLOW_TRACKING_URI: {MLFLOW_TRACKING_URI}")
    if not MLFLOW_TRACKING_URI:
        raise ValueError("MLFLOW_TRACKING_URI is not set. Please check your .env file.")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    X, y = prepare_data(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # base_params = {
    #     "n_estimators": 100,
    #     "max_depth": 3,
    #     "learning_rate": 0.1,
    #     "random_state": 42,
    # }
    # clf = train_model(X_train, y_train, base_params)

    # Uncomment the line below and comment out best_params_to_date
    # to run hyperparameter tuning
    OPTUNA_DB_CONN_URL = os.getenv(
        "OPTUNA_DB_CONN_URL"
    )  # This should be set in your .env file
    print(f"OPTUNA_DB_CONN_URL: {OPTUNA_DB_CONN_URL}")
    clf = tune_model_with_cv(X_train, y_train, OPTUNA_DB_CONN_URL)

    # Train final model with best tuned hyperparameters to-date
    # These parameters are based on the best results from previous tuning runs
    # X_test precision/recall/f1: 0.921 0.833 0.875
    # best_params_to_date = {
    # "n_estimators": 374,
    # "learning_rate": 0.06277193144197914,
    # "max_depth": 3,
    # "min_child_weight": 1,
    # "gamma": 0.0007237920056163315,
    # "subsample": 0.8280956289121524,
    # "colsample_bytree": 0.7587172587106015,
    # "reg_alpha": 0.00013524609914364934,
    # "reg_lambda": 0.002246828534497257,
    # "max_delta_step": 4,
    # }
    # clf = train_model(X_train, y_train, best_params_to_date)

    # First evaluate tuned model on training data to check for bias
    evaluate_model(clf, X_train, y_train, "X_train")

    # Next evaluate tuned model on test data to check for variance
    # Only promote model in registry if flag is set
    evaluate_model(clf, X_test, y_test, "X_test", promote_model=should_promote_model)
