from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelParameters:
    """
    30 coupled SEIHR model parameters per region.
    Values extracted from data sources or estimated via LLM retrieval.
    """
    region: str
    
    # Transmission & exposure dynamics (unit: 1/days)
    beta_base: float  # baseline transmission rate from fossil intensity
    sigma: float      # incubation rate (E -> I)
    gamma: float      # recovery rate from outpatient (I -> R)
    eta: float        # hospitalization rate (I -> H)
    rho: float        # discharge rate from hospital (H -> R)
    omega: float      # loss of immunity (R -> S)
    
    # Pollution impact multipliers (dimensionless)
    beta_sensitivity: float  # responsiveness of beta to X changes
    x_scale: float           # pollution intensity scale factor
    
    # Policy feedback (unit: 1/days)
    kappa: float      # baseline fossil dependency decay
    lambda_rate: float  # feedback intensity: H -> X reduction
    
    # Transboundary coupling (dimensionless, per region pair)
    psi_transport: float  # population/exposure transport coefficient
    phi_transport: float  # pollution transport coefficient
    transboundary_lag_days: int  # days before transboundary effect appears
    
    # Initial conditions (units vary)
    s0: float  # initial susceptible
    e0: float  # initial exposed
    i0: float  # initial affected
    h0: float  # initial hospitalized
    r0: float  # initial recovered
    x0: float  # initial fossil dependency (0-1 scale)
    
    # Time constants (unit: days)
    pollution_lag_days: int  # PM2.5 -> health effect lag
    policy_response_days: int  # H observation -> policy lag
    
    # Metadata
    source_metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "beta_base": self.beta_base,
            "sigma": self.sigma,
            "gamma": self.gamma,
            "eta": self.eta,
            "rho": self.rho,
            "omega": self.omega,
            "beta_sensitivity": self.beta_sensitivity,
            "x_scale": self.x_scale,
            "kappa": self.kappa,
            "lambda_rate": self.lambda_rate,
            "psi_transport": self.psi_transport,
            "phi_transport": self.phi_transport,
            "transboundary_lag_days": self.transboundary_lag_days,
            "s0": self.s0,
            "e0": self.e0,
            "i0": self.i0,
            "h0": self.h0,
            "r0": self.r0,
            "x0": self.x0,
            "pollution_lag_days": self.pollution_lag_days,
            "policy_response_days": self.policy_response_days,
            "source_metadata": self.source_metadata,
        }
