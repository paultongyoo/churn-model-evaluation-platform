"""
Test that prepare_dataset calls upon the same prepare logic
used in modeling training that returns prepared X and y feature set
of the same length.
"""

import unittest
from unittest.mock import patch

import pandas as pd
from churn_prediction_pipeline import NUMERICAL_COLUMNS
from churn_prediction_pipeline import TARGET_COLUMN
from churn_prediction_pipeline import prepare_dataset


class TestPrepareDataset(unittest.TestCase):

    def setUp(self):
        self.patcher_logger = patch("churn_prediction_pipeline.get_run_logger")
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        self.patcher_logger.stop()

    def test_prepare_dataset_success(self):
        """
        Test that prepare_dataset retrieves and prepares
        a dataset with the same length for X and y.
        """

        # Create dataframe with random data
        df = pd.DataFrame()
        df[TARGET_COLUMN] = [0, 1, 0, 1]
        for col in NUMERICAL_COLUMNS:
            df[col] = [1, 2, 3, 4]  # Mock numerical columns

        with patch("churn_prediction_pipeline.prepare_data") as mock_prepare_data:
            mock_prepare_data.return_value = (df[NUMERICAL_COLUMNS], df[TARGET_COLUMN])

            X, y = prepare_dataset.fn(df)  # pylint: disable=invalid-name

        self.assertEqual(len(X), len(y))
        mock_prepare_data.assert_called_once_with(df)
