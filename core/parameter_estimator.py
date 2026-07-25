"""
Parameter Estimator: Orchestrates retrieval + LLM → ModelParameters
"""

from pathlib import Path

from llm.llama_client import LlamaClient
from llm.validator import ParameterValidator
from core.parameters import ModelParameters
from rag.retriever import Retriever


class ParameterEstimator:
    """Orchestrates LLM parameter estimation pipeline."""

    def __init__(
        self,
        retriever: Retriever | None = None,
        llm: LlamaClient | None = None,
    ):
        self.retriever = retriever or Retriever()
        self.llm = llm or LlamaClient()
        self.validator = ParameterValidator()
        self.last_trace: dict = {}

    def estimate_for_scenario(
        self,
        region: str,
        scenario_description: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> ModelParameters:
        """
        Estimate full ModelParameters for a region/scenario.
        
        Pipeline:
        1. Retrieve policy + health context
        2. Call LLM to estimate parameters
        3. Populate ModelParameters with retrieved initial conditions
        
        Args:
            region: e.g., "UK_Yorkshire"
            scenario_description: e.g., "Coal plant closure on 2023-04-01"
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            use_cache: Use cached retrieval results
            
        Returns:
            Fully populated ModelParameters ready for simulation
        """
        print(f"\n{'='*60}")
        print(f"Parameter Estimation: {region}")
        print(f"{'='*60}")
        
        # Step 1: Retrieve context
        print("\n[1/3] Retrieving context...")
        policy_context = self.retriever.retrieve_policy_context(
            region, start_date, end_date, use_cache=use_cache
        )
        health_context = self.retriever.retrieve_health_context(
            region, start_date, end_date, use_cache=use_cache
        )
        
        # Format for LLM
        policy_text = self.retriever.format_for_llm(policy_context)
        health_text = self.retriever.format_for_llm(health_context)
        combined_context = f"{policy_text}\n\n{health_text}"
        
        # Step 2: Call LLM
        print("\n[2/3] Estimating parameters via LLM...")
        param_dict = self.llm.estimate_parameters(
            region=region,
            scenario_description=scenario_description,
            retrieval_context=combined_context,
        )
        
        # Step 3: Build ModelParameters
        print("\n[3/3] Building ModelParameters...")
        
        # Get initial conditions from config or defaults
        initial_values = self._load_initial_values()
        region_init = initial_values.get(region, {})
        defaults = initial_values.get("defaults", {})
        validation_defaults = {
            "region": region,
            **defaults,
            "s0": region_init.get("s0", 1000000),
            "e0": region_init.get("e0", 500),
            "i0": region_init.get("i0", 100),
            "h0": region_init.get("h0", 50),
            "r0": region_init.get("r0", 100000),
            "x0": region_init.get("x0", 0.3),
        }
        clean_params = self.validator.validate(param_dict, defaults=validation_defaults)
        
        params = ModelParameters(
            region=region,
            beta_base=clean_params["beta_base"],
            sigma=clean_params["sigma"],
            gamma=clean_params["gamma"],
            eta=clean_params["eta"],
            rho=clean_params["rho"],
            omega=clean_params["omega"],
            beta_sensitivity=clean_params["beta_sensitivity"],
            x_scale=clean_params["x_scale"],
            kappa=clean_params["kappa"],
            lambda_rate=clean_params["lambda_rate"],
            psi_transport=clean_params["psi_transport"],
            phi_transport=clean_params["phi_transport"],
            transboundary_lag_days=clean_params["transboundary_lag_days"],
            s0=clean_params["s0"],
            e0=clean_params["e0"],
            i0=clean_params["i0"],
            h0=clean_params["h0"],
            r0=clean_params["r0"],
            x0=clean_params["x0"],
            pollution_lag_days=clean_params["pollution_lag_days"],
            policy_response_days=clean_params["policy_response_days"],
            source_metadata={
                "retrieval_policy": policy_context.timestamp,
                "retrieval_health": health_context.timestamp,
                "llm_model": self.llm.model,
                "scenario": scenario_description,
                "date_range": f"{start_date} to {end_date}",
                "llm_rationale": self.llm.last_rationale,
            }
        )

        self.last_trace[region] = {
            "policy_query": policy_context.query,
            "health_query": health_context.query,
            "policy_cache_hit": policy_context.cache_hit,
            "health_cache_hit": health_context.cache_hit,
            "policy_tavily_results": policy_context.tavily_results,
            "health_tavily_results": health_context.tavily_results,
            "policy_local_documents": policy_context.local_documents,
            "health_local_documents": health_context.local_documents,
            "policy_graph_context": policy_context.graph_context,
            "health_graph_context": health_context.graph_context,
            "llm_model": self.llm.model,
            "llm_rationale": self.llm.last_rationale,
            "parameters": params.to_dict(),
        }
        
        print(f"\n[OK] Estimated {region} parameters:")
        print(f"  beta_base: {params.beta_base:.3f}")
        print(f"  kappa: {params.kappa:.4f}")
        print(f"  lambda: {params.lambda_rate:.3f}")
        print(f"  X0: {params.x0:.2f}")
        
        return params

    def _load_initial_values(self) -> dict:
        """Load initial values from config."""
        import json
        try:
            with open("math/initial_values.json") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load initial values: {e}")
            return {"defaults": {}}
