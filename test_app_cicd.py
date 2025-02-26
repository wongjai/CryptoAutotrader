"""
Test classes. Version controlled and CI/CD specific (GitHub secrets required!).
"""

import os

from config import TestData
from predict import PredictionApp

class TestLLM:

    def test_any(self):
        """
        Run abstract LLM prediction on test data (check if not None)
        :return:
        """
        os.environ["DEFAULT_PREDICTION_API"] = "PROBABILITY_LLM"
        prediction_app = PredictionApp("probability_llm.env")
        prediction_function = prediction_app.predict_with_any_llm
        assert prediction_function(TestData.DEFAULT_DATA_TO_TEST_API_UP) is not None, \
            "Couldn't get prediction"

    def test_probability_up(self):
        """
        Run LLM prediction with prob. on test data
        :return:
        """
        os.environ["DEFAULT_PREDICTION_API"] = "PROBABILITY_LLM"
        prediction_app = PredictionApp("probability_llm.env")
        prediction_function = prediction_app.predict_probability_with_llm
        assert prediction_function(TestData.DEFAULT_DATA_TO_TEST_API_UP) == "up", \
            "Incorrect prediction"

    def test_probability_down(self):
        """
        Run LLM prediction with prob. on test data
        :return:
        """
        os.environ["DEFAULT_PREDICTION_API"] = "PROBABILITY_LLM"
        prediction_app = PredictionApp("probability_llm.env")
        prediction_function = prediction_app.predict_probability_with_llm
        assert prediction_function(TestData.DEFAULT_DATA_TO_TEST_API_DOWN) == "down", \
            "Incorrect prediction"

    def test_basic_up(self):
        os.environ["DEFAULT_PREDICTION_API"] = "LLM"
        prediction_app = PredictionApp("llm.env")
        prediction_function = prediction_app.predict_up_or_down
        assert prediction_function(TestData.DEFAULT_DATA_TO_TEST_API_UP) == "up", \
            "Incorrect prediction"

    def test_basic_down(self):
        os.environ["DEFAULT_PREDICTION_API"] = "LLM"
        prediction_app = PredictionApp("llm.env")
        prediction_function = prediction_app.predict_up_or_down
        assert prediction_function(TestData.DEFAULT_DATA_TO_TEST_API_DOWN) == "down", \
            "Incorrect prediction"
