"""
Unit tests for the AWS Lambda function that triggers
Prefect workflows when an object is uploaded to S3.
"""

from s3_to_prefect_lambda.lambda_function import lambda_handler


def test_lambda_handler():
    """Test the lambda_handler function with a mock S3 event."""
    event = {
        "Records": [
            {"s3": {"bucket": {"name": "test-bucket"}, "object": {"key": "test-key"}}}
        ]
    }

    context = {}

    response = lambda_handler(event, context)

    assert response["statusCode"] == 200
