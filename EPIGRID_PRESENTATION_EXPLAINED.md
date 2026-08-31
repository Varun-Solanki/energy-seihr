# EPIGRID Presentation Explained

This is a short guide to `epigrid.pdf`. It covers slides 1-13 and 16-19. Slides 14-15 (software/hardware) and slide 20 (references) are skipped.

## Core idea

EPIGRID is a **coupled energy-health simulation**. It estimates how fossil-fuel dependency may affect pollution-related health burden, and how rising health burden may create pressure for cleaner energy.

It is a **model**, not direct proof that a policy caused a real number of hospitalizations to change. Results depend on equations, assumptions, starting values, and parameters.

## Slides 1-2: Project and problem

The project combines two layers:

- **Health layer**: `S, E, I, H, R`
- **Energy layer**: `X`, a fossil-dependency/pollution-intensity score

The main feedback loop is:

`fossil dependency -> pollution/exposure pressure -> illness/hospitalization -> policy pressure -> lower fossil dependency`

Key terms:

- **PM2.5**: very small air-pollution particles, 2.5 micrometres or smaller, which can harm lungs and cardiovascular health.
- **Transboundary pollution**: pollution from one region affects another region, usually described as upwind to downwind movement.
- **Coupled**: variables affect each other instead of being modeled separately.
- **Delayed effect**: an exposure may affect health later, not immediately.

The project declares delay parameters, but the current solver does not yet apply those delays.

## Slides 3-6: Objectives, comparison, literature, and gaps

EPIGRID aims to:

1. Simulate health and fossil dependency together using ODEs.
2. Compare predictions with historical data through **backtesting**.
3. Use RAG and an LLM to convert policy scenarios into parameters.
4. Compare an intervention with a **counterfactual**.
5. Model multiple linked regions.

**Backtesting** means running the model over a past period and comparing predicted values with observed values. It is needed because a stable mathematical model can still make poor real-world predictions.

A **counterfactual** asks what the model predicts if an event did not happen. For example:

- Intervention: Drax closes.
- Counterfactual: Drax remains open.

The difference is the modelled impact of closure. It is not a directly observed alternate reality.

The research gap is that typical health models, energy models, and air-quality studies usually cover only part of this loop. EPIGRID adds policy feedback and region-to-region transport.

The `299K in 2022` text on slide 3 has no definition or source on the slide. Do not use it until the team verifies what it measures.

## Slide 7: State variables

Each region has this state vector:

`[S, E, I, H, R, X]`

| Symbol | Meaning | Unit/range |
| --- | --- | --- |
| `S` | Susceptible people, who can enter the exposure pathway | people, >= 0 |
| `E` | Exposed people | people, >= 0 |
| `I` | Affected/outpatient people | people, >= 0 |
| `H` | Hospitalized people | people, >= 0 |
| `R` | Recovered people | people, >= 0 |
| `X` | Fossil-dependency/pollution score | 0 to 1 |

Although the slide calls `I` infectious, the code treats it more like an affected outpatient group. It should not automatically be interpreted as a contagious disease state.

The `0` suffix means an initial value: `s0`, `e0`, `i0`, `h0`, `r0`, and `x0` are the values at day 0.

## Slides 8, 11, and 13: System workflow

`scenario -> retrieval -> LLM parameter estimation -> validation -> RK4 simulation -> plots/results`

1. **Scenario**: the user writes a request, such as "close gas plants in Yorkshire by 2027." The current parser mainly detects the region and year from keywords.
2. **RAG retrieval**: RAG means Retrieval-Augmented Generation. The system collects relevant local documents, cached search results, optional web results, and graph context before asking the LLM for parameters.
3. **Knowledge graph**: a network of nodes (regions, events, records) and edges (relationships such as `DOWNWIND_OF`). It provides structured context; it is not the simulation itself.
4. **LLM estimation**: the LLM proposes parameter values based on the scenario and retrieved context. If unavailable, a deterministic keyword-based fallback is used. Deterministic means the same input gives the same output.
5. **Validation**: values are converted, bounded, and completed with defaults before simulation.
6. **Simulation/output**: RK4 calculates daily values, then the system produces trajectories and scenario comparisons.

## Slide 9: Multi-region dynamics

Each region is a node in a spatial network. A **coupling matrix** stores the strength and direction of influence, for example:

`(UK_Yorkshire, UK_SouthEast): 0.001`

This means Yorkshire can influence the South East. The reverse value can be different.

The code applies incoming cross-region exposure pressure and pollution influence. `transboundary_lag_days` is declared as the intended travel delay, but it is not currently used by the solver.

## Slide 10: Equations

An **ODE** (ordinary differential equation) describes a rate of change. `dH/dt`, for example, means how quickly the hospitalized count changes per day.

### Exposure rate

```text
beta(X) = beta_base * (1 + beta_sensitivity * (X - 0.5))
local_exposure = beta(X) * S * I / N
N = S + E + I + H + R
```

`beta_base` is the base exposure rate. `beta_sensitivity` controls how much fossil dependency changes that rate. Higher `X` usually gives higher exposure pressure.

### Health states

Let `T` mean incoming transboundary exposure.

```text
dS/dt = -local_exposure - T + omega * R
dE/dt =  local_exposure + T - sigma * E
dI/dt =  sigma * E - gamma * I - eta * I
dH/dt =  eta * I - rho * H
dR/dt =  gamma * I + rho * H - omega * R
```

