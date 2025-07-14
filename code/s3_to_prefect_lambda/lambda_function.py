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

        payload = {"bucket": bucket, "key": key}
        deployment_id = get_deployment_id()

        print("TODO: Trigger Prefect flow with:")
        print("Payload: ", payload)
        print("Deployment ID: ", deployment_id)

        # prefect_url = os.environ["PREFECT_TRIGGER_URL"]
        # response = http.request("POST", prefect_url, body=json.dumps(payload),
        # headers={"Content-Type": "application/json"})
        # print("Prefect response:", response.status)

    return {"statusCode": 200}


def get_deployment_id():
    """
    Retrieve the deployment ID for a given flow and deployment name.
    """
    response = requests.get(
        f"{prefect_api_url}/deployments",
        params={"flow_name": FLOW_NAME, "name": DEPLOYMENT_NAME},
        timeout=60,
    )

    response.raise_for_status()
    deployments = response.json()
    if deployments:
        return deployments[0]["id"]

    raise ValueError("Deployment not found")
