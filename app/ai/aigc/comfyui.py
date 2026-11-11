"""ComfyUI 对接客户端：把 ComfyUI 的 AIGC 生图能力接入 CRM 业务。

能力：提交 workflow（/prompt）→ 轮询结果（/history）→ 下载产物（/view）
典型 CRM 场景：
- 营销素材生成：输入活动文案 → LLM 产出画面提示词 → ComfyUI 生成海报/配图；
- 客户案例图定制：批量生成行业化封面图。

运行 demo（需本地 ComfyUI 已启动，默认 http://127.0.0.1:8188）：
    python -m app.ai.aigc.comfyui
"""
import asyncio
import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """ComfyUI REST API 客户端。

    ComfyUI 的 workflow 有两种格式：
    - UI导出的节点图格式（带 nodes/links）—— 用于 /api 开头的 API格式接口；
    - API格式（prompt/类名为键的扁平JSON）—— 直接提交给 /prompt。
    此客户端使用后者（在ComfyUI里「设置→开启Dev模式→导出API格式」获取模板）。
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.AsyncClient(timeout=timeout)

    # ------------------------------------------------------------------
    # 基础能力
    # ------------------------------------------------------------------
    async def ping(self) -> bool:
        try:
            r = await self.http.get(f"{self.base_url}/system_stats")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def submit(self, workflow_api: dict) -> str:
        """提交工作流，返回 prompt_id（用于查询结果）。"""
        r = await self.http.post(f"{self.base_url}/prompt", json={"prompt": workflow_api})
        r.raise_for_status()
        return r.json()["prompt_id"]

    async def wait_result(self, prompt_id: str, timeout: float = 300, interval: float = 2.0) -> dict:
        """轮询 /history 直到任务完成，返回 outputs 结构。"""
        waited = 0.0
        while waited < timeout:
            r = await self.http.get(f"{self.base_url}/history/{prompt_id}")
            r.raise_for_status()
            data = r.json()
            entry = data.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("completed") or entry.get("outputs"):
                    return entry.get("outputs", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI执行失败: {json.dumps(status, ensure_ascii=False)}")
            await asyncio.sleep(interval)
            waited += interval
        raise TimeoutError(f"等待ComfyUI结果超时: {prompt_id}")

    async def collect_files(self, outputs: dict, out_dir: str = "data/aigc") -> list[str]:
        """从 outputs 中收集图片/视频产物并下载到本地。"""
        files = []
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for node_result in outputs.values():
            for key in ("images", "gifs", "videos"):
                for item in node_result.get(key, []):
                    if item.get("type") != "output":
                        continue
                    params = {"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                              "type": "output"}
                    r = await self.http.get(f"{self.base_url}/view", params=params)
                    r.raise_for_status()
                    path = out / item["filename"]
                    path.write_bytes(r.content)
                    files.append(str(path))
        return files

    # ------------------------------------------------------------------
    # 高层封装：文生图（模板化的最小 SD workflow，按本地模型名修改）
    # ------------------------------------------------------------------
    async def text2image(self, prompt: str, negative: str = "", width: int = 1024,
                         height: int = 1024, steps: int = 25, seed: int | None = None,
                         checkpoint: str = "sd_xl_base_1.0.safetensors",
                         out_dir: str = "data/aigc") -> list[str]:
        """文生图：组装最小可用 workflow 并提交。

        注意：checkpoint 需替换为本机 ComfyUI/models/checkpoints 下实际存在的模型名。
        """
        import random
        if seed is None:
            seed = random.randint(1, 2**31)

        workflow = {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": seed, "steps": steps, "cfg": 7.0,
                "sampler_name": "euler", "scheduler": "normal",
                "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0],
                "negative": ["7", 0], "latent_image": ["5", 0]}},
            "4": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": checkpoint}},
            "5": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": negative or "低质量、变形、多余手指", "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "crm_aigc",
                                                        "images": ["8", 0]}},
        }
        prompt_id = await self.submit(workflow)
        logger.info("ComfyUI任务已提交: %s", prompt_id)
        outputs = await self.wait_result(prompt_id)
        return await self.collect_files(outputs, out_dir)


async def demo() -> None:
    """独立演示：为CRM营销活动生成一张宣传图。"""
    logging.basicConfig(level=logging.INFO)
    client = ComfyUIClient()
    if not await client.ping():
        print("ComfyUI 未启动（默认 http://127.0.0.1:8188），请先启动后重试。")
        return
    files = await client.text2image(
        prompt="modern SaaS CRM dashboard, clean UI, blue theme, professional, "
               "high quality, 4k, marketing poster",
        width=1024, height=1024,
    )
    print("生成完成：")
    for f in files:
        print("  ", f)


if __name__ == "__main__":
    asyncio.run(demo())
