"""
Test script to validate the complete simulation core.
Tests: parameter schema, RK4 engine, and runner orchestration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json

import numpy as np

from core.parameters import ModelParameters
from core.runner import Scenario, SimulationRunner


def test_parameter_creation():
    """Test ModelParameters dataclass with Yorkshire data."""
    params = ModelParameters(
        region="UK_Yorkshire",
        beta_base=0.5,
        sigma=0.2,
        gamma=0.1,
        eta=0.05,
        rho=0.1,
        omega=0.01,
        beta_sensitivity=1.0,
        x_scale=0.5,
        kappa=0.01,
        lambda_rate=0.05,
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
        source_metadata={"source": "data/processed/normalized_records.jsonl"}
    )
    
    print("✓ ModelParameters created successfully")
    print(f"  Region: {params.region}")
    print(f"  Population: {params.s0 + params.e0 + params.i0 + params.r0 + params.h0:,.0f}")
    print(f"  Initial X (fossil): {params.x0:.2f}")
    
    # Test serialization
    param_dict = params.to_dict()
    assert "region" in param_dict
    assert param_dict["beta_base"] == 0.5
    print("✓ to_dict() serialization works")
    
    assert params.region == "UK_Yorkshire"


def test_schema_validation():
    """Test parameter schema against JSON Schema."""
    schema_path = Path("contracts/parameter_schema.json")
    with open(schema_path) as f:
        schema = json.load(f)
    
    print(f"✓ Parameter schema loaded: {len(schema['properties'])} properties")
    assert "beta_base" in schema["properties"]
    assert "s0" in schema["required"]
    print(f"  Required fields: {schema['required']}")
    

def test_simulation_run():
    """Test full simulation run with 30-day forecast."""
    # Create parameters for two coupled regions
    params_yorkshire = ModelParameters(
        region="UK_Yorkshire",
        beta_base=0.5,
        sigma=0.2,
        gamma=0.1,
        eta=0.05,
        rho=0.1,
        omega=0.01,
        beta_sensitivity=1.0,
        x_scale=0.5,
        kappa=0.01,
        lambda_rate=0.05,
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
    
    # Create scenario
    scenario = Scenario(
        description="30-day forecast from 2023-04-01 (post-Drax closure)",
        start_date="2023-04-01",
        end_date="2023-04-30",
        regions=["UK_Yorkshire", "UK_SouthEast"],
        parameters={
            "UK_Yorkshire": params_yorkshire,
            "UK_SouthEast": params_southeast,
        },
        coupling_matrix={
            ("UK_Yorkshire", "UK_SouthEast"): 0.001,  # Yorkshire -> SE
            ("UK_SouthEast", "UK_Yorkshire"): 0.0005,  # SE -> Yorkshire
        }
    )
    
    # Run simulation
    runner = SimulationRunner()
    output = runner.run(scenario)
    
    print("✓ Simulation completed successfully")
    print(f"  Scenario: {scenario.description}")
    print(f"  Duration: {scenario.start_date} to {scenario.end_date}")
    print(f"  Regions: {', '.join(scenario.regions)}")
    
    # Validate outputs
    for region, result in output.trajectory.items():
        print(f"\n  {region}:")
        print(f"    Time steps: {len(result.time)}")
        print(f"    State shape: {result.trajectory.shape}")
        assert result.trajectory.shape[0] == len(result.time)
        assert result.trajectory.shape[1] == 6  # S, E, I, H, R, X
        
        # Check that trajectories are physically reasonable
        S, E, I, H, R, X = result.trajectory.T
        assert np.all(S >= 0), "Susceptible went negative"
        assert np.all(E >= 0), "Exposed went negative"
        assert np.all(I >= 0), "Infected went negative"
        assert np.all(H >= 0), "Hospitalized went negative"
        assert np.all(R >= 0), "Recovered went negative"
        assert np.all((X >= 0) & (X <= 1)), "Fossil dependency out of [0,1]"
        
        print(f"    ✓ All state variables within valid ranges")
        print(f"    Initial: S={S[0]:.0f}, E={E[0]:.0f}, I={I[0]:.0f}, H={H[0]:.0f}, R={R[0]:.0f}, X={X[0]:.2f}")
        print(f"    Final:   S={S[-1]:.0f}, E={E[-1]:.0f}, I={I[-1]:.0f}, H={H[-1]:.0f}, R={R[-1]:.0f}, X={X[-1]:.2f}")


if __name__ == "__main__":
    print("=" * 60)
    print("SIMULATION CORE TEST SUITE")
    print("=" * 60)
    
    try:
        print("\n[1/4] Testing ModelParameters creation...")
        test_parameter_creation()
        
        print("\n[2/4] Testing parameter schema...")
        test_schema_validation()
        
        print("\n[3/4] Testing full simulation run...")
        test_simulation_run()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nSimulation core is operational and ready for:")
        print("  - Integration with LLM parameter estimation")
        print("  - Multi-region backtesting (April 2023 - Dec 2024)")
        print("  - Output generation (plots, metrics, validation)")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
