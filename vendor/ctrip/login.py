"""
携程登录模块

支持扫码登录携程，Cookie持久化到 ~/.ctrip/
"""
import json
import os
import sys
import time
from typing import Optional, Tuple, Dict, Any

from .client import CtripClient, DEFAULT_COOKIE_PATH, DEFAULT_USER_DATA_DIR


class LoginAction:
    """携程登录动作"""

    def __init__(self, client: CtripClient):
        self.client = client

    def check_login_status(self, navigate: bool = True) -> Tuple[bool, Optional[str]]:
        """
        检查登录状态

        Returns:
            (是否已登录, 用户名)
        """
        page = self.client.page

        if navigate:
            self.client.navigate("https://www.ctrip.com")
            time.sleep(3)

        # 方式1：检查 cookie 里是否包含登录相关字段
        # 携程登录成功后会出现这些cookie（按可靠性排序）
        try:
            cookies = self.client.context.cookies()
            login_cookie_names = [
                '_u', 'UA', '_jfi', 'MKT_Pages viewed',
                'IsLogged', 'ticket', 'cticket',
                # 携程passport域登录标识
                'w_tuid', 'w_lid',
            ]
            # 只看 .ctrip.com 域名的cookie
            ctrip_cookies = [c for c in cookies if 'ctrip.com' in c.get('domain', '')]
            found = [c['name'] for c in ctrip_cookies if c['name'] in login_cookie_names]
            if found:
                username = self._try_get_username()
                return True, username or "已登录用户"
        except Exception:
            pass

        # 方式2：通过JS检查页面登录状态
        try:
            is_logged = page.evaluate("""() => {
                // 携程首页会设置全局变量
                if (window.userInfo && window.userInfo.isLogin) return true;
                // 检查header中的用户信息
                const userEl = document.querySelector(
                    '[class*="header-user"], [class*="user-name"], [class*="userName"], ' +
                    '[class*="login-success"], [data-login="true"]'
                );
                if (userEl) return true;
                // 检查是否有登录/注册按钮（有=未登录）
                const loginBtn = document.querySelector('[class*="login-btn"], [class*="LoginBtn"]');
                if (!loginBtn) return true;  // 没有登录按钮=已登录
                return false;
            }""")
            if is_logged:
                username = self._try_get_username()
                return True, username or "已登录用户"
        except Exception:
            pass

        return False, None

    def _try_get_username(self) -> Optional[str]:
        """尝试从页面提取用户昵称"""
        try:
            name = self.client.page.evaluate("""() => {
                if (window.userInfo && window.userInfo.nickName) return window.userInfo.nickName;
                const el = document.querySelector(
                    '.header-user-name, .user-name, [class*="nickname"], [class*="userName"]'
                );
                return el ? el.textContent.trim() : '';
            }""")
            return name if name else None
        except Exception:
            return None

    def wait_for_login(self, timeout: int = 180, min_wait: int = 5) -> bool:
        """
        等待用户扫码登录

        携程登录页面会显示二维码，用户用携程App扫码即可。
        min_wait设短，让检测尽早开始。

        Args:
            timeout: 总超时(秒)
            min_wait: 最少等待(秒) — 设短一些让检测早开始

        Returns:
            是否登录成功
        """
        start = time.time()
        prev_cookie_count = len(self.client.context.cookies())

        print(f"⏳ 请用携程App扫描二维码登录（超时{timeout}秒）...", file=sys.stderr)

        # 阶段1: 短暂强制等待
        while time.time() - start < min_wait:
            time.sleep(1)

        # 阶段2: 高频轮询检测
        check_count = 0
        while time.time() - start < timeout:
            check_count += 1
            try:
                # 方法A: 检查cookie数量变化（最可靠）
                cookies = self.client.context.cookies()
                ctrip_cookies = [c for c in cookies if 'ctrip.com' in c.get('domain', '')]
                current_count = len(cookies)

                # 登录后cookie数量会显著增加
                if current_count > prev_cookie_count + 5:
                    print(f"✅ 检测到Cookie数量变化 {prev_cookie_count} → {current_count}，登录成功！", file=sys.stderr)
                    time.sleep(3)
                    try:
                        self.client.page.goto("https://www.ctrip.com", wait_until="networkidle", timeout=15000)
                        time.sleep(3)
                    except Exception:
                        time.sleep(3)
                    self.client._save_cookies()
                    return True

                # 方法B: 检查已知登录cookie名
                login_cookie_names = ['_u', 'UA', '_jfi', 'IsLogged', 'ticket', 'cticket']
                found = [c['name'] for c in ctrip_cookies if c['name'] in login_cookie_names]
                if found:
                    print(f"✅ 检测到登录Cookie: {found}，登录成功！", file=sys.stderr)
                    time.sleep(3)
                    try:
                        self.client.page.goto("https://www.ctrip.com", wait_until="networkidle", timeout=15000)
                        time.sleep(3)
                    except Exception:
                        time.sleep(3)
                    self.client._save_cookies()
                    return True

                # 方法C: 检查页面URL是否跳转回首页
                current_url = self.client.page.url
                if 'passport.ctrip.com' not in current_url and 'login' not in current_url.lower():
                    print(f"✅ 页面已跳转到 {current_url}，登录成功！", file=sys.stderr)
                    time.sleep(3)
                    self.client._save_cookies()
                    return True

                # 方法D: 通过JS检查页面元素
                if check_count % 3 == 0:  # 每3次检查一次JS，减少性能开销
                    try:
                        is_logged = self.client.page.evaluate("""() => {
                            if (window.userInfo && window.userInfo.isLogin) return true;
                            const el = document.querySelector('[class*="header-user"], [data-login="true"]');
                            return !!el;
                        }""")
                        if is_logged:
                            print("✅ 页面检测到登录状态，登录成功！", file=sys.stderr)
                            time.sleep(3)
                            self.client._save_cookies()
                            return True
                    except Exception:
                        pass

                # 更新cookie计数基线（页面刷新可能带来新cookie）
                prev_cookie_count = max(prev_cookie_count, current_count)

            except Exception as e:
                if check_count % 10 == 0:
                    print(f"  检测异常: {e}", file=sys.stderr)

            # 进度提示
            elapsed = int(time.time() - start)
            if elapsed > 0 and elapsed % 30 == 0:
                print(f"  仍在等待扫码... 已等{elapsed}秒", file=sys.stderr)

            time.sleep(2)

        print("❌ 登录超时", file=sys.stderr)
        return False


