# Ubuntu Chrome自动匹配更新脚本 v2.0

## 功能概述

这是一个增强版的Ubuntu Chrome启动脚本，专门用于解决Chrome和ChromeDriver版本不匹配的问题。脚本会自动检查、更新Chrome浏览器，并智能匹配兼容的ChromeDriver版本。

## 主要功能特性

### 🚀 自动更新功能
- **自动检查并更新Chrome浏览器**：使用apt包管理器自动更新到最新版本
- **智能安装Chrome**：如果系统未安装Chrome，会自动下载并安装
- **强制更新机制**：Chrome更新后自动触发ChromeDriver更新

### 🎯 智能版本匹配
- **完全匹配优先**：首先尝试下载与Chrome完全匹配的ChromeDriver版本
- **兼容性回退**：如果完全匹配失败，智能尝试兼容版本（±5个patch版本）
- **增强版本检查**：详细比较主版本、次版本、构建版本和补丁版本
- **容错机制**：版本差异在可接受范围内时允许继续运行

### 📊 增强的错误处理
- **详细日志记录**：所有操作都会记录到日志文件
- **版本信息备份**：自动备份版本信息到文件
- **彩色输出**：使用不同颜色区分信息类型（错误、成功、警告、信息）
- **进程管理**：提供Chrome进程ID，方便管理

### 🛠️ 多种运行模式
- **正常启动模式**：完整的检查、更新和启动流程
- **仅检查模式**：只检查版本兼容性，不启动Chrome
- **帮助模式**：显示详细的使用说明
- **版本信息模式**：显示脚本版本信息

## 使用方法

### 基本用法
```bash
# 正常启动（完整流程）
bash start_chrome_ubuntu.sh

# 仅检查版本兼容性
bash start_chrome_ubuntu.sh --check-only

# 显示帮助信息
bash start_chrome_ubuntu.sh --help

# 显示脚本版本
bash start_chrome_ubuntu.sh --version
```

### 文件说明
- **脚本文件**：`start_chrome_ubuntu.sh`
- **日志文件**：`chrome_update.log`（自动生成）
- **备份文件**：`version_backup.txt`（自动生成）

## 版本匹配策略

### 1. 完全匹配（优先级最高）
尝试下载与Chrome版本完全一致的ChromeDriver

### 2. 向下兼容（patch版本-1到-5）
如果完全匹配失败，尝试较低的patch版本

### 3. 向上兼容（patch版本+1到+3）
如果向下兼容失败，尝试较高的patch版本

### 4. 版本检查规则
- **主版本和次版本**：必须完全匹配
- **构建版本**：允许不同，但会显示警告
- **补丁版本**：差异超过10时建议更新

## 日志和备份

### 日志记录
所有操作都会记录到 `chrome_update.log` 文件中，包括：
- 时间戳
- 操作类型（INFO、SUCCESS、WARNING、ERROR）
- 详细信息

### 版本备份
每次运行都会将当前版本信息备份到 `version_backup.txt`，包括：
- Chrome版本
- ChromeDriver版本和路径
- 系统信息
- 时间戳

## 故障排除

### 常见问题

1. **Chrome未安装**
   - 脚本会自动尝试安装Chrome
   - 如果安装失败，请检查网络连接和权限

2. **ChromeDriver下载失败**
   - 检查网络连接
   - 查看日志文件了解具体错误
   - 手动访问 https://googlechromelabs.github.io/chrome-for-testing/ 检查可用版本

3. **版本不匹配警告**
   - 脚本会尝试自动修复
   - 如果仍有问题，可以使用 `--check-only` 模式查看详细信息

4. **权限问题**
   - 确保有sudo权限
   - 检查 `/usr/local/bin/` 目录的写权限

### 手动清理
如果需要手动清理：
```bash
# 删除ChromeDriver
sudo rm -f /usr/local/bin/chromedriver
sudo rm -f /usr/bin/chromedriver

# 清理临时文件
rm -rf /tmp/chromedriver_update

# 清理Chrome用户数据（可选）
rm -rf ~/ChromeDebug
```

## 技术细节

### 下载源
- Chrome：Ubuntu官方APT仓库
- ChromeDriver：Google官方测试仓库 (chrome-for-testing-public)

### 安装路径
- ChromeDriver：`/usr/local/bin/chromedriver`
- Chrome用户数据：`~/ChromeDebug`

### Chrome启动参数
脚本使用了优化的Chrome启动参数，包括：
- 远程调试端口：9222
- 禁用GPU加速（适合服务器环境）
- 禁用各种后台功能
- 测试模式配置

## 更新历史

### v2.0 (2024-12-19)
- 增强版本匹配算法
- 添加详细日志记录
- 增加版本信息备份
- 支持多种运行模式
- 改进错误处理机制
- 添加自动Chrome安装功能

### v1.0
- 基础的Chrome和ChromeDriver版本检查
- 简单的版本匹配逻辑
- 基本的Chrome启动功能

## 许可证

本脚本为开源项目，可自由使用和修改。

## 支持

如有问题或建议，请查看日志文件 `chrome_update.log` 获取详细信息。