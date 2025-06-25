#!/bin/bash

# Ubuntu Chrome启动脚本
# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 获取Chrome完整版本号
get_chrome_version() {
    if [ -x "$SCRIPT_DIR/google-chrome" ]; then
        "$SCRIPT_DIR/google-chrome" --version | awk '{print $3}'
    elif [ -x "$SCRIPT_DIR/chrome" ]; then
        "$SCRIPT_DIR/chrome" --version | awk '{print $3}'
    else
        echo "Chrome not found"
        return 1
    fi
}

# 添加自动更新Chrome功能
update_chrome() {
    echo -e "${YELLOW}检查Chrome更新...${NC}"
    
    # 获取当前Chrome版本
    CURRENT_VERSION=$(get_chrome_version)
    if [ "$CURRENT_VERSION" = "Chrome not found" ]; then
        echo -e "${RED}Chrome未安装，无法更新${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}当前Chrome版本: $CURRENT_VERSION${NC}"
    
    # 获取最新稳定版Chrome版本
    echo -e "${YELLOW}获取最新Chrome版本信息...${NC}"
    LATEST_VERSION=$(curl -s "https://omahaproxy.appspot.com/all.json" | 
                    grep -o '"os":"linux".*"channel":"stable".*"current_version":"[^"]*"' | 
                    grep -o '"current_version":"[^"]*"' | 
                    cut -d'"' -f4)
    
    if [ -z "$LATEST_VERSION" ]; then
        echo -e "${RED}无法获取最新Chrome版本信息${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}最新Chrome版本: $LATEST_VERSION${NC}"
    
    # 比较版本
    if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
        echo -e "${GREEN}Chrome已是最新版本${NC}"
        return 0
    fi
    # 将版本号转换为可比较的格式
    CURRENT_MAJOR=$(echo "$CURRENT_VERSION" | cut -d'.' -f1)
    LATEST_MAJOR=$(echo "$LATEST_VERSION" | cut -d'.' -f1)
    
    if [ "$CURRENT_MAJOR" -lt "$LATEST_MAJOR" ] || [ "$CURRENT_VERSION" != "$LATEST_VERSION" ]; then
        echo -e "${YELLOW}Chrome需要更新，从 $CURRENT_VERSION 更新到 $LATEST_VERSION${NC}"
        
        # 检查是否有本地Chrome安装
        if [ -x "$SCRIPT_DIR/google-chrome" ] || [ -x "$SCRIPT_DIR/chrome" ]; then
            # 本地安装版本，尝试下载新版本
            echo -e "${YELLOW}检测到本地Chrome安装，尝试下载更新...${NC}"
            
            TMP_DIR="/tmp/chrome_update"
            mkdir -p "$TMP_DIR"
            cd "$TMP_DIR" || return 1
            
            # 下载最新版本的Chrome
            CHROME_URL="https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
            echo -e "${YELLOW}下载Chrome安装包...${NC}"
            if ! curl -sfLo chrome.deb "$CHROME_URL"; then
                echo -e "${RED}下载Chrome失败${NC}"
                return 1
            fi
            
            # 解压并替换本地Chrome
            echo -e "${YELLOW}解压并更新本地Chrome...${NC}"
            dpkg-deb -x chrome.deb chrome_extracted
            
            # 备份旧版本
            if [ -x "$SCRIPT_DIR/google-chrome" ]; then
                mv "$SCRIPT_DIR/google-chrome" "$SCRIPT_DIR/google-chrome.bak"
            fi
            
            # 复制新版本
            cp chrome_extracted/opt/google/chrome/chrome "$SCRIPT_DIR/google-chrome"
            chmod +x "$SCRIPT_DIR/google-chrome"
            
            # 复制必要的库文件
            mkdir -p "$SCRIPT_DIR/lib"
            cp -r chrome_extracted/opt/google/chrome/lib/* "$SCRIPT_DIR/lib/" 2>/dev/null || true
            # 清理临时文件
            cd "$SCRIPT_DIR"
            rm -rf "$TMP_DIR"
            
            # 验证更新
            NEW_VERSION=$(get_chrome_version)
            if [ "$NEW_VERSION" = "$LATEST_VERSION" ]; then
                echo -e "${GREEN}Chrome已成功更新到版本 $NEW_VERSION${NC}"
                return 0
            else
                echo -e "${YELLOW}Chrome可能未成功更新，当前版本: $NEW_VERSION${NC}"
                # 恢复备份
                if [ -f "$SCRIPT_DIR/google-chrome.bak" ]; then
                    mv "$SCRIPT_DIR/google-chrome.bak" "$SCRIPT_DIR/google-chrome"
                    echo -e "${YELLOW}已恢复到原版本${NC}"
                fi
            fi
        else
            # 系统安装版本，使用apt更新
            echo -e "${YELLOW}使用系统包管理器更新Chrome...${NC}"
            
            # 确保Chrome存储库已添加
            if [ ! -f /etc/apt/sources.list.d/google-chrome.list ]; then
                echo -e "${YELLOW}添加Google Chrome存储库...${NC}"
                echo "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
                wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
            fi
            
            # 更新并安装
            echo -e "${YELLOW}更新软件包列表...${NC}"
            sudo apt-get update -qq
            
            echo -e "${YELLOW}安装/更新Chrome...${NC}"
            if sudo apt-get install -y google-chrome-stable; then
                # 验证更新
                NEW_VERSION=$(google-chrome --version | awk '{print $3}')
                echo -e "${GREEN}Chrome已更新到版本 $NEW_VERSION${NC}"
                return 0
            else
                echo -e "${RED}Chrome更新失败${NC}"
                return 1
            fi
        fi
    fi
    
    return 1
}

# 检查已安装的 chromedriver 是否匹配当前 Chrome
check_driver() {
    CHROME_VERSION=$(get_chrome_version)
    if [ "$CHROME_VERSION" = "Chrome not found" ]; then
        echo -e "${RED}Chrome 未安装${NC}"
        return 1
    fi
    
    CHROME_MAJOR_MINOR=$(echo "$CHROME_VERSION" | cut -d'.' -f1-2)

    # 只查找项目根目录下的 chromedriver
    DRIVER_PATH=""
    for path in "$SCRIPT_DIR/chromedriver"; do
        if [ -x "$path" ]; then
            DRIVER_PATH="$path"
            break
        fi
    done

    if [ -z "$DRIVER_PATH" ]; then
        echo -e "${RED}chromedriver 未安装${NC}"
        return 1
    fi


    DRIVER_VERSION=$("$DRIVER_PATH" --version | awk '{print $2}')
    DRIVER_MAJOR_MINOR=$(echo "$DRIVER_VERSION" | cut -d'.' -f1-2)

    echo -e "${YELLOW}Chrome 版本: $CHROME_VERSION${NC}"
    echo -e "${YELLOW}chromedriver 版本: $DRIVER_VERSION${NC}"

    if [ "$CHROME_VERSION" != "$DRIVER_VERSION" ]; then
        echo -e "${RED}版本不匹配，需更新驱动${NC}"
        return 1
    fi

    echo -e "${GREEN}版本匹配，驱动正常${NC}"
    return 0
}

# 自动安装兼容的 chromedriver（Ubuntu版本）
install_driver() {
    echo -e "${YELLOW}尝试下载安装兼容的 chromedriver...${NC}"
    CHROME_VERSION=$(get_chrome_version)
    BASE_VERSION=$(echo "$CHROME_VERSION" | cut -d'.' -f1-3)
    PATCH_VERSION=$(echo "$CHROME_VERSION" | cut -d'.' -f4)

    TMP_DIR="/tmp/chromedriver_update"
    mkdir -p "$TMP_DIR"
    cd "$TMP_DIR" || return 1
    
    for ((i=0; i<3; i++)); do
        TRY_PATCH=$((PATCH_VERSION - i))
        TRY_VERSION="${BASE_VERSION}.${TRY_PATCH}"
        DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${TRY_VERSION}/linux64/chromedriver-linux64.zip"

        echo -e "${YELLOW}尝试版本: $TRY_VERSION${NC}"

        curl -sfLo chromedriver.zip "$DRIVER_URL"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}成功下载 chromedriver ${TRY_VERSION}${NC}"
            rm -rf chromedriver-linux64*
            unzip -qo chromedriver.zip
            mv chromedriver-linux64/chromedriver "$SCRIPT_DIR/chromedriver"
            chmod +x "$SCRIPT_DIR/chromedriver"
            echo -e "${GREEN}安装成功: $("$SCRIPT_DIR/chromedriver" --version)${NC}"
            cd "$SCRIPT_DIR"
            return 0
        fi
    done

    echo -e "${RED}未能下载兼容 chromedriver（尝试了 3 个 patch 版本）${NC}"
    return 1
}

# 主流程
echo -e "${YELLOW}开始执行浏览器启动流程...${NC}"

if ! check_driver; then
    echo -e "${YELLOW}驱动不兼容，尝试修复...${NC}"
    if install_driver; then
        check_driver || {
            echo -e "${RED}驱动更新后仍然不兼容${NC}"
            exit 1
        }
    else
        echo -e "${RED}驱动更新失败${NC}"
        exit 1
    fi
fi

export DISPLAY=:1

# 设置X11授权
if [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
else
    # 尝试生成授权文件
    touch "$HOME/.Xauthority"
    export XAUTHORITY="$HOME/.Xauthority"
fi

echo -e "${YELLOW}使用 DISPLAY=1"
echo -e "${YELLOW}使用 XAUTHORITY=$XAUTHORITY${NC}"

# 清理崩溃文件
rm -f "$HOME/ChromeDebug/SingletonLock"
rm -f "$HOME/ChromeDebug/SingletonSocket"
rm -f "$HOME/ChromeDebug/SingletonCookie"
rm -f "$HOME/ChromeDebug/Default/Last Browser"
rm -f "$HOME/ChromeDebug/Default/Last Session"
rm -f "$HOME/ChromeDebug/Default/Last Tabs"

# 修复 Preferences 里记录的崩溃状态
PREF_FILE="$HOME/ChromeDebug/Default/Preferences"
if [ -f "$PREF_FILE" ]; then
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREF_FILE"
fi

# 启动 Chrome（调试端口）- 只用项目根目录下的 chrome
echo -e "${GREEN}启动 Chrome 中...${NC}"
if [ -x "$SCRIPT_DIR/google-chrome" ]; then
    "$SCRIPT_DIR/google-chrome" \
        --remote-debugging-port=9222 \
        --no-sandbox \
        --disable-gpu \
        --disable-software-rasterizer \
        --disable-dev-shm-usage \
        --disable-background-networking \
        --disable-default-apps \
        --disable-extensions \
        --disable-sync \
        --metrics-recording-only \
        --no-first-run \
        --disable-session-crashed-bubble \
        --disable-translate \
        --disable-background-timer-throttling \
        --disable-backgrounding-occluded-windows \
        --disable-renderer-backgrounding \
        --disable-features=TranslateUI,BlinkGenPropertyTrees,SitePerProcess,IsolateOrigins \
        --noerrdialogs \
        --disable-infobars \
        --disable-notifications \
        --test-type \
        --user-data-dir="$HOME/ChromeDebug" \
        about:blank
else
    echo -e "${RED}Chrome 未找到${NC}"
    exit 1
fi
