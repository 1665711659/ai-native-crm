"""TTS（语音合成）模块：为数字员工/外呼话术提供语音输出。

- EdgeTTSProvider：微软 Edge-TTS，免费、中文音色丰富（默认，pip install edge-tts）。
- ArkTTSProvider：火山方舟 TTS 骨架（大模型语音合成，需控制台开通，付费商用授权更稳）。

运行 demo：python -m app.ai.aigc.tts
"""
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, out_path: str, voice: str = "") -> str:
        """合成语音并保存到 out_path，返回文件路径。"""


class EdgeTTSProvider(TTSProvider):
    """免费方案：Edge-TTS。中文推荐音色：zh-CN-XiaoxiaoNeural（女）/ zh-CN-YunxiNeural（男）。"""

    DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

    async def synthesize(self, text: str, out_path: str, voice: str = "") -> str:
        import edge_tts  # 延迟导入：未安装扩展依赖时不影响主服务

        voice = voice or self.DEFAULT_VOICE
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)
        return out_path


class ArkTTSProvider(TTSProvider):
    """火山方舟 TTS 骨架（OpenAI兼容 /audio/speech 接口，按控制台文档补全即可）。"""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def synthesize(self, text: str, out_path: str, voice: str = "") -> str:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/audio/speech",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": text, "voice": voice or "default"},
            )
            r.raise_for_status()
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(r.content)
            return out_path


def build_tts(cfg) -> TTSProvider:
    """工厂：默认使用免费的 Edge-TTS；需要商用级音质时切换 ArkTTSProvider。"""
    return EdgeTTSProvider()


async def demo() -> None:
    tts = EdgeTTSProvider()
    text = "您好，我是智赢CRM的AI助理。注意到贵司近期关注批量剪辑效率，我们准备了专属方案，期待与您交流。"
    path = await tts.synthesize(text, "data/aigc/follow_up_greeting.mp3")
    print(f"跟进话术已合成: {path}")


if __name__ == "__main__":
    asyncio.run(demo())
