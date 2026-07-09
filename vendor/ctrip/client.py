"""
携程浏览器客户端封装

使用 Playwright 持久化上下文，
支持扫码登录、Cookie持久化、反检测隐身脚本。
"""
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright
except ImportError:
    print("请先安装 playwright: pip install playwright && playwright install chromium", file=sys.stderr)
    raise


# Cookie 文件路径（备份用）
DEFAULT_COOKIE_PATH = os.path.expanduser("~/.ctrip/cookies.json")

# 持久化浏览器数据目录（保存 cookies + localStorage + sessionStorage 等全部会话状态）
DEFAULT_USER_DATA_DIR = os.path.expanduser("~/.ctrip/browser-data")


class CtripClient:
    """携程浏览器客户端"""

    # 频率控制参数
    MIN_INTERVAL = 2.0       # 两次导航最小间隔（秒）
    MAX_INTERVAL = 5.0       # 两次导航最大间隔（秒）
    BURST_THRESHOLD = 5      # 连续请求阈值，超过后增加额外冷却
    BURST_COOLDOWN = 8.0     # 连续请求冷却时间（秒）

    def __init__(
        self,
        headless: bool = True,
        cookie_path: str = DEFAULT_COOKIE_PATH,
        user_data_dir: str = DEFAULT_USER_DATA_DIR,
        timeout: int = 60,
    ):
        self.headless = headless
        self.cookie_path = cookie_path
        self.user_data_dir = user_data_dir
        self.timeout = timeout * 1000  # 转换为毫秒

        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 请求计时器
        self._last_navigate_time: float = 0.0
        self._navigate_count: int = 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """启动浏览器（持久化上下文，自动保存全部会话状态）"""
        self.playwright = sync_playwright().start()
        os.makedirs(self.user_data_dir, exist_ok=True)

        # 使用持久化上下文：自动保存 cookies + localStorage + sessionStorage
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ],
            ignore_default_args=['--enable-automation'],
        )

        # 注入反检测隐身脚本
        self.context.add_init_script(STEALTH_JS)

        # 如果持久化目录是新的但有旧 cookie 备份文件，迁移恢复
        if not self.context.cookies() and os.path.exists(self.cookie_path):
            self._load_cookies()

        # 复用持久化上下文的已有页面，或创建新页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout)

    def close(self):
        """关闭浏览器"""
        self._save_cookies()

        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

    def _load_cookies(self):
        """从文件加载 Cookie"""
        if not os.path.exists(self.cookie_path):
            return
        try:
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            if cookies:
                self.context.add_cookies(cookies)
        except Exception as e:
            print(f"加载 Cookie 失败: {e}", file=sys.stderr)

    def _save_cookies(self):
        """保存 Cookie 到文件"""
        if not self.context:
            return
        try:
            cookies = self.context.cookies()
            os.makedirs(os.path.dirname(self.cookie_path), exist_ok=True)
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存 Cookie 失败: {e}", file=sys.stderr)

    def _throttle(self):
        """请求频率控制"""
        now = time.time()
        elapsed = now - self._last_navigate_time if self._last_navigate_time > 0 else 999

        if self._navigate_count > 0 and self._navigate_count % self.BURST_THRESHOLD == 0:
            cooldown = self.BURST_COOLDOWN + random.uniform(0, 3)
            if elapsed < cooldown:
                wait = cooldown - elapsed
                time.sleep(wait)
        elif elapsed < self.MIN_INTERVAL:
            wait = random.uniform(self.MIN_INTERVAL, self.MAX_INTERVAL) - elapsed
            if wait > 0:
                time.sleep(wait)

        self._last_navigate_time = time.time()
        self._navigate_count += 1

    def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """导航到指定 URL（含频率控制）"""
        if not self.page:
            raise RuntimeError("浏览器未启动")

        self._throttle()
        self.page.goto(url, wait_until=wait_until)
        time.sleep(random.uniform(1.5, 3.0))
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass


# 反检测隐身脚本
STEALTH_JS = """
// 1. 移除 navigator.webdriver 标记
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. 伪造 chrome 运行时对象
if (!window.chrome) { window.chrome = {}; }
if (!window.chrome.runtime) {
    window.chrome.runtime = {
        onMessage: { addListener: function(){}, removeListener: function(){} },
        sendMessage: function(){},
        connect: function(){ return { onMessage: { addListener: function(){} }, postMessage: function(){} }; }
    };
}

// 3. 伪造插件列表
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const arr = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        arr.item = (i) => arr[i] || null;
        arr.namedItem = (n) => arr.find(p => p.name === n) || null;
        arr.refresh = () => {};
        return arr;
    }
});

// 4. 伪造语言列表
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });

// 5. 修复 Permissions API
if (navigator.permissions) {
    const origQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (params) => {
        if (params.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return origQuery(params);
    };
}

// 6. WebGL 渲染器信息
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {
    if (param === 37445) return 'Intel Inc.';
    if (param === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, param);
};
"""
