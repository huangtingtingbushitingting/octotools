from typing import Any

def create_llm_engine(model_string: str, use_cache: bool = False, is_multimodal: bool = True, **kwargs) -> Any:
    """
    Factory function to create appropriate LLM engine instance.
    """

    usage_component = kwargs.pop("usage_component", "unspecified")

    if model_string.startswith("forge/"):
        from .openai import ChatOpenAI
        engine = ChatOpenAI(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif model_string.startswith("vllm-"):
        from .vllm import ChatVLLM
        routed_model = model_string.replace("vllm-", "", 1)
        engine = ChatVLLM(model_string=routed_model, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif model_string.startswith("litellm-"):
        from .litellm import ChatLiteLLM
        routed_model = model_string.replace("litellm-", "", 1)
        engine = ChatLiteLLM(model_string=routed_model, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif model_string.startswith("together-"):
        from .together import ChatTogether
        routed_model = model_string.replace("together-", "", 1)
        engine = ChatTogether(model_string=routed_model, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif model_string.startswith("ollama-"):
        from .ollama import ChatOllama
        routed_model = model_string.replace("ollama-", "", 1)
        engine = ChatOllama(model_string=routed_model, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif model_string.startswith("azure-"):
        from .azure import ChatAzureOpenAI
        routed_model = model_string.replace("azure-", "")
        engine = ChatAzureOpenAI(model_string=routed_model, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif any(x in model_string for x in ["gpt", "o1", "o3", "o4"]):
        from .openai import ChatOpenAI
        engine = ChatOpenAI(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif "claude" in model_string:
        from .anthropic import ChatAnthropic
        engine = ChatAnthropic(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif any(x in model_string for x in ["deepseek-v4-flash", "deepseek-reasoner","deepseek-chat"]):
        from .deepseek import ChatDeepseek
        engine = ChatDeepseek(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif "gemini" in model_string:
        from .gemini import ChatGemini
        engine = ChatGemini(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif "grok" in model_string:
        from .xai import ChatGrok
        engine = ChatGrok(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    else:
        raise ValueError(
            f"Engine {model_string} not supported. "
            "If you are using Azure OpenAI models, please ensure the model string has the prefix 'azure-'. "
            "For Together models, use 'together-'. For VLLM models, use 'vllm-'. For LiteLLM models, use 'litellm-'. "
            "For Ollama models, use 'ollama-'. "
            "For other custom engines, you can edit the factory.py file and add its interface file. "
            "Your pull request will be warmly welcomed!"
        )

    from octotools.research.usage import instrument_engine

    return instrument_engine(
        engine,
        component=usage_component,
        model=model_string,
    )
