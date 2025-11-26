# YouTube API 部署指南

## 更新内容

### 主要改进:
1. **添加 Deno JavaScript 运行时支持** - 解决 YouTube n-signature 提取问题
2. **添加远程组件下载** - 自动下载 EJS challenge solver
3. **智能路径检测** - 根据操作系统和用户自动选择正确的 yt-dlp 和 deno 路径
4. **改进错误处理** - 即使视频格式不可用,只要字幕下载成功就返回成功
5. **增强重试逻辑** - 更长的等待时间应对速率限制

## 部署前准备

### 1. 安装 Deno (如果未安装)

```bash
# Linux/macOS
curl -fsSL https://deno.land/install.sh | sh

# 或者使用 Homebrew (macOS)
brew install deno
```

安装后确认路径:
```bash
which deno
# 通常输出: /root/.deno/bin/deno 或 ~/.deno/bin/deno
```

### 2. 更新 yt-dlp 到最新版本

```bash
pip install -U yt-dlp

# 或使用系统包管理器
# Ubuntu/Debian:
sudo apt update && sudo apt install -y yt-dlp

# macOS:
brew upgrade yt-dlp
```

### 3. 确保 cookies.txt 在项目根目录且有效

从浏览器导出最新的 YouTube cookies:
```bash
# 使用浏览器扩展 "Get cookies.txt LOCALLY"
# 或使用命令:
yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.youtube.com/watch?v=any_video
```

### 4. 设置环境变量

```bash
export YOUTUBE_API_KEY="your_youtube_api_key_here"
```

## 部署步骤

### 1. 上传更新后的代码到服务器

```bash
# 上传 main.py
scp main.py user@server:/path/to/youtube-api/

# 上传 requirements.txt
scp requirements.txt user@server:/path/to/youtube-api/

# 上传 cookies.txt (如果更新)
scp cookies.txt user@server:/path/to/youtube-api/
```

### 2. 在服务器上安装依赖

```bash
ssh user@server
cd /path/to/youtube-api

# 激活虚拟环境 (如果使用)
source venv/bin/activate

# 安装/更新依赖
pip install -r requirements.txt
pip install -U yt-dlp
```

### 3. 验证 Deno 安装

```bash
# 检查 deno 是否安装
which deno

# 如果未安装,执行:
curl -fsSL https://deno.land/install.sh | sh

# 添加到 PATH (如果需要)
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 4. 重启服务

```bash
# 使用 systemd
sudo systemctl restart youtube-api

# 或使用 supervisorctl
sudo supervisorctl restart youtube-api

# 或手动重启 (如果使用 screen/tmux)
pkill -f "uvicorn main:app"
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 验证部署

### 1. 检查服务状态

```bash
# systemd
sudo systemctl status youtube-api

# 查看日志
sudo journalctl -u youtube-api -f
```

应该看到:
```
使用 yt-dlp 路径: /usr/local/bin/yt-dlp
使用 deno 路径: /root/.deno/bin/deno
```

### 2. 测试 API

```bash
curl -X POST "http://your-server:8000/download-subtitles/" \
  -H "Content-Type: application/json" \
  -d '{"video_id": "geTHOGyL_60", "video_url": "https://www.youtube.com/watch?v=geTHOGyL_60"}'
```

## 新增的命令行参数

代码现在会自动添加这些参数:

1. `--extractor-args "youtube:player_client=web;jsruntimes=/path/to/deno"`
   - 指定使用 web player 客户端
   - 指定 JavaScript 运行时为 Deno

2. `--remote-components "ejs:github"`
   - 允许从 GitHub 下载 EJS challenge solver 脚本
   - 解决 n-signature 提取问题

## 故障排查

### 问题 1: 仍然出现 "n challenge solving failed"

**解决方案:**
```bash
# 确保 deno 在 PATH 中
export PATH="$HOME/.deno/bin:$PATH"

# 手动测试 yt-dlp
yt-dlp --cookies cookies.txt \
  --extractor-args "youtube:jsruntimes=$HOME/.deno/bin/deno" \
  --remote-components "ejs:github" \
  --write-auto-sub --skip-download \
  https://www.youtube.com/watch?v=test_video_id
```

### 问题 2: HTTP 429 Too Many Requests

**解决方案:**
- 更新 cookies.txt (确保是最新的,未过期的)
- 增加重试等待时间 (代码已设置为 10, 20, 30 秒)
- 考虑使用代理或 VPN

### 问题 3: Deno 权限问题

**解决方案:**
```bash
# 确保 deno 可执行
chmod +x ~/.deno/bin/deno

# 如果使用 systemd,确保服务用户有权限访问 deno
sudo chown -R service_user:service_user ~/.deno
```

## 性能优化建议

1. **使用缓存**: 代码已实现 TTL 缓存,相同视频 24 小时内会直接返回缓存
2. **批量处理**: 如果需要下载多个视频字幕,建议增加请求间隔
3. **监控日志**: 定期检查 429 错误频率,调整请求频率

## 相关链接

- [yt-dlp EJS 文档](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [Deno 安装指南](https://deno.land/manual/getting_started/installation)
- [YouTube Cookies 导出教程](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
