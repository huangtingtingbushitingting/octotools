try:
    from openai import OpenAI#为了获取openai格式的客户端工具包
except ImportError:
    raise ImportError("Please install the openai package by running `pip install openai`, and add 'DEEPSEEK_API_KEY' to your environment variables.")
#DEEPSEEK_API_KEY 是你要连接的目标“服务器”的钥匙
import os
import json
import platformdirs
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
from typing import List, Union
from .base import EngineLM, CachedEngine


class ChatDeepseek(EngineLM, CachedEngine):
    DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."

    def __init__(
        self,
        model_string="deepseek-v4-flash",
        use_cache: bool=False,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        is_multimodal: bool=False):

        self.model_string = model_string
        self.use_cache = use_cache
        self.system_prompt = system_prompt
        self.is_multimodal = is_multimodal

        self.is_chat_model = any(x in model_string for x in ["deepseek-v4-flash"])
        self.is_reasoning_model = any(x in model_string for x in ["deepseek-reasoner"])
#deepseek的chat_model和reasoning_model具有不同的参数，所有要分开开设置

        if self.use_cache:
            root = platformdirs.user_cache_dir("octotools")
            cache_path = os.path.join(root, f"cache_deepseek_{model_string}.db")
            super().__init__(cache_path=cache_path)

        if os.getenv("DEEPSEEK_API_KEY") is None:
            raise ValueError("Please set the DEEPSEEK_API_KEY environment variable.")
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )

    @retry(wait=wait_random_exponential(min=1, max=5), stop=stop_after_attempt(5))#generate调用失败的应对方法
    def generate(self, content: Union[str, List[Union[str, bytes]]], system_prompt=None, **kwargs):
        if isinstance(content, str):
            return self._generate_text(content, system_prompt=system_prompt, **kwargs)
        elif isinstance(content, list):
            return self._generate_multimodal(content, system_prompt=system_prompt, **kwargs)
#generate主要作用是并行打包，将问题交给真正的处理器，并且不支持多模态数据，不支持传入图片，只可以纯文本
#如果数据是多模态的则需要 调用together.py中的

    def _generate_text(
        self, prompt, system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99, response_format=None,
    extra_body={"thinking": {"type": "disabled"}}
    ):
        sys_prompt_arg = system_prompt if system_prompt else self.system_prompt

        if self.use_cache:
            cache_key = sys_prompt_arg + prompt#
            cache_or_none = self._check_cache(cache_key)
            if cache_or_none is not None:#如果之前问过相同的问题则直接，且允许使用cache，则相同的问题直接从cache中取出
                return cache_or_none
        
        if self.is_chat_model and response_format is not None:
            schema = (response_format.model_json_schema() if hasattr(response_format, "model_json_schema")
                      else response_format.schema())
            structured_prompt = (
                prompt + "\n\nReturn only valid JSON matching this JSON Schema:\n" +
                json.dumps(schema, ensure_ascii=False)
            )
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": structured_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                response_format={"type": "json_object"},
            )
            response = response.choices[0].message.content
            response = (response_format.model_validate_json(response)
                        if hasattr(response_format, "model_validate_json")
                        else response_format.parse_raw(response))

        elif self.is_chat_model:
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,


            )
            response = response.choices[0].message.content

        elif self.is_reasoning_model:
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                top_p=top_p,
                extra_body=extra_body,
            )
            response = response.choices[0].message.content

        if self.use_cache:
            self._save_cache(cache_key, response)
        return response
    def _generate_multimodal(
        self,
        content,
        system_prompt=None,
        temperature=0,
        max_tokens=4000,
        top_p=0.99,
        response_format=None,
        extra_body={"thinking": {"type": "disabled"}}
    ):
        sys_prompt_arg = system_prompt if system_prompt else self.system_prompt
    
        # ---------- 缓存逻辑（与 _generate_text 一致） ----------
        if self.use_cache:
            # 注意：content 是 list，可能含 bytes，用 str(content) 作为缓存键（简单处理）
            cache_key = sys_prompt_arg + str(content)
            cache_or_none = self._check_cache(cache_key)
            if cache_or_none is not None:
                return cache_or_none
    
        # ---------- 构建多模态用户消息 ----------
        user_content = []
        for item in content:
            if isinstance(item, str):
                user_content.append({"type": "text", "text": item})
            elif isinstance(item, bytes):
                # The current DeepSeek endpoint is text-only. Image-aware local tools
                # receive the original path separately; the planner only needs context.
                user_content.append({
                    "type": "text",
                    "text": "[An image was provided and will be processed by the enabled image tool.]",
                })
            else:
                # 其他类型转为文本（如数字、路径等）
                user_content.append({"type": "text", "text": str(item)})
    
        messages = []
        if sys_prompt_arg:
            messages.append({"role": "system", "content": sys_prompt_arg})
        messages.append({"role": "user", "content": user_content})
    
        # ---------- API 调用（沿用 _generate_text 的分支逻辑） ----------
        if self.is_chat_model and response_format is not None:
            schema = (response_format.model_json_schema() if hasattr(response_format, "model_json_schema")
                      else response_format.schema())
            user_content.append({
                "type": "text",
                "text": "Return only valid JSON matching this JSON Schema:\n" + json.dumps(schema, ensure_ascii=False),
            })
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                response_format={"type": "json_object"},
            )
            response = response.choices[0].message.content
            response = (response_format.model_validate_json(response)
                        if hasattr(response_format, "model_validate_json")
                        else response_format.parse_raw(response))

        elif self.is_chat_model:
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            response = response.choices[0].message.content
    
        elif self.is_reasoning_model:
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                extra_body=extra_body,
            )
            response = response.choices[0].message.content
        else:
            # 默认走 chat 模型（防止未定义）
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            response = response.choices[0].message.content
    
        # ---------- 缓存保存 ----------
        if self.use_cache:
            self._save_cache(cache_key, response)
    
        return response
    def __call__(self, prompt, **kwargs):
        return self.generate(prompt, **kwargs)
    