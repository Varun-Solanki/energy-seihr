from __future__ import annotations

import json
import re

from openai import OpenAI

from config.settings import settings


class LlamaClient:
    """OpenRouter client for SEIHR parameter estimation."""

    def __init__(self) -> None:
        self.client = (
            OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)
            if settings.openrouter_api_key
            else None
        )
        self.model = settings.openrouter_model
        self.last_raw_response = ""
        self.last_rationale = ""

    def estimate_parameters(
        self,
        region: str,
        scenario_description: str,
        retrieval_context: str,
    ) -> dict[str, float]:
        """Estimate SEIHR-energy parameters, with a deterministic offline fallback."""
        print(f"Estimating parameters for {region}...")

        if not self.client:
            print("  - OpenRouter API key not configured; using deterministic fallback")
            return self._fallback_parameters(region, scenario_description, retrieval_context)

        prompt = self._build_estimation_prompt(region, scenario_description, retrieval_context)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You estimate parameters for a coupled SEIHR-energy model. "
                            "Use the provided evidence only and return strict JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=900,
                extra_headers={
                    "HTTP-Referer": settings.openrouter_site_url,
                    "X-Title": settings.openrouter_app_name,
                },
            )
            content = response.choices[0].message.content or ""
            self.last_raw_response = content
            params = self._parse_parameters(content)
            if params:
                print(f"  - OpenRouter returned {len(params)} parameters")
                return params
        except Exception as exc:
            print(f"  - OpenRouter error: {exc}")

        print("  - Falling back to deterministic parameter estimates")
        return self._fallback_parameters(region, scenario_description, retrieval_context)

    def _build_estimation_prompt(
        self,
        region: str,
        scenario_description: str,
        retrieval_context: str,
    ) -> str:
        return f"""
Estimate parameters for a coupled SEIHR-energy public-health model.

REGION: {region}
SCENARIO: {scenario_description}

RETRIEVED CONTEXT:
{retrieval_context}

STATE VARIABLES:
S susceptible, E pollution-exposed/asymptomatic, I affected outpatient,
H hospitalized, R recovered, X fossil dependency / pollution intensity.

PARAMETER BOUNDS:
- beta_base: 0 to 2
- sigma: 0 to 1
- gamma: 0 to 1
- eta: 0 to 1
- rho: 0 to 1
- omega: 0 to 0.1
- beta_sensitivity: 0 to 5
- x_scale: 0 to 1
- kappa: 0 to 0.1
- lambda_rate: 0 to 0.2
- psi_transport: 0 to 0.01
- phi_transport: 0 to 0.01
- transboundary_lag_days: 1 to 365
- pollution_lag_days: 1 to 365
- policy_response_days: 1 to 365

ESTIMATION RULES:
1. Higher fossil dependence, PM2.5, coal, or gas reliance should raise beta_base
   and beta_sensitivity.
2. Closure, phase-out, or clean-power policy should raise kappa.
3. Strong health burden, hospitalization, respiratory, or cardiovascular evidence
   should raise lambda_rate.
4. Use conservative epidemiological priors for missing values.
5. Return every numeric parameter listed in the JSON shape below.

Return only this JSON shape:
{{
  "rationale": "one concise evidence-based explanation",
  "beta_base": 0.48,
  "sigma": 0.2,
  "gamma": 0.1,
  "eta": 0.05,
  "rho": 0.1,
  "omega": 0.01,
  "beta_sensitivity": 1.2,
  "x_scale": 0.5,
  "kappa": 0.02,
  "lambda_rate": 0.08,
  "psi_transport": 0.001,
  "phi_transport": 0.002,
  "transboundary_lag_days": 30,
  "pollution_lag_days": 90,
  "policy_response_days": 180
}}
"""

    def _parse_parameters(self, response_text: str) -> dict[str, float]:
        try:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not json_match:
                return {}
            payload = json.loads(json_match.group(0))
        except json.JSONDecodeError as exc:
            print(f"Parameter parsing error: {exc}")
            return {}

        self.last_rationale = str(payload.pop("rationale", ""))
        aliases = {
            "lambda": "lambda_rate",
            "psi": "psi_transport",
            "phi": "phi_transport",
        }
        params: dict[str, float] = {}
        for key, value in payload.items():
            normalized_key = aliases.get(key, key)
            try:
                params[normalized_key] = float(value)
            except (TypeError, ValueError):
                continue
        return params

    def _fallback_parameters(
        self,
        region: str,
        scenario_description: str,
        retrieval_context: str,
    ) -> dict[str, float]:
        text = f"{region} {scenario_description} {retrieval_context}".lower()
        close_signal = any(word in text for word in ["closure", "close", "phase out", "phaseout", "retire"])
        gas_signal = "gas" in text
        coal_signal = "coal" in text
        pollution_signal = any(word in text for word in ["pm2.5", "pollution", "particulate", "air quality"])
        health_signal = any(word in text for word in ["hospital", "respiratory", "cardiovascular", "asthma", "copd"])

        params = {
            "beta_base": 0.42,
            "sigma": 0.2,
            "gamma": 0.1,
            "eta": 0.04,
            "rho": 0.12,
            "omega": 0.004,
            "beta_sensitivity": 0.9,
            "x_scale": 0.5,
            "kappa": 0.012,
            "lambda_rate": 0.045,
            "psi_transport": 0.0008,
            "phi_transport": 0.0015,
            "transboundary_lag_days": 30,
            "pollution_lag_days": 90,
            "policy_response_days": 180,
        }

        region_text = region.lower()
        if "yorkshire" in region_text:
            params["beta_base"] = 0.46
            params["beta_sensitivity"] = 1.15
            params["psi_transport"] = 0.0012
        elif "southeast" in region_text or "south east" in region_text:
            params["beta_base"] = 0.38
            params["beta_sensitivity"] = 0.8
            params["psi_transport"] = 0.0006

        if coal_signal:
            params["beta_base"] += 0.04
            params["beta_sensitivity"] += 0.2
        if gas_signal:
            params["beta_base"] += 0.02
            params["beta_sensitivity"] += 0.1
        if close_signal:
            params["kappa"] = 0.025 if gas_signal else 0.035
        if pollution_signal:
            params["phi_transport"] = 0.0025
        if health_signal:
            params["lambda_rate"] = 0.08

        self.last_rationale = (
            "Fallback used scenario keywords and retrieved pollution/health evidence "
            "to set conservative SEIHR-energy parameters."
        )
        return params
