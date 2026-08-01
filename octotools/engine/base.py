# Reference: https://github.com/zou-group/textgrad/blob/main/textgrad/engine/base.py

import hashlib
import diskcache as dc
from abc import ABC, abstractmethod

class EngineLM(ABC):
    """就是说EngineLM无法直接被调用，只可以由子类继承，
并且子类必须自己实现被@abstractmethod修饰的方法，
其目的是为了定义一个统一的框架"""
    system_prompt: str = "You are a helpful, creative, and smart assistant."
    model_string: str
    @abstractmethod
    def generate(self, prompt, system_prompt=None, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        pass


class CachedEngine:
    def __init__(self, cache_path):
        super().__init__()
        self.cache_path = cache_path
        self.cache = dc.Cache(cache_path)#返回一个diskcache的实例对像，类似与存储在磁盘上的python字典对像

    def _hash_prompt(self, prompt: str):#将prompt序列化成结构对像，避免对像碰撞
        return hashlib.sha256(f"{prompt}".encode()).hexdigest()

    def _check_cache(self, prompt: str):#检查是否在cache中存在相同的问题
        if prompt in self.cache:
            return self.cache[prompt]
        else:
            return None

    def _save_cache(self, prompt: str, response: str):#把内容保存到cache中
        self.cache[prompt] = response

#对象进行存盘或者被序列化时会自动调用
    def __getstate__(self):
        # Remove the cache from the state before pickling序列化，在进行序列化前清除状态中的缓存,只保存cache是在的地址，只序列化地址
        state = self.__dict__.copy()#浅复制当前实列化的CachedEngine的所有属性
        del state['cache']
        return state

#对象进行读盘或者被反序列化时会自动调用
    def __setstate__(self, state):
        # Restore the cache after unpickling
        self.__dict__.update(state)
        self.cache = dc.Cache(self.cache_path)#根据地址找到cache缓存