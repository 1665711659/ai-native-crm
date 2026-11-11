"""向量化（Embedding）模块：双实现可切换。

- APIEmbedder：OpenAI 兼容 /embeddings 接口（火山方舟 doubao-embedding 等）。
- MockEmbedder：本地确定性 hash 向量（中文 bigram 分桶），
  无需任何外部依赖即可让 RAG 检索链路离线跑通（演示/测试用）。
"""
import hashlib
import math
from abc import ABC, abstractmethod

import httpx
import numpy as np


class BaseEmbedder(ABC):
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> np.ndarray:
        """批量向量化，返回 shape=(n, dim) 的已归一化矩阵。"""


class APIEmbedder(BaseEmbedder):
    """OpenAI 兼容 Embedding 接口客户端。"""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.http = httpx.AsyncClient(timeout=60)
        self.dim = 0  # 首次调用后由返回值确定

    async def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1))
        resp = await self.http.post(
            f"{self.cfg.llm_base_url}/embeddings",
            json={"model": self.cfg.embedding_model, "input": texts},
            headers={"Authorization": f"Bearer {self.cfg.llm_api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        vectors = np.array([d["embedding"] for d in data], dtype=np.float32)
        self.dim = vectors.shape[1]
        return self._normalize(vectors)

    @staticmethod
    def _normalize(m: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return m / norms


class MockEmbedder(BaseEmbedder):
    """本地确定性 hash 向量：中文二元组(bigram)分桶计数 + L2归一化。

    特点：完全离线、结果确定（同文本同向量）、对中文短文本有一定区分度，
    仅用于演示与冒烟测试；生产请配置 EMBEDDING_MODEL 使用真实语义向量。
    """

    dim = 256

    async def embed(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._one(t) for t in texts]) if texts else np.zeros((0, self.dim))

    def _one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = [text[i:i + 2] for i in range(max(len(text) - 1, 0))] or [text]
        for tk in tokens:
            h = int(hashlib.md5(tk.encode("utf-8")).hexdigest()[:8], 16)
            vec[h % self.dim] += 1.0
            vec[(h >> 12) % self.dim] += 0.5  # 第二个哈希位增强区分度
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec


def build_embedder(cfg) -> BaseEmbedder:
    """工厂：配置了 EMBEDDING_MODEL 且有 Key => API；否则本地 Mock。"""
    if cfg.use_api_embedding:
        return APIEmbedder(cfg)
    return MockEmbedder()
