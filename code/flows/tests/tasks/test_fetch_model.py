"""This file contains tests for the fetch_model function."""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from flows.churn_prediction_pipeline import fetch_model

"""Test class for the fetch_model function.
This class contains unit tests to ensure that the fetch_model function
correctly retrieves a model from MLflow and handles errors appropriately."""


class TestFetchModel(unittest.TestCase):
    @patch("flows.churn_prediction_pipeline.mlflow")
    def test_fetch_model_success(self, mock_mlflow):
        """
        Test that fetch_model retrieves the model correctly.
        """
        mock_model = MagicMock()
        mock_model.input_example = {"feature1": "value1", "feature2": "value2"}
        mock_mlflow.pyfunc.load_model.return_value = mock_model

        model = fetch_model("http://mlflow-server:5000", "test_model", "latest")

        self.assertEqual(
            model.input_example, {"feature1": "value1", "feature2": "value2"}
        )
        mock_mlflow.pyfunc.load_model.assert_called_once_with(
            model_uri="models:/test_model@latest"
        )
