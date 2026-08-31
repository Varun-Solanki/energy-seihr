# EPIGRID Data Sources Explained
This file explains every data/evidence source in EPIGRID: what it contains, how the code reads it, where it is used, and what it currently does not do.

## 1. Big picture
EPIGRID uses sources in three separate ways:
```text
Operational feeds: National Grid + DEFRA + NHS Fingertips
  -> ingestion -> normalized records -> knowledge graph -> retrieval context
Evidence sources: hosted HTML + Tavily cache + graph records
  -> RAG retrieval -> LLM/fallback -> estimated parameters
Validation source: local NHS hospitalization time series
  -> compare real H(t) with simulated H(t)
```
Important: most external sources currently influence the model indirectly through retrieval/LLM context. They are not yet direct time-series inputs to the ODE solver.
## 2. Common source format
`SourcePayload` in `ingestion/base.py` stores raw input before parsing: `source_name`, `source_uri`, optional `local_path`, `content_type`, `raw_text`, and `metadata`.
`NormalizedRecord` is the standard parsed form: `source_name`, `record_type`, `period`, `region`, `value`, `unit`, and `metadata`.
This is normalization: different APIs/files are converted into one common shape so the graph/retriever can handle them consistently. The orchestrator is `IngestionPipeline` in `ingestion/pipeline.py`.

## 3. National Grid carbon-intensity and generation-mix data
What it contains: electricity carbon intensity and generation mix. Carbon intensity means grams of CO2 per kWh of electricity. Generation mix means the percentage share from fuels such as gas, coal, wind, solar, nuclear, and biomass.
Code path: `ingestion/national_grid.py`.
Expected input: JSON with `data[]`. Each item may contain `from`, `to`, `region` or `shortname`, `intensity.actual`, `intensity.forecast`, and `generationmix[]` with `fuel` and `perc`.
Normalized output: carbon-intensity rows become `record_type = intensity`, unit `gco2_per_kwh`; fuel-share rows become `record_type = generation_mix`, unit `percent`; fuel type and actual/forecast status go into metadata.
Where used: records can enter the knowledge graph, be retrieved by region, and be passed to the LLM parameter estimator. Fossil dependence, coal/gas reliance, and closure/phase-out evidence can adjust `beta_base`, `beta_sensitivity`, and `kappa`.
Meaning for the model: this source should eventually help derive or validate the fossil/pollution score `X`.
Current limitation: the solver does not directly convert National Grid carbon intensity or fuel percentage into `X`. `X` is still an abstract 0-to-1 state controlled by parameters and equations.
Checks needed: map grid regions to EPIGRID regions, separate actual from forecast values, align dates, document units, and create a real formula from energy data to `X`.
## 4. DEFRA PM2.5 data
What it contains: PM2.5 air-pollution data. PM2.5 means fine particulate matter up to 2.5 micrometres in diameter, usually measured in micrograms per cubic metre.
Why it matters: PM2.5 is the physical bridge between energy emissions and health effects. Fossil fuel combustion can raise PM2.5, and PM2.5 exposure is linked to respiratory and cardiovascular harm.
Code path: `ingestion/defra.py`.
Expected input: CSV. The parser currently assumes first column = `period`, second column = `region`, last column = PM2.5 value. It stores the unit as `ugm-3`.
Where used: normalized PM2.5 records can enter the graph, support RAG retrieval, and influence LLM/fallback parameter estimation. Higher PM2.5/pollution evidence can raise `beta_base` and `beta_sensitivity`.
Declared model connection: `pollution_lag_days` is meant to represent delay between pollution exposure and health effect.
Current limitation: the ODE solver does not read a real PM2.5 time series, does not compute `X` from PM2.5, and does not apply `pollution_lag_days` as an actual delay.
Checks needed: use named CSV columns instead of positions, validate date format, validate units, handle missing values, and confirm the region matches the simulated region.

## 5. NHS Fingertips health indicators
What it contains: public-health indicators from NHS Fingertips, such as regional disease, hospitalization, mortality, deprivation, or respiratory-health measures depending on the selected page/dataset.
Intended model role: provide health context and eventually real ground truth for `H`, the hospitalized/health-burden compartment.
Code path: `ingestion/fingertips.py`.
Current parser behavior: fetches an HTML page, strips tags, and creates one `health_indicator` record with `period = unknown`, `region = None`, `value = None`, `unit = None`, plus a 500-character text preview in metadata.
Where used: mainly graph/retrieval context. It is not currently a numeric hospitalization feed.
Validation path: `validation/backtester.py` expects `data/ground_truth/NHS_hospitalization_<region>.json` containing `hospitalization_timeseries`.
Current limitation: no real NHS ground-truth JSON files are present. If missing, the backtester generates synthetic hospitalization data from a baseline, seasonality, an intervention effect, and random noise. That only tests code flow; it is not real validation.
Choice required before real use: define exactly what `H` means: daily respiratory admissions, weekly COPD/asthma admissions, all respiratory hospitalizations, rate per 100,000, occupied beds, etc. Counts and rates cannot be compared without conversion.

