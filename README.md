# Twitter内容保存工具

一个用于保存Twitter推文和媒体文件到本地的Python命令行工具。支持单个推文和推文串（thread）的完整保存，包括文本内容、图片和视频。

## 功能特性

- ✅ 支持单个推文和推文串的保存
- ✅ 自动下载推文中的图片和视频
- ✅ 生成格式化的文本文件和JSON元数据
- ✅ 智能的目录结构组织
- ✅ 支持多种Twitter URL格式
- ✅ 完善的错误处理和重试机制
- ✅ 美观的命令行界面和进度显示

## 安装要求

- Python 3.7+
- FFmpeg (可选，用于视频缩略图生成)

## 技术说明

**本工具使用网页抓取技术，无需 Twitter API 密钥**
- 🚀 使用 Playwright 浏览器自动化技术
- 🔓 无需 Twitter 开发者账户
- 💰 完全免费，无 API 费用
- 🛡️ 自动反检测机制

## 安装步骤

1. 克隆或下载项目文件

2. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```

3. 安装 Playwright 浏览器（必需）：
   ```bash
   python -m playwright install chromium
   ```

4. （可选）配置自定义保存路径，编辑 `config.ini` 文件

## 配置说明

配置文件 `config.ini` 示例：

```ini
[storage]
base_path = /mnt/nas/saved_tweets
create_date_folders = true

[download]
max_retries = 3
timeout_seconds = 30

[scraper]
use_playwright = true
headless = true
debug_mode = false
```

**配置项说明：**
- `base_path`: 推文保存路径
- `create_date_folders`: 是否创建日期文件夹
- `max_retries`: 下载失败重试次数
- `timeout_seconds`: 请求超时时间（秒）
- `use_playwright`: 是否使用 Playwright（推荐开启）
- `headless`: 是否无头模式运行浏览器
- `debug_mode`: 调试模式（会保存截图）

## 使用方法

### Web界面（推荐）

启动Web应用：

```bash
python run_web.py
```

然后在浏览器中访问 `http://localhost:6201`

**Web界面功能：**
- 🌐 友好的网页界面
- 📝 输入Twitter URL进行保存
- 📊 实时任务队列状态
- 🔄 自动处理API速率限制
- 📱 响应式设计，支持移动设备
- 📋 查看已保存推文列表
- 👁️ 在线预览保存的推文内容

### 命令行界面

#### 基本用法

```bash
# 保存单个推文
python main.py https://x.com/wangzhian8848/status/1946831616485290146

# 保存推文串
python main.py https://twitter.com/username/status/1234567890

# 支持 x.com 域名
python main.py https://x.com/username/status/1234567890
```

#### 高级选项

```bash
# 不下载媒体文件
python main.py https://twitter.com/username/status/1234567890 --no-media

# 只获取单个推文，不检查推文串（减少API调用）
python main.py https://twitter.com/username/status/1234567890 --single-only

# 强制作为推文串处理
python main.py https://twitter.com/username/status/1234567890 --thread-only

# 使用自定义配置文件
python main.py https://twitter.com/username/status/1234567890 --config custom_config.ini

# 自定义输出目录
python main.py https://twitter.com/username/status/1234567890 --output /path/to/save

# 显示详细输出
python main.py https://twitter.com/username/status/1234567890 --verbose
```

### 支持的URL格式

- `https://twitter.com/username/status/1234567890`
- `https://x.com/username/status/1234567890`
- `https://mobile.twitter.com/username/status/1234567890`
- `https://m.twitter.com/username/status/1234567890`

## 输出文件结构

```
saved_tweets/
├── 2023-01-01_1234567890123456789/
│   ├── content.txt          # 推文文本内容
│   ├── metadata.json        # 推文元数据
│   ├── images/              # 图片文件夹
│   │   ├── image_01.jpg
│   │   └── image_02.png
│   └── videos/              # 视频文件夹
│       └── video_01.mp4
```

### 文件说明

- **content.txt**: 包含格式化的推文内容，包括作者信息、发布时间、推文文本和媒体文件列表
- **metadata.json**: 包含完整的推文元数据，便于程序化处理
- **images/**: 推文中的图片文件
- **videos/**: 推文中的视频文件

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试文件
python -m pytest tests/test_twitter_service.py

# 运行测试并显示覆盖率
python -m pytest tests/ --cov=.
```

## 故障排除

### 常见问题

1. **"Tweet not found" 错误**
   - 推文可能已被删除
   - 推文可能是私有的
   - 检查URL是否正确

2. **Playwright 浏览器未安装**
   - 运行: `python -m playwright install chromium`
   - 确保安装了 Playwright 库

3. **网络连接问题**
   - 检查网络连接
   - 检查防火墙设置
   - Twitter 可能临时不可访问

4. **文件权限错误**
   - 确保对输出目录有写入权限
   - 检查磁盘空间是否充足

### 调试技巧

1. 使用 `--verbose` 参数查看详细输出
2. 检查配置文件是否正确
3. 验证URL格式是否支持
4. 查看错误日志信息
5. 启用 debug_mode 查看浏览器截图

## 配置参数说明

| 参数                  | 说明                     | 默认值           |
| --------------------- | ------------------------ | ---------------- |
| `base_path`           | 保存文件的基础路径       | `/mnt/nas/saved_tweets` |
| `create_date_folders` | 是否创建日期文件夹       | `true`           |
| `max_retries`         | 最大重试次数             | `3`              |
| `timeout_seconds`     | 请求超时时间（秒）       | `30`             |
| `use_playwright`      | 使用 Playwright 抓取     | `true`           |
| `headless`            | 无头模式运行浏览器       | `true`           |
| `debug_mode`          | 调试模式（保存截图）     | `false`          |

## 技术特点

- **无需 API 密钥**: 使用网页抓取技术，完全免费
- **浏览器自动化**: Playwright 模拟真实浏览器行为
- **反检测机制**: 随机 User-Agent、视口大小等
- **完整数据提取**: 文本、图片、视频、用户信息
- **稳定可靠**: 自动重试、错误恢复机制

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 更新日志

### v1.0.0
- 初始版本发布
- 支持单个推文和推文串保存
- 支持图片和视频下载
- 完整的命令行界面
- 全面的测试覆盖

## 联系方式

如有问题或建议，请通过GitHub Issues联系。