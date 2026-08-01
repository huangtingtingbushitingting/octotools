# Reference: https://github.com/zou-group/textgrad/blob/main/textgrad/engine/openai.py

try:
    import vllm
except ImportError:
    raise ImportError("If you'd like to use VLLM models, please install the vllm package by running `pip install vllm`.")

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("If you'd like to use VLLM models, please install the openai package by running `pip install openai`.")

import os
import json
import base64
import platformdirs
from typing import List, Union

from .base import EngineLM, CachedEngine
#本地私有部署
class ChatVLLM(EngineLM, CachedEngine):
    DEFAULT_SYSTEM_PROMPT = "You are a helpful, creative, and smart assistant."

    def __init__(
        self,
        model_string="Qwen/Qwen2.5-VL-3B-Instruct",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        is_multimodal: bool=False,
        use_cache: bool=True,
        **kwargs):
        """
        :param model_string:
        :param system_prompt:
        :param is_multimodal:
        """

        self.model_string = model_string
        self.use_cache = use_cache
        self.system_prompt = system_prompt
        self.is_multimodal = is_multimodal

        if self.use_cache:
            root = platformdirs.user_cache_dir("octotools")
            cache_path = os.path.join(root, f"cache_vllm_{self.model_string}.db")
            self.image_cache_dir = os.path.join(root, "image_cache")
            os.makedirs(self.image_cache_dir, exist_ok=True)
            super().__init__(cache_path=cache_path)
        
        try:
            self.client = OpenAI(
                base_url="http://localhost:8888/v1",#请求发送到本机VLLM端口
                api_key="dummy-token",#VLLM 是本地开源服务，默认不校验身份。这里填任何字符串
            )
        except Exception as e:
            raise ValueError(f"Failed to connect to VLLM server. Please ensure the server is running and try again. Please ensure that the model is running at localhost:8888.")
            #查看本地部署的模型框架与实际的是否符合
        if self.client.models.list().data[0].id != self.model_string:
            #client.models.list()返回当前运行的所有模型的列表
            raise ValueError(f"The VLLM server is running, but the model {self.model_string} is not available. Please check the model name and try again.")


    def generate(self, content: Union[str, List[Union[str, bytes]]], system_prompt=None, **kwargs):
        if isinstance(content, str):
            return self._generate_text(content, system_prompt=system_prompt, **kwargs)
        
        elif isinstance(content, list):
            if (not self.is_multimodal):
                raise NotImplementedError(f"Multimodal generation is only supported for {self.model_string}.")
            
            return self._generate_multimodal(content, system_prompt=system_prompt, **kwargs)
        
    def _generate_text(
        self, prompt, system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99, response_format=None
    ):

        sys_prompt_arg = system_prompt if system_prompt else self.system_prompt

        if self.use_cache:
            cache_key = sys_prompt_arg + prompt
            cache_or_none = self._check_cache(cache_key)
            if cache_or_none is not None:
                return cache_or_none
        

        # Chat models without structured outputs
        response = self.client.chat.completions.create(
            model=self.model_string,
            messages=[
                {"role": "system", "content": sys_prompt_arg},
                {"role": "user", "content": prompt},
            ],
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        response = response.choices[0].message.content

        if self.use_cache:
            self._save_cache(cache_key, response)
        return response

    def __call__(self, prompt, **kwargs):
        return self.generate(prompt, **kwargs)

    def _format_content(self, content: List[Union[str, bytes]]) -> List[dict]:
        formatted_content = []
        for item in content:
            if isinstance(item, bytes):
                base64_image = base64.b64encode(item).decode('utf-8')
                formatted_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            elif isinstance(item, str):
                formatted_content.append({
                    "type": "text",
                    "text": item
                })
            else:
                raise ValueError(f"Unsupported input type: {type(item)}")
        return formatted_content

    def _generate_multimodal(
        self, content: List[Union[str, bytes]], system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99, response_format=None
    ):#属于多模态大模型API调用，把用户输入的文本和图像（混合内容）打包成标准格式，发给 DeepSeek / OpenAI 的多模态 API，并接收生成的回答
        sys_prompt_arg = system_prompt if system_prompt else self.system_prompt
        formatted_content = self._format_content(content)

        if self.use_cache:
            cache_key = sys_prompt_arg + json.dumps(formatted_content)
            cache_or_none = self._check_cache(cache_key)
            if cache_or_none is not None:
                return cache_or_none


        response = self.client.chat.completions.create(
            model=self.model_string,
            messages=[
                {"role": "system", "content": sys_prompt_arg},
                {"role": "user", "content": formatted_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        response_text = response.choices[0].message.content

        if self.use_cache:
            self._save_cache(cache_key, response_text)
        return response_text
