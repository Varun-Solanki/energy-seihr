import numpy as np

from core.parameters import ModelParameters
from core.runner import Scenario, SimulationRunner


def _params(region: str, x0: float, s0: float = 10000) -> ModelParameters:
    return ModelParameters(
        region=region,
        beta_base=0.35,
        sigma=0.2,
        gamma=0.1,
        eta=0.03,
        rho=0.12,
        omega=0.004,
        beta_sensitivity=0.8,
        x_scale=0.5,
        kappa=0.005,
        lambda_rate=0.02,
        psi_transport=0.002,
        phi_transport=0.002,
        transboundary_lag_days=30,
        s0=s0,
        e0=100,
        i0=50,
        h0=10,
        r0=500,
        x0=x0,
        pollution_lag_days=90,
        policy_response_days=180,
    )


def test_runner_bounds_state_and_x() -> None:
    scenario = Scenario(
        description="bounds check",
        start_date="2026-01-01",
        end_date="2026-02-01",
        regions=["UK_Yorkshire"],
        parameters={"UK_Yorkshire": _params("UK_Yorkshire", 0.9)},
    )

    result = SimulationRunner().run(scenario).trajectory["UK_Yorkshire"].trajectory

    assert np.all(result[:, :5] >= 0)
    assert np.all((result[:, 5] >= 0) & (result[:, 5] <= 1))


def test_joint_coupling_changes_downwind_trajectory() -> None:
    regions = ["UK_Yorkshire", "UK_SouthEast"]
    parameters = {
        "UK_Yorkshire": _params("UK_Yorkshire", 0.8),
        "UK_SouthEast": _params("UK_SouthEast", 0.2, s0=12000),
    }
    base = Scenario(
        description="no coupling",
        start_date="2026-01-01",
        end_date="2026-03-01",
        regions=regions,
        parameters=parameters,
        coupling_matrix={},
    )
    coupled = Scenario(
        description="coupled",
        start_date="2026-01-01",
        end_date="2026-03-01",
        regions=regions,
        parameters=parameters,
        coupling_matrix={("UK_Yorkshire", "UK_SouthEast"): 0.02},
    )

    runner = SimulationRunner()
    base_h = runner.run(base).trajectory["UK_SouthEast"].trajectory[:, 3]
    coupled_h = runner.run(coupled).trajectory["UK_SouthEast"].trajectory[:, 3]

    assert not np.allclose(base_h, coupled_h)
    assert coupled_h.sum() > base_h.sum()
