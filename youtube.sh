#!/bin/bash
# 测试 yt-dlp 下载字幕

DENO_PATH=$(which deno || echo "$HOME/.deno/bin/deno")
echo "使用 Deno 路径: $DENO_PATH"

yt-dlp --cookies cookies.txt \
  --write-auto-sub \
  --sub-format vtt \
  --skip-download \
  --output "downloads/%(id)s" \
  --extractor-args "youtube:player_client=web;jsruntimes=$DENO_PATH" \
  --remote-components "ejs:github" \
  https://www.youtube.com/watch?v=-W9cztx4O3o