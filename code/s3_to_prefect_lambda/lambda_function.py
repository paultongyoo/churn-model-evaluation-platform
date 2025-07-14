# pylint: disable=unused-argument
"""Lambda function to trigger Prefect flows when files are uploaded to S3."""
import json
import os

import requests
import urllib3

http = urllib3.PoolManager()

prefect_api_url = os.environ["PREFECT_API_URL"]
FLOW_NAME = "churn_prediction_pipeline"
DEPLOYMENT_NAME = "default"


def lambda_handler(event, context):
    """
    Lambda function handler to process S3 events and trigger Prefect flows.
    Args:
        event (dict): The event data from S3, containing bucket and object key.
        context (object): The context object provided by AWS Lambda.
    Returns:
        dict: Response indicating the status of the operation.
    """
    # Log the received event for debugging purposes
    print("Received event:", json.dumps(event))

    records = event.get("Records", [])
    for record in records:
        s3 = record["s3"]
        bucket = s3["bucket"]["name"]
        key = s3["object"]["key"]

        payload = {"parameters": {"bucket": bucket, "key": key}}
        deployment_id = get_deployment_id()

        print(f"Triggering Prefect flow for bucket: {bucket}, key: {key}")
        print(f"Using deployment ID: {deployment_id}")

        prefect_trigger_url = (
            f"{prefect_api_url}/deployments/{deployment_id}/create_flow_run"
        )
        response = requests.post(prefect_trigger_url, json=payload, timeout=60)

        print("Prefect response:", response.status_code, response.text)

    return {"statusCode": 200}


def get_deployment_id():
    """
    Retrieve the deployment ID for a given flow and deployment name.
    """
    response = requests.get(
        f"{prefect_api_url}/deployments/name/{FLOW_NAME}/{DEPLOYMENT_NAME}",
        timeout=60,
    )

    response.raise_for_status()
    deployment = response.json()
    if deployment:
        return deployment["id"]

    raise ValueError("Deployment not found")
