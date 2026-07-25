# Quick Start: Simulation Core

## Installation & Setup

```bash
# Navigate to project
cd energy-seihr

# (Optional) Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

## Run Tests

```bash
# Full test suite
python scripts/test_simulation_core.py

# Expected output: ✓ ALL TESTS PASSED
```

## Run Standard Scenarios

```bash
# Drax closure + counterfactual comparison
python scripts/scenario_builder.py

# Shows impact: -70.7% Yorkshire, -15.6% South East hospitalizations
```

## Create Custom Scenario (Python API)

```python
from core.parameters import ModelParameters
from core.runner import Scenario, SimulationRunner

# 1. Define parameters
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
)

# 2. Create scenario
scenario = Scenario(
    description="My scenario",
    start_date="2023-01-01",
    end_date="2023-12-31",
    regions=["UK_Yorkshire"],
    parameters={"UK_Yorkshire": params},
    coupling_matrix={}  # No coupling if single region
)

# 3. Run simulation
runner = SimulationRunner()
output = runner.run(scenario)

# 4. Extract results
trajectory = output.trajectory["UK_Yorkshire"]
time_grid = trajectory.time  # numpy array
states = trajectory.trajectory  # (T × 6) array

# 5. Access individual variables
S, E, I, H, R, X = states.T
print(f"Final hospitalized: {H[-1]:.0f}")
print(f"Final fossil dependency: {X[-1]:.2f}")
```

## Key Files

| File | Purpose |
|------|---------|
| `core/parameters.py` | Parameter dataclass (22 fields) |
| `core/runner.py` | Simulation orchestration & ODEs |
| `core/ode_engine.py` | RK4 solver (unchanged) |
| `math/initial_values.json` | Initial conditions |
| `contracts/parameter_schema.json` | Parameter validation schema |
| `scripts/test_simulation_core.py` | Test suite |
| `scripts/scenario_builder.py` | Standard scenarios |

## Parameter Ranges

| Parameter | Min | Max | Typical | Unit |
|-----------|-----|-----|---------|------|
| beta_base | 0 | 2 | 0.5 | 1/days |
| sigma | 0 | 1 | 0.2 | 1/days |
| gamma | 0 | 1 | 0.1 | 1/days |
| eta | 0 | 1 | 0.05 | 1/days |
| rho | 0 | 1 | 0.1 | 1/days |
| omega | 0 | 0.1 | 0.01 | 1/days |
| beta_sensitivity | 0 | 5 | 1.0 | dimensionless |
| kappa | 0 | 0.1 | 0.01 | 1/days |
| lambda_rate | 0 | 0.2 | 0.05 | 1/days |
| X₀ | 0 | 1 | 0.25-0.35 | dimensionless |
| S₀ | 1000 | 10M | region-specific | population |

## State Variables

| Variable | Meaning | Unit | Bounds |
|----------|---------|------|--------|
| S | Susceptible | people | ≥ 0 |
| E | Exposed | people | ≥ 0 |
| I | Infected/affected | people | ≥ 0 |
| H | Hospitalized | people | ≥ 0 |
| R | Recovered | people | ≥ 0 |
| X | Fossil dependency | 0-1 scale | [0, 1] |

## Output Format

```python
output.trajectory[region]  # type: SimulationResult
  .time                     # numpy array, shape (T,)
  .trajectory               # numpy array, shape (T, 6)
```

## Troubleshooting

**Import error: "No module named 'core'"**
```bash
# Make sure you're in the project root:
cd energy-seihr

# And run with PYTHONPATH set:
export PYTHONPATH=.
python scripts/test_simulation_core.py
```

**NaN or infinite values in output**
- Check initial conditions (s0, e0, etc.) are positive
- Check parameters are within schema bounds
- Check N = S + E + I + R > 0 (population non-zero)

**Simulation too slow**
- Reduce date range (fewer days = faster)
- Reduce number of regions
- Use coarser time grid (but may lose accuracy)

## Next Steps

1. **Phase 4**: Integrate Tavily + OpenRouter to estimate parameters from LLM
2. **Phase 5**: Run backtesting (Apr 2023 - Dec 2024) against NHS data
3. **Phase 6**: Generate plots, validation table, transboundary analysis

## Resources

- Equations: [math/equations.md](math/equations.md)
- Implementation Details: [SIMULATION_CORE_STATUS.md](SIMULATION_CORE_STATUS.md)
- Complete Overview: [PHASE_3_SUMMARY.md](PHASE_3_SUMMARY.md)
- Operational Checklist: [OPERATIONAL_CHECKLIST.md](OPERATIONAL_CHECKLIST.md)

