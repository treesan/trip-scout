# 小红书调研工作流 (OpenCLI + Chrome CDP)

## 前提

`agent-reach` 的小红书 MCP 通道不稳定。稳定方案是 OpenCLI + Chrome CDP。

## OpenCLI 安装

GitHub: https://github.com/jackwener/OpenCLI

```bash
npm install -g @jackwener/opencli
```

安装后确认 PATH 能找到它。如果全局 npm 装在 `~/.npm-global/bin`，需要在 `~/.zshenv` 里加：

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
```

验证：

```bash
opencli --version   # 应返回 1.7.0+
opencli doctor      # 检查 daemon、extension、Chrome 连通性
```

### Browser Bridge 扩展

OpenCLI 需要一个 Chrome 扩展来桥接浏览器：

1. 从 [GitHub Releases](https://github.com/jackwener/OpenCLI/releases) 下载 `opencli-extension.zip`
2. 解压到 `~/.opencli/extensions/opencli-extension`
3. Chrome 打开 `chrome://extensions` → 开启「开发者模式」→ 「加载已解压的扩展程序」→ 选上面的目录

### OpenCLI 内置小红书命令（备选方案）

OpenCLI 自带 xiaohongshu 适配器，支持 `search`、`note`、`feed` 等命令：

```bash
opencli xiaohongshu search '玉ひで 东京' --limit 10 -f json
```

但这条路依赖 Browser Bridge 扩展 + daemon 全部在线，实测不一定稳定。
如果不稳定，走下面的 CDP 直连方案更可靠。

## 环境路径参考

- `opencli` 可执行文件：`~/.npm-global/bin/opencli`
- `opencli` 安装目录：`~/.npm-global/lib/node_modules/@jackwener/opencli`
- CDP 实现：`~/.npm-global/lib/node_modules/@jackwener/opencli/dist/src/browser/cdp.js`
- Browser Bridge 扩展：`~/.opencli/extensions/opencli-extension`

## 最小复现流程

### Step 1：启动可调试 Chrome

```bash
'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --user-data-dir=/tmp/opencli-chrome-cdp \
  --profile-directory=Default \
  --remote-debugging-port=9223 \
  'https://www.xiaohongshu.com/explore'
```

用单独的 `user-data-dir`，开 `9223` 调试口，先打开小红书。

### Step 2：CDPBridge 连接

```js
import { CDPBridge } from '~/.npm-global/lib/node_modules/@jackwener/opencli/dist/src/browser/cdp.js';

const bridge = new CDPBridge();
const page = await bridge.connect({
  cdpEndpoint: 'http://127.0.0.1:9223',
  timeout: 10
});
```

### Step 3：搜索 — 直接进路由

**关键：不要模拟输入框。** 小红书前端有双 input、透明 input、联想层、风控逻辑，模拟输入会假成功。

直接导航到搜索结果页：

```js
await bridge.send('Page.navigate', {
  url: 'https://www.xiaohongshu.com/search_result?keyword=' + encodeURIComponent(query)
});
```

### Step 4：拦截搜索 API

监听网络请求，抓：

```
POST https://edith.xiaohongshu.com/api/sns/web/v1/search/notes
```

请求体示例：
```json
{
  "keyword": "人形町 玉秀",
  "page": 1,
  "page_size": 20,
  "sort": "general",
  "note_type": 0
}
```

返回：笔记 id、xsec_token、标题、作者、点赞、收藏、评论。

第一轮筛选不需要开详情页。搜索前排结果就够判断信号强弱。

### Step 5：详情页提取

搜索结果拿到 `id` + `xsec_token`，拼详情页 URL：

```
https://www.xiaohongshu.com/explore/<id>?xsec_token=<token>&xsec_source=
```

DOM 提取：

```js
document.querySelector('#detail-title')?.innerText     // 标题
document.querySelector('#detail-desc')?.innerText      // 正文
document.querySelector('.author-container .username')?.innerText  // 作者
```

找不到时退回 `document.body.innerText.slice(0, 2000)`。

### Step 6：两段式流程

1. 搜索结果页抓前 10-20 条
2. 只开最相关的 2-3 条详情页

好处：快、不容易被风控、先判断信号强弱、写进 `.md` 更干净。

## 筛选标准

### 保留（真店信号）

- 店名明确、地址明确、菜品明确
- 有自己体验
- 高频词在多条笔记里重复出现

### 不保留

- 泛东京合集里顺手带一句
- 标题写酒店/散步，正文才顺手提店
- 明显搬运

### 能帮决策的信息

优先保留：
- 要不要排队
- 是主餐还是收尾
- 更适合白天还是晚上
- 更像打卡还是更像稳饭
- 容不容易踩空

不优先：纯情绪表达、漂亮但没用的形容、重复三遍的"氛围很好"

## 写回格式

写回时只留一层结论，不搬笔记原文：

- 店名
- 一条代表笔记链接
- 两三句压缩判断

## 搜索建议接口

```
GET https://edith.xiaohongshu.com/api/sns/web/v1/search/recommend?keyword=...
```

能返回联想词。做行程研究价值不大，优先级低。

## 常见坑

1. **agent-reach ≠ 小红书可用** — 先跑 `agent-reach doctor`，小红书 MCP 没配就别浪费时间
2. **输入框不好惹** — 搜索结果页路由是更稳入口
3. **fetch 直接调接口可能被拦** — 返回 `code:300011` 要求切换账号。最稳还是走真实页面 + CDP 抓响应
4. **搜索结果混地区内容** — 不是噪音，能看出店在片区里的角色，但不能直接当单店口碑

## 技能拆分建议

- `SKILL.md`：触发条件 + 总流程
- `references/xhs-research.md`：本文件
- `references/query-patterns.md`（未来可加）：搜索词模板
- `references/writeback-format.md`（未来可加）：压缩模板
- `scripts/`（未来可加）：Chrome 启动、搜索抓取、批量详情提取
