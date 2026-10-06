from __future__ import annotations

import numpy as np


class Metrics:
    def mse(self, predicted: np.ndarray, actual: np.ndarray) -> float:
        return float(np.mean((predicted - actual) ** 2))

class AdvancedMetrics:
    def calculate_cumulative_burden_error(self, predicted_H: np.ndarray, actual_H: np.ndarray) -> float:
        """
        Simulation Metric: Cumulative Burden Error (AUC Error)
        Percentage error between predicted total hospital-days and actual historic hospital-days.
        """
        predicted_auc = np.sum(predicted_H)
        actual_auc = np.sum(actual_H)
        
        if actual_auc == 0:
            return 0.0
            
        # Percentage error (negative means under-prediction, positive means over-prediction)
        return float(((predicted_auc - actual_auc) / actual_auc) * 100)

    def calculate_parameter_prior_violations(self, params: dict) -> int:
        """
        LLM Metric: Parameter Prior Violation Count.
        Returns the number of parameters that violate strict epidemiological/physics bounds.
        """
        violations = 0
        bounds = {
            "beta_base": (0.0, 2.0),
            "sigma": (0.0, 1.0),
            "gamma": (0.0, 1.0),
            "eta": (0.0, 1.0),
            "rho": (0.0, 1.0),
            "omega": (0.0, 0.1),
            "beta_sensitivity": (0.0, 5.0),
            "x_scale": (0.0, 1.0),
            "kappa": (0.0, 0.1),
            "lambda_rate": (0.0, 0.2),
            "psi_transport": (0.0, 0.01),
            "phi_transport": (0.0, 0.01),
        }
        
        for key, (min_val, max_val) in bounds.items():
            if key in params:
                val = params[key]
                if val < min_val or val > max_val:
                    violations += 1
                    
        return violations

    def calculate_faithfulness_heuristic(self, rationale: str, retrieved_chunks: list[str]) -> float:
        """
        Retrieval Metric: Faithfulness (Heuristic).
        Checks if the key terms used in the LLM's rationale actually exist in the retrieved context.
        Returns a score from 0.0 to 1.0 (1.0 means highly faithful / low hallucination).
        """
        if not rationale or not retrieved_chunks:
            return 0.0
            
        import re
        # Extract substantial words from rationale
        words = set(re.findall(r'\b[a-zA-Z]{4,}\b', rationale.lower()))
        
        # Stop words to filter out
        stop_words = {"this", "that", "with", "from", "were", "have", "been", "based"}
        words = {w for w in words if w not in stop_words}
        
        if not words:
            return 1.0
            
        combined_context = " ".join(retrieved_chunks).lower()
        
        matches = sum(1 for word in words if word in combined_context)
        return float(matches / len(words))
