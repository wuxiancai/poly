#!/bin/bash

CHROME_PROFILE="$HOME/ChromeDebug"

echo "🧹 清理 Chrome 配置目录中的锁定文件: $CHROME_PROFILE"

# 确保 Chrome 不在运行
echo "🔍 正在终止 Chrome 相关进程..."
pkill -f "$CHROME_PROFILE" 2>/dev/null

# 等待一下进程完全退出
sleep 1

# 删除锁文件
LOCK_FILES=(
    "SingletonLock"
    "SingletonSocket"
    "SingletonCookie"
)

for file in "${LOCK_FILES[@]}"; do
    TARGET="$CHROME_PROFILE/$file"
    if [ -e "$TARGET" ]; then
        echo "🗑️ 删除 $TARGET"
        rm -f "$TARGET"
    fi
done

echo "✅ 清理完成，可以重新启动 Chrome 了。"