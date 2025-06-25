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
    if command -v google-chrome-stable &> /dev/null; then
        google-chrome-stable --version | awk '{print $3}'
    else
        echo "Chrome not found"
        return 1
    fi
}

# 添加自动更新Chrome功能
update_chrome() {
    echo -e "${YELLOW}检查并更新Chrome...${NC}"
    
    # 获取更新前的版本
    CURRENT_VERSION=$(google-chrome-stable --version 2>/dev/null | awk '{print $3}')
    echo -e "${YELLOW}当前Chrome版本: $CURRENT_VERSION${NC}"
    
    # 使用apt直接更新Chrome
    echo -e "${YELLOW}更新软件包列表...${NC}"
    sudo apt update -qq
    
    echo -e "${YELLOW}更新Chrome...${NC}"
    sudo apt --only-upgrade install -y google-chrome-stable
    
    # 获取更新后的版本
    NEW_VERSION=$(google-chrome-stable --version 2>/dev/null | awk '{print $3}')
    echo -e "${GREEN}更新后Chrome版本: $NEW_VERSION${NC}"
    
    # 检查是否更新成功
    if [ "$CURRENT_VERSION" != "$NEW_VERSION" ]; then
        echo -e "${GREEN}Chrome已成功更新: $CURRENT_VERSION -> $NEW_VERSION${NC}"
    else
        echo -e "${GREEN}Chrome已是最新版本: $NEW_VERSION${NC}"
    fi
    
    return 0
}


# 检查已安装的 chromedriver 是否匹配当前 Chrome
check_driver() {
    CHROME_VERSION=$(get_chrome_version)
    if [ "$CHROME_VERSION" = "Chrome not found" ]; then
        echo -e "${RED}Chrome 未安装${NC}"
        return 1
    fi
    
    # 检查系统路径中的chromedriver
    DRIVER_PATH=""
    if command -v chromedriver &> /dev/null; then
        DRIVER_PATH=$(which chromedriver)
    fi

    if [ -z "$DRIVER_PATH" ]; then
        echo -e "${RED}chromedriver 未安装${NC}"
        return 1
    fi

    DRIVER_VERSION=$("$DRIVER_PATH" --version | awk '{print $2}')
    
    echo -e "${YELLOW}Chrome 版本: $CHROME_VERSION${NC}"
    echo -e "${YELLOW}chromedriver 版本: $DRIVER_VERSION${NC}"
    echo -e "${YELLOW}chromedriver 路径: $DRIVER_PATH${NC}"

    # 比较主版本号和次版本号
    CHROME_MAJOR_MINOR=$(echo "$CHROME_VERSION" | cut -d'.' -f1-2)
    DRIVER_MAJOR_MINOR=$(echo "$DRIVER_VERSION" | cut -d'.' -f1-2)
    
    if [ "$CHROME_MAJOR_MINOR" != "$DRIVER_MAJOR_MINOR" ]; then
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
            
            # 安装到系统路径
            echo -e "${YELLOW}安装chromedriver到系统路径...${NC}"
            sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
            sudo chmod +x /usr/local/bin/chromedriver
            
            echo -e "${GREEN}安装成功: $(chromedriver --version)${NC}"
            cd "$SCRIPT_DIR"
            return 0
        fi
    done

    echo -e "${RED}未能下载兼容 chromedriver（尝试了 3 个 patch 版本）${NC}"
    return 1
}

# 主流程
echo -e "${YELLOW}开始执行浏览器启动流程...${NC}"

# 首先更新Chrome
echo -e "${YELLOW}====== 开始检查并更新Chrome ======${NC}"
update_chrome
echo -e "${YELLOW}====== Chrome更新完成 ======${NC}"

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

# 启动 Chrome（调试端口）- 使用系统安装的Chrome
echo -e "${GREEN}启动 Chrome 中...${NC}"
if command -v google-chrome-stable &> /dev/null; then
    google-chrome-stable \
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
    echo -e "${RED}Chrome 未找到，请确保已安装 google-chrome-stable${NC}"
    exit 1
fi