## 6. Static initial values and defaults
Source file: `math/initial_values.json`.
What it contains: starting states for Yorkshire and South East: `s0`, `e0`, `i0`, `h0`, `r0`, `x0`, plus default parameters such as `beta_base`, `sigma`, `kappa`, and `pollution_lag_days`.
Where used: `ParameterEstimator` reads these defaults; `SimulationRunner` uses the six starting values as the initial state for each region.
Meaning: these values start the simulation directly, unlike most external sources.
Current limitation: the file has no field-level provenance. It does not say which dataset, date, method, or transformation produced each starting number.

## 7. Local hosted evidence documents
Source folder: `hosted-data/`.
Files and use:
| File | What it contributes | Current use |
| --- | --- | --- |
| `who-air-quality-guidelines.html` | PM2.5 health guidance | retrieval context |
| `pm25-source-sector-mortality.html` | PM2.5 sources and mortality burden | energy-to-health rationale |
| `influenza-epidemic-model.html` | compartment-model background | supports SEIHR structure |
| `coal-power-burden-germany.html` | coal-power health burden example | policy/coal context, not UK-specific evidence |
| `clean-air-strategy-2019.html` | UK clean-air policy | policy and `kappa` context |
Code path: `rag/retriever.py`.
Retrieval behavior: the retriever splits a query into terms longer than three characters, counts keyword matches in local HTML files, keeps the top five, extracts snippets, and sends them to the LLM.
Current limitation: this is keyword retrieval. It does not prove source quality, date relevance, regional applicability, or causality.

## 8. Knowledge graph
Code path: `knowledge_graph/`.
What it is: a derived structure built from normalized records. It creates nodes for records and regions, then connects records to regions.
Extra built-in nodes: Drax closure, UK coal phase-out, PM2.5-health link, and a `DOWNWIND_OF` relation from Yorkshire to South East.
Where used: graph records are retrieved by region and passed as structured context to the LLM.
Current limitation: the graph stores relationships and provenance. It does not calculate causal effects or automatically change the ODE equations. Default causal links are manually authored assumptions.

## 9. Tavily search cache
Source folder: `data/retrieval_cache/`.
What it contains: cached web-search snippets for each scenario/region. Typical queries combine region, energy policy, coal/gas/renewables/decarbonization, NHS hospitalization, respiratory health, air quality, pollution, and PM2.5.
Where used: cached titles, URLs, snippets, and scores are merged with local evidence and graph context, then sent to the LLM estimator.
Current limitation: snippets do not directly populate `X`, `H`, or any ODE state.
Historical-risk warning: existing cache timestamps are from 2026 while the Drax study period is 2023-2024. A historical backtest must avoid future-data leakage by using only sources available before the prediction cut-off date.

## 10. OpenRouter / LLM
What it is: a processing service, not a factual data source.
Where used: `llm/llama_client.py` and parameter-estimation flow.
What it does: reads retrieved evidence and returns JSON parameter proposals. Fossil/PM2.5 evidence can raise exposure-related parameters, closure/phase-out evidence can raise `kappa`, and hospital evidence can affect `lambda_rate`.
Validation: the parameter schema checks required fields, numeric types, and min/max bounds.
Current limitation: schema validation only checks shape and allowed ranges. It does not prove that the estimated parameters are statistically correct.
Fallback behavior: if the LLM is unavailable, deterministic keyword rules adjust defaults using words like `coal`, `gas`, `closure`, `pollution`, and `hospital`.

## 11. Literature sources named in the PDF
These justify the project idea but are not fully ingested as raw datasets:
| Source family | Role | Current direct use |
| --- | --- | --- |
| WHO Global Air Quality Guidelines | PM2.5 health guidance | local summary retrieval |
| Harvard PM2.5 research | exposure-health evidence | conceptual/search context |
| DEFRA Clean Air Strategy | UK air-quality policy | local summary retrieval |
| IPCC AR6 | energy-transition framing | no direct import |
| GBD / IHME | pollution disease-burden methods | no direct import |
Meaning: these sources support assumptions. They do not replace dated regional data needed for calibration and validation.

## 12. Source-to-model mapping
| Source | Immediate output | Intended use | Current actual use |
| --- | --- | --- | --- |
| National Grid | intensity + generation-mix records | derive/validate `X` | graph/RAG context |
| DEFRA PM2.5 | PM2.5 records | exposure and lag evidence | graph/RAG context |
| NHS Fingertips | HTML preview | real `H(t)` and health context | non-numeric context |
| initial-values JSON | initial states + defaults | start simulation | direct solver input |
| hosted HTML | evidence snippets | parameter support | LLM context |
| knowledge graph | linked records/events | structured context | LLM context |
| Tavily cache | web snippets | regional policy/health context | LLM context |
| OpenRouter/LLM | parameter JSON | choose parameters | processor, not source |
| synthetic backtest data | artificial `H(t)` | test metrics pipeline | development fallback |

## 13. What must improve for real results
The project needs versioned source files/URLs, exact region mapping, a formula from energy/PM2.5 data to `X`, a precise definition of `H`, real NHS hospitalization time series, real use of pollution lags in the ODE, calibration on one period, testing on a later unseen period, and a provenance table for every parameter.

## Final takeaway
EPIGRID has source-ingestion and retrieval plumbing, but most evidence currently affects the simulation indirectly through context and parameter estimation. The only direct numerical inputs are scenario parameters and hard-coded initial/default values. Real time-aligned data and documented calibration are still the main missing pieces.
