"""
Phase 4: Parameter Estimation & Backtesting
Orchestrates: Retrieval → LLM → Parameters → Simulation → Validation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parameter_estimator import ParameterEstimator
from core.runner import Scenario, SimulationRunner
from validation.backtester import Backtester


def main():
    print("\n" + "=" * 70)
    print("PHASE 4: LLM PARAMETER ESTIMATION & BACKTESTING")
    print("=" * 70)
    
    # Initialize components
    estimator = ParameterEstimator()
    runner = SimulationRunner()
    backtester = Backtester()
    
    # Step 1: Estimate parameters via LLM
    print("\n[STEP 1/4] Estimating parameters via LLM + Retrieval...")
    print("-" * 70)
    
    scenario_description = (
        "Drax coal-fired power plant closure announced April 1, 2023. "
        "Expected to reduce regional fossil fuel dependency and air pollution. "
        "Backtest period: April 2023 - December 2024 (21 months post-closure)."
    )
    
    params_yorkshire = estimator.estimate_for_scenario(
        region="UK_Yorkshire",
        scenario_description=scenario_description,
        start_date="2023-04-01",
        end_date="2024-12-31",
        use_cache=True,
    )
    
    params_southeast = estimator.estimate_for_scenario(
        region="UK_SouthEast",
        scenario_description=scenario_description,
        start_date="2023-04-01",
        end_date="2024-12-31",
        use_cache=True,
    )
    
    # Step 2: Create scenario
    print("\n[STEP 2/4] Creating backtesting scenario...")
    print("-" * 70)
    
    scenario = Scenario(
        description="Drax Closure Backtest (Apr 2023 - Dec 2024)",
        start_date="2023-04-01",
        end_date="2024-12-31",
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
    
    print(f"Scenario created: {len(scenario.regions)} regions, 275 days")
    print(f"Coupling matrix: {len(scenario.coupling_matrix)} edges")
    
    # Step 3: Run simulation
    print("\n[STEP 3/4] Running simulation with LLM-estimated parameters...")
    print("-" * 70)
    
    output = runner.run(scenario)
    print(f"[OK] Simulation complete: {len(output.trajectory)} regions")
    
    for region, result in output.trajectory.items():
        S, E, I, H, R, X = result.trajectory.T
        print(f"\n  {region}:")
        print(f"    Hospitalized: {H[0]:.0f} to {H[-1]:.0f}")
        print(f"    Fossil dependency: {X[0]:.2f} to {X[-1]:.2f}")
    
    # Step 4: Backtest
    print("\n[STEP 4/4] Backtesting against ground truth...")
    print("-" * 70)
    
    backtest_results = []
    for region in scenario.regions:
        result = output.trajectory[region]
        backtest = backtester.backtest(
            region=region,
            scenario="Drax Closure",
            result=result,
            start_date=scenario.start_date,
            end_date=scenario.end_date,
        )
        backtest_results.append(backtest)
        
        print(f"\n  {region}:")
        print(f"    RMSE: {backtest.metrics.rmse:.2f} hospitalizations")
        print(f"    MAE:  {backtest.metrics.mae:.2f} hospitalizations")
        print(f"    R²:   {backtest.metrics.r_squared:.3f}")
        print(f"    Peak error: {backtest.metrics.peak_error:.0f} at day {backtest.metrics.peak_error_time}")
    
    # Generate report
    print("\n" + "=" * 70)
    report_path = backtester.generate_report(backtest_results)
    print(f"Report: {report_path}")
    
    print("\n" + "=" * 70)
    print("PHASE 4 COMPLETE")
    print("=" * 70)
    print("\nNext: Phase 5 - Output Generation (plots, metrics, validation)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
