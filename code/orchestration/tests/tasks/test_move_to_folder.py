"""
This file contains tests for the move_to_folder function.
"""

import unittest
from unittest.mock import patch

from churn_prediction_pipeline import FOLDER_LOGS
from churn_prediction_pipeline import move_to_folder

"""
Test class for the move_to_folder function.
This class contains unit tests to ensure that the move_to_folder function
correctly moves an S3 object to a specified folder and handles errors appropriately.
"""


class TestMoveToFolder(unittest.TestCase):

    def setUp(self):
        self.patcher_s3_client = patch("churn_prediction_pipeline.s3_client")
        self.patcher_logger = patch("churn_prediction_pipeline.get_run_logger")

        self.mock_s3_client = self.patcher_s3_client.start()
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_s3_client.stop()
        self.patcher_logger.stop()

    def test_move_to_folder_success(self):
        """
        Test that move_to_folder successfully moves an S3 object
        to a specified folder and a log file is also created.
        """
        mock_bucket = "test-bucket"
        mock_key = "test-folder/test-file.csv"
        mock_folder = "new-folder"

        # Mock the copy and delete operations
        self.mock_s3_client.copy_object.return_value = {}
        self.mock_s3_client.delete_object.return_value = {}

        new_key = move_to_folder(mock_bucket, mock_key, mock_folder)

        # Assert that the new key is constructed correctly
        expected_new_key = f"{mock_folder}/test-file.csv"
        self.assertEqual(new_key, expected_new_key)
        self.mock_s3_client.copy_object.assert_called_once_with(
            Bucket=mock_bucket,
            CopySource={"Bucket": mock_bucket, "Key": mock_key},
            Key=expected_new_key,
        )
        self.mock_s3_client.delete_object.assert_called_once_with(
            Bucket=mock_bucket, Key=mock_key
        )

        # Assert that a log message was created
        _, kwargs = self.mock_s3_client.put_object.call_args
        self.assertEqual(kwargs["Bucket"], mock_bucket)
        self.assertEqual(kwargs["Key"], f"{FOLDER_LOGS}/test-file.csv.log")
