"""
小红书通用工具：a1/web_id 生成、sec cookie 获取

基于 Spider_XHS (https://github.com/cv-cat/Spider_XHS) xhs_utils/common_util.py，
移除了对 xhs_creator_util 的依赖，将 generate_xsc 内联。
移除了 load_env/init（trip-scout 不使用 .env 方式管理 cookie）。
"""
import os
import time
import random
import hashlib
import binascii
import json

import execjs
import requests
from loguru import logger

from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_util import generate_xs_xs_common, generate_x_b3_traceid, generate_xray_traceid

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
_WEBSECTIGA_ENV_PATH = os.path.join(_STATIC_DIR, 'xhs_websectiga_env.js')

_A1_CHARSET = 'abcdefghijklmnopqrstuvwxyz1234567890'
_AS_URL = 'https://as.xiaohongshu.com'


def generate_a1():
    """生成小红书 a1 cookie 值"""
    ts_hex = hex(int(time.time() * 1000))[2:]
    random_str = ''.join(random.choices(_A1_CHARSET, k=30))
    a_part = ts_hex + random_str + '5' + '0' + '000'
    crc = binascii.crc32(a_part.encode()) & 0xFFFFFFFF
    return (a_part + str(crc))[:52]


def generate_web_id(a1):
    """根据 a1 生成 web_id"""
    return hashlib.md5(a1.encode()).hexdigest()


def _generate_xsc(a1, api, data=''):
    """
    生成完整签名头集合（x-s/x-t/x-s-common/x-b3-traceid/x-xray-traceid）

    原始版本在 xhs_creator_util.py 中，此处内联以避免引入 creator 模块。
    """
    xs, xt, xs_common = generate_xs_xs_common(a1, api, data)
    headers = {}
    headers['x-s'] = xs
    headers['x-t'] = str(xt)
    headers['x-s-common'] = xs_common
    headers['x-b3-traceid'] = generate_x_b3_traceid()
    headers['x-xray-traceid'] = generate_xray_traceid()
    return headers


def _load_websectiga_env():
    try:
        return open(_WEBSECTIGA_ENV_PATH, 'r', encoding='utf-8').read()
    except FileNotFoundError:
        return None


def fetch_sec_cookies(cookies, headers):
    """获取 sec_poison_id 和 websectiga"""
    sec_poison_id = None
    websectiga = None

    api = '/api/sec/v1/scripting'
    data = {"callFrom": "web", "callback": "seccallback"}
    h = dict(headers)
    h['content-type'] = 'application/json;charset=UTF-8'
    sign_h = _generate_xsc(cookies['a1'], api, data)
    h.update(sign_h)
    data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    try:
        resp = requests.post(
            _AS_URL + api,
            headers=h,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        sec_poison_id = res.get('data', {}).get('secPoisonId')
        jsvmp_code = res.get('data', {}).get('data', '')
        if jsvmp_code:
            env = _load_websectiga_env()
            if env:
                try:
                    js_code = env + '\n' + jsvmp_code + '\nvar __result = _websectiga_result;'
                    ctx = execjs.compile(js_code)
                    websectiga = ctx.eval('__result') or None
                except Exception as e:
                    logger.debug(f'websectiga jsvmp execution failed: {e}')
    except Exception as e:
        logger.debug(f'fetch sec cookies failed: {e}')
    return sec_poison_id, websectiga


def fetch_gid(cookies, headers):
    """获取 gid cookie"""
    api = '/api/sec/v1/shield/webprofile'
    data = {
        "platform": "Windows",
        "sdkVersion": "4.3.5",
        "svn": "2",
        "profileData": ""
    }
    h = dict(headers)
    h['content-type'] = 'application/json'
    sign_h = _generate_xsc(cookies['a1'], api, data)
    h.update(sign_h)
    data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    try:
        resp = requests.post(
            _AS_URL + api,
            headers=h,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value
        if 'gid' in cookies:
            return cookies['gid']
    except Exception as e:
        logger.debug(f'fetch gid failed: {e}')
    return None
