"""Tornado API 接口层：统一响应格式 / 错误处理 / 路由注册。"""
from app.handlers.agent_handler import AgentChatHandler
from app.handlers.base import BaseHandler, HealthHandler
from app.handlers.customer_handler import (CustomerDetailHandler,
                                           CustomerListHandler,
                                           FollowUpListHandler)
from app.handlers.rag_handler import (RAGDocumentListHandler,
                                      RAGIndexHandler, RAGQueryHandler)
from app.handlers.workflow_handler import WorkflowTriggerHandler

__all__ = [
    "BaseHandler", "HealthHandler",
    "CustomerListHandler", "CustomerDetailHandler", "FollowUpListHandler",
    "RAGQueryHandler", "RAGIndexHandler", "RAGDocumentListHandler",
    "AgentChatHandler", "WorkflowTriggerHandler",
]
