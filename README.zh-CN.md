# Twitter/X 内容归档工具

通过浏览器自动化技术将 Twitter/X 上的推文和媒体文件保存到本地，无需 Twitter API 密钥。支持文本、图片、视频的完整归档，提供 Web 图形界面与命令行两种使用方式。

![Python](https://img.shields.io/badge/Python-3.7%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![No API Key](https://img.shields.io/badge/Twitter%20API-不需要-brightgreen)

[English](README.md)

---

## ✨ 功能特性

- 无需 Twitter API 密钥，使用 Playwright 浏览器自动化抓取
- 支持单条推文归档（推文串抓取功能暂未支持）
- 自动下载图片和视频
- 生成多格式内容文件：纯文本、Markdown、Reader-mode HTML
- 保存完整元数据（作者信息、发布时间等）为 JSON
- 内置任务队列与失败重试机制（指数退避）
- Web UI 支持实时日志流、任务监控和内容浏览
- 每条归档内容可生成唯一分享链接
- 可选：基于 Gemini API 的 AI 智能标签生成
- 可选：通过 FFmpeg 生成视频缩略图

---

## 🚀 快速开始

**前提条件：** Python 3.7+，FFmpeg 可选（用于视频缩略图）。

```bash
# 1. 克隆仓库
git clone https://github.com/yelosheng/twitter-saver.git
cd twitter-saver

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器（必需）
python -m playwright install chromium

# 4. 复制并编辑配置文件
cp config.ini.example config.ini
```

### 启动 Web 界面

```bash
python run_web.py
```

浏览器访问 `http://localhost:6201`，默认登录账号：`admin` / 密码：`admin`。

> **首次登录后请立即修改密码：**
> ```bash
> python tools/change_password.py
> ```

---

## ⚙️ 配置说明

将 `config.ini.example` 复制为 `config.ini` 并按需修改。

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `[storage] base_path` | 推文保存路径 | `./saved_tweets` |
| `[storage] create_date_folders` | 按日期创建子文件夹 | `true` |
| `[download] max_retries` | 下载失败最大重试次数 | `3` |
| `[download] timeout_seconds` | 请求超时时间（秒） | `30` |
| `[scraper] use_playwright` | 使用 Playwright 浏览器自动化（推荐） | `true` |
| `[scraper] headless` | 无头模式运行浏览器 | `true` |
| `[scraper] debug_mode` | 调试模式，出错时保存截图 | `false` |
| `[ai] gemini_api_key` | Gemini API 密钥（可选，用于 AI 标签） | 未设置 |

**环境变量覆盖：**

| 环境变量 | 说明 |
|---|---|
| `SAVE_PATH` | 覆盖保存路径 |
| `USE_PLAYWRIGHT` | 覆盖 Playwright 开关 |
| `PLAYWRIGHT_HEADLESS` | 覆盖无头模式 |
| `PLAYWRIGHT_DEBUG` | 设为 `true` 启用调试截图 |
| `SSL_CERT_PATH` / `SSL_KEY_PATH` | 启用 HTTPS |

---

## 📖 使用方法

### Web 界面

启动后访问 `http://localhost:6201`：

| 页面 | 功能 |
|---|---|
| `/` | 提交 Twitter URL 开始归档 |
| `/tasks` | 查看任务队列状态 |
| `/saved` | 浏览和搜索已归档推文 |
| `/tags` | 管理 AI 生成的标签 |
| `/retries` | 查看失败任务并手动重试 |
| `/view/<slug>` | 通过分享链接查看归档内容 |
| `/debug` | 系统状态和卡死任务重置 |
| `/help` | 油猴脚本安装说明 |

### 命令行

```bash
# 归档单条推文
python main.py https://x.com/username/status/1234567890

# 跳过媒体下载
python main.py https://x.com/username/status/1234567890 --no-media

# 指定输出目录
python main.py https://x.com/username/status/1234567890 --output /path/to/save

# 显示详细输出
python main.py https://x.com/username/status/1234567890 --verbose
```

**支持的 URL 格式：**

```
https://twitter.com/username/status/1234567890
https://x.com/username/status/1234567890
https://mobile.twitter.com/username/status/1234567890
https://m.twitter.com/username/status/1234567890
```

---

## 📁 输出结构

```
saved_tweets/
└── 2024-01-15_1234567890123456789/
    ├── content.txt        # 推文纯文本
    ├── content.html       # Reader-mode HTML
    ├── content.md         # Markdown 格式
    ├── metadata.json      # 完整元数据（作者、时间等）
    ├── avatar.jpg         # 作者头像
    ├── images/
    ├── videos/
    └── thumbnails/        # 视频缩略图（需 FFmpeg）
```

---

## 🏷️ AI 标签功能（可选）

归档成功后可自动为推文生成语义标签，帮助分类和检索。生成方法按优先级排列：

1. **Gemini API** — 在 `config.ini` 中设置 `gemini_api_key`（推荐，免费额度充足）。提示词模板位于 `prompts.ini`，可自定义。
2. **规则匹配** — 无需 API 密钥，基于内置关键词规则自动生成基础标签。

通过 Web 界面的 `/tags` 页面可管理所有标签，也可在 `/saved` 页面对单条内容手动触发标签生成。

---

## 🖱️ 浏览器脚本（油猴）

安装油猴脚本后，可在 Twitter/X 每条推文下直接点击保存按钮一键归档，无需离开页面或手动复制链接。

**安装步骤：**
1. 安装 [Tampermonkey](https://www.tampermonkey.net/) 浏览器扩展
2. 启动 Web 界面：`python run_web.py`
3. 访问 `http://localhost:6201/help`，点击安装链接

**配置后端地址：**
点击 Tampermonkey 扩展图标 → 找到脚本 → 点击 **⚙️ 设置后端地址**，输入你的服务地址（默认为 `http://localhost:6201`）。

脚本文件位于 `tampermonkey/twitter-saver.user.js`。

---

## 🔧 故障排除

**推文无法找到** — 推文可能已被删除或设为私有，请检查 URL 是否正确，并确认该推文在浏览器中可以正常访问。

**Playwright 浏览器未安装** — 运行 `python -m playwright install chromium`。

**网络连接问题** — 检查网络连接和防火墙设置。如果所在地区访问 Twitter/X 受限，需要配置代理后再使用本工具。

**文件权限错误** — 确认对 `base_path` 所指向的目录有写入权限，并检查磁盘剩余空间。

**任务卡死不动** — 访问 Web 界面的 `/debug` 页面，使用「重置卡死任务」功能。

**启用调试模式** — 在 `config.ini` 中设置 `debug_mode = true`，或设置环境变量 `PLAYWRIGHT_DEBUG=true`，出错时会自动保存浏览器截图至项目根目录。

---

## ⚠️ 免责声明

- **仅供个人存档使用。** 本工具设计用途为个人保存公开内容，供离线阅读和个人研究。
- **请遵守 Twitter/X 服务条款。** 使用本工具须符合 [Twitter/X 服务条款](https://twitter.com/en/tos)。用户对自身的使用行为及其法律合规性承担全部责任。
- **禁止商业用途和大规模抓取。** 本工具不得用于商业目的、批量数据采集、训练机器学习模型或任何形式的大规模抓取行为。
- **尊重他人版权。** 推文内容的版权归原作者所有，请勿在未经授权的情况下转载、分发或二次利用他人内容。
- **作者不对滥用行为负责。** 本项目作者不对任何因滥用本工具而产生的法律问题、账号封禁或其他后果承担责任。

---

## 📄 License

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

欢迎通过 GitHub Issues 报告问题或提出功能建议，也欢迎提交 Pull Request。提交前请确保现有测试通过：

```bash
python -m pytest tests/
```
