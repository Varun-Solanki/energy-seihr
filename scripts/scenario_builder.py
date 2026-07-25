"""
Utility script to build and run common scenarios.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parameters import ModelParameters
from core.runner import Scenario, SimulationRunner


def build_drax_closure_scenario() -> Scenario:
    """
    Scenario: Drax coal plant closure on 2023-04-01 in Yorkshire.
    Models 9-month period (Apr 2023 - Dec 2023) to observe health impact.
    """
    params_yorkshire = ModelParameters(
        region="UK_Yorkshire",
        beta_base=0.45,
        sigma=0.2,
        gamma=0.1,
        eta=0.05,
        rho=0.1,
        omega=0.01,
        beta_sensitivity=1.2,
        x_scale=0.5,
        kappa=0.02,
        lambda_rate=0.08,
        psi_transport=0.001,
        phi_transport=0.002,
        transboundary_lag_days=30,
        s0=1300000,
        e0=500,
        i0=100,
        h0=50,
        r0=100000,
        x0=0.30,
        pollution_lag_days=90,
        policy_response_days=180,
    )
    
    params_southeast = ModelParameters(
        region="UK_SouthEast",
        beta_base=0.4,
        sigma=0.2,
        gamma=0.1,
        eta=0.05,
        rho=0.1,
        omega=0.01,
        beta_sensitivity=0.8,
        x_scale=0.5,
        kappa=0.01,
        lambda_rate=0.05,
        psi_transport=0.001,
        phi_transport=0.002,
        transboundary_lag_days=30,
        s0=4500000,
        e0=1000,
        i0=200,
        h0=100,
        r0=350000,
        x0=0.25,
        pollution_lag_days=90,
        policy_response_days=180,
    )
    
    return Scenario(
        description="Drax Closure Impact Study (April - Dec 2023)",
        start_date="2023-04-01",
        end_date="2023-12-31",
        regions=["UK_Yorkshire", "UK_SouthEast"],
        parameters={
            "UK_Yorkshire": params_yorkshire,
            "UK_SouthEast": params_southeast,
        },
        coupling_matrix={
            ("UK_Yorkshire", "UK_SouthEast"): 0.001,
            ("UK_SouthEast", "UK_Yorkshire"): 0.0002,
        }
    )


def build_counterfactual_scenario() -> Scenario:
    """
    Counterfactual: What if Drax closure did NOT happen?
    Models same 9-month period with coal plant still operational.
    """
    params_yorkshire = ModelParameters(
        region="UK_Yorkshire",
        beta_base=0.52,
        sigma=0.2,
        gamma=0.1,
        eta=0.05,
        rho=0.1,
        omega=0.01,
        beta_sensitivity=1.0,
        x_scale=0.5,
        kappa=0.005,
        lambda_rate=0.03,
        psi_transport=0.001,
        phi_transport=0.002,
        transboundary_lag_days=30,
        s0=1300000,
        e0=500,
        i0=100,
        h0=50,
        r0=100000,
        x0=0.35,
        pollution_lag_days=90,
        policy_response_days=180,
    )
    
    params_southeast = ModelParameters(
        region="UK_SouthEast",
        beta_base=0.42,
        sigma=0.2,
        gamma=0.1,
        eta=0.05,
        rho=0.1,
        omega=0.01,
        beta_sensitivity=0.8,
        x_scale=0.5,
        kappa=0.01,
        lambda_rate=0.05,
        psi_transport=0.001,
        phi_transport=0.002,
        transboundary_lag_days=30,
        s0=4500000,
        e0=1000,
        i0=200,
        h0=100,
        r0=350000,
        x0=0.26,
        pollution_lag_days=90,
        policy_response_days=180,
    )
    
    return Scenario(
        description="Counterfactual: Drax Still Operating (April - Dec 2023)",
        start_date="2023-04-01",
        end_date="2023-12-31",
        regions=["UK_Yorkshire", "UK_SouthEast"],
        parameters={
            "UK_Yorkshire": params_yorkshire,
            "UK_SouthEast": params_southeast,
        },
        coupling_matrix={
            ("UK_Yorkshire", "UK_SouthEast"): 0.0015,
            ("UK_SouthEast", "UK_Yorkshire"): 0.0002,
        }
    )


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SCENARIO BUILDER: Standard Scenarios")
    print("="*60)
    
    runner = SimulationRunner()
    
    print("\n[Scenario 1] Drax Closure (Actual)")
    print("-" * 60)
    scenario1 = build_drax_closure_scenario()
    print(scenario1.description)
    
    output1 = runner.run(scenario1)
    print(f"\nCompleted: {len(output1.trajectory)} regions, 275 days")
    
    for region in output1.trajectory:
        result = output1.trajectory[region]
        S, E, I, H, R, X = result.trajectory.T
        print(f"\n  {region}:")
        print(f"    Hospitalized (start): {H[0]:.0f} (end): {H[-1]:.0f}")
        print(f"    Fossil dependency: {X[0]:.2f} -> {X[-1]:.2f}")
    
    print("\n" + "="*60)
    print("[Scenario 2] Counterfactual (No Closure)")
    print("-" * 60)
    scenario2 = build_counterfactual_scenario()
    print(scenario2.description)
    
    output2 = runner.run(scenario2)
    print(f"\nCompleted: {len(output2.trajectory)} regions, 275 days")
    
    for region in output2.trajectory:
        result = output2.trajectory[region]
        S, E, I, H, R, X = result.trajectory.T
        print(f"\n  {region}:")
        print(f"    Hospitalized (start): {H[0]:.0f} (end): {H[-1]:.0f}")
        print(f"    Fossil dependency: {X[0]:.2f} -> {X[-1]:.2f}")
    
    print("\n" + "="*60)
    print("COMPARISON: Drax Closure Impact")
    print("="*60)
    
    for region in ["UK_Yorkshire", "UK_SouthEast"]:
        H1 = output1.trajectory[region].trajectory[:, 3]
        H2 = output2.trajectory[region].trajectory[:, 3]
        
        hosp_diff = H2[-1] - H1[-1]
        pct_change = (hosp_diff / H2[-1]) * 100
        
        print(f"\n{region}:")
        print(f"  Counterfactual H(end): {H2[-1]:.0f}")
        print(f"  Actual H(end):         {H1[-1]:.0f}")
        print(f"  Reduction:             {hosp_diff:.0f} hospitalizations (-{pct_change:.1f}%)")
