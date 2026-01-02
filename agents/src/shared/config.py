"""Shared configuration for Socratic Seminar agents.

This module contains configuration patterns used across all agents:
- AgentConfig: Per-agent configuration with payment settings
- Helper functions for resolving configuration values
"""

import os
from dataclasses import dataclass, field
from typing import Any

from src.shared.state import DEFAULT_COST_PER_ITERATION_SATS


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

@dataclass
class AgentConfig:
    """Configuration for an agent.
    
    Each agent can have its own configuration including:
    - Payment settings (cost per iteration)
    - Agent-specific settings
    
    The cost_per_iteration can be overridden by:
    1. Environment variable (COST_PER_ITERATION_SATS)
    2. Client input (payment_cost_per_iteration in state)
    
    Priority: client input > env var > agent default
    
    Example:
        # In agent's graph.py
        AGENT_CONFIG = AgentConfig(
            name="deepresearch",
            cost_per_iteration=15,  # Research costs more due to web searches
        )
        
        # When creating middleware
        CashuPaymentMiddleware(
            cost_per_iteration=AGENT_CONFIG.get_cost_per_iteration()
        )
    """
    
    # Agent name (used for logging, metrics)
    name: str
    
    # Default cost per iteration in satoshis
    # Can be overridden by env var or client input
    cost_per_iteration: int = DEFAULT_COST_PER_ITERATION_SATS
    
    # Additional agent-specific settings
    settings: dict[str, Any] = field(default_factory=dict)
    
    def get_cost_per_iteration(self, client_override: int | None = None) -> int:
        """Get the effective cost per iteration.
        
        Priority:
        1. Client override (if provided and valid)
        2. Environment variable COST_PER_ITERATION_SATS
        3. Agent's configured default
        
        Args:
            client_override: Optional cost override from client input
            
        Returns:
            Effective cost per iteration in satoshis
        """
        # Client override takes highest priority
        if client_override is not None and client_override > 0:
            return client_override
        
        # Environment variable
        env_cost = os.getenv("COST_PER_ITERATION_SATS")
        if env_cost:
            try:
                return int(env_cost)
            except ValueError:
                pass
        
        # Agent default
        return self.cost_per_iteration


# =============================================================================
# PREDEFINED AGENT CONFIGS
# =============================================================================

# DeepTutor: Socratic dialogue assistant
DEEPTUTOR_CONFIG = AgentConfig(
    name="deeptutor",
    cost_per_iteration=10,  # Standard cost for dialogue
    settings={
        "max_iterations": 50,
    },
)

# DeepResearch: Web research agent  
DEEPRESEARCH_CONFIG = AgentConfig(
    name="deepresearch",
    cost_per_iteration=15,  # Higher cost due to web searches
    settings={
        "max_concurrent_research_units": 3,
        "max_researcher_iterations": 3,
    },
)

