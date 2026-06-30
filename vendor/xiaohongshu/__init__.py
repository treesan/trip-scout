"""
xiaohongshu-skill (vendored into trip-scout)

基于 xiaohongshu-mcp Go 源码翻译的 Python Playwright 实现
来源: https://github.com/DeliciousBuding/xiaohongshu-skill (MIT)
trip-scout 只内化酒店口碑验证需要的核心模块: client/login/search/feed。
写操作模块(comment/publish/interact 等)未纳入, 需要时从原 skill 获取。
"""

from .client import XiaohongshuClient, create_client, DEFAULT_COOKIE_PATH
from . import login
from . import search
from . import feed

__version__ = "1.3.0"
__all__ = [
    "XiaohongshuClient",
    "create_client",
    "DEFAULT_COOKIE_PATH",
    "login",
    "search",
    "feed",
]
