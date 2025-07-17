"""
This file contains tests for the validate-file_input function.
"""

import unittest
from io import BytesIO
from unittest.mock import MagicMock
from unittest.mock import patch

import pandas as pd
from churn_prediction_pipeline import validate_file_input
from pandas.testing import assert_frame_equal


class TestValidateFileInput(unittest.TestCase):

    def setUp(self):

        self.patcher_s3_client = patch("churn_prediction_pipeline.s3_client")
        self.patcher_logger = patch("churn_prediction_pipeline.get_run_logger")
        self.patcher_pd = patch("churn_prediction_pipeline.pd")

        self.mock_s3_client = self.patcher_s3_client.start()
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_s3_client.stop()
        self.patcher_logger.stop()

    @patch("churn_prediction_pipeline.pd")
    def test_validate_file_input_success(self, mock_pd):
        """
        Test that validate_file_input returns True when the file confirms
        to the validation requirements:
        -- Expected file extension (csv)
        -- Can be converted into a CSV (i.e. calling read_csv does not raise an error)
        -- CSV contains expected columns
        """

        mock_bucket = "any_bucket"
        mock_key = "key_with_required_file_extension.csv"
        mock_input_example = pd.DataFrame(
            columns=["expected_feature_1", "expected_feature_2"]
        )

        # Set up mock return values
        self.mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                lambda: "expected_feature_1,expected_feature_2\nvalue1,value2\n"
            )
        }
        mock_pd.read_csv.return_value = pd.DataFrame(
            {
                "expected_feature_1": ["any_value_1"],
                "expected_feature_2": ["any_value_2"],
            }
        )

        result, input_df, error_message = validate_file_input.fn(
            mock_bucket, mock_key, mock_input_example
        )

        # Assert that the S3 client and pandas read_csv were called correctly
        self.mock_s3_client.get_object.assert_called_once_with(
            Bucket=mock_bucket, Key=mock_key
        )
        mock_pd.read_csv.assert_called_once_with(
            self.mock_s3_client.get_object.return_value["Body"]
        )

        # Assert that the result is True and no error message is returned
        self.assertTrue(result)
        assert_frame_equal(input_df, mock_pd.read_csv.return_value)
        self.assertIsNone(error_message)

    def test_validate_file_input_invalid_csv(self):
        """
        Test that validate_file_input returns False when the file cannot be read as a CSV.
        """
        mock_bucket = "any_bucket"
        mock_key = "malformed.csv"
        mock_input_example = pd.DataFrame(
            columns=["expected_feature_1", "expected_feature_2"]
        )

        # Simulate invalid binary data
        binary_data = b"\xff\xfe\xfa\xfb\xfd"
        self.mock_s3_client.get_object.return_value = {"Body": BytesIO(binary_data)}

        result, input_df, error_message = validate_file_input.fn(
            mock_bucket, mock_key, mock_input_example
        )

        self.assertFalse(result)
        self.assertIsNone(input_df)
        self.assertTrue(error_message.startswith("Error reading CSV file"))

    @patch("churn_prediction_pipeline.pd")
    def test_validate_file_input_missing_columns(self, mock_pd):
        """
        Test that validate_file_input returns False when the file does not contain
        all of the columns expected by the input example.
        """

        mock_bucket = "any_bucket"
        mock_key = "expected_extension.csv"
        mock_input_example = pd.DataFrame(
            columns=["expected_feature_1", "expected_feature_2"]
        )

        self.mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                lambda: "expected_feature_1,expected_feature_2\nvalue1,value2\n"
            )
        }
        mock_pd.read_csv.return_value = pd.DataFrame(
            {
                "expected_feature_1": ["any_value_1"]
                # Removed 'expected_feature_2' to simulate missing column
            }
        )

        result, input_df, error_message = validate_file_input.fn(
            mock_bucket, mock_key, mock_input_example
        )

        self.assertFalse(result)
        self.assertIsNone(input_df)
        self.assertEqual(
            error_message,
            f"""Input file {mock_key} does not match expected structure.
            Expected columns: {mock_input_example.columns.tolist()}""",
        )
