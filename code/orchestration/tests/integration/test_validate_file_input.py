# pylint: disable=too-many-locals
"""
Integration tests the validate_file_input function with
LocalStack S3.
"""

import io
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import boto3
import pandas as pd
from churn_prediction_pipeline import NUMERICAL_COLUMNS
from churn_prediction_pipeline import TARGET_COLUMN
from churn_prediction_pipeline import validate_file_input
from testcontainers.localstack import LocalStackContainer


class IntegrationTestValidateFileInput(unittest.TestCase):

    def setUp(self):
        self.patcher_logger = patch("churn_prediction_pipeline.get_run_logger")
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_logger.stop()

    def test_valid_file(self):
        """
        Test that validate_file_input checks the S3 key
        and validates the input example DataFrame for a valid file.
        """
        # Start LocalStack container
        with LocalStackContainer(image="localstack/localstack:latest").with_services(
            "s3"
        ) as localstack:
            s3_endpoint_url = localstack.get_url()

            # Persist a CSV with the expected columns to LocalStack S3
            bucket_name = "test-bucket"
            key = "test-file.csv"
            expected_columns = NUMERICAL_COLUMNS + [TARGET_COLUMN]
            data = {col: [1, 2, 3, 4] for col in expected_columns}
            data[TARGET_COLUMN] = [0, 1, 0, 1]
            df = pd.DataFrame(data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")
            local_s3 = boto3.client(
                "s3", region_name="us-east-1", endpoint_url=s3_endpoint_url
            )
            local_s3.create_bucket(Bucket=bucket_name)
            local_s3.put_object(Bucket=bucket_name, Key=key, Body=csv_bytes)

            # Mocking Secret.load method only to prevent Prefect from being called
            # Intentionally not mocking the S3 client creation to test the integration
            with patch("churn_prediction_pipeline.Secret.load") as mock_secret_load:
                mock_secret = MagicMock()
                mock_secret.get.return_value = "anything"
                mock_secret_load.return_value = mock_secret

                is_valid, df_read, error_msg = validate_file_input.fn(
                    bucket_name, key, df, s3_endpoint_url
                )

            self.assertTrue(is_valid)
            self.assertEqual(df_read.shape, df.shape)
            self.assertListEqual(list(df_read.columns), expected_columns)
            self.assertIsNone(error_msg)

    def test_invalid_file_extension(self):
        """
        Assert that validate_file_input returns False
        for an invalid file extension.
        """
        # Start LocalStack container
        with LocalStackContainer(image="localstack/localstack:latest").with_services(
            "s3"
        ) as localstack:
            s3_endpoint_url = localstack.get_url()

            # Persist a CSV with unexpected file extension to LocalStack S3
            bucket_name = "test-bucket"
            key = "test-file.asdfasdfadsf"
            region = "us-east-1"
            expected_columns = NUMERICAL_COLUMNS + [TARGET_COLUMN]
            data = {col: [1, 2, 3, 4] for col in expected_columns}
            data[TARGET_COLUMN] = [0, 1, 0, 1]
            df = pd.DataFrame(data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")
            local_s3 = boto3.client(
                "s3", region_name=region, endpoint_url=s3_endpoint_url
            )
            local_s3.create_bucket(Bucket=bucket_name)
            local_s3.put_object(Bucket=bucket_name, Key=key, Body=csv_bytes)

            # Mocking Secret.load method only to prevent Prefect from being called
            # Intentionally not mocking the S3 client creation to test the integration
            with patch("churn_prediction_pipeline.Secret.load") as mock_secret_load:
                mock_secret = MagicMock()
                mock_secret.get.return_value = "anything"
                mock_secret_load.return_value = mock_secret

                is_valid, df_read, error_msg = validate_file_input.fn(
                    bucket_name, key, df, s3_endpoint_url
                )

            self.assertFalse(is_valid)
            self.assertIsNone(df_read)
            self.assertEqual(
                error_msg, f"Invalid file type for {key}. Expected a CSV file."
            )

    def test_invalid_file_contents(self):
        """
        Assert that validate_file_input returns False
        for an invalid file extension.
        """
        # Start LocalStack container
        with LocalStackContainer(image="localstack/localstack:latest").with_services(
            "s3"
        ) as localstack:
            s3_endpoint_url = localstack.get_url()

            # Persist a CSV with unexpected columns to LocalStack S3
            bucket_name = "test-bucket"
            key = "test-file-diff-cols.csv"
            region = "us-east-1"
            expected_columns = NUMERICAL_COLUMNS + [TARGET_COLUMN]
            unexpected_columns = ["odd_col_1", "odd_col_2"] + [TARGET_COLUMN]
            data = {col: [1, 2, 3, 4] for col in unexpected_columns}
            data[TARGET_COLUMN] = [0, 1, 0, 1]
            df_unexpected = pd.DataFrame(data)
            csv_buffer = io.StringIO()
            df_unexpected.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")
            local_s3 = boto3.client(
                "s3", region_name=region, endpoint_url=s3_endpoint_url
            )
            local_s3.create_bucket(Bucket=bucket_name)
            local_s3.put_object(Bucket=bucket_name, Key=key, Body=csv_bytes)

            # Provide input example with expected columns
            df_expected = pd.DataFrame(columns=expected_columns)

            # Mocking Secret.load method only to prevent Prefect from being called
            # Intentionally not mocking the S3 client creation to test the integration
            with patch("churn_prediction_pipeline.Secret.load") as mock_secret_load:
                mock_secret = MagicMock()
                mock_secret.get.return_value = "anything"
                mock_secret_load.return_value = mock_secret

                is_valid, df_read, error_msg = validate_file_input.fn(
                    bucket_name, key, df_expected, s3_endpoint_url
                )

            self.assertFalse(is_valid)
            self.assertIsNone(df_read)
            self.assertEqual(
                error_msg,
                (
                    f"Input file {key} does not match expected structure. "
                    f"Expected columns: {expected_columns}"
                ),
            )
