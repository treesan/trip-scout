"""
携程酒店差评抓取模块

通过 Playwright + API 双轨方式抓取携程酒店评论，支持：
- 扫码登录 + Cookie持久化
- API优先(快) → 浏览器降级(稳)
- 差评分类统计(成长性/可接受/本质性/系统性)
- 近3月趋势分析
- 踩雷风险评估
"""
from .client import CtripClient, DEFAULT_COOKIE_PATH, DEFAULT_USER_DATA_DIR
from .login import check_login, login, logout
from .reviews import fetch_and_analyze, analyze_reviews, ReviewsFetcher, search_hotel_id

__all__ = [
    "CtripClient",
    "DEFAULT_COOKIE_PATH",
    "DEFAULT_USER_DATA_DIR",
    "check_login",
    "login",
    "logout",
    "fetch_and_analyze",
    "analyze_reviews",
    "search_hotel_id",
]
