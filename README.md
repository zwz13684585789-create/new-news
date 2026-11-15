# 每日全球要闻简报 · GitHub Actions 版

每天北京时间 **08:00** 自动抓取政治、经济、F1、AI 四个板块的新闻，按“同一事件、不同来源”聚类，标注来源的政治倾向，生成：

- 一个可直接阅读的 **HTML 表格**（GitHub Pages 发布）
- 一个可编辑的 **XLSX**（速览 / 要闻明细 / 来源明细 / 说明）
- 一份 **Markdown** 存档
- 一封 **邮件**（可选，默认发给 `MAIL_TO`，可附 XLSX）

整个流程跑在 GitHub Actions 上，**不需要你的电脑开机，也不需要 DSH 应用在线**。

> 想先看效果：`demo/index.html` 是用内置样例生成的离线预览，直接双击打开即可。

---

## 5 分钟部署

### 1. 建仓库并上传

新建一个 GitHub 仓库，把本目录全部文件上传（或解压 zip 后 push）。建议 **public**：GitHub Pages 对 public 仓库免费；private 仓库的 Pages 需要付费计划。

### 2. 打开 Pages

仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。

### 3. 配置变量与密钥

**Settings → Secrets and variables → Actions**：

| 类型 | 名称 | 值 | 必填 |
|---|---|---|---|
| Variable | `MAIL_TO` | `you@example.com`（换成你的 163 地址） | 发邮件时必填 |
| Variable | `PAGES_URL` | `https://<你的用户名>.github.io/<仓库名>/` | 建议 |
| Secret | `SMTP_USER` | `you@163.com`（换成你的 163 地址） | 163 发信必填 |
| Secret | `SMTP_PASS` | 163 的 **客户端授权密码**（不是登录密码） | 163 发信必填 |
| Secret | `DEEPSEEK_API_KEY` | DeepSeek API Key | 可选，中文摘要更稳 |
| Secret | `RESEND_API_KEY` | Resend API Key | 可选，替代 163 SMTP |

> 邮箱地址没有写死在代码里，放在 Variable 里，避免公开仓库泄露。

### 4. 手动跑一次

**Actions → Daily Brief → Run workflow**。跑完后：

- 网页：`https://<你的用户名>.github.io/<仓库名>/`
- 邮件：看 `docs/email-status.json` 的 `status`；成功是 `sent`，没配是 `skipped`，失败会带 `error`。

之后每天 UTC 00:00（北京时间 08:00）自动运行。

---

## 邮件怎么配（163 邮箱）

1. 网页登录 163 邮箱 → **设置 → POP3/SMTP/IMAP** → 开启 **SMTP 服务**。
2. 按提示获取 **客户端授权密码**（一串独立密码，只显示一次）。
3. 在 GitHub 里加：
   - Secret `SMTP_USER` = 你的 163 地址
   - Secret `SMTP_PASS` = 刚才的授权密码
4. 可选：Secret `SMTP_HOST` = `smtp.163.com`，Secret `SMTP_PORT` = `465`。不填时，代码检测到 `@163.com` 会自动用这两个值。

**如果 163 拒收 GitHub 的海外 IP**（常见报错 `SMTPAuthenticationError` / `Connection refused` / 被退信），换 Resend：

