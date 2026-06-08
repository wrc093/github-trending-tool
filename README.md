# GitHub Trending Tool

每日自动爬取 GitHub Trending 热门项目，通过 LLM 生成详细中文概括 + 自定义标签，导出为精美的 PDF / HTML / Markdown，并推送到飞书群。

## 效果预览

| 内容 | 说明 |
|------|------|
| 📄 PDF | A4 精美排版，支持中文，可离线阅读 |
| 🏷️ 标签 | 每个项目自动打上 Agent、Memory、LLM 等分类标签 |
| 📝 概括 | LLM 生成 3-5 段详细描述，说明项目用途、场景和关注理由 |
| 🔔 飞书推送 | PDF 文件 + 文本摘要直接发送到飞书群 |

---

## 教程一：本地运行

### 1. 环境要求

- Python 3.9+
- macOS 系统自带中文字体（PingFang SC）

### 2. 克隆 & 安装依赖

```bash
git clone https://github.com/wrc093/github-trending-tool.git
cd github-trending-tool
pip install -r requirements.txt
```

> **macOS 用户**：WeasyPrint 需要额外的系统库，安装命令：
> ```bash
> brew install pango cairo glib
> ```

### 3. 配置文件

复制环境变量模板并填写：

```bash
cp .env.example .env
```

编辑 `.env`，以下是**必填项**和**可选项**：

#### 必填项

```bash
# 飞书应用凭证（用于发送 PDF 文件和文本消息到群聊）
FEISHU_APP_ID=你的飞书应用 ID
FEISHU_APP_SECRET=你的飞书应用密钥
```

> 飞书应用创建方式：
> 1. 打开 [飞书开放平台](https://open.feishu.cn/app) → 创建自建应用
> 2. 在「权限管理」中开启：`im:message:send_as_bot`、`im:file`
> 3. 在「事件与回调」→「机器人」中启用机器人能力
> 4. 将机器人添加到目标群聊

#### LLM 配置（可选，不填则不使用 LLM）

```bash
LLM_ENABLED=true
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1   # 阿里云通义千问示例
LLM_API_KEY=你的 API Key
LLM_MODEL=qwen3-vl-plus                                          # 模型名称
```

> 支持任何 OpenAI 兼容的 API 接口，包括：
> - 阿里云通义千问（DashScope）
> - OpenAI
> - 本地 Ollama
> - 其他兼容服务

#### 爬取配置（可选）

```bash
TRENDING_LANGUAGE=          # 按语言过滤，留空爬取全部（如填 python 只爬 Python 榜）
TRENDING_TOP_N=25           # 爬取项目数量
TRENDING_TIMEOUT=30         # 请求超时时间（秒）
```

### 4. 运行

```bash
# 完整运行（爬取 → 生成概括 → 导出 → 推送飞书）
python main.py

# 仅预览，不实际推送（dry-run 模式）
python main.py --dry-run

# 跳过飞书推送
python main.py --no-export

# 跳过项目概括生成
python main.py --no-project-summary

# 开启详细日志
python main.py --verbose
```

### 5. 输出

运行后产物保存在 `output/{日期}/` 目录下：

```
output/2026-06-08/
├── github-trending-2026-06-08.md    # Markdown
├── github-trending-2026-06-08.html  # HTML
── github-trending-2026-06-08.pdf   # PDF（A4 排版）
```

---

## 教程二：部署到自己的 GitHub Actions

### 1. Fork 仓库

点击仓库右上角 **Fork** 按钮，将代码复制到你的 GitHub 账号下。

### 2. 启用 GitHub Actions

1. 进入 Fork 后的仓库 → **Settings** → **Actions** → **General**
2. 确保 **Allow all actions and reusable workflows** 已选中
3. 点击 **Save**

### 3. 配置 Secrets

进入 **Settings** → **Secrets and variables** → **Actions**，添加以下 **Secrets**：

| Secret 名称 | 说明 | 是否必填 |
|------------|------|---------|
| `FEISHU_APP_ID` | 飞书自建应用的 App ID | ✅ 必填 |
| `FEISHU_APP_SECRET` | 飞书自建应用的 App Secret | ✅ 必填 |
| `LLM_API_KEY` | LLM API 密钥 | 可选 |
| `LLM_API_BASE` | LLM API 地址 | 可选 |

### 4. 配置 Variables

在同一个页面，切换到 **Variables** 标签页，添加：

| Variable 名称 | 默认值 | 说明 |
|--------------|--------|------|
| `LLM_ENABLED` | `false` | 是否启用 LLM 生成概括 |
| `LLM_MODEL` | `gpt-4o-mini` | LLM 模型名称 |
| `TRENDING_TOP_N` | `25` | 爬取项目数量 |

### 5. 修改推送时间（可选）

编辑 `.github/workflows/daily-trending.yml`，修改 cron 表达式：

```yaml
on:
  schedule:
    # 每天北京时间 9:00（UTC 1:00）
    # cron 格式：分 时 日 月 周（UTC 时间）
    - cron: '0 1 * * *'
  workflow_dispatch:  # 支持手动触发
```

> **Cron 时间换算**：北京时间 = UTC + 8，所以北京时间 9:00 = UTC 1:00
>
> 常用时间参考：
> - 早上 8:00 → `cron: '0 0 * * *'`
> - 早上 9:00 → `cron: '0 1 * * *'`
> - 晚上 18:00 → `cron: '0 10 * * *'`
> - 晚上 20:00 → `cron: '0 12 * * *'`

### 6. 手动触发测试

进入仓库 → **Actions** → 选择 **GitHub Trending 每日推送** → 点击 **Run workflow** → 选择分支 → 点击 **Run workflow**

运行完成后：
- 飞书群会收到 **PDF 文件** + **文本摘要** 两条消息
- Actions 页面底部可下载 PDF 产物（保留 30 天）

### 7. 注意事项

- GitHub Actions 的 `ubuntu-latest` 环境已预装中文字体（`fonts-wqy-zenhei`），无需额外配置
- 如果 LLM API 调用失败，会自动降级为基于规则的简单概括
- 爬取 GitHub Trending 失败时会自动重试（30 分钟内指数退避）

---

## 项目结构

```
github-trending-tool/
├── main.py                      # 主入口
├── config.py                    # 配置管理
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量模板
├── src/
│   ├── scraper.py               # GitHub Trending 爬虫（含重试机制）
│   ├── summarizer.py            # 总结生成（LLM / 模板两种模式）
│   ├── project_summarizer.py    # Top 10 项目详细概括 + 标签
│   ├── exporter.py              # 导出 Markdown / HTML / PDF
│   └── publisher/
│       ├── base.py              # 发布器基类
│       ── feishu.py            # 飞书 Open API 发布器
├── output/                      # 输出目录（按日期组织）
└── .github/workflows/
    └── daily-trending.yml       # GitHub Actions 定时任务
```
