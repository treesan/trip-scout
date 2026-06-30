# Trip Scout 🧭

> 个人 / 家庭自驾游机酒搜索与行程规划助手 — 双平台比价 + 酒店信任筛选 + 行程规划 + 自进化学习

Trip Scout 是一个多平台 AI Skill（Claude Code / OpenClaw），帮你搜机票、选酒店、避雷加盟翻牌、规划自驾行程，并从每次旅行中学习你的偏好。

## ✨ 特性

### 机酒搜索

- **双平台搜索** — 飞猪 + 携程问道并行比价，给明确建议而非罗列
- **酒店信任体系** — 品牌信任梯度、加盟/直营识别、差评分类（成长性 vs 本质性）、黑榜
- **小红书交叉验证** — TOP3 酒店真实口碑校准，过滤软文、反哺避雷
- **携程差评量化** — 内置 API 抓取近 12 月差评并分类量化

### 行程规划

- **4-beat 交互规划** — 收集约束 → 参考行程 → POI + 美食研究 → 生成互动地图
- **大众点评 + 小红书美食研究** — 按位置筛选餐厅，交叉验证口碑
- **Leaflet 行程地图** — 移动端优先，含时间线、导航链接、小红书链接、预订按钮
- **灵活行程** — 输出参考行程而非脚本，旅途中天气/疲劳/心情随时可调整

### 自进化

- **记忆体系** — 记录偏好 / 入住历史 / 学到的规则，越用越懂你
- **跨行程积累** — 品牌信任、避雷规则、美食偏好持续沉淀

## 📦 安装

### Claude Code

克隆到 Claude Code 的 skills 目录（或 symlink 过去）：

```bash
git clone https://github.com/treesan/trip-scout.git ~/.claude/skills/trip-scout
cd ~/.claude/skills/trip-scout

# 1. Python 依赖(小红书口碑验证)
pip install -r requirements.txt
playwright install chromium

# 2. 初始化运行时记忆(从 templates/ 拷贝模板,首次必跑)
python scripts/init_memory.py

# 3. 环境变量
export FLYAI_API_KEY="..."      # 飞猪
export WENDAO_API_KEY="..."     # 携程问道

# 4. 首次用小红书需扫码登录(cookie 存 ~/.xiaohongshu/cookies.json)
python scripts/xhs.py qrcode --show
python scripts/xhs.py check-login
```

### OpenClaw

```bash
# 方式一: symlink 到 OpenClaw skills 目录(开发推荐)
ln -s /path/to/trip-scout ~/.openclaw/skills/trip-scout

# 方式二: 从 ClawHub 安装(发布后可用)
# 在 OpenClaw 中搜索 trip-scout 安装
```

安装后同上初始化 Python 依赖和运行时记忆。

## 🚀 使用

直接对 AI 说自然语言即可：

**机酒搜索**（触发词：搜机票、搜酒店、找酒店、订机票、机酒搜索）：

- "帮我搜 7/15 北京到伊宁的机票，2 人"
- "那拉提 7/20-7/22 找个亲子友好的酒店，预算 800/晚"
- "奎屯亚朵是加盟还是直营？查下差评"

**行程规划**（触发词：行程规划、行程地图、plan my trip、做个行程）：

- "帮我规划伊犁 7 天自驾行程，2 大 1 小，偏好自然风光"
- "那拉提附近有什么好吃的？大众点评搜一下"
- "把行程生成地图页面，手机上能看"

## 📁 结构

```
SKILL.md              # Skill 入口与流程
references/           # 各阶段工作流文档
scripts/
  init_memory.py      # 首次运行初始化运行时记忆
  xhs.py              # 小红书口碑验证入口
  ctrip_reviews.py    # 携程差评抓取分析
templates/            # 运行时记忆模板(MEMORY.md / blacklist.md)
vendor/xiaohongshu/   # 内置小红书客户端(MIT, 源自 DeliciousBuding/xiaohongshu-skill)
```

运行时数据存放在 `~/.trip-scout/`（首次 `init_memory.py` 自动创建），不入库。

## 🙏 致谢

- [DeliciousBuding/xiaohongshu-skill](https://github.com/DeliciousBuding/xiaohongshu-skill) — 小红书 Playwright 客户端（MIT，已内化酒店口碑验证所需核心模块）

## 📄 License

MIT — 见 [LICENSE](LICENSE)
