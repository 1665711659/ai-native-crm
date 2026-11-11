"""全局配置：从环境变量 / .env 文件加载（见 .env.example）。

设计要点：
- 不配置 LLM_API_KEY 时自动进入「离线演示模式」：LLM 走 Mock 规则模拟、
  Embedding 走本地 hash 向量，全链路（RAG / Agent / Workflow）离线可跑通。
- LLM 采用 OpenAI 兼容协议，默认指向火山方舟，一行配置可切 DeepSeek / GLM 等。
"""
import os

from dotenv import load_dotenv

load_dotenv()  # 读取项目根目录 .env（存在时）


class Config:
    """集中式配置对象。生产环境可替换为 pydantic-settings 等方案。"""

    def __init__(self) -> None:
        # ---------- Web 服务 ----------
        self.port: int = int(os.getenv("PORT", "8888"))
        self.debug: bool = os.getenv("DEBUG", "1") == "1"

        # ---------- 数据库 ----------
        # sqlite: 零配置演示库（默认）；mysql: 生产（见 requirements.txt）
        self.db_backend: str = os.getenv("DB_BACKEND", "sqlite").lower()
        self.sqlite_path: str = os.getenv("SQLITE_PATH", "data/crm.db")
        self.mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
        self.mysql_user: str = os.getenv("MYSQL_USER", "root")
        self.mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
        self.mysql_database: str = os.getenv("MYSQL_DATABASE", "ai_crm")

        # ---------- LLM（OpenAI 兼容协议）----------
        self.llm_base_url: str = os.getenv(
            "LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        ).rstrip("/")
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_model: str = os.getenv("LLM_MODEL", "doubao-seed-evolving-v1.5")
        # 留空 => 本地 Mock 向量（离线演示）；配置模型名 => 调用 /embeddings API
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "")

        # ---------- AIGC ----------
        self.comfyui_url: str = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
        # 本机 ComfyUI/models/checkpoints 下实际存在的模型名
        self.comfyui_checkpoint: str = os.getenv("COMFYUI_CHECKPOINT", "sd_xl_base_1.0.safetensors")
        self.ffmpeg_path: str = os.getenv("FFMPEG_PATH", "ffmpeg")

    # ---------- 便捷判断 ----------
    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def use_api_embedding(self) -> bool:
        return bool(self.llm_configured and self.embedding_model)


CONFIG = Config()
