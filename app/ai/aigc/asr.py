"""ASR（语音转写）模块：把销售通话录音转为结构化文本，喂给 LLM 做跟进摘要。

典型CRM链路：通话录音 → ASR转写 → LLM提取(需求/预算/异议/下一步) → 自动写跟进记录。

- LocalWhisperProvider：本地 faster-whisper（免费、离线、中文效果好）。
  安装：pip install faster-whisper （首次运行自动下载模型）
- 云端ASR（火山/阿里）：实现 ASRProvider 接口替换即可。

运行 demo：python -m app.ai.aigc.asr data/call.wav
"""
import asyncio
import sys
from abc import ABC, abstractmethod
from pathlib import Path


class ASRProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, language: str = "zh") -> str:
        """转写音频文件，返回纯文本。"""


class LocalWhisperProvider(ASRProvider):
    """本地 faster-whisper（CTranslate2 加速版，CPU 可跑）。"""

    def __init__(self, model_size: str = "small") -> None:
        self.model_size = model_size
        self._model = None  # 懒加载

    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # 延迟导入：扩展依赖
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(self, audio_path: str, language: str = "zh") -> str:
        model = self._ensure_model()
        segments, _info = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: model.transcribe(audio_path, language=language, vad_filter=True),
        )
        return "".join(seg.text for seg in segments).strip()


async def llm_extract_follow_up(transcript: str, llm) -> dict:
    """示例：转写文本 → LLM 结构化提取（供 Agent 写入跟进记录）。"""
    result = await llm.chat([{
        "role": "user",
        "content": (
            "从以下销售通话转写中提取结构化信息，返回JSON："
            '{"customer_intent": "", "budget": "", "objections": [], "next_step": ""}\n\n'
            f"转写内容：\n{transcript}"
        ),
    }], temperature=0.1)
    return {"transcript": transcript, "extraction": result.content}


async def demo() -> None:
    if len(sys.argv) < 2:
        print("用法: python -m app.ai.aigc.asr <音频文件路径>")
        return
    audio = Path(sys.argv[1])
    if not audio.exists():
        print(f"文件不存在: {audio}")
        return
    text = await LocalWhisperProvider().transcribe(str(audio))
    print(f"转写结果：\n{text}")


if __name__ == "__main__":
    asyncio.run(demo())
