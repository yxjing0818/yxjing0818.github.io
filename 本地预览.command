#!/bin/bash
# 双击这个文件即可在本地预览整个博客（效果和部署后一致）。
# 它会先自动扫描文件夹生成清单，再启动本地服务器并打开浏览器。按 Ctrl+C 关闭。
cd "$(dirname "$0")"
echo "正在扫描文件夹、生成内容清单…"
python3 generate.py
PORT=8000
echo ""
echo "本地预览地址：http://localhost:$PORT"
echo "（关闭预览：回到这个窗口按 Ctrl+C）"
( sleep 1 && open "http://localhost:$PORT" ) &
python3 -m http.server $PORT
