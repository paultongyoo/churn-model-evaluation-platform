"""
This file contains tests for the fetch_model function.
"""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from flows.churn_prediction_pipeline import fetch_model

"""
Test class for the fetch_model function.
This class contains unit tests to ensure that the fetch_model function
correctly retrieves a model from MLflow and handles errors appropriately.
"""


class TestFetchModel(unittest.TestCase):

    def setUp(self):
        self.patcher_mlflow = patch("flows.churn_prediction_pipeline.mlflow")
        self.patcher_logger = patch("flows.churn_prediction_pipeline.get_run_logger")

        self.mock_mlflow = self.patcher_mlflow.start()
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_mlflow.stop()
        self.patcher_logger.stop()

    def test_fetch_model_success(self):
        """
        Test that fetch_model retrieves the model correctly.
        """

        mock_model = MagicMock()
        mock_model.input_example = {"feature1": "value1", "feature2": "value2"}
        self.mock_mlflow.pyfunc.load_model.return_value = mock_model

        model = fetch_model.fn("http://mlflow-server:5000", "test_model", "latest")

        self.assertEqual(
            model.input_example, {"feature1": "value1", "feature2": "value2"}
        )
        self.mock_mlflow.pyfunc.load_model.assert_called_once_with(
            model_uri="models:/test_model@latest"
        )

    def test_fetch_model_missing_model(self):
        """
        Test that fetch_model raises expected error type with
        the expected error message when the model is not found.
        """
        expected_error = (
            "Failed to fetch model 'missing_model' with alias 'latest' - "
            "Does it exist in the MLFlow registry?'"
        )
        self.mock_mlflow.pyfunc.load_model.side_effect = RuntimeError(expected_error)

        with self.assertRaises(RuntimeError) as context:
            fetch_model.fn("http://mlflow-server:5000", "missing_model", "latest")

        self.assertTrue(str(context.exception).startswith(expected_error))