- `S -> E`: local or incoming exposure.
- `E -> I`: progression to affected state.
- `I -> R`: outpatient recovery.
- `I -> H`: hospital admission.
- `H -> R`: hospital discharge/recovery.
- `R -> S`: loss of temporary protection.

### Fossil-dependency state

```text
dX/dt = -kappa * X - lambda_rate * (H / N) + pollution_inflow
pollution_inflow = transboundary_pollution * phi_transport
```

- `kappa`: baseline rate of fossil-dependency reduction.
- `lambda_rate`: strength of health-to-policy feedback.
- `H/N`: hospitalization share of the modelled population.
- `phi_transport`: strength of incoming regional pollution influence.

### RK4 solver

**RK4** (fourth-order Runge-Kutta) turns these rate equations into daily values. It estimates the slope four times during each day and combines them, making it more accurate than a single start-of-day estimate.

## Slide 12: Validation and clamping

The schema defines 22 parameters, their types, and allowed ranges. This prevents an LLM value from making the solver unstable or meaningless.

**Clamping** means forcing a value into the allowed range:

- `beta_base = 4` becomes `2`.
- `omega = -1` becomes `0`.
- `transboundary_lag_days = 999.1` becomes `365` after rounding.

The validation process:

1. Reads LLM JSON and maps aliases such as `lambda` to `lambda_rate`.
2. Converts values to number/integer/string as required.
3. Applies minimum and maximum values.
4. Uses defaults for missing required fields when available.
5. Keeps population states non-negative and `X` between 0 and 1.

Clamping prevents a software failure. It does not prove that an estimated value is scientifically correct.

## Slide 16: Data ingestion and knowledge graph

The data path is:

`National Grid energy data + DEFRA PM2.5 data + NHS indicators -> normalization -> NormalizedRecord -> NetworkX graph`

**Ingestion** means collecting data. **Normalization** means converting different formats such as JSON, CSV, and HTML into the same record structure:

```text
source_name, record_type, period, region, value, unit, metadata
```

NetworkX is the Python library used to create the graph. The graph links records and regions to support retrieval. Real-data ingestion exists in part, but real-data calibration is not complete.

## Slide 17: Drax results

The slide compares a Drax closure run with a no-closure counterfactual.

| Region | Closure | No closure | Reported reduction |
| --- | ---: | ---: | ---: |
| Yorkshire | 5,189 | 17,720 | 70.70% |
| South East | 26,876 | 31,853 | 15.60% |

```text
reduction % = (counterfactual H - intervention H) / counterfactual H * 100
```

The graph's horizontal axis is time; the vertical axis is the modelled hospitalized count `H`. A lower closure curve means fewer hospitalizations under the closure assumptions.

These values are illustrative model outputs, not verified historical findings. There is also a date mismatch: the PDF says April 2023-December 2024, while `scripts/scenario_builder.py` uses April-December 2023 for its 275-day run. This should be corrected before formal presentation.

## Slides 18-19: Completed, in-progress, and to-do work

Implemented modules include the parameter schema, RK4 solver, current transboundary equations, ingestion clients, graph builder, RAG retriever, LLM integration, clamping, plots, and basic tests.

Still needed:

- **Real ground-truth backtesting** against date-matched NHS data. The current backtester uses synthetic data when a local real-data file is absent.
- **Calibration optimization**: repeatedly adjust parameters, run the model, and minimize error against training data.
- **Graph weight adjustment**: the `WeightAdjuster` is currently a placeholder.
- **Interactive dashboard**: useful for presentation, but it does not improve scientific accuracy.

Backtesting metrics in the code:

| Metric | Meaning |
| --- | --- |
| MSE | Average squared error; penalizes large mistakes strongly |
| RMSE | Square root of MSE; expressed in hospitalizations |
| MAE | Average absolute error; typical error size |
| R-squared | Fit to variation in observed data; 1 is perfect, 0 is weak, negative is worse than average prediction |
| Peak error | Largest absolute prediction error and its day |

If observed and simulated series have different lengths, the code uses **interpolation**, which estimates in-between values to compare them point by point. Dates and data frequency still need to match correctly.

## All parameters

| Group | Parameters | Purpose | Current status |
| --- | --- | --- |
| Identity | `region` | Region name | used |
| Health rates | `beta_base`, `sigma`, `gamma`, `eta`, `rho`, `omega` | Exposure and movement between health states | used |
| Fossil response | `beta_sensitivity`, `kappa`, `lambda_rate` | Effect of `X`, decarbonisation, health-policy feedback | used |
| Regional transport | `psi_transport`, `phi_transport` | Cross-region exposure and pollution effects | used |
| Initial state | `s0`, `e0`, `i0`, `h0`, `r0`, `x0` | Starting values at day 0 | used |
| Intended future terms | `x_scale`, `transboundary_lag_days`, `pollution_lag_days`, `policy_response_days` | Scale and time delays | declared, not applied in current solver |

## Final takeaway

EPIGRID has a working scenario-to-simulation software pipeline. Its main remaining scientific work is to implement the declared delays, ingest aligned real UK data, calibrate parameters, and perform genuine out-of-sample backtesting. Until then, present its outputs as **illustrative scenarios**, not measured evidence of policy impact.
