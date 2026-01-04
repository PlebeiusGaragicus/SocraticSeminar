"""Shared model factory for Socratic Seminar agents.

Supports:
- qwen3-coder: Local Qwen3 model via OpenAI-compatible endpoint
- grok-4-1-fast-non-reasoning: XAI's Grok 4 cloud model

Dynamic Model Selection:
- Use get_configurable_model() to get a model that can be swapped at runtime
- Frontend passes model selection via config: {"configurable": {"llm_model": "grok-4-1-fast-non-reasoning"}}

Note: We use a custom DynamicModelRouter instead of configurable_alternatives because
the LangGraph server doesn't propagate config.configurable to the model invocation.
"""

import os
import json
from typing import Literal, Any, Optional, Iterator, AsyncIterator, List, Sequence

from langchain_core.runnables import ConfigurableField, RunnableConfig
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_openai import ChatOpenAI

# Debug log path
DEBUG_LOG_PATH = "/Users/satoshi/Downloads/SocraticSeminar/.cursor/debug.log"

def _debug_log(location: str, message: str, data: dict, hypothesis_id: str = "D"):
    """Write a debug log entry to the NDJSON log file."""
    try:
        import time
        entry = {
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "hypothesisId": hypothesis_id
        }
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Silently ignore logging errors


# =============================================================================
# CONFIGURATION
# =============================================================================

# Model selection type (matches frontend)
LLMModelType = Literal["qwen3-coder-30b-a3b-instruct-mlx", "grok-4-1-fast-non-reasoning"]

# Default model when not specified
DEFAULT_LLM_MODEL: LLMModelType = "qwen3-coder-30b-a3b-instruct-mlx"

# Config key for model selection (used in RunnableConfig)
MODEL_CONFIG_KEY = "llm_model"

# Qwen3 Coder configuration (local OpenAI-compatible endpoint)
QWEN3_MODEL = os.getenv("QWEN3_MODEL", "qwen3-coder-30b-a3b-instruct-mlx")
QWEN3_BASE_URL = os.getenv("QWEN3_BASE_URL", os.getenv("LLM_BASE_URL"))
QWEN3_API_KEY = os.getenv("QWEN3_API_KEY", os.getenv("LLM_API_KEY", "not-needed"))

# Grok 4 Fast configuration (XAI cloud)
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
GROK4_MODEL = os.getenv("GROK4_MODEL", "grok-4-1-fast-non-reasoning")


