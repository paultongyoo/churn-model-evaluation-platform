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
from sklearn.metrics import make_scorer
from sklearn.metrics import recall_score
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

CUSTOMER_CHURN_DATASET = "../../../data/customer_churn_0.csv"

TARGET_COLUMN = "churn"
TARGET_PREDICTION_COLUMN = "churn_prediction"
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
    "status",
    "customer_value",
]

MODEL_NAME = "XGBoostChurnModel"
MODEL_ALIAS = "staging"
MODEL_REFERENCE_DATA_FILE_NAME = "reference_data.csv"
MODEL_REFERENCE_DATA_FOLDER = "reference_data"


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
        mlflow.set_tag("dataset", dataset_name)

        y_pred = model.predict(data_X)

        print(f"\nLogging {dataset_name} model to MLflow...")
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
        print()

        if promote_model:
            print(
                (
                    "Attaching reference data artifact to model and "
                    f"applying promotinon alias '{MODEL_ALIAS}'..."
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


def tune_model_with_cv(data_X, data_y):
    """
    Tunes the hyperparameters of the XGBoost model using Optuna with cross-validation.
    This function defines the objective function for Optuna, which uses stratified cross-validation
    and recall scoring to evaluate the model's performance.
    """

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 7),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 7),
            "gamma": trial.suggest_float("gamma", 0, 0.5),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1.0, 20.0),
            "tree_method": "hist",
            "eval_metric": "logloss",
        }

        model = XGBClassifier(**params)

        # Use stratified CV and recall scoring
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        scores = cross_val_score(
            model, data_X, data_y, scoring=make_scorer(recall_score), cv=cv, n_jobs=-1
        )

        return np.mean(scores)

    # Run the optimization
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=100)

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

    env_path = Path().resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    MLFLOW_TRACKING_URI = os.getenv(
        "MLFLOW_TRACKING_URI"
    )  # This should be set in your .env file
    print(f"MLFLOW_TRACKING_URI: {MLFLOW_TRACKING_URI}")
    if not MLFLOW_TRACKING_URI:
        raise ValueError("MLFLOW_TRACKING_URI is not set. Please check your .env file.")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("mlops-churn-pipeline")

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

    # Uncomment the line below to run hyperparameter tuning
    # clf = tune_model_with_cv(X_train, y_train)

    # Train final model with best tuned hyperparameters to-date
    # These parameters are based on the best results from previous tuning runs
    # X_test precision/recall/f1: 0.92 0.81 0.86
    best_params_to_date = {
        "n_estimators": 352,
        "learning_rate": 0.07154324375438634,
        "max_depth": 7,
        "min_child_weight": 1,
        "gamma": 0.23500630396472585,
        "subsample": 0.9472361823473306,
        "colsample_bytree": 0.6149847610884563,
        "reg_alpha": 0.029080723124195962,
        "reg_lambda": 1.9394489642211972,
    }
    clf = train_model(X_train, y_train, best_params_to_date)

    # First evaluate tuned model on training data to check for bias
    evaluate_model(clf, X_train, y_train, "X_train")

    # Next evaluate tuned model on test data to check for variance
    # Only promote model in registry if flag is set
    evaluate_model(clf, X_test, y_test, "X_test", promote_model=should_promote_model)
