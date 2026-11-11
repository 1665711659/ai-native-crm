"""AIGC 接口：ComfyUI 文生图（管理台可视化入口）。"""
import re

import tornado.web

from app.ai.aigc.comfyui import ComfyUIClient
from app.handlers.base import ApiError, BaseHandler
from config import CONFIG

# 离线模式的中->英提示词词典（长词优先匹配）。配置 LLM_API_KEY 后走大模型翻译，效果更好。
ZH_EN_DICT = [
    ("商业产品摄影", "commercial product photography"), ("产品摄影", "product photography"),
    ("产品海报", "product poster"), ("宣传海报", "promotional poster"), ("海报", "poster"),
    ("现代科技风", "modern technology style"), ("科技感", "futuristic technology style"),
    ("高科技", "high technology"), ("科技", "technology"),
    ("水果汁", "fresh fruit juice"), ("果汁", "fruit juice"), ("好喝", "delicious"),
    ("水果", "fresh fruits"), ("奶茶", "milk tea"), ("咖啡", "coffee"),
    ("美食", "delicious food"), ("早餐", "breakfast"), ("蛋糕", "cake"),
    ("小狗", "cute puppy"), ("小猫", "cute kitten"), ("猫", "cat"), ("狗", "dog"),
    ("风景", "beautiful landscape"), ("雪山", "snow mountain"), ("森林", "forest"),
    ("日落", "sunset"), ("日出", "sunrise"), ("海滩", "beach"), ("星空", "starry night sky"),
    ("城市", "city skyline"), ("夜景", "city night view"), ("汽车", "car"),
    ("手机", "smartphone"), ("电脑", "laptop computer"), ("办公室", "modern office"),
    ("简洁", "clean minimal design"), ("高清", "high quality, detailed"),
    ("高质量", "high quality"), ("细节", "highly detailed"), ("真实", "realistic"),
    ("蓝色", "blue tone"), ("红色", "red tone"), ("绿色", "green tone"),
    ("温馨", "cozy warm atmosphere"), ("专业", "professional"), ("创意", "creative"),
    ("横版", "landscape composition"), ("竖版", "portrait composition"),
    ("一杯", "a glass of"), ("一瓶", "a bottle of"), ("一个", "a"), ("夏天", "summer"),
    ("冬天", "winter"), ("阳光", "sunlight"), ("灯光", "studio lighting"),
    ("背景", "background"), ("特写", "close-up shot"), ("静物", "still life"),
]


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


async def _translate_prompt(text: str, llm) -> tuple[str, str]:
    """中文提示词 -> 英文 SD prompt。返回 (翻译结果, 来源说明)。

    优先级：英文原样 > LLM 翻译 > 离线词典兜底。
    """
    if not _has_chinese(text):
        return text, "英文输入，无需翻译"

    if CONFIG.llm_configured:
        try:
            r = await llm.chat([{
                "role": "user",
                "content": (
                    "将下面的中文描述翻译并扩写成一段英文 Stable Diffusion 提示词。"
                    "要求：标签式短语用逗号连接，包含主体、风格、光影、画质词，"
                    "只输出英文提示词本身，不要任何解释。\n\n中文：" + text
                ),
            }])
            if r.content and not _has_chinese(r.content.strip()):
                return r.content.strip(), "LLM 翻译"
        except Exception:  # noqa: BLE001 —— LLM失败降级词典
            pass

    translated = text
    for zh, en in ZH_EN_DICT:
        translated = translated.replace(zh, f", {en}, ")
    leftover = re.sub(r"[\u4e00-\u9fff]", "", translated)      # 删未命中的汉字
    leftover = re.sub(r"[，。！？、：；]", ",", leftover)          # 中文标点转英文逗号
    leftover = re.sub(r",(\s*,)+", ",", leftover)              # 折叠连续逗号
    leftover = re.sub(r"\s*,\s*", ", ", leftover).strip(" ,")  # 规范化逗号间距
    if not leftover:
        leftover = text  # 完全翻不出来，原样交给模型
    note = "离线词典翻译（词汇有限，配置 LLM_API_KEY 可获得完整翻译扩写）"
    return leftover, note


class AigcText2ImageHandler(BaseHandler):
    """POST /api/aigc/text2image —— 提交文生图任务并等待结果下载。

    body: {prompt, negative?, width?, height?, steps?, checkpoint?}
    支持中文提示词：自动翻译为英文 SD prompt（LLM 优先 / 离线词典兜底）。
    返回: {files: [...], translated: "...", translate_note: "..."}
    """

    async def post(self) -> None:
        body = self.get_json_body()
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            raise ApiError("提示词(prompt)不能为空")

        prompt, translate_note = await _translate_prompt(prompt, self.ctx.llm)

        client = ComfyUIClient(base_url=CONFIG.comfyui_url)
        if not await client.ping():
            raise ApiError(
                f"ComfyUI 未连接（{CONFIG.comfyui_url}）。请先启动本机 ComfyUI，"
                f"或在 .env 修改 COMFYUI_URL。", status=503)

        files = await client.text2image(
            prompt=prompt,
            negative=body.get("negative", ""),
            width=self.to_int(body.get("width", 1024), 1024, "width"),
            height=self.to_int(body.get("height", 1024), 1024, "height"),
            steps=min(max(self.to_int(body.get("steps", 20), 20, "steps"), 4), 50),
            checkpoint=body.get("checkpoint") or CONFIG.comfyui_checkpoint,
        )
        # 磁盘路径 data/aigc/x.png -> Web路径 /aigc/x.png
        urls = ["/aigc/" + f.replace("\\", "/").split("data/aigc/")[-1] for f in files]
        self.ok({"files": urls, "count": len(urls),
                 "translated": prompt, "translate_note": translate_note})


class AigcStatusHandler(BaseHandler):
    """GET /api/aigc/status —— ComfyUI 连接状态（管理台指示灯用）。"""

    async def get(self) -> None:
        ok = await ComfyUIClient(base_url=CONFIG.comfyui_url).ping()
        self.ok({"comfyui_url": CONFIG.comfyui_url, "connected": ok,
                 "checkpoint": CONFIG.comfyui_checkpoint})
