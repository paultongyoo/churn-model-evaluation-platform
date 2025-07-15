# pylint: disable=invalid-name,broad-exception-caught
"""
This module houses the Prefect flow for the churn prediction pipeline.
It orchestrates the entire process from data ingestion to model evaluation.
It also includes task(s) to retrain the model if the model's churn prediction
performance does not meet specified threshold.
"""

import sys
from datetime import datetime
from datetime import timezone

import boto3
import mlflow.pyfunc
import pandas as pd
from prefect import flow
from prefect import get_run_logger
from prefect import task

AWS_REGION = "us-east-2"
s3_client = boto3.client("s3", region_name=AWS_REGION)

MODEL_NAME = "XGBoostChurnModel"
MODEL_ALIAS = "staging"

FOLDER_INPUT = "data/input"
FOLDER_PROCESSING = "data/processing"
FOLDER_PROCESSED = "data/processed"
FOLDER_ERRORED = "data/errored"
FOLDER_LOGS = "data/logs"


@task
def fetch_model(model_name: str, alias: str):
    """
    Fetch the model from MLflow registry.
    Args:
        model_name (str): The name of the model in MLflow.
        alias (str): The alias of the model version to fetch.
    Returns:
        mlflow.pyfunc.PyFuncModel: The loaded MLflow model.
    """
    logger = get_run_logger()
    logger.info("Fetching model '%s' with alias '%s'", model_name, alias)

    model = mlflow.pyfunc.load_model(model_uri=f"models:/{model_name}@{alias}")
    logger.info("Model '%s' fetched successfully: %s", model_name, model)
    return model


@task
def validate_file_input(bucket: str, key: str, input_example: pd.DataFrame) -> bool:
    """
    Validate the S3 key to ensure it points to a valid input file.
    Args:
        s3_key (str): The S3 key of the file to validate.
        input_example (pd.DataFrame): Example DataFrame structure for validation.
    Returns:
        bool: True if the file is valid, False otherwise.
    """
    logger = get_run_logger()
    logger.info("Validating S3 key: %s", key)

    if not key.endswith(".csv"):
        err_msg = f"Invalid file type for {key}. Expected a CSV file."
        logger.error(err_msg)
        return False, err_msg

    # Read the file from S3
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = pd.read_csv(response["Body"])
    except Exception as e:
        err_msg = f"Error reading CSV file {key}: {e}"
        logger.error(err_msg)
        return False, err_msg

    data.columns = data.columns.str.strip()  # Strip whitespace from column names
    logger.info("Data columns: %s", data.columns.tolist())

    # Validate against the input example
    if not all(col in data.columns for col in input_example.columns):
        err_msg = f"""Input file {key} does not match expected structure.
            Expected columns: {input_example.columns.tolist()}"""
        logger.error(err_msg)
        return False, err_msg

    return True


@task
def move_to_folder(bucket: str, key: str, folder: str, message: str = ""):
    """
    Move the S3 object to a specified folder.
    """
    logger = get_run_logger()

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


@flow(name="churn_prediction_pipeline", log_prints=True)
def churn_prediction_pipeline(bucket: str, key: str):
    """
    A Prefect flow that orchestrates the churn prediction pipeline.
    It includes tasks for data ingestion, preprocessing, model training,
    evaluation, and potentially retraining the model based on performance.
    """
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
        success, err_msg = validate_file_input(bucket, latest_s3_key, input_example)
        if not success:
            move_to_folder(bucket, latest_s3_key, FOLDER_ERRORED, message=err_msg)
            return

        # Here you would call other tasks to perform the steps of the pipeline
        # For example:
        # data = ingest_data()
        # preprocessed_data = preprocess_data(data)
        # model = train_model(preprocessed_data)
        # evaluate_model(model, preprocessed_data)
    except Exception as e:
        err_msg = f"An unexpected error occurred in the churn prediction pipeline: {e}"
        logger.error(err_msg)
        if latest_s3_key:
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
