"""数字员工示例3：Airtest 安卓自动化（移动端数字员工）。

适用场景：在企业微信/钉钉 APP 内自动执行客户跟进动作 ——
定时给待跟进客户发送个性化消息（内容来自 LLM 生成），实现"手机上的数字员工"。

环境准备：
    pip install airtest
    安卓手机开启USB调试连接，或启动模拟器（adb devices 可见设备）
    首次需在Airtest IDE中对自己的企微版本截图并替换下方图片资源路径

嵌入 async 服务：Airtest 为同步API，用 IOLoop.run_in_executor 包装即可：
    result = await IOLoop.current().run_in_executor(None, send_wechat_followup, ...)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WeComDigitalEmployee:
    """企业微信自动跟进数字员工（骨架：核心流程已给出，坐标/图片需按机型适配）。

    稳定性建议：
    - 优先使用 airtest 的图片识别（touch(Template(...))）而非写死坐标；
    - 关键步骤后 snapshot() 留证；
    - 接入 poco（原生控件定位）可进一步提升稳定性（需目标APP支持）。
    """

    def __init__(self, device_serial: str) -> None:
        self.device_serial = device_serial

    def connect(self) -> None:
        from airtest.core.api import connect_device

        connect_device(f"android:///{self.device_serial}")

    def open_customer_chat(self, customer_name: str) -> bool:
        """打开与指定客户的会话：搜索 → 点击结果。"""
        from airtest.core.api import exists, template, touch, wait

        # 1. 打开企业微信（包名按实际环境调整）
        # start_app("com.tencent.wework")
        # 2. 点击搜索入口（Template 使用项目内截图资源）
        # touch(Template("img/wecom_search.png", record_pos=..., resolution=...))
        # 3. 输入客户名并搜索
        # text(customer_name)
        # 4. 点击搜索结果中的客户
        # if exists(Template("img/wecom_chat_item.png")): touch(...); return True
        logger.info("open_customer_chat(%s) —— 骨架流程，请按机型/APP版本适配资源图", customer_name)
        return True

    def send_message(self, customer_name: str, message: str) -> dict:
        """完整动作：打开会话 → 输入消息 → 发送 → 截图留证。"""
        from airtest.core.api import snapshot, text, touch  # noqa: F401

        if not self.open_customer_chat(customer_name):
            return {"ok": False, "error": f"未找到客户会话: {customer_name}"}
        # text(message)
        # touch(Template("img/wecom_send.png"))
        # snapshot(filename=f"data/digital_employee/followup_{customer_name}.png")
        logger.info("send_message -> %s: %s", customer_name, message[:30])
        return {"ok": True, "customer": customer_name, "message": message}


def run_followup_batch(device_serial: str, tasks: list[dict]) -> list[dict]:
    """批量执行跟进：tasks = [{customer_name, message}, ...]。

    典型编排（生产）：
      CRM库中查询 next_follow_up_at <= now 的客户
      → LLM 生成个性化话术（含客户历史跟进上下文）
      → 本函数批量执行 → 写回跟进记录(channel='wecom_auto')
    """
    employee = WeComDigitalEmployee(device_serial)
    employee.connect()
    results = []
    for t in tasks:
        results.append(employee.send_message(t["customer_name"], t["message"]))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 示例：python -m app.ai.digital_employee.android_airtest
    print("Airtest 数字员工骨架。请连接设备后调用 run_followup_batch()。")
    print("任务示例：", [{"customer_name": "王建国", "message": "王总您好，上次聊到的方案我发您微信了~"}])
