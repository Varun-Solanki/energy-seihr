from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from config.settings import settings
from core.parameter_estimator import ParameterEstimator
from core.parameters import ModelParameters
from core.runner import Scenario, SimulationRunner


STATE_NAMES = ["S", "E", "I", "H", "R", "X"]


def main() -> None:
    args = parse_args()
    scenario_text = args.scenario
    from llm.llama_client import LlamaClient
    client = LlamaClient()
    target_region, companion_region = client.resolve_regions(scenario_text)
    regions = [target_region, companion_region]
    start_date = args.start_date or date.today().isoformat()
    end_date = args.end_date or infer_end_date(scenario_text, start_date)
    slug = slugify(scenario_text)

    ensure_default_graph(settings.outputs_dir / "knowledge_graph.gexf")

    estimator = ParameterEstimator()
    parameters: dict[str, ModelParameters] = {}
    for region in regions:
        params = estimator.estimate_for_scenario(
            region=region,
            scenario_description=scenario_text,
            start_date=start_date,
            end_date=end_date,
            use_cache=not args.refresh_retrieval,
        )
        if region != target_region:
            params = dampen_non_target_policy_response(params)
        parameters[region] = params

    scenario = Scenario(
        description=scenario_text,
        start_date=start_date,
        end_date=end_date,
        regions=regions,
        parameters=parameters,
        coupling_matrix=default_coupling_matrix(regions),
    )

    runner = SimulationRunner()
    output = runner.run(scenario)

    counterfactual = Scenario(
        description=f"Counterfactual: no intervention for {scenario_text}",
        start_date=start_date,
        end_date=end_date,
        regions=regions,
        parameters={region: counterfactual_parameters(params, region == target_region) for region, params in parameters.items()},
        coupling_matrix=default_coupling_matrix(regions, counterfactual=True),
    )
    counterfactual_output = runner.run(counterfactual)

    artifact_paths = write_outputs(
        slug=slug,
        scenario=scenario,
        output=output,
        counterfactual=counterfactual,
        counterfactual_output=counterfactual_output,
        target_region=target_region,
        trace=estimator.last_trace,
    )

    print_summary(scenario, output, counterfactual_output, target_region, artifact_paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an energy-health SEIHR scenario.")
    parser.add_argument("scenario", help="Plain-language scenario, e.g. 'close all gas plants in Yorkshire by 2027'")
    parser.add_argument("--start-date", help="Simulation start date, YYYY-MM-DD")
    parser.add_argument("--end-date", help="Simulation end date, YYYY-MM-DD")
    parser.add_argument("--refresh-retrieval", action="store_true", help="Ignore Tavily retrieval cache")
    return parser.parse_args()


def infer_region(text: str) -> str:
    lowered = text.lower()
    if "south east" in lowered or "southeast" in lowered:
        return "UK_SouthEast"
    if "yorkshire" in lowered:
        return "UK_Yorkshire"
    return settings.default_region


def ordered_regions(target_region: str) -> list[str]:
    companion = "UK_SouthEast" if target_region != "UK_SouthEast" else "UK_Yorkshire"
    return [target_region, companion]


def infer_end_date(text: str, start_date: str) -> str:
    match = re.search(r"\b(?:by|in|before)\s+(20\d{2})\b", text.lower())
    if match:
        return f"{match.group(1)}-12-31"
    start = datetime.fromisoformat(start_date).date()
    return (start + timedelta(days=365 * settings.default_simulation_years)).isoformat()


def default_coupling_matrix(regions: list[str], counterfactual: bool = False) -> dict[tuple[str, str], float]:
    base = 0.0015 if counterfactual else 0.001
    reverse = 0.0002
    return {
        (regions[0], regions[1]): base,
        (regions[1], regions[0]): reverse,
    }


def dampen_non_target_policy_response(params: ModelParameters) -> ModelParameters:
    return replace(params, kappa=min(params.kappa, 0.012), source_metadata={**params.source_metadata, "policy_role": "downwind_region"})


def counterfactual_parameters(params: ModelParameters, is_target: bool) -> ModelParameters:
    if not is_target:
        return params
    return replace(
        params,
        beta_base=min(params.beta_base + 0.05, 2.0),
        beta_sensitivity=min(params.beta_sensitivity + 0.15, 5.0),
        kappa=min(params.kappa, 0.006),
        lambda_rate=min(params.lambda_rate, 0.04),
        x0=min(params.x0 + 0.08, 1.0),
        source_metadata={**params.source_metadata, "counterfactual": "no closure or accelerated phase-out"},
    )


def ensure_default_graph(path: Path) -> None:
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    graph = nx.DiGraph()
    graph.add_node("region::UK_Yorkshire", kind="Region", label="UK_Yorkshire", region="UK_Yorkshire")
    graph.add_node("region::UK_SouthEast", kind="Region", label="UK_SouthEast", region="UK_SouthEast")
    graph.add_node(
        "event::drax_closure_2023",
        kind="EnergyEvent",
        label="Drax coal unit closure 2023",
        region="UK_Yorkshire",
        value="coal generation reduction",
        unit="policy_event",
    )
    graph.add_node(
        "event::uk_coal_phaseout_2024",
        kind="PolicyEvent",
        label="UK coal phase-out completed 2024",
        region="UK_Yorkshire",
        value="coal phase-out",
        unit="policy_event",
    )
    graph.add_node(
        "event::pm25_health_link",
        kind="HealthEvent",
        label="PM2.5 linked respiratory and cardiovascular admissions",
        region="UK_Yorkshire",
        value="hospitalization pressure",
        unit="health_event",
    )
    graph.add_edge("event::uk_coal_phaseout_2024", "event::drax_closure_2023", kind="TRIGGERED", lag_days=0)
    graph.add_edge("event::drax_closure_2023", "event::pm25_health_link", kind="PRECEDED", lag_days=90)
    graph.add_edge("event::drax_closure_2023", "region::UK_Yorkshire", kind="DERIVED_FROM", relation="region")
    graph.add_edge("event::pm25_health_link", "region::UK_Yorkshire", kind="DERIVED_FROM", relation="region")
    graph.add_edge("region::UK_Yorkshire", "region::UK_SouthEast", kind="DOWNWIND_OF", weight=0.001)
    nx.write_gexf(graph, path)


def write_outputs(
    slug: str,
    scenario: Scenario,
    output,
    counterfactual: Scenario,
    counterfactual_output,
    target_region: str,
    trace: dict[str, Any],
) -> dict[str, str]:
    trajectories_dir = settings.outputs_dir / "trajectories"
    plots_dir = settings.outputs_dir / "plots"
    results_dir = settings.outputs_dir / "results"
    for directory in [trajectories_dir, plots_dir, results_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    trajectory_path = trajectories_dir / f"{slug}.json"
    comparison_path = trajectories_dir / f"{slug}_counterfactual.json"
    trace_path = results_dir / f"{slug}_retrieval_trace.json"
    parameter_path = results_dir / f"{slug}_parameter_estimates.json"
    trajectory_plot = plots_dir / f"{slug}_trajectory.png"
    comparison_plot = plots_dir / f"{slug}_comparison.png"
    transboundary_plot = plots_dir / f"{slug}_transboundary.png"

    write_json(trajectory_path, serialize_run(scenario, output))
    write_json(comparison_path, serialize_run(counterfactual, counterfactual_output))
    write_json(
        trace_path,
        {
            "scenario": scenario.description,
            "target_region": target_region,
            "impact_summary": impact_summary(output, counterfactual_output, target_region),
            "trace": trace,
        },
    )
    write_json(parameter_path, {region: params.to_dict() for region, params in scenario.parameters.items()})

    plot_trajectory(output, target_region, trajectory_plot)
    plot_comparison(output, counterfactual_output, target_region, comparison_plot)
    plot_transboundary(output, scenario.regions, transboundary_plot)

    return {
        "trajectory_json": str(trajectory_path),
        "counterfactual_json": str(comparison_path),
        "retrieval_trace": str(trace_path),
        "parameter_estimates": str(parameter_path),
        "trajectory_plot": str(trajectory_plot),
        "comparison_plot": str(comparison_plot),
        "transboundary_plot": str(transboundary_plot),
    }


def serialize_run(scenario: Scenario, output) -> dict[str, Any]:
    start = datetime.fromisoformat(scenario.start_date).date()
    payload: dict[str, Any] = {
        "description": scenario.description,
        "start_date": scenario.start_date,
        "end_date": scenario.end_date,
        "regions": scenario.regions,
        "coupling_matrix": {f"{source}->{target}": value for (source, target), value in scenario.coupling_matrix.items()},
        "trajectories": {},
    }
    for region, result in output.trajectory.items():
        rows = []
        for index, values in enumerate(result.trajectory):
            row = {"date": (start + timedelta(days=int(result.time[index]))).isoformat()}
            row.update({name: float(value) for name, value in zip(STATE_NAMES, values)})
            rows.append(row)
        payload["trajectories"][region] = rows
    return payload


def plot_trajectory(output, target_region: str, path: Path) -> None:
    result = output.trajectory[target_region]
    S, E, I, H, R, X = result.trajectory.T
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(result.time, E, label="Exposed")
    axes[0].plot(result.time, I, label="Affected")
    axes[0].plot(result.time, H, label="Hospitalized")
    axes[0].plot(result.time, R, label="Recovered")
    axes[0].set_ylabel("People")
    axes[0].legend(loc="best")
    axes[0].grid(alpha=0.25)
    axes[1].plot(result.time, X, color="#2f6f4e", label="Fossil dependency X")
    axes[1].set_ylabel("X")
    axes[1].set_xlabel("Days")
    axes[1].set_ylim(-0.02, 1.02)
    axes[1].legend(loc="best")
    axes[1].grid(alpha=0.25)
    fig.suptitle(f"SEIHR-X trajectory: {target_region}")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_comparison(output, counterfactual_output, target_region: str, path: Path) -> None:
    actual = output.trajectory[target_region]
    counterfactual = counterfactual_output.trajectory[target_region]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(actual.time, actual.trajectory[:, 3], label="Scenario")
    ax.plot(counterfactual.time, counterfactual.trajectory[:, 3], label="Counterfactual", linestyle="--")
    ax.set_title(f"Hospitalization comparison: {target_region}")
    ax.set_xlabel("Days")
    ax.set_ylabel("Hospitalized")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_transboundary(output, regions: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    for region in regions:
        result = output.trajectory[region]
        ax.plot(result.time, result.trajectory[:, 3], label=region)
    ax.set_title("Transboundary health effect")
    ax.set_xlabel("Days")
    ax.set_ylabel("Hospitalized")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def impact_summary(output, counterfactual_output, target_region: str) -> dict[str, float]:
    scenario_h = output.trajectory[target_region].trajectory[:, 3]
    counterfactual_h = counterfactual_output.trajectory[target_region].trajectory[:, 3]
    scenario_burden = float(scenario_h.sum())
    counterfactual_burden = float(counterfactual_h.sum())
    avoided_burden = counterfactual_burden - scenario_burden
    avoided_pct = (avoided_burden / counterfactual_burden * 100) if counterfactual_burden else 0.0
    return {
        "scenario_final_hospitalized": float(scenario_h[-1]),
        "counterfactual_final_hospitalized": float(counterfactual_h[-1]),
        "scenario_peak_hospitalized": float(scenario_h.max()),
        "counterfactual_peak_hospitalized": float(counterfactual_h.max()),
        "scenario_hospital_days": scenario_burden,
        "counterfactual_hospital_days": counterfactual_burden,
        "avoided_hospital_days": avoided_burden,
        "avoided_hospital_days_percent": avoided_pct,
    }


def print_summary(
    scenario: Scenario,
    output,
    counterfactual_output,
    target_region: str,
    artifact_paths: dict[str, str],
) -> None:
    print("\n" + "=" * 70)
    print("SCENARIO COMPLETE")
    print("=" * 70)
    print(f"Scenario: {scenario.description}")
    print(f"Dates: {scenario.start_date} to {scenario.end_date}")
    print(f"Regions: {', '.join(scenario.regions)}")

    for region in scenario.regions:
        result = output.trajectory[region]
        S, E, I, H, R, X = result.trajectory.T
        print(f"\n{region}")
        print(f"  Hospitalized: {H[0]:.0f} -> {H[-1]:.0f}")
        print(f"  Fossil dependency X: {X[0]:.3f} -> {X[-1]:.3f}")

    impact = impact_summary(output, counterfactual_output, target_region)
    print(f"\nTarget impact ({target_region})")
    print(f"  Counterfactual peak H:       {impact['counterfactual_peak_hospitalized']:.0f}")
    print(f"  Scenario peak H:             {impact['scenario_peak_hospitalized']:.0f}")
    print(f"  Counterfactual hospital-days:{impact['counterfactual_hospital_days']:.0f}")
    print(f"  Scenario hospital-days:      {impact['scenario_hospital_days']:.0f}")
    print(
        "  Avoided hospital-days:       "
        f"{impact['avoided_hospital_days']:.0f} ({impact['avoided_hospital_days_percent']:.1f}%)"
    )
    print(f"  Final H, scenario/counterfactual: {impact['scenario_final_hospitalized']:.0f} / {impact['counterfactual_final_hospitalized']:.0f}")

    print("\nArtifacts")
    for label, path in artifact_paths.items():
        print(f"  {label}: {path}")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug[:80] or "scenario"


if __name__ == "__main__":
    main()
