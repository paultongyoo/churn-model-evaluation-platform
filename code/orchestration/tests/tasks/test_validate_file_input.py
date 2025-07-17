"""
This file contains tests for the validate-file_input function.
"""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import pandas as pd
from orchestration.churn_prediction_pipeline import validate_file_input


class TestValidateFileInput(unittest.TestCase):

    def setUp(self):

        self.patcher_s3_client = patch(
            "orchestration.churn_prediction_pipeline.s3_client"
        )
        self.patcher_logger = patch(
            "orchestration.churn_prediction_pipeline.get_run_logger"
        )
        self.patcher_pd = patch("orchestration.churn_prediction_pipeline.pd")

        self.mock_s3_client = self.patcher_s3_client.start()
        self.mock_pd = self.patcher_pd.start()
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_s3_client.stop()
        self.patcher_pd.stop()
        self.patcher_logger.stop()

    def test_validate_file_input_success(self):
        """
        Test that validate_file_input returns True when the file confirms
        to the validation requirements:
        -- Expected file extension (csv)
        -- Can be converted into a CSV (i.e. calling read_csv does not raise an error)
        -- CSV contains expected columns
        """
        mock_bucket = "any_bucket"
        mock_key = "key_with_required_file_extension.csv"
        mock_input_example = MagicMock()
        mock_input_example.columns = pd.Index(
            ["expected_feature_1", "expected_feature_2"]
        )

        # Set up mock return values
        self.mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                lambda: "expected_feature_1,expected_feature_2\nvalue1,value2\n"
            )
        }
        self.mock_pd.read_csv.return_value = pd.DataFrame(
            {
                "expected_feature_1": ["any_value_1"],
                "expected_feature_2": ["any_value_2"],
            }
        )

        result, error_message = validate_file_input.fn(
            mock_bucket, mock_key, mock_input_example
        )

        # Assert that the S3 client and pandas read_csv were called correctly
        self.mock_s3_client.get_object.assert_called_once_with(
            Bucket=mock_bucket, Key=mock_key
        )
        self.mock_pd.read_csv.assert_called_once_with(
            self.mock_s3_client.get_object.return_value["Body"]
        )

        # Assert that the result is True and no error message is returned
        self.assertTrue(result)
        self.assertIsNone(error_message)
