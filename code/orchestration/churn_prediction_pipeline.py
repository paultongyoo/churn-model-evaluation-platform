# pylint: disable=invalid-name,broad-exception-caught,fixme,too-many-arguments,too-many-positional-arguments,unused-import
"""
This module houses the Prefect flow for the churn prediction pipeline.
It orchestrates the entire process from data ingestion to model evaluation.
It also includes task(s) to retrain the model if the model's churn prediction
performance does not meet specified threshold.
"""

import os
import re
import sys
from datetime import datetime
from datetime import timezone

import boto3
import mlflow
import pandas as pd
from evidently import BinaryClassification
from evidently import DataDefinition
from evidently import Dataset
from evidently import Report
from evidently.errors import EvidentlyError
from evidently.presets import ClassificationPreset
from evidently.presets import DataDriftPreset
from evidently.ui.workspace import RemoteWorkspace
from mlflow.artifacts import download_artifacts
from modeling.churn_model_training import MODEL_ALIAS
from modeling.churn_model_training import MODEL_NAME
from modeling.churn_model_training import MODEL_REFERENCE_DATA_FILE_NAME
from modeling.churn_model_training import MODEL_REFERENCE_DATA_FOLDER
from modeling.churn_model_training import NUMERICAL_COLUMNS
from modeling.churn_model_training import TARGET_COLUMN
from modeling.churn_model_training import TARGET_PREDICTION_COLUMN
from modeling.churn_model_training import clean_column_names
from modeling.churn_model_training import prepare_data
from prefect import flow
from prefect import get_run_logger
from prefect import task
from prefect.blocks.system import Secret
from prefect.variables import Variable
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

SECRET_KEY_AWS_REGION = "aws-region"

FOLDER_INPUT = "data/input"
FOLDER_PROCESSING = "data/processing"
FOLDER_PROCESSED = "data/processed"
FOLDER_ERRORED = "data/errored"
FOLDER_LOGS = "data/logs"

DATABASE_NAME = "metrics_db"
SECRET_KEY_DB_USERNAME = "db-username"
SECRET_KEY_DB_PASSWORD = "db-password"
SECRET_KEY_DB_ENDPOINT = "db-endpoint"
TABLE_NAME_DRIFT_METRICS = "drift_metrics"

EVIDENTLY_PROJECT_NAME = "mlops-churn-pipeline"
EVIDENTLY_PROJECT_ID_BLOCK_NAME = "evidently-project-id"
SECRET_KEY_EVIDENTLY_UI_URL = "evidently-url"

SECRET_KEY_GRAFANA_ADMIN_USER = "grafana-admin-user"

SECRET_KEY_CHURN_MODEL_ALERTS_TOPIC_ARN = "churn-model-alerts-topic-arn"

# Define the Data Drift Report model
Base = declarative_base()


