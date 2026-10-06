import pytest
import numpy as np
from validation.metrics import AdvancedMetrics

def test_cumulative_burden_error():
    metrics = AdvancedMetrics()
    
    predicted = np.array([10, 20, 30])  # total = 60
    actual = np.array([10, 15, 25])     # total = 50
    
    error = metrics.calculate_cumulative_burden_error(predicted, actual)
    # (60 - 50) / 50 * 100 = 20.0%
    assert error == 20.0

def test_parameter_prior_violations():
    metrics = AdvancedMetrics()
    
    # Valid parameters
    valid_params = {
        "beta_base": 0.5,
        "gamma": 0.1,
        "kappa": 0.05
    }
    assert metrics.calculate_parameter_prior_violations(valid_params) == 0
    
    # Invalid parameters
    invalid_params = {
        "beta_base": 2.5,   # Should be <= 2.0 (Violation 1)
        "gamma": -0.1,      # Should be >= 0.0 (Violation 2)
        "kappa": 0.2        # Should be <= 0.1 (Violation 3)
    }
    assert metrics.calculate_parameter_prior_violations(invalid_params) == 3

def test_faithfulness_heuristic():
    metrics = AdvancedMetrics()
    
    rationale = "Delhi coal emissions heavily influence respiratory hospitalization rates."
    chunks = [
        "The coal plants in Delhi cause severe respiratory issues.",
        "Hospitalization rates are up."
    ]
    
    score = metrics.calculate_faithfulness_heuristic(rationale, chunks)
    # words from rationale: 'delhi', 'coal', 'emissions', 'heavily', 'influence', 'respiratory', 'hospitalization', 'rates'
    # in chunks: 'delhi', 'coal', 'respiratory', 'hospitalization', 'rates'
    # matches: 5
    # total: 8
    # score: 5/8 = 0.625
    assert score == 0.625
