"""
Test that generate_predictions calls the model's 'predict' method
and returns predictions of the same length as the input data.
"""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from churn_prediction_pipeline import generate_predictions


class TestGeneratePredictions(unittest.TestCase):

    def setUp(self):
        self.patcher_logger = patch("churn_prediction_pipeline.get_run_logger")
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_logger.stop()

    def test_generate_predictions_success(self):
        """
        Test that generate_predictions returns predictions
        with the same length as the input data.
        """
        # Mock input data
        df_X = MagicMock()  # pylint: disable=invalid-name
        df_X.shape = (4, 5)  # Mocking a DataFrame with 4 rows and 5 columns

        # Mock model and prediction
        mock_model = MagicMock()
        mock_model.predict.return_value = [0, 1, 0, 1]

        with patch("churn_prediction_pipeline.fetch_model", return_value=mock_model):
            predictions = generate_predictions.fn(df_X, mock_model)

        self.assertEqual(len(predictions), df_X.shape[0])
        mock_model.predict.assert_called_once_with(df_X)
