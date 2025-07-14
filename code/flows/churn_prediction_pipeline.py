"""
This module houses the Prefect flow for the churn prediction pipeline.
It orchestrates the entire process from data ingestion to model evaluation.
It also includes task(s) to retrain the model if the model's churn prediction
performance does not meet specified threshold.
"""

import sys

from prefect import flow


@flow(name="churn_prediction_pipeline", log_prints=True)
def churn_prediction_pipeline(bucket: str, key: str):
    """
    A Prefect flow that orchestrates the churn prediction pipeline.
    It includes tasks for data ingestion, preprocessing, model training,
    evaluation, and potentially retraining the model based on performance.
    """
    print("Starting the Churn Prediction Pipeline...")
    print(f"Processing data from bucket: {bucket}, key: {key}")

    # Here you would call other tasks to perform the steps of the pipeline
    # For example:
    # data = ingest_data()
    # preprocessed_data = preprocess_data(data)
    # model = train_model(preprocessed_data)
    # evaluate_model(model, preprocessed_data)


# This allows the flow to be run directly for testing purposes
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python churn_prediction_pipeline.py <bucket> <key>")
        sys.exit(1)
    param1 = sys.argv[1]
    param2 = sys.argv[2]
    print(f"Running churn prediction pipeline with bucket: {param1}, key: {param2}")
    churn_prediction_pipeline(bucket=param1, key=param2)
