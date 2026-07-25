# energy-seihr

Dual-layer SEIHR framework for simulating interdependencies between energy generation and public health.

## MVP scope
- Data-driven ingestion from National Grid carbon intensity, DEFRA PM2.5, and NHS Fingertips
- Knowledge graph built from sourced records
- OpenRouter chat model for retrieval-guided parameter estimation
- RK4-based coupled ODE simulation
- Backtesting against the April 2023 to December 2024 period

## Run a Scenario

```bash
python scripts/run_scenario.py "close all gas plants in Yorkshire by 2027"
```

The command runs retrieval, parameter estimation, coupled RK4 simulation,
counterfactual comparison, and output generation. Results are written under:

- `outputs/trajectories/`
- `outputs/plots/`
- `outputs/results/`

If Tavily or OpenRouter is unavailable, the runner falls back to local hosted
paper context plus deterministic parameter estimates so the terminal workflow
still completes. Set `TAVILY_API_KEY`, `OPENROUTER_API_KEY`,
`OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`, and optionally
`OPENROUTER_MODEL=openai/gpt-4o-mini` in `.env` for live retrieval and LLM
estimation.

## Status
Terminal MVP path implemented. Ground-truth validation still depends on adding
real local NHS/National Grid backtest files.
