from llm.llama_client import LlamaClient
from llm.validator import ParameterValidator


def test_llm_parser_normalizes_aliases_and_rationale() -> None:
    client = LlamaClient()

    parsed = client._parse_parameters(
        '{"rationale":"evidence used","beta_base":0.4,"lambda":0.07,"psi":0.002,"phi":0.003}'
    )

    assert parsed["beta_base"] == 0.4
    assert parsed["lambda_rate"] == 0.07
    assert parsed["psi_transport"] == 0.002
    assert parsed["phi_transport"] == 0.003
    assert client.last_rationale == "evidence used"


def test_parameter_validator_clamps_schema_bounds() -> None:
    validator = ParameterValidator()

    params = validator.validate(
        {"beta_base": 4, "omega": -1, "transboundary_lag_days": 999.1},
        defaults={"region": "UK_Yorkshire", "sigma": 0.2},
    )

    assert params["beta_base"] == 2
    assert params["omega"] == 0
    assert params["transboundary_lag_days"] == 365
    assert params["region"] == "UK_Yorkshire"
