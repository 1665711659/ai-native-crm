"""AIGC 接口：ComfyUI 文生图（管理台可视化入口）。"""
import tornado.web

from app.ai.aigc.comfyui import ComfyUIClient
from app.handlers.base import ApiError, BaseHandler
from config import CONFIG


class AigcText2ImageHandler(BaseHandler):
    """POST /api/aigc/text2image —— 提交文生图任务并等待结果下载。

    body: {prompt, negative?, width?, height?, checkpoint?}
    返回: {files: ["aigc/xxx.png", ...]}（可直接作为 <img src> 使用）
    """

    async def post(self) -> None:
        body = self.get_json_body()
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            raise ApiError("提示词(prompt)不能为空")

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
            checkpoint=body.get("checkpoint") or CONFIG.comfyui_checkpoint,
        )
        # 磁盘路径 data/aigc/x.png -> Web路径 /aigc/x.png
        urls = ["/aigc/" + f.replace("\\", "/").split("data/aigc/")[-1] for f in files]
        self.ok({"files": urls, "count": len(urls)})


class AigcStatusHandler(BaseHandler):
    """GET /api/aigc/status —— ComfyUI 连接状态（管理台指示灯用）。"""

    async def get(self) -> None:
        ok = await ComfyUIClient(base_url=CONFIG.comfyui_url).ping()
        self.ok({"comfyui_url": CONFIG.comfyui_url, "connected": ok,
                 "checkpoint": CONFIG.comfyui_checkpoint})
