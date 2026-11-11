"""FFmpeg 视频后处理工具集：subprocess 异步封装。

覆盖 AIGC 视频生产线的通用后处理环节：
- delogo       去除水印（插值填充）
- burn_subtitle 烧录字幕（默认样式：微软雅黑、白字黑边、底部居中）
- replace_audio 替换音轨（AI视频保留原视频原声的典型需求）
- concat       分段拼接
- extract_audio 抽取音轨

运行 demo：python -m app.ai.aigc.ffmpeg（生成测试媒体并演示全流程）
"""
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FFmpegToolkit:
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg = ffmpeg_path

    # ------------------------------------------------------------------
    async def _run(self, args: list[str]) -> bytes:
        """执行 ffmpeg 命令，失败时抛出带 stderr 的异常。"""
        proc = await asyncio.create_subprocess_exec(
            self.ffmpeg, *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg 执行失败: {err.decode(errors='ignore')[-1500:]}")
        return _out

    # ------------------------------------------------------------------
    # 原子能力
    # ------------------------------------------------------------------
    async def delogo(self, input: str, output: str,
                     x: int, y: int, w: int, h: int) -> str:
        """去除视频水印区域（双线性插值填充）。坐标为水印矩形左上角与宽高。"""
        await self._run(["-y", "-i", input,
                         "-vf", f"delogo=x={x}:y={y}:w={w}:h={h}",
                         "-c:a", "copy", output])
        return output

    async def burn_subtitle(self, input: str, output: str, srt_path: str,
                            style: str | None = None) -> str:
        """烧录SRT字幕。默认样式：微软雅黑16px、白字黑边、底部居中。

        Windows注意：srt 路径建议使用相对路径或正斜杠，避免盘符冒号与
        subtitles滤镜参数分隔符冲突；含空格路径需用引号包裹。
        """
        style = style or ("FontName=Microsoft YaHei,FontSize=16,PrimaryColour=&H00FFFFFF,"
                          "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
                          "Alignment=2,MarginV=40")
        await self._run(["-y", "-i", input,
                         "-vf", f"subtitles={srt_path}:force_style='{style}'",
                         "-c:a", "copy", output])
        return output

    async def replace_audio(self, video: str, audio: str, output: str) -> str:
        """替换视频音轨（如AI生成画面保留原视频原声）。"""
        await self._run(["-y", "-i", video, "-i", audio,
                         "-map", "0:v", "-map", "1:a",
                         "-c:v", "copy", "-c:a", "aac", "-shortest", output])
        return output

    async def concat(self, segments: list[str], output: str, list_file: str | None = None) -> str:
        """无损拼接分段视频（需编码参数一致）。"""
        list_file = list_file or "data/aigc/concat_list.txt"
        Path(list_file).parent.mkdir(parents=True, exist_ok=True)
        content = "".join(f"file '{Path(s).as_posix()}'\n" for s in segments)
        Path(list_file).write_text(content, encoding="utf-8")
        await self._run(["-y", "-f", "concat", "-safe", "0", "-i", list_file,
                         "-c", "copy", output])
        return output

    async def extract_audio(self, video: str, output: str) -> str:
        """抽取音轨（后续可送 ASR 转写或复用给新视频）。"""
        await self._run(["-y", "-i", video, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output])
        return output

    # ------------------------------------------------------------------
    # 组合流水线示例：AI片段 → 去水印 → 烧字幕 → 换回原声
    # ------------------------------------------------------------------
    async def postprocess_ai_clip(self, ai_clip: str, original_clip: str,
                                  srt_path: str | None = None,
                                  logo_box: tuple | None = None,
                                  output: str = "data/aigc/final.mp4") -> str:
        """AI生成片段的标准后处理：去水印(可选) → 烧字幕(可选) → 替换为原视频音轨。"""
        work = Path("data/aigc")
        work.mkdir(parents=True, exist_ok=True)
        cur = ai_clip

        if logo_box:
            x, y, w, h = logo_box
            cur = await self.delogo(cur, str(work / "step1_delogo.mp4"), x, y, w, h)

        if srt_path:
            cur = await self.burn_subtitle(cur, str(work / "step2_sub.mp4"), srt_path)

        # 抽出原视频音轨并替换
        orig_audio = await self.extract_audio(original_clip, str(work / "orig_audio.mp3"))
        await self.replace_audio(cur, orig_audio, output)
        logger.info("后处理完成: %s", output)
        return output


async def demo() -> None:
    """生成10秒测试视频并演示后处理流水线。"""
    logging.basicConfig(level=logging.INFO)
    tk = FFmpegToolkit()
    work = Path("data/aigc")
    work.mkdir(parents=True, exist_ok=True)
    test_video = str(work / "test_src.mp4")

    await tk._run(["-y", "-f", "lavfi", "-i", "testsrc=duration=10:size=1280x720:rate=25",
                   "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
                   "-c:v", "libx264", "-c:a", "aac", "-shortest", test_video])
    print(f"测试视频已生成: {test_video}")
    print("可用流水线（示例）: await tk.postprocess_ai_clip(ai_clip, original, 'subs.srt', logo_box=(x,y,w,h))")


if __name__ == "__main__":
    asyncio.run(demo())
