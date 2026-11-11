"""导入演示客户数据（可选，不会污染知识库）。

运行：python scripts/seed_data.py
说明：customers 表已有数据时跳过；服务启动时知识库种子单独自动导入。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import Database  # noqa: E402
from app.services.customer_service import CustomerService  # noqa: E402
from config import CONFIG  # noqa: E402

SEED_CUSTOMERS = [
    {"name": "王建国", "company": "长沙卓锐传媒有限公司", "phone": "13807311234",
     "email": "wangjg@zhuorui.cn", "industry": "文化传媒", "status": "prospect",
     "value": 36000, "source": "官网留资", "notes": "短视频带货团队，20人规模，关注批量剪辑效率"},
    {"name": "李思颖", "company": "深圳市星河智造科技有限公司", "phone": "13923885671",
     "email": "lisy@xinghe-tech.com", "industry": "智能制造", "status": "negotiating",
     "value": 128000, "source": "展会", "notes": "50账号旗舰版意向，法务审核合同中"},
    {"name": "张伟", "company": "北京云杉教育集团", "phone": "13701234567",
     "email": "zhangwei@yunsan-edu.cn", "industry": "教育", "status": "lead",
     "value": 15000, "source": "广告投放", "notes": "K12转型职业培训，询问教育优惠"},
    {"name": "陈曼", "company": "杭州锦鲤电子商务有限公司", "phone": "13666668888",
     "email": "chenman@jinli-ec.com", "industry": "电商零售", "status": "won",
     "value": 88000, "source": "老客户转介绍", "notes": "已签年付专业版30账号"},
    {"name": "刘洋", "company": "成都蓉城医疗器械有限公司", "phone": "13508156789",
     "email": "liuyang@rc-med.cn", "industry": "医疗器械", "status": "prospect",
     "value": 66000, "source": "销售陌拜", "notes": "合规要求高，需要私有化部署方案"},
    {"name": "赵晓红", "company": "上海骏达物流股份公司", "phone": "13482123456",
     "email": "zhaoxh@junda-logi.com", "industry": "物流运输", "status": "lost",
     "value": 0, "source": "电话销售", "notes": "预算原因暂缓，半年后复访"},
    {"name": "孙浩", "company": "广州猎鹰网络科技有限公司", "phone": "13318889999",
     "email": "sunhao@lieying.net", "industry": "游戏", "status": "negotiating",
     "value": 45000, "source": "内容营销", "notes": "对比竞品中，重点演示了数字员工模块"},
    {"name": "周婷", "company": "武汉光谷生物技术公司", "phone": "13277770000",
     "email": "zhouting@gg-bio.cn", "industry": "生物医药", "status": "lead",
     "value": 20000, "source": "线上直播", "notes": "研发销售双团队使用场景"},
]

SEED_FOLLOW_UPS = [
    (1, "电话沟通30分钟，对方关注批量剪辑产出效率，约下周演示AIGC模块", "phone"),
    (2, "发送报价单与SLA条款，等待法务反馈，预计本周签约", "email"),
    (4, "完成合同签署与首期付款，安排实施排期，下周 kickoff", "visit"),
    (7, "竞品对比演示：重点展示Agent自然语言查客户与自动跟进写入", "visit"),
]


async def main() -> None:
    db = Database(CONFIG)
    await db.connect()
    await db.init_schema()
    svc = CustomerService(db)

    existing = await db.fetch_one("SELECT COUNT(*) AS c FROM customers")
    if existing and existing["c"] > 0:
        print(f"客户表已有 {existing['c']} 条数据，跳过导入。")
        await db.close()
        return

    for data in SEED_CUSTOMERS:
        customer = await svc.create(data)
        print(f"  + 客户[{customer['id']}] {customer['name']} - {customer['company']}")
        for cid, content, channel in SEED_FOLLOW_UPS:
            if cid == customer["id"]:
                await svc.add_follow_up(cid, content, channel=channel)

    stats = await svc.stats()
    print(f"\n导入完成：{stats['total_customers']} 位客户，总金额 {stats['total_value']} 元")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
