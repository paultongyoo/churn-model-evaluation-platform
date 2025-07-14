# pylint: disable=unused-argument
"""Lambda function to trigger Prefect flows when files are uploaded to S3."""
import json

import urllib3

http = urllib3.PoolManager()


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

        print("TODO: Trigger Prefect flow with payload:", payload)

        # prefect_url = os.environ["PREFECT_TRIGGER_URL"]
        # response = http.request("POST", prefect_url, body=json.dumps(payload),
        # headers={"Content-Type": "application/json"})
        # print("Prefect response:", response.status)

    return {"statusCode": 200}