1. 注册 [resend.com](https://resend.com)，创建 API Key。
2. 验证一个发件域名；没有域名时可用 `onboarding@resend.dev`，但它只能发到注册 Resend 的那个邮箱。
3. GitHub 加 Secret `RESEND_API_KEY`，Variable `MAIL_FROM`（如 `brief@yourdomain.com`）。
4. 代码会优先走 Resend，不再走 SMTP。

> 邮件里是精简版表格 + 网页版链接，附件是同日 XLSX。邮件发送失败不会影响网页发布；状态会写在 `docs/email-status.json`。

---

## 中文摘要怎么来

脚本本身只用标准库抓 RSS，不做翻译。中文改写按以下优先级选择模型：

1. `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL`（任意 OpenAI 兼容端点）
2. `DEEPSEEK_API_KEY`（默认 `deepseek-chat`）
3. `GITHUB_TOKEN` + GitHub Models（默认 `openai/gpt-4o-mini`，工作流已给 `models: read` 权限）

都没有时，页面仍会生成，但标题和摘要保留英文原文，并在顶部显示提示。**不会因为模型不可用而中断。**

想固定用 DeepSeek：在 GitHub 加 `DEEPSEEK_API_KEY` 即可，代码会优先用它。

---

## 本地运行

```bash
python -m pip install -r requirements.txt

# 真实抓取（不翻译、不发邮件）
python scripts/build_brief.py --no-llm --no-email

# 用内置样例做离线预览（不联网）
python scripts/build_brief.py --sample --no-llm --no-email --out docs-sample

# 只预览邮件，不发送（生成 docs/email-preview.eml）
MAIL_TO=you@example.com python scripts/build_brief.py --sample --email-dry-run
```

Windows PowerShell 里把 `MAIL_TO=...` 换成：

```powershell
$env:MAIL_TO="you@example.com"
python scripts/build_brief.py --sample --email-dry-run
```

产物在 `docs/`：`index.html`（最新）、`YYYY-MM-DD.html`、`.xlsx`、`.md`、`archive.html`、`data/`。

---

## 自定义来源

编辑 `scripts/sources.py`：

```python
Feed("bbc-world", "BBC", "中", "政治", "https://feeds.bbci.co.uk/news/world/rss.xml")
```

参数依次是：内部 key、显示名、倾向标签、板块、RSS 地址。

倾向标签可选：`左 / 中左 / 中 / 中右 / 右 / 官媒 / 专业 / 一手`。官媒不放进左右轴；专业/一手用于体育、行业与公司官方来源。

抓取失败不会中断构建，日志里会打 `[feed:fail]`，页面顶部会显示失败数量。

---

## 工作原理

1. **抓取**：40+ 个 RSS/Atom 源，48 小时窗口，12 路并发，单源 12 秒超时。
2. **过滤**：AI/F1/经济按关键词过滤，避免科技/商业 feed 里的无关条目混进板块。
3. **聚类**：标题词重叠 + 专有名词重叠 + 序列相似度；同一媒体在同一故事中只保留一条。
4. **合并**：同一事件的不同角度（如“Musk 请愿”与“亚洲政府反应”）按专有名词重合度合并。
5. **排序**：来源数量、倾向多样性、是否有中间来源、时效性。
6. **改写**：可选调用模型，输出中文标题、3 条事实、叙事差异与每家来源的一句角度。
7. **渲染**：HTML / Markdown / XLSX；邮件用独立的内联样式 HTML，避免客户端丢样式。
8. **发布**：提交到 `docs/`，再用 GitHub Pages 部署。

---

## 已知限制

- **RSS 不是全量新闻**。付费墙媒体（WSJ、Bloomberg、FT）的 RSS 可能只有标题/摘要；没有 RSS 的媒体不会出现。
- **聚类是启发式的**。同一事件可能被拆成两条，也可能把两条相近的事并成一条；表里的“单一来源”标记是提示，不是断言。
- **GitHub 定时任务可能延迟几分钟**，高峰时更久；cron 写的是 UTC 00:00。
- **仓库 60 天无活动会被暂停定时任务**；本工作流每天提交 `docs/`，通常能保持活跃。
- **163 SMTP 对海外 IP 不友好**；优先用 Resend，或把 163 设为备用。
- **模型可能改写过度**。Prompt 里已要求“只用输入事实”，但自动摘要仍需人工扫一眼；页面会保留原始来源链接。
- **GitHub Models 有速率限制**；失败会自动回退到英文原文，不会卡住发布。

---

## 文件结构

```
.github/workflows/daily-brief.yml   # 每天 08:00 CST 构建 + 提交 + 发布 + 发信
scripts/
  build_brief.py                    # 入口：抓取 → 改写 → 渲染 → 发信
  pipeline.py                       # RSS 解析、聚类、排序
  sources.py                        # 来源与倾向注册表
  llm.py                            # 可选中文改写
  render.py                         # HTML / Markdown / XLSX / 邮件 HTML
  mailer.py                         # SMTP / Resend
  send_email.py                     # 对已生成的一天补发邮件
templates/style.css                 # 页面样式
sample/sample.json                  # 离线样例（16 条）
docs/                               # 生成物，GitHub Pages 根目录
requirements.txt
```

---

## 安全

- 不要把 163 授权密码、DeepSeek Key、Resend Key 写进代码或提交到仓库；只放 GitHub Secrets。
- `MAIL_TO` 放 Variable 而不是代码，避免公开仓库暴露邮箱。
- 如果密钥曾经出现在提交历史里，立刻在服务商后台吊销并重新生成。

---

*自动生成的研究简报，不构成投资、法律或政治建议。*
