"""
trip-scout 小红书纯 API 客户端

基于 Spider_XHS (https://github.com/cv-cat/Spider_XHS) 核心模块，
使用直接 HTTP API 调用替代浏览器自动化，降低被风控检测的风险。

与旧版浏览器自动化方案的关键区别：
- 无浏览器自动化 → 无 CDP 痕迹 → 被检测风险低
- 逆向 XHS 签名算法 (x-s/x-t/x-s-common) → 直接 API 调用
- 需要 PyExecJS + Node.js 执行签名 JS
- Cookie 从浏览器 DevTools 手动获取或通过 QR 码登录 API 获取
"""