# =============================================================================
# MODEL FACTORY
# =============================================================================

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class DebugModelCallback(BaseCallbackHandler):
    """Callback to log when the model is actually invoked."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        # #region agent log
        _debug_log(
            f"models.py:callback:{self.model_name}", 
            f"LLM START - {self.model_name} is being invoked", 
            {"model_name": self.model_name, "num_prompts": len(prompts) if prompts else 0},
            "F"
        )
        # #endregion

    def on_chat_model_start(self, serialized, messages, **kwargs):
        # #region agent log
        _debug_log(
            f"models.py:callback:{self.model_name}", 
            f"CHAT MODEL START - {self.model_name} is being invoked", 
            {"model_name": self.model_name, "num_messages": len(messages) if messages else 0},
            "F"
        )
        # #endregion


def get_model(
    temperature: float = 0.7,
    model_name: LLMModelType | None = None,
):
    """Get the configured chat model.
    
    Supports two models:
    - qwen3-coder: Local Qwen3 30B model, fast & private
    - grok-4-1-fast-non-reasoning: XAI cloud Grok 4 model, very capable
    
    Args:
        temperature: Model temperature (default: 0.7)
        model_name: Which model to use (default: qwen3-coder)
        
    Returns:
        Configured ChatOpenAI instance
        
    Environment Variables:
        QWEN3_MODEL: Qwen3 model name (default: qwen3-coder-30b-a3b-instruct-mlx)
        QWEN3_BASE_URL: Base URL for Qwen3 endpoint
        QWEN3_API_KEY: API key for Qwen3
        XAI_API_KEY: XAI API key for Grok
        GROK4_MODEL: Grok 4 model name (default: grok-4-1-fast-non-reasoning)
    """
    effective_model = model_name or DEFAULT_LLM_MODEL
    
    # #region agent log
    _debug_log("models.py:get_model", "get_model called", {"model_name": model_name, "effective_model": effective_model, "temperature": temperature}, "D")
    # #endregion
    
    if effective_model == "grok-4-1-fast-non-reasoning":
        # XAI's Grok 4 Fast
        # #region agent log
        _debug_log("models.py:get_model:grok", "Creating Grok model", {"base_url": XAI_BASE_URL, "model": GROK4_MODEL}, "D")
        # #endregion
        model = ChatOpenAI(
            model=GROK4_MODEL,
            base_url=XAI_BASE_URL,
            api_key=XAI_API_KEY,
            temperature=temperature,
            callbacks=[DebugModelCallback("grok-4")],
        )
        return model
    else:
        # Qwen3 Coder (default) - local OpenAI-compatible endpoint
        kwargs = {
            "model": QWEN3_MODEL,
            "temperature": temperature,
            "callbacks": [DebugModelCallback("qwen3")],
        }
        if QWEN3_BASE_URL:
            kwargs["base_url"] = QWEN3_BASE_URL
        if QWEN3_API_KEY:
            kwargs["api_key"] = QWEN3_API_KEY
        
        # #region agent log
        _debug_log("models.py:get_model:qwen", "Creating Qwen model", {"base_url": QWEN3_BASE_URL, "model": QWEN3_MODEL}, "D")
        # #endregion
        return ChatOpenAI(**kwargs)


# =============================================================================
# TOOL-BOUND MODEL ROUTER (for models with tools bound)
# =============================================================================

from langchain_core.runnables import Runnable

class ToolBoundModelRouter(Runnable):
    """Routes invocations to the appropriate tool-bound model based on config.
    
    This is used after bind_tools() is called on DynamicModelRouter.
    It holds references to each model's tool-bound version and routes at invocation time.
    """
    
    def __init__(self, models: dict, default_model: str, config_key: str):
        self.models = models
        self.default_model = default_model
        self.config_key = config_key
    
    def _get_model(self, config: Optional[RunnableConfig] = None):
        """Get the appropriate bound model based on config."""
        from langchain_core.runnables.config import get_config
        
        model_name = self.default_model
        
        # Try to get config from context if not provided or empty
        effective_config = config
        if not config or not config.get("configurable"):
            try:
                context_config = get_config()
                if context_config and context_config.get("configurable"):
                    effective_config = context_config
            except Exception:
                pass
        
        # #region agent log
        config_keys = list(effective_config.keys()) if effective_config else []
        config_debug = {}
        if effective_config:
            for key in ["configurable", "tags", "metadata", "callbacks", "run_name"]:
                if key in effective_config:
                    val = effective_config[key]
                    config_debug[key] = str(val)[:200] if val else None
        _debug_log("ToolBoundModelRouter:_get_model:config_details", "Config received", {"config_keys": config_keys, "config_debug": config_debug, "used_context": effective_config is not config}, "I")
        # #endregion
        
        if effective_config:
            configurable = effective_config.get("configurable", {})
            model_name = configurable.get(self.config_key, self.default_model)
        
        selected = self.models.get(model_name, self.models[self.default_model])
        
        # #region agent log
        model_info = str(type(selected).__name__)
        _debug_log("ToolBoundModelRouter:_get_model", "Selecting bound model", {"selected_model": model_name, "model_type": model_info}, "H")
        # #endregion
        
        return selected
    
    def invoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Any:
        """Route to the appropriate bound model."""
        model = self._get_model(config)
        
        # #region agent log
        _debug_log("ToolBoundModelRouter:invoke", "Invoking bound model", {"model_type": type(model).__name__}, "H")
        # #endregion
        
        return model.invoke(input, config=config, **kwargs)
    
    async def ainvoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Any:
        """Route to the appropriate bound model (async)."""
        model = self._get_model(config)
        
        # #region agent log
        _debug_log("ToolBoundModelRouter:ainvoke", "Async invoking bound model", {"model_type": type(model).__name__}, "H")
        # #endregion
        
        return await model.ainvoke(input, config=config, **kwargs)
    
    def stream(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> Iterator:
        """Route streaming to the appropriate bound model."""
        model = self._get_model(config)
        return model.stream(input, config=config, **kwargs)
    
    async def astream(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> AsyncIterator:
        """Route async streaming to the appropriate bound model."""
        model = self._get_model(config)
        async for chunk in model.astream(input, config=config, **kwargs):
            yield chunk
    
    def bind_tools(self, tools: Sequence[Any], **kwargs) -> "ToolBoundModelRouter":
        """Re-bind tools to all underlying models."""
        bound_models = {
            name: model.bind_tools(tools, **kwargs) if hasattr(model, 'bind_tools') else model
            for name, model in self.models.items()
        }
        return ToolBoundModelRouter(
            models=bound_models,
            default_model=self.default_model,
            config_key=self.config_key,
        )
    
    def with_structured_output(self, schema: Any, **kwargs) -> "ToolBoundModelRouter":
        """Apply structured output to all underlying models."""
        bound_models = {
            name: model.with_structured_output(schema, **kwargs) if hasattr(model, 'with_structured_output') else model
            for name, model in self.models.items()
        }
        return ToolBoundModelRouter(
            models=bound_models,
            default_model=self.default_model,
            config_key=self.config_key,
        )


# =============================================================================
# DYNAMIC MODEL ROUTER (reads model selection from config at invocation time)
# =============================================================================

class DynamicModelRouter(BaseChatModel):
    """A chat model that routes to different underlying models based on config.
    
    This is a clean, standard approach that works with LangGraph because it
    reads the model selection at invocation time from the RunnableConfig.
    
    Usage:
        model = DynamicModelRouter(temperature=0.0)
        
        # At invocation time, pass the model selection in config:
        result = await model.ainvoke(
            messages,
            config={"configurable": {"llm_model": "grok-4-1-fast-non-reasoning"}}
        )
    """
    
    temperature: float = 0.0
    _models: dict = {}
    
    def __init__(self, temperature: float = 0.0, **kwargs):
        super().__init__(temperature=temperature, **kwargs)
        # Pre-create both models
        # #region agent log
        _debug_log("DynamicModelRouter:init", "Creating router with models", {"temperature": temperature}, "G")
        # #endregion
        self._models = {
            "qwen3-coder-30b-a3b-instruct-mlx": get_model(temperature=temperature, model_name="qwen3-coder-30b-a3b-instruct-mlx"),
            "grok-4-1-fast-non-reasoning": get_model(temperature=temperature, model_name="grok-4-1-fast-non-reasoning"),
        }
    
    @property
    def _llm_type(self) -> str:
        return "dynamic-model-router"
    
    def _get_model_from_config(self, config: Optional[RunnableConfig] = None) -> BaseChatModel:
        """Get the appropriate model based on config."""
        model_name = DEFAULT_LLM_MODEL
        
        if config:
            configurable = config.get("configurable", {})
            model_name = configurable.get(MODEL_CONFIG_KEY, DEFAULT_LLM_MODEL)
        
        # #region agent log
        _debug_log("DynamicModelRouter:_get_model_from_config", "Selecting model from config", {"config_configurable": config.get("configurable", {}) if config else {}, "selected_model": model_name}, "G")
        # #endregion
        
        return self._models.get(model_name, self._models[DEFAULT_LLM_MODEL])
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Fallback generate - uses default model."""
        model = self._models[DEFAULT_LLM_MODEL]
        return model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
    
    def invoke(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        """Route to the appropriate model based on config."""
        model = self._get_model_from_config(config)
        
        # #region agent log
        model_base_url = getattr(model, 'openai_api_base', None) or getattr(model, 'base_url', 'unknown')
        _debug_log("DynamicModelRouter:invoke", "Invoking selected model", {"selected_model_base_url": str(model_base_url), "config_keys": list(config.keys()) if config else []}, "G")
        # #endregion
        
        return model.invoke(input, config=config, **kwargs)
    
    async def ainvoke(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        """Route to the appropriate model based on config (async)."""
        model = self._get_model_from_config(config)
        
        # #region agent log
        model_base_url = getattr(model, 'openai_api_base', None) or getattr(model, 'base_url', 'unknown')
        _debug_log("DynamicModelRouter:ainvoke", "Async invoking selected model", {"selected_model_base_url": str(model_base_url), "config_keys": list(config.keys()) if config else []}, "G")
        # #endregion
        
        return await model.ainvoke(input, config=config, **kwargs)
    
    def stream(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> Iterator[BaseMessage]:
        """Route streaming to the appropriate model based on config."""
        model = self._get_model_from_config(config)
        
        # #region agent log
        model_base_url = getattr(model, 'openai_api_base', None) or getattr(model, 'base_url', 'unknown')
        _debug_log("DynamicModelRouter:stream", "Streaming with selected model", {"selected_model_base_url": str(model_base_url)}, "G")
        # #endregion
        
        return model.stream(input, config=config, **kwargs)
    
    async def astream(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> AsyncIterator[BaseMessage]:
        """Route async streaming to the appropriate model based on config."""
        model = self._get_model_from_config(config)
        
        # #region agent log
        model_base_url = getattr(model, 'openai_api_base', None) or getattr(model, 'base_url', 'unknown')
        _debug_log("DynamicModelRouter:astream", "Async streaming with selected model", {"selected_model_base_url": str(model_base_url)}, "G")
        # #endregion
        
        async for chunk in model.astream(input, config=config, **kwargs):
            yield chunk
    
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ToolBoundModelRouter":
        """Bind tools to all underlying models.
        
        Returns a ToolBoundModelRouter that wraps the bound models and routes
        based on config at invocation time.
        """
        # #region agent log
        _debug_log("DynamicModelRouter:bind_tools", "bind_tools called", {"num_tools": len(tools) if tools else 0, "kwargs_keys": list(kwargs.keys())}, "H")
        # #endregion
        
        bound_models = {}
        for name, model in self._models.items():
            bound = model.bind_tools(tools, **kwargs)
            bound_models[name] = bound
            # #region agent log
            _debug_log("DynamicModelRouter:bind_tools:bound", f"Bound tools to {name}", {"bound_type": type(bound).__name__}, "H")
            # #endregion
        
        return ToolBoundModelRouter(
            models=bound_models,
            default_model=DEFAULT_LLM_MODEL,
            config_key=MODEL_CONFIG_KEY,
        )
    
    def with_structured_output(self, schema: Any, **kwargs: Any) -> "ToolBoundModelRouter":
        """Apply structured output to all underlying models."""
        bound_models = {
            name: model.with_structured_output(schema, **kwargs)
            for name, model in self._models.items()
        }
        return ToolBoundModelRouter(
            models=bound_models,
            default_model=DEFAULT_LLM_MODEL,
            config_key=MODEL_CONFIG_KEY,
        )


def get_configurable_model(temperature: float = 0.0):
    """Get a model that can be dynamically selected at runtime via config.
    
    Uses DynamicModelRouter which reads the model selection from RunnableConfig
    at invocation time.
    
    Args:
        temperature: Model temperature (default: 0.0 for deterministic output)
        
    Returns:
        A DynamicModelRouter that responds to {"configurable": {"llm_model": "..."}}
        
    Usage:
        # In graph creation
        model = get_configurable_model()
        agent = create_agent(model, ...)
        
        # At invocation time, the model will be selected based on config
    """
    # #region agent log
    _debug_log("models.py:get_configurable_model", "Creating DynamicModelRouter", {"temperature": temperature}, "E")
    # #endregion
    
    return DynamicModelRouter(temperature=temperature)

