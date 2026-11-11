"""向量存储与检索：基于 numpy 的内存向量库（MVP）。

- 余弦相似度检索（向量入库前已归一化，退化为点积，性能好）。
- 数据来源：kb_documents 表（启动时全量重建索引），元数据与向量内存对齐。
- 生产演进路线：接口不变，替换为 pgvector / Milvus / Qdrant 即可，
  上层 RAGPipeline 无需改动（只依赖 search(doc, score) 的返回结构）。
"""
import numpy as np


class NumpyVectorStore:
    def __init__(self) -> None:
        self.dim = 0
        self._matrix: np.ndarray | None = None  # shape=(n, dim)
        self.docs: list[dict] = []

    # ------------------------------------------------------------------
    @property
    def size(self) -> int:
        return len(self.docs)

    def build(self, docs: list[dict], vectors: np.ndarray) -> int:
        """全量重建索引。docs: [{id, title, content, source, ...}]"""
        if len(docs) != vectors.shape[0]:
            raise ValueError("docs 与 vectors 数量不一致")
        self.dim = int(vectors.shape[1])
        self.docs = docs
        self._matrix = vectors.astype(np.float32)
        return self.size

    def search(self, query_vec: np.ndarray, top_k: int = 3) -> list[dict]:
        """余弦相似度 Top-K 检索。返回 [{doc, score}]，按得分降序。"""
        if self._matrix is None or self.size == 0 or self.dim == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        sims = self._matrix @ (q / qn)  # 库内向量已归一化 => 点积即余弦
        top_k = min(top_k, self.size)
        order = np.argsort(-sims)[:top_k]
        return [
            {"doc": self.docs[int(i)], "score": round(float(sims[i]), 4)}
            for i in order
            if float(sims[i]) > 0.05  # 过滤基本无相关的噪声结果
        ]
