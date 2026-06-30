# Trip Scout 🧭

> 个人 / 家庭自驾游机酒搜索与规划助手 — 双平台比价 + 酒店信任筛选 + 自进化学习

Trip Scout 是一个 Claude Code Skill，帮你搜机票、选酒店、避雷加盟翻牌，并从每次入住中学习你的偏好。

## ✨ 特性

- **双平台搜索** — 飞猪 + 携程问道并行比价，给明确建议而非罗列
- **酒店信任体系** — 品牌信任梯度、加盟/直营识别、差评分类（成长性 vs 本质性）、黑榜
- **小红书交叉验证** — TOP3 酒店真实口碑校准，过滤软文、反哺避雷
- **携程差评量化** — 内置 API 抓取近 12 月差评并分类量化
- **自进化记忆** — 记录偏好 / 入住历史 / 学到的规则，越用越懂你

## 📦 安装

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

## 🚀 使用

直接对 Claude 说自然语言即可（触发词：搜机票、搜酒店、找酒店、订机票、机酒搜索）：

- "帮我搜 7/15 北京到伊宁的机票，2 人"
- "那拉提 7/20-7/22 找个亲子友好的酒店，预算 800/晚"
- "奎屯亚朵是加盟还是直营？查下差评"

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
