"""
Backtesting Framework: Validate simulations vs ground truth (NHS + National Grid data)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from core.runner import SimulationResult


@dataclass
class ValidationMetrics:
    """Validation metrics comparing simulation to ground truth."""
    
    mse: float          # Mean Squared Error
    rmse: float         # Root Mean Squared Error
    mae: float          # Mean Absolute Error
    r_squared: float    # R squared coefficient
    peak_error: float   # Max absolute error
    peak_error_time: int  # Time index of peak error
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "mse": self.mse,
            "rmse": self.rmse,
            "mae": self.mae,
            "r_squared": self.r_squared,
            "peak_error": self.peak_error,
            "peak_error_time": self.peak_error_time,
        }


@dataclass
class BacktestResult:
    """Result of a single backtest run."""
    
    region: str
    scenario: str
    date_range: str
    predicted_H: np.ndarray    # Predicted hospitalization trajectory
    actual_H: np.ndarray       # Ground truth hospitalization trajectory
    time_grid: np.ndarray      # Time indices
    metrics: ValidationMetrics
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "scenario": self.scenario,
            "date_range": self.date_range,
            "metrics": self.metrics.to_dict(),
            "predicted_H_init": float(self.predicted_H[0]),
            "predicted_H_final": float(self.predicted_H[-1]),
            "actual_H_init": float(self.actual_H[0]),
            "actual_H_final": float(self.actual_H[-1]),
        }


class Backtester:
    """Backtests simulations against ground truth data."""

    def __init__(self, ground_truth_dir: Path | None = None):
        self.ground_truth_dir = ground_truth_dir or Path("data/ground_truth")
        self.ground_truth_dir.mkdir(parents=True, exist_ok=True)

    def backtest(
        self,
        region: str,
        scenario: str,
        result: SimulationResult,
        start_date: str,
        end_date: str,
    ) -> BacktestResult:
        """
        Backtest simulation against ground truth.
        
        Args:
            region: e.g., "UK_Yorkshire"
            scenario: e.g., "Drax Closure"
            result: SimulationResult from runner
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            
        Returns:
            BacktestResult with metrics
        """
        # Extract H (hospitalization) from simulation
        predicted_H = result.trajectory[:, 3]  # Column 3 is H
        
        # Load ground truth
        actual_H = self._load_ground_truth(region, start_date, end_date)
        
        # If lengths don't match, interpolate
        if len(actual_H) != len(predicted_H):
            actual_H = self._interpolate_to_length(actual_H, len(predicted_H))
        
        # Calculate metrics
        metrics = self._calculate_metrics(predicted_H, actual_H)
        
        return BacktestResult(
            region=region,
            scenario=scenario,
            date_range=f"{start_date} to {end_date}",
            predicted_H=predicted_H,
            actual_H=actual_H,
            time_grid=result.time,
            metrics=metrics,
        )

    def _load_ground_truth(self, region: str, start_date: str, end_date: str) -> np.ndarray:
        """
        Load ground truth hospitalization data from NHS.
        
        For now, returns synthetic data. In production, would query NHS API.
        """
        # Synthetic ground truth for backtesting (replace with real NHS data)
        file_path = self.ground_truth_dir / f"NHS_hospitalization_{region}.json"
        
        if file_path.exists():
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    values = data.get("hospitalization_timeseries", [])
                    return np.array(values, dtype=np.float64)
            except Exception as e:
                print(f"Warning: Could not load ground truth: {e}")
        
        # Fallback: generate synthetic ground truth
        # In reality, this would come from NHS Fingertips API
        print(f"Generating synthetic ground truth for {region} (replace with real NHS data)")
        return self._generate_synthetic_ground_truth(region, start_date, end_date)

    def _generate_synthetic_ground_truth(
        self,
        region: str,
        start_date: str,
        end_date: str,
    ) -> np.ndarray:
        """Generate realistic synthetic ground truth for testing."""
        from datetime import datetime, timedelta
        
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        num_days = (end - start).days + 1
        
        # Base hospitalization (realistic for region)
        base_H = {"UK_Yorkshire": 200, "UK_SouthEast": 500}.get(region, 300)
        
        # Seasonal trend (winter peak)
        seasonal = 100 * np.sin(np.arange(num_days) * 2 * np.pi / 365)
        
        # Policy intervention (if Drax closure date in range)
        intervention = np.zeros(num_days)
        drax_date = datetime(2023, 4, 1)
        if start <= drax_date <= end:
            drax_idx = (drax_date - start).days
            intervention[drax_idx:] = -50 * (1 - np.exp(-0.01 * np.arange(num_days - drax_idx)))
        
        # Random noise
        noise = np.random.normal(0, 20, num_days)
        
        # Combine
        H_truth = base_H + seasonal + intervention + noise
        return np.maximum(H_truth, 10)  # Ensure non-negative

    def _interpolate_to_length(self, data: np.ndarray, target_length: int) -> np.ndarray:
        """Interpolate array to target length."""
        if len(data) == target_length:
            return data
        
        old_indices = np.linspace(0, 1, len(data))
        new_indices = np.linspace(0, 1, target_length)
        return np.interp(new_indices, old_indices, data)

    def _calculate_metrics(
        self,
        predicted: np.ndarray,
        actual: np.ndarray,
    ) -> ValidationMetrics:
        """Calculate validation metrics."""
        errors = predicted - actual
        
        mse = np.mean(errors ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(errors))
        
        # R squared score
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Peak error
        abs_errors = np.abs(errors)
        peak_error_idx = np.argmax(abs_errors)
        peak_error = abs_errors[peak_error_idx]
        
        return ValidationMetrics(
            mse=float(mse),
            rmse=float(rmse),
            mae=float(mae),
            r_squared=float(r_squared),
            peak_error=float(peak_error),
            peak_error_time=int(peak_error_idx),
        )

    def generate_report(
        self,
        results: list[BacktestResult],
        output_path: Path | None = None,
    ) -> str:
        """Generate backtesting report."""
        output_path = output_path or Path("outputs/backtest_report.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "num_backtests": len(results),
            "results": [r.to_dict() for r in results],
            "summary": self._summarize_results(results),
        }
        
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[OK] Backtest report saved to {output_path}")
        return str(output_path)

    def _summarize_results(self, results: list[BacktestResult]) -> dict[str, Any]:
        """Summarize backtest results."""
        rmse_values = [r.metrics.rmse for r in results]
        mae_values = [r.metrics.mae for r in results]
        r2_values = [r.metrics.r_squared for r in results]
        
        return {
            "mean_rmse": float(np.mean(rmse_values)),
            "mean_mae": float(np.mean(mae_values)),
            "mean_r2": float(np.mean(r2_values)),
            "best_fit_region": results[np.argmax(r2_values)].region if results else "N/A",
            "worst_fit_region": results[np.argmin(r2_values)].region if results else "N/A",
        }
