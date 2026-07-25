from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from core.ode_engine import RK4Engine, SimulationResult
from core.parameters import ModelParameters


@dataclass(frozen=True)
class Scenario:
    """Scenario descriptor for simulation runner."""
    description: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    regions: list[str]  # e.g., ["UK_Yorkshire", "UK_SouthEast"]
    parameters: dict[str, ModelParameters]  # region -> params
    coupling_matrix: dict[tuple[str, str], float] = None  # (region_from, region_to) -> coupling strength


@dataclass(frozen=True)
class RunOutput:
    trajectory: dict[str, SimulationResult]
    plots: list[str]
    metrics: dict[str, Any]


class SimulationRunner:
    """Orchestrates SEIHR simulation with data-driven parameters."""
    
    def __init__(
        self,
        engine: RK4Engine | None = None,
        initial_values_path: Path | None = None,
    ):
        self.engine = engine or RK4Engine()
        self.initial_values_path = initial_values_path or Path("math/initial_values.json")
        self._load_initial_values()
    
    def _load_initial_values(self) -> None:
        """Load initial population conditions from JSON."""
        if self.initial_values_path.exists():
            with open(self.initial_values_path) as f:
                self.initial_conditions = json.load(f)
        else:
            self.initial_conditions = {"defaults": {}}
    
    def run(self, scenario: Scenario) -> RunOutput:
        """
        Execute simulation for scenario across all regions.
        
        Args:
            scenario: Scenario with regions, parameters, coupling matrix, date range
            
        Returns:
            RunOutput with trajectories, plots, and metrics
        """
        # Parse date range into time grid (daily timesteps)
        start = datetime.fromisoformat(scenario.start_date)
        end = datetime.fromisoformat(scenario.end_date)
        num_days = (end - start).days + 1
        time_grid = np.linspace(0, num_days - 1, num_days)  # days from t0
        
        # Build coupling matrix if not provided
        coupling_matrix = scenario.coupling_matrix or {}
        
        initial_state = np.concatenate(
            [
                self._build_initial_state(region, scenario.parameters[region])
                for region in scenario.regions
            ]
        )

        def derivative_fn(t: float, state: np.ndarray) -> np.ndarray:
            return self._coupled_derivatives(
                t,
                state,
                scenario.regions,
                scenario.parameters,
                coupling_matrix,
            )

        joint_result = self.engine.integrate(derivative_fn, initial_state, time_grid)
        joint_trajectory = self._bound_joint_trajectory(joint_result.trajectory)

        trajectories = {}
        for index, region in enumerate(scenario.regions):
            start_col = index * 6
            end_col = start_col + 6
            trajectories[region] = SimulationResult(
                time=joint_result.time.copy(),
                trajectory=joint_trajectory[:, start_col:end_col],
            )
        
        return RunOutput(trajectory=trajectories, plots=[], metrics={})
    
    def _build_initial_state(self, region: str, params: ModelParameters) -> np.ndarray:
        """Build initial state vector [S, E, I, H, R, X] from parameters or defaults."""
        return np.array([
            params.s0,
            params.e0,
            params.i0,
            params.h0,
            params.r0,
            params.x0,
        ], dtype=np.float64)
    
    def _coupled_derivatives(
        self,
        t: float,
        state: np.ndarray,
        all_regions: list[str],
        all_params: dict[str, ModelParameters],
        coupling_matrix: dict[tuple[str, str], float],
    ) -> np.ndarray:
        region_states = {
            region: state[index * 6 : (index + 1) * 6]
            for index, region in enumerate(all_regions)
        }
        derivatives = []
        for region in all_regions:
            derivatives.append(
                self._seihr_derivatives(
                    t,
                    region_states[region],
                    all_params[region],
                    all_regions,
                    all_params,
                    coupling_matrix,
                    region_states,
                )
            )
        return np.concatenate(derivatives)

    def _seihr_derivatives(
        self,
        t: float,
        state: np.ndarray,
        params: ModelParameters,
        all_regions: list[str],
        all_params: dict[str, ModelParameters],
        coupling_matrix: dict[tuple[str, str], float],
        region_states: dict[str, np.ndarray] | None = None,
    ) -> np.ndarray:
        """
        Compute derivatives dX/dt for coupled SEIHR model.
        
        State vector: [S, E, I, H, R, X]
        where X is fossil dependency (0-1 scale).
        """
        S, E, I, H, R, X = state
        X = float(np.clip(X, 0.0, 1.0))
        N = max(S + E + I + H + R, 1.0)
        
        # Transmission rate modulated by energy mix
        # beta(t) = beta_base * (1 + beta_sensitivity * (X - 0.5))
        # Higher X (fossil) -> higher transmission
        beta = params.beta_base * (1.0 + params.beta_sensitivity * (X - 0.5))
        
        # Transboundary influx from coupled regions
        # Assume exposure pressure from other regions proportional to their health burden
        transboundary_exposure = 0.0
        transboundary_pollution = 0.0
        for source_region in all_regions:
            if source_region != params.region:
                key = (source_region, params.region)
                if key in coupling_matrix:
                    coupling_strength = coupling_matrix[key]
                    source_state = region_states.get(source_region) if region_states else None
                    if source_state is None:
                        source_params = all_params[source_region]
                        source_state = self._build_initial_state(source_region, source_params)
                    source_S, source_E, source_I, source_H, source_R, source_X = source_state
                    source_N = max(source_S + source_E + source_I + source_H + source_R, 1.0)
                    health_pressure = (source_I + source_H) / source_N
                    transboundary_exposure += coupling_strength * source_X * params.psi_transport * S
                    transboundary_exposure += coupling_strength * health_pressure * S
                    transboundary_pollution += coupling_strength * source_X
        
        # SEIHR ODEs with transboundary terms
        # dS/dt: loss to infection, gain from immunity waning, transboundary inflow
        local_exposure = beta * S * I / N
        dS_dt = -local_exposure - transboundary_exposure + params.omega * R

        # dE/dt: gain from exposed, loss to infectious
        dE_dt = local_exposure + transboundary_exposure - params.sigma * E
        
        # dI/dt: gain from exposed, loss to recovery and hospitalization
        dI_dt = params.sigma * E - params.gamma * I - params.eta * I
        
        # dH/dt: gain from hospitalization, loss to recovery
        dH_dt = params.eta * I - params.rho * H
        
        # dR/dt: gain from recovery (both outpatient and hospital)
        dR_dt = params.gamma * I + params.rho * H - params.omega * R
        
        # dX/dt: fossil dependency dynamics
        # Decreases with policy pressure (H -> X reduction)
        # Increases with transboundary pollution inflow
        policy_pressure = params.lambda_rate * (H / N) if N > 0 else 0
        pollution_inflow = transboundary_pollution * params.phi_transport
        dX_dt = -params.kappa * X - policy_pressure + pollution_inflow
        dX_dt = np.clip(dX_dt, -0.1, 0.1)  # Bound rate of change
        
        return np.array([dS_dt, dE_dt, dI_dt, dH_dt, dR_dt, dX_dt], dtype=np.float64)

    def _bound_joint_trajectory(self, trajectory: np.ndarray) -> np.ndarray:
        bounded = trajectory.copy()
        for column in range(bounded.shape[1]):
            if column % 6 == 5:
                bounded[:, column] = np.clip(bounded[:, column], 0.0, 1.0)
            else:
                bounded[:, column] = np.maximum(bounded[:, column], 0.0)
        return bounded