# ====== 顶层便捷函数 ======

def check_login(
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> Tuple[bool, Optional[str]]:
    """检查登录状态"""
    client = CtripClient(headless=True, cookie_path=cookie_path)
    try:
        client.start()
        action = LoginAction(client)
        return action.check_login_status(navigate=True)
    finally:
        client.close()


def login(
    headless: bool = False,
    cookie_path: str = DEFAULT_COOKIE_PATH,
    timeout: int = 180,
) -> Dict[str, Any]:
    """
    登录携程（打开浏览器 → 用户扫码 → 等待登录）

    Args:
        headless: True=不弹窗口(需先生成二维码), False=弹窗口扫码(推荐)
        timeout: 超时秒数(默认180)

    Returns:
        登录结果字典
    """
    client = CtripClient(headless=headless, cookie_path=cookie_path)
    try:
        client.start()
        action = LoginAction(client)

        # 先检查是否已登录
        is_logged_in, username = action.check_login_status(navigate=True)
        if is_logged_in:
            return {
                "status": "logged_in",
                "username": username,
                "message": "已登录",
            }

        # 导航到携程登录页面
        client.navigate("https://passport.ctrip.com/user/login")
        time.sleep(3)

        # 携程登录页默认显示二维码，等待用户扫码
        print("请在弹出的浏览器窗口中扫码登录...", file=sys.stderr)

        success = action.wait_for_login(timeout=timeout)
        if success:
            # 再确认一下
            is_logged_in, username = action.check_login_status(navigate=False)
            return {
                "status": "logged_in",
                "username": username or "已登录用户",
                "message": "扫码登录成功",
            }
        return {
            "status": "timeout",
            "username": None,
            "message": "扫码超时",
        }

    finally:
        client.close()


def logout(cookie_path: str = None):
    """删除浏览器持久化数据和 Cookie 文件，重置登录状态"""
    import shutil
    user_data_dir = DEFAULT_USER_DATA_DIR
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir)
    path = cookie_path or DEFAULT_COOKIE_PATH
    if os.path.exists(path):
        os.remove(path)
    return {"status": "ok", "message": "登录状态已清除"}