class DriftMetric(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = TABLE_NAME_DRIFT_METRICS

    id = Column(Integer, primary_key=True)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


@task(retries=3, retry_delay_seconds=5)
def fetch_model(model_name: str, alias: str):
    """
    Fetch the model from MLflow registry.
    Args:
        model_name (str): The name of the model in MLflow.
        alias (str): The alias of the model version to fetch.
    Returns:
        mlflow.pyfunc.PyFuncModel: The fetched model.
    """
    logger = get_run_logger()
    MLFLOW_TRACKING_URI = Secret.load("mlflow-tracking-uri").get()
    logger.info("Setting MLflow tracking URI: %s", MLFLOW_TRACKING_URI)
    logger.info("Fetching model '%s' with alias '%s'", model_name, alias)

    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        model = mlflow.pyfunc.load_model(model_uri=f"models:/{model_name}@{alias}")
        logger.info("Model '%s' fetched successfully: %s", model_name, model)
        return model
    except Exception as e:
        err_msg = (
            f"Failed to fetch model '{model_name}' with alias '{alias}' "
            f"- Does it exist in the MLFlow registry?': {e}"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e


@task
def validate_file_input(
    bucket: str, key: str, input_example: pd.DataFrame, endpoint_url=None
) -> bool:
    """
    Validate the S3 key to ensure it points to a valid input file.
    Args:
        s3_key (str): The S3 key of the file to validate.
        input_example (pd.DataFrame): Example DataFrame structure for validation.
    Returns:
        bool: True if the file is valid, False otherwise.
        pd.DataFrame: The DataFrame read from the file if valid, None if invalid.
        str: Error message if validation fails, None if successful.
    """
    logger = get_run_logger()
    s3_client = create_s3_client(endpoint_url)

    logger.info("Validating S3 key: %s", key)

    if not key.endswith(".csv"):
        err_msg = f"Invalid file type for {key}. Expected a CSV file."
        logger.error(err_msg)
        return False, None, err_msg

    # Read the file from S3
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = pd.read_csv(response["Body"])
    except Exception as e:
        err_msg = f"Error reading CSV file {key}: {e}"
        logger.error(err_msg)
        return False, None, err_msg

    data = clean_column_names(data)
    logger.info("Data columns: %s", data.columns.tolist())

    # Validate against the input example
    if not all(col in data.columns for col in input_example.columns):
        err_msg = (
            f"Input file {key} does not match expected structure. "
            f"Expected columns: {input_example.columns.tolist()}"
        )
        logger.error(err_msg)
        return False, None, err_msg

    return True, data, None


@task
def prepare_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepare the labeled churn dataset for model inference.  Reuses the
    prepare_data function from the churn_training module.
    Args:
        df (pd.DataFrame): The input DataFrame containing churn data.
    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: The feature DataFrame (X).
            - pd.Series: The target Series (y).
    """
    logger = get_run_logger()
    logger.info("Preparing churn dataset...")

    return prepare_data(df)


@task
def generate_predictions(X: pd.DataFrame, model) -> pd.DataFrame:
    """
    Generates churn predictions using the provided model.
    Args:
        X (pd.DataFrame): The feature DataFrame.
        model (mlflow.pyfunc.PyFuncModel): The MLflow model to use for predictions.
    Returns:
        pd.DataFrame: The DataFrame with predictions appended as a new column.
    """
    logger = get_run_logger()
    logger.info("Generating predictions...")

    # Make predictions
    y_pred = model.predict(X)

    logger.info("Predictions generated successfully.")
    return y_pred


@task(retries=3, retry_delay_seconds=5)
def log_predictions(
    X: pd.DataFrame,
    y_actual: pd.Series,
    y_pred: pd.Series,
    bucket: str,
    key: str,
) -> str:
    """
    Logs the predictions to S3 and returns the new S3 key.
    Args:
        X (pd.DataFrame): The feature DataFrame.
        y_actual (pd.Series): The actual labels.
        y_pred (pd.Series): The predicted labels.
        y_pred_proba (pd.Series): The predicted probabilities.
        model (mlflow.pyfunc.PyFuncModel): The MLflow model used for predictions.
        bucket (str): The S3 bucket to log the predictions.
        key (str): The S3 key for the input data.
    Returns:
        str: The new S3 key where the predictions are logged.
        predictions_df (pd.DataFrame): The DataFrame containing predictions.
    """
    logger = get_run_logger()
    s3_client = create_s3_client()

    logger.info("Logging predictions to S3...")

    # Create final DataFrame with predictions
    #
    # Ensure TARGET_COLUMN and TARGET_PREDICTION_COLUMN are integers
    # This is necessary for compatibility with Evidently
    predictions_df = X.copy()
    predictions_df[TARGET_COLUMN] = y_actual.to_numpy(dtype=int)
    predictions_df[TARGET_PREDICTION_COLUMN] = y_pred.astype(int)

    # Define the output file name by combining original key and model details
    filename = os.path.basename(key)
    filename = filename.replace(".csv", "")
    model_version_obj = mlflow.tracking.MlflowClient().get_model_version_by_alias(
        name=MODEL_NAME, alias=MODEL_ALIAS
    )
    model_version = model_version_obj.version
    output_filename = f"{filename}_predictions_{MODEL_NAME}_v{model_version}.csv"
    logger.info("Output filename for predictions: %s", output_filename)
    output_key = f"{FOLDER_PROCESSING}/{output_filename}"

    # Replace the original file with predictions
    logger.info("Uploading predictions to S3: %s://%s", bucket, output_key)
    csv_buffer = predictions_df.to_csv(index=False)
    s3_client.put_object(Bucket=bucket, Key=output_key, Body=csv_buffer)
    s3_client.delete_object(Bucket=bucket, Key=key)

    logger.info("Predictions logged successfully to %s://%s", bucket, output_key)

    return output_key, predictions_df


@task(retries=3, retry_delay_seconds=5)
def generate_data_report(
    prediction_df: pd.DataFrame,
):  # pylint: disable=too-many-locals
    """
    Generate an Evidently.ai data and prediction drift report.
    Args:
        inference_df (pd.DataFrame): The input DataFrame containing churn data.
        prediction_df (pd.DataFrame): The DataFrame containing predictions.
    Returns:
        Evidently Report Run: The drift report run.
        run_add_results: The results of adding the report to Evidently UI (contains report URL)
    """
    logger = get_run_logger()
    logger.info("Generating data report...")

    # Load reference data for drift comparison
    try:
        model_version_obj = mlflow.tracking.MlflowClient().get_model_version_by_alias(
            name=MODEL_NAME, alias=MODEL_ALIAS
        )
        run_id = model_version_obj.run_id
        reference_data_local_path = download_artifacts(
            run_id=run_id,
            artifact_path=f"{MODEL_REFERENCE_DATA_FOLDER}/{MODEL_REFERENCE_DATA_FILE_NAME}",
        )
        reference_df = pd.read_csv(reference_data_local_path)
        logger.info(
            "Reference data loaded successfully from %s - Shape: %s",
            reference_data_local_path,
            reference_df.shape,
        )
    except Exception as e:
        err_msg = (
            f"Failed to load artifact data from '{MODEL_REFERENCE_DATA_FOLDER}/"
            f"{MODEL_REFERENCE_DATA_FILE_NAME}' - Does it exist in the MLFlow registry?': {e}"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e

    # Define Evidently DataDefinition and Training and Inference datasets
    data_definition = DataDefinition(
        classification=[
            BinaryClassification(
                target=TARGET_COLUMN, prediction_labels=TARGET_PREDICTION_COLUMN
            )
        ],
        numerical_columns=NUMERICAL_COLUMNS,
    )

    # Ensure Target columns are integers for compatibility with Evidently
    reference_df[TARGET_COLUMN] = reference_df[TARGET_COLUMN].astype(int)
    reference_df[TARGET_PREDICTION_COLUMN] = reference_df[
        TARGET_PREDICTION_COLUMN
    ].astype(int)

    reference_dataset = Dataset.from_pandas(
        reference_df, data_definition=data_definition
    )
    predictions_dataset = Dataset.from_pandas(
        prediction_df, data_definition=data_definition
    )

    data_report = Report([DataDriftPreset(), ClassificationPreset()])

    data_report_run = data_report.run(
        reference_data=reference_dataset, current_data=predictions_dataset
    )

    # Add report to Evidently UI
    evidently_ui_url = Secret.load(SECRET_KEY_EVIDENTLY_UI_URL).get()
    logger.info("Evidently UI URL: %s", evidently_ui_url)
    workspace = RemoteWorkspace(evidently_ui_url)
    evidently_project_id = get_evidently_project_id()
    if evidently_project_id:
        try:
            project = workspace.get_project(evidently_project_id)
        except EvidentlyError:
            logger.error(
                "Failed to get Evidently project with ID %s, creating a new one...",
                evidently_project_id,
            )
            project = workspace.create_project(EVIDENTLY_PROJECT_NAME)
            save_evidently_project_id(project.id)
    else:
        logger.info("Creating new Evidently project: %s", EVIDENTLY_PROJECT_NAME)
        project = workspace.create_project(EVIDENTLY_PROJECT_NAME)
        save_evidently_project_id(project.id)
    run_add_results = workspace.add_run(project.id, data_report_run)

    logger.info("Data report generated successfully.")
    logger.info("View the report at: %s", evidently_ui_url)
    logger.info(
        "Data Drift and Classification evaluation results: %s", data_report_run.dict()
    )

    return data_report_run, run_add_results


@task(retries=3, retry_delay_seconds=5)
def save_report_to_database(report_run: Report) -> None:
    """
    Save the Evidently report run to the database.
    Args:
        report_run (Report): The Evidently report run to save.
    Returns:
        session: SQLAlchemy session for database interaction.
    Raises:
        RuntimeError: If there is an error saving the report to the database.
    """
    logger = get_run_logger()
    logger.info("Saving Evidently report run to database...")
    try:
        # Connect to the database
        secrets = load_database_secrets()
        session = connect_to_database(secrets)
        logger.info("Connected to database successfully.")

        # Parse the drift metrics from the report run
        drift_report = report_run.dict()
        parse_and_save_drift_metrics(drift_report, session)

        # Grant Grafana Admin User access to the drift metrics table
        grant_grafana_access_to_drift_table(session)

        logger.info("Saved %s drift metrics to DB.", len(drift_report["metrics"]))
    except Exception as e:
        session.rollback()
        err_msg = f"Failed to save Evidently report run to database: {e}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e
    finally:
        session.close()
        logger.info("Database session closed.")


@task
def assess_data_drift(drift_report: dict):
    """
    Assess whether the majority of the dataset's columns have drifted and
    returns the .
    Args:
        drift_report (dict): The Evidently drift report dictionary.
    Returns:
        tuple: A tuple containing:
            - bool: True if data drift exceeds threshold, False otherwise.
            - int: Number of columns that drifted.
            - list: List of drifted column names.
    """
    logger = get_run_logger()
    is_data_drifted = False
    num_cols_drifted = 0
    drifted_columns = []
    for metric in drift_report["metrics"]:
        if metric.get("metric_id").startswith("DriftedColumnsCount"):
            value = metric.get("value")
            is_data_drifted = float(value["share"]) > 0.5
            num_cols_drifted = int(value["count"])
        elif metric.get("metric_id").startswith("ValueDrift"):
            value = metric.get("value")
            if float(value) < 0.05:
                column_name = (
                    metric.get("metric_id").split("(")[1].split("=")[1].strip(")")
                )
                drifted_columns.append(column_name)

    logger.info(
        "Data drift assessment: is_data_drifted=%s, num_cols_drifted=%d, drifted_columns=%s",
        is_data_drifted,
        num_cols_drifted,
        drifted_columns,
    )
    return is_data_drifted, num_cols_drifted, drifted_columns


@task
def assess_prediction_scores(drift_report: dict, score_threshold=0.70):
    """
    Assess whether the prediction scores (F1, Precision, Recall, Accuracy)
    are below a specified threshold.
    Args:
        drift_report (dict): The Evidently drift report dictionary.
        score_threshold (float): The threshold below which scores are considered low.
    Returns:
        tuple: A tuple containing:
            - bool: True if any scores are below the threshold, False otherwise.
            - int: Number of scores below the threshold.
            - list: List of column names with scores below the threshold.
    """
    logger = get_run_logger()
    any_scores_below_threshold = False
    num_scores_below_threshold = 0
    scores_below_threshold = []
    score_names = [
        "F1Score",
        "Precision",
        "Recall",
        "Accuracy",
    ]
    for score in score_names:
        for metric in drift_report["metrics"]:
            if metric.get("metric_id").startswith(f"{score}("):
                logger.info(
                    "Checking %s with value %s",
                    metric.get("metric_id"),
                    metric.get("value"),
                )
                value = metric.get("value")
                if float(value) < score_threshold:
                    any_scores_below_threshold = True
                    num_scores_below_threshold += 1
                    scores_below_threshold.append((score, value))

    logger.info(
        (
            "Scores assessment: any_scores_below_threshold=%s, "
            "num_scores_below_threshold=%d, scores_below_threshold=%s"
        ),
        any_scores_below_threshold,
        num_scores_below_threshold,
        scores_below_threshold,
    )
    return (
        any_scores_below_threshold,
        num_scores_below_threshold,
        scores_below_threshold,
    )


def parse_and_save_drift_metrics(drift_report: dict, session) -> list[dict]:
    """
    Parse the Evidently drift report to extract drift metrics.
    Args:
        drift_report (dict): The Evidently drift report dictionary.
    Returns:
        list[dict]: A list of dictionaries containing drift metrics.
    """
    drift_metrics = []

    for metric in drift_report["metrics"]:
        metric_id = metric.get("metric_id")
        simple_metric_name = simplify_metric_name(metric_id)
        value = metric.get("value")

        # Case 1: scalar value (float or int)
        if isinstance(value, (float, int)):
            drift_metrics.append(
                DriftMetric(
                    metric_name=simple_metric_name,
                    value=float(value),
                    created_at=datetime.utcnow(),
                )
            )

        # Case 2: dictionary value (e.g., per-label metrics)
        elif isinstance(value, dict):
            for key, subvalue in value.items():
                if isinstance(subvalue, (float, int)):
                    drift_metrics.append(
                        DriftMetric(
                            metric_name=f"{simple_metric_name}[{key}]",
                            value=float(subvalue),
                            created_at=datetime.now(timezone.utc),
                        )
                    )

        # Optionally log or raise on unexpected formats
        else:
            print(f"Skipping unsupported metric: {metric_id} with value: {value}")

    session.add_all(drift_metrics)
    session.commit()


def simplify_metric_name(metric_id: str) -> str:
    """
    Converts a metric_id string to a simplified, lowercase name.

    Examples:
    - "Accuracy()" → "accuracy"
    - "F1Score(conf_matrix=True)" → "f1score"
    - "ValueDrift(column=age_group)" → "valuedrift_age_group"
    - "F1ByLabel()" with label="0" → "f1bylabel_0"
    """

    # Match function name (e.g., "F1Score", "Accuracy")
    match = re.match(r"([a-zA-Z0-9_]+)(\((.*?)\))?", metric_id)
    base = match.group(1).lower() if match else metric_id.lower()

    # Try to extract column from ValueDrift(column=foo)
    column_match = re.search(r"column=([\w\d_]+)", metric_id)
    if column_match:
        base += f"_{column_match.group(1).lower()}"

    return base


def get_evidently_project_id():
    """
    Get the Evidently project ID for the current project.
    Returns:
        str: The Evidently project ID or None if it doesn't exist.
    """
    try:
        evidently_project_id = Variable.get(EVIDENTLY_PROJECT_ID_BLOCK_NAME)
        print(f"✅ Loaded existing Evidently Project ID: {evidently_project_id}")
        return evidently_project_id
    except ValueError:
        # Block doesn't exist yet
        print("No existing Evidently Project ID, returning None")
        return None


def save_evidently_project_id(project_id: str):
    """
    Save the Evidently project ID to a Prefect block for future reference.
    Args:
        project_id (str): The Evidently project ID to save.
    """
    print(f"Saving Evidently Project ID: {project_id}")
    Variable.set(EVIDENTLY_PROJECT_ID_BLOCK_NAME, str(project_id), overwrite=True)
    print(f"✅ Saved Evidently Project ID: {project_id}")


def load_database_secrets():
    """
    Load database secrets from Prefect Secrets.
    Returns:
        dict: A dictionary containing the database credentials.
    """
    logger = get_run_logger()
    logger.info("Loading database secrets...")

    try:
        db_username = Secret.load(SECRET_KEY_DB_USERNAME).get()
        db_password = Secret.load(SECRET_KEY_DB_PASSWORD).get()
        db_endpoint = Secret.load(SECRET_KEY_DB_ENDPOINT).get()
        logger.info("Database secrets loaded successfully.")
        return {
            "username": db_username,
            "password": db_password,
            "endpoint": db_endpoint,
            "database": DATABASE_NAME,
        }
    except Exception as e:
        err_msg = f"Failed to load database secrets: {e}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from e


@task(retries=3, retry_delay_seconds=5)
def connect_to_database(secrets: dict):
    """
    Connect to the database using the provided secrets.
    Args:
        secrets (dict): A dictionary containing the database credentials.
    Returns:
        session: SQLAlchemy session object for database interaction.
    """
    logger = get_run_logger()
    logger.info("Connecting to the database...")

    logger.info(
        "Connecting to database %s at %s with user %s",
        secrets["database"],
        secrets["endpoint"],
        secrets["username"],
    )

    DATABASE_URL = (
        f"postgresql+psycopg2://{secrets['username']}:{secrets['password']}"
        f"@{secrets['endpoint']}/{secrets['database']}"
    )

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    Base.metadata.create_all(engine)

    logger.info("Database connection established successfully.")
    return session


@task(retries=3, retry_delay_seconds=5)
def move_to_folder(bucket: str, key: str, folder: str, message: str = ""):
    """
    Move the S3 object to a specified folder.
    """
    logger = get_run_logger()
    s3_client = create_s3_client()

    # Move the file to the specified folder
    filename = key.split("/")[-1]
    new_key = f"{folder}/{filename}"
    logger.info("Attempting to move %s://%s to %s...", bucket, key, new_key)
    s3_client.copy_object(
        Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=new_key
    )
    s3_client.delete_object(Bucket=bucket, Key=key)
    logger.info("Moved %s to %s", key, new_key)

    # Log the move
    log_msg = (
        f"{datetime.now(timezone.utc).isoformat()} Moved {key} → {new_key}. {message}\n"
    )
    logger.info(log_msg.strip())

    # Define log key
    log_key = f"{FOLDER_LOGS}/{filename}.log"

    # Append log to S3 (create if doesn't exist)
    try:
        existing = (
            s3_client.get_object(Bucket=bucket, Key=log_key)["Body"].read().decode()
        )
    except s3_client.exceptions.NoSuchKey:
        existing = ""

    updated_log = existing + log_msg
    s3_client.put_object(Bucket=bucket, Key=log_key, Body=updated_log.encode())

    return new_key


@task
def send_drift_alert_email(
    latest_s3_key: str, num_drifted_cols, drifted_col_names, run_add_results
):
    """
    Send an alert email if a significant number of columns have drifted.
    Args:
        latest_s3_key (str): The S3 key of the latest processed file.
        num_drifted_cols (int): The number of columns that have drifted.
        drifted_col_names (list): List of names of the drifted columns.
        run_add_results: The results of adding the report to Evidently UI (contains report URL)
    """
    logger = get_run_logger()
    churn_model_alerts_topic_arn = Secret.load(
        SECRET_KEY_CHURN_MODEL_ALERTS_TOPIC_ARN
    ).get()

    alert_message = (
        f"Majority of columns drifted from reference data in the latest run.\n\n"
        f"Filename: {os.path.basename(latest_s3_key)}.\n\n"
        f"{num_drifted_cols} Column(s) Drifted:\n"
    )
    for col in drifted_col_names:
        alert_message += f"- {col}\n"

    email_subject = f"Customer Data Drift Alert: {num_drifted_cols} Column(s) Drifted"
    alert_message += (
        f"\nPlease review the Evidently report at {run_add_results.url}"
        f" and take necessary actions."
    )
    logger.info("Drift detected, sending alert: %s", alert_message)
    send_sns_alert(email_subject, alert_message, churn_model_alerts_topic_arn)

    logger.info(
        "Alert sent to SNS topic %s with subject '%s'",
        churn_model_alerts_topic_arn,
        email_subject,
    )


@task
def send_scores_alert_email(
    latest_s3_key: str, num_scores_below_threshold: int, scores_below_threshold: list
):
    """
    Send an alert email if any prediction scores are below the threshold.
    Args:
        latest_s3_key (str): The S3 key of the latest processed file.
        num_scores_below_threshold (int): The number of scores below the threshold.
        scores_below_threshold (list): List of names of the columns with low scores.
    """
    logger = get_run_logger()
    churn_model_alerts_topic_arn = Secret.load(
        SECRET_KEY_CHURN_MODEL_ALERTS_TOPIC_ARN
    ).get()

    alert_message = (
        f"Predictions scored below threshold in the latest run.\n\n"
        f"Filename: {os.path.basename(latest_s3_key)}.\n\n"
        f"{num_scores_below_threshold} Score(s) Below Threshold:\n"
    )
    for score, value in scores_below_threshold:
        alert_message += f"- {score}: {value:.3f}\n"

    email_subject = (
        f"Customer Prediction Scores Alert: {num_scores_below_threshold} "
        "Scores Below Threshold"
    )
    logger.info("Scores below threshold detected, sending alert: %s", alert_message)
    send_sns_alert(email_subject, alert_message, churn_model_alerts_topic_arn)


@task(retries=3, retry_delay_seconds=5)
def send_sns_alert(subject: str, message: str, topic_arn: str):
    """
    Send an alert message to an SNS topic.
    Args:
        message (str): The message to send.
        topic_arn (str): The ARN of the SNS topic to publish to.
    Returns:
        dict: The response from the SNS publish operation.
    """
    sns = boto3.client("sns")
    response = sns.publish(TopicArn=topic_arn, Message=message, Subject=f"🚨 {subject}")
    return response


def create_s3_client(endpoint_url: str = None):
    """
    Create an S3 client using the AWS region from Prefect secrets.
    Args:
        endpoint_url (str): Optional S3 endpoint URL to use.  Used for local testing.
    Returns:
        boto3.client: The S3 client.
    """
    AWS_REGION = Secret.load(SECRET_KEY_AWS_REGION).get()
    return boto3.client("s3", region_name=AWS_REGION, endpoint_url=endpoint_url)


def grant_grafana_access_to_drift_table(session: Session):
    """
    Grant Grafana Admin User access to the drift metrics table.
    Args:
        session (Session): SQLAlchemy session for database interaction.
    Raises:
        RuntimeError: If there is an error granting access to the Grafana Admin User.
    """
    grafana_admin_user = Secret.load(SECRET_KEY_GRAFANA_ADMIN_USER).get()
    logger = get_run_logger()
    logger.info(
        "Granting Grafana Admin User '%s' access to the drift metrics table...",
        grafana_admin_user,
    )
    try:
        grant_sql = (
            f"GRANT SELECT ON TABLE {TABLE_NAME_DRIFT_METRICS} TO {grafana_admin_user};"
        )
        session.execute(text(grant_sql))
        session.commit()
        logger.info("Access granted successfully.")
    except Exception as e:
        err_msg = (
            f"Failed to grant access to Grafana Admin User '{grafana_admin_user}' "
            f"for table {TABLE_NAME_DRIFT_METRICS}: {e}"
        )
        logger.error(err_msg)
        session.rollback()
        raise RuntimeError(err_msg) from e


@flow(name="churn_prediction_pipeline", log_prints=True)
def churn_prediction_pipeline(bucket: str, key: str):  # pylint: disable=too-many-locals
    """
    A Prefect flow that orchestrates the churn prediction pipeline.
    It includes tasks for data ingestion, preprocessing, model training,
    evaluation, and potentially retraining the model based on performance.
    """
    latest_s3_key = key  # Initialize with the original key for exception handling
    s3_client = create_s3_client()

    try:
        logger = get_run_logger()
        logger.info("Starting the Churn Prediction Pipeline...")
        logger.info("Processing data from bucket: %s, key: %s", bucket, key)

        # Validate bucket and key existence
        if not s3_client.head_bucket(Bucket=bucket):
            logger.error("Bucket %s does not exist.", bucket)
            return
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
        except s3_client.exceptions.ClientError as e:
            logger.error(
                "Object %s does not exist in bucket %s. Error: %s", key, bucket, e
            )
            return

        # Fetch the model from MLflow
        model = fetch_model(MODEL_NAME, MODEL_ALIAS)
        input_example = pd.DataFrame(model.input_example)
        logger.info("Model input example columns: %s", input_example.columns.tolist())

        # Move file to processing folder
        latest_s3_key = move_to_folder(bucket, key, FOLDER_PROCESSING)

        # Validate the input file, using the model input example
        success, inference_df, err_msg = validate_file_input(
            bucket, latest_s3_key, input_example
        )
        if not success:
            move_to_folder(bucket, latest_s3_key, FOLDER_ERRORED, message=err_msg)
            return

        X, y = prepare_dataset(inference_df)

        y_pred = generate_predictions(X, model)

        latest_s3_key, predictions_df = log_predictions(
            X, y, y_pred, bucket, latest_s3_key
        )

        drift_report_run, run_add_results = generate_data_report(predictions_df)

        save_report_to_database(drift_report_run)

        is_data_drifted, num_drifted_cols, drifted_col_names = assess_data_drift(
            drift_report_run.dict()
        )
        if is_data_drifted:
            send_drift_alert_email(
                latest_s3_key, num_drifted_cols, drifted_col_names, run_add_results
            )
        else:
            logger.info("No drift detected in the latest run.")

        # Assess prediction scores
        score_threshold = 0.70  # Define the threshold for low scores
        (
            any_scores_below_threshold,
            num_scores_below_threshold,
            scores_below_threshold,
        ) = assess_prediction_scores(drift_report_run.dict(), score_threshold)
        if any_scores_below_threshold:
            send_scores_alert_email(
                latest_s3_key, num_scores_below_threshold, scores_below_threshold
            )
            logger.warning(
                "Some prediction scores are below the threshold of %.2f. "
                "Consider retraining the model.",
                score_threshold,
            )
            # TODO: Retrain the model if needed
        else:
            logger.info("All prediction scores are above the threshold.")

        logger.info("Churn prediction pipeline completed successfully.")
        move_to_folder(bucket, latest_s3_key, FOLDER_PROCESSED)

    except Exception as e:
        err_msg = f"An unexpected error occurred in the churn prediction pipeline: {e}"
        logger.error(err_msg)
        move_to_folder(bucket, latest_s3_key, FOLDER_ERRORED, message=err_msg)
        return


# This allows the flow to be run directly for testing purposes
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python churn_prediction_pipeline.py <bucket> <key>")
        sys.exit(1)
    param1 = sys.argv[1]
    param2 = sys.argv[2]
    print(f"Running churn prediction pipeline with bucket: {param1}, key: {param2}")
    churn_prediction_pipeline(bucket=param1, key=param2)
