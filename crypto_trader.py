# -*- coding: utf-8 -*-
# polymarket_v1
import platform
import tkinter as tk
from tkinter import E, ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import json
import threading
import time
import os
import subprocess
from screeninfo import get_monitors
import logging
from datetime import datetime, timezone, timedelta
import re
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pyautogui
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import socket
import sys
import logging
from xpath_config import XPathConfig
from threading import Thread
import random
import requests

class Logger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 如果logger已经有处理器，则不再添加新的处理器
        if not self.logger.handlers:
            # 创建logs目录（如果不存在）
            if not os.path.exists('logs'):
                os.makedirs('logs')
                
            # 设置日志文件名（使用当前日期）
            log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}.log"
            
            # 创建文件处理器
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # 创建控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            
            # 创建格式器
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # 添加处理器到logger
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)

class CryptoTrader:
    def __init__(self):
        super().__init__()
        self.logger = Logger('poly')
        self.driver = None
        self.running = False
        self.trading = False
        self.login_running = False
        # 添加交易状态
        self.start_login_monitoring_running = False
        self.url_monitoring_running = False
        self.refresh_page_running = False
        # 添加重试次数和间隔
        self.retry_count = 3
        self.retry_interval = 5
        # 添加交易次数计数器
        self.trade_count = 0
        self.sell_count = 0 
        self.reset_trade_count = 0 
        # 添加定时器
        self.refresh_page_timer = None  # 用于存储定时器ID
        self.url_check_timer = None
        # 添加登录状态监控定时器
        self.login_check_timer = None
        # 添加URL and refresh_page监控锁
        self.url_monitoring_lock = threading.Lock()
        self.refresh_page_lock = threading.Lock()
        # 默认买价
        self.default_target_price = 52
        # 买卖触发条件之一:最少成交数量SHARES
        self.asks_shares = 99
        self.bids_shares = 99
        # 买入价格冗余
        self.price_premium = 2
        # 按钮区域按键 WIDTH
        self.button_width = 8
        # 停止事件
        self.stop_event = threading.Event()
        # 初始化金额为 0
        for i in range(1, 4):  # 1到4
            setattr(self, f'yes{i}_amount', 0)
            setattr(self, f'no{i}_amount', 0)
        # 初始化 UI 界面
        try:
            self.config = self.load_config()
            self.setup_gui()
            # 获取屏幕尺寸并设置窗口位置
            self.root.update_idletasks()  # 确保窗口尺寸已计算
            window_width = self.root.winfo_width()
            screen_height = self.root.winfo_screenheight()
            # 设置窗口位置在屏幕最左边
            self.root.geometry(f"{window_width}x{screen_height}+0+0")
        except Exception as e:
            self.logger.error(f"初始化失败: {str(e)}")
            messagebox.showerror("错误", "程序初始化失败，请检查日志文件")
            sys.exit(1)

        # 打印启动参数
        self.logger.info(f"✅ 初始化成功: {sys.argv}")
      
    def load_config(self):
        """加载配置文件，保持默认格式"""
        try:
            # 默认配置
            default_config = {
                'website': {'url': ''},
                'trading': {
                    'Up1': {'target_price': 0, 'amount': 0},
                    'Up2': {'target_price': 0, 'amount': 0},
                    'Up3': {'target_price': 0, 'amount': 0},
                    'Up4': {'target_price': 0, 'amount': 0},
                    'Up5': {'target_price': 0, 'amount': 0},

                    'Down1': {'target_price': 0, 'amount': 0},
                    'Down2': {'target_price': 0, 'amount': 0},
                    'Down3': {'target_price': 0, 'amount': 0},
                    'Down4': {'target_price': 0, 'amount': 0},
                    'Down5': {'target_price': 0, 'amount': 0}
                },
                'url_history': []
            }
            
            try:
                # 尝试读取现有配置
                with open('config.json', 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.logger.info("✅ 成功加载配置文件")
                    
                    # 合并配置
                    for key in default_config:
                        if key not in saved_config:
                            saved_config[key] = default_config[key]
                        elif isinstance(default_config[key], dict):
                            for sub_key in default_config[key]:
                                if sub_key not in saved_config[key]:
                                    saved_config[key][sub_key] = default_config[key][sub_key]
                    return saved_config
            except FileNotFoundError:
                self.logger.warning("配置文件不存在，创建默认配置")
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                return default_config
            except json.JSONDecodeError:
                self.logger.error("配置文件格式错误，使用默认配置")
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                return default_config
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            raise
    
    def save_config(self):
        """保存配置到文件,保持JSON格式化"""
        try:
            for position, frame in [('Yes', self.yes_frame), ('No', self.no_frame)]:
                # 精确获取目标价格和金额的输入框
                entries = [
                    w for w in frame.winfo_children() 
                    if isinstance(w, ttk.Entry) and "price" in str(w).lower()
                ]
                amount_entries = [
                    w for w in frame.winfo_children()
                    if isinstance(w, ttk.Entry) and "amount" in str(w).lower()
                ]

                # 添加类型转换保护
                try:
                    target_price = float(entries[0].get().strip() or '0') if entries else 0
                except ValueError as e:
                    self.logger.error(f"价格转换失败: {e}, 使用默认值0")
                    target_price = 0

                try:
                    amount = float(amount_entries[0].get().strip() or '0') if amount_entries else 0
                except ValueError as e:
                    self.logger.error(f"金额转换失败: {e}, 使用默认值0")
                    amount = 0

                # 使用正确的配置键格式
                config_key = f"{position}1"  # 改为Yes1/No1
                self.config['trading'][config_key]['target_price'] = target_price
                self.config['trading'][config_key]['amount'] = amount

            # 处理网站地址历史记录
            current_url = self.url_entry.get().strip()
            if current_url:
                if 'url_history' not in self.config:
                    self.config['url_history'] = []
                
                # 清空历史记录
                self.config['url_history'].clear()
                # 只保留当前URL
                self.config['url_history'].insert(0, current_url)
                # 确保最多保留1条
                self.config['url_history'] = self.config['url_history'][:1]
                self.url_entry['values'] = self.config['url_history']
            
            # 保存配置到文件，使用indent=4确保格式化
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f)
                
        except Exception as e:
            self.logger.error(f"保存配置失败: {str(e)}")
            raise

    """从这里开始设置 GUI 直到 771 行"""
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Polymarket Automatic Trading System Power by @wuxiancai")
        # 创建主滚动框架
        main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        # 配置滚动区域
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        # 在 Canvas 中创建窗口
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        # 简化的滚动事件处理
        def _on_mousewheel(event):
            try:
                if platform.system() == 'Linux':
                    if event.num == 4:
                        main_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        main_canvas.yview_scroll(1, "units")
                elif platform.system() == 'Darwin':
                    main_canvas.yview_scroll(-int(event.delta), "units")
                else:  # Windows
                    main_canvas.yview_scroll(-int(event.delta/120), "units")
            except Exception as e:
                self.logger.error(f"滚动事件处理错误: {str(e)}")
        # 绑定滚动事件
        if platform.system() == 'Linux':
            main_canvas.bind_all("<Button-4>", _on_mousewheel)
            main_canvas.bind_all("<Button-5>", _on_mousewheel)
        else:
            main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # 添加简化的键盘滚动支持
        def _on_arrow_key(event):
            try:
                if event.keysym == 'Up':
                    main_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    main_canvas.yview_scroll(1, "units")
            except Exception as e:
                self.logger.error(f"键盘滚动事件处理错误: {str(e)}")
        # 绑定方向键
        main_canvas.bind_all("<Up>", _on_arrow_key)
        main_canvas.bind_all("<Down>", _on_arrow_key)
        
        # 放置滚动组件
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        """创建按钮和输入框样式"""
        style = ttk.Style()
        style.configure('Red.TButton', foreground='red', font=('TkDefaultFont', 14, 'bold'))
        style.configure('Black.TButton', foreground='black', font=('TkDefaultFont', 14, 'normal'))
        style.configure('Red.TEntry', foreground='red', font=('TkDefaultFont', 14, 'normal'))
        style.configure('Blue.TButton', foreground='blue', font=('TkDefaultFont', 14, 'normal'))
        style.configure('Blue.TLabel', foreground='blue', font=('TkDefaultFont', 14, 'normal'))
        style.configure('Red.TLabel', foreground='red', font=('TkDefaultFont', 14, 'normal'))
        style.configure('Red.TLabelframe.Label', foreground='red')
        style.configure('Black.TLabel', foreground='black', font=('TkDefaultFont', 14, 'normal'))
        style.configure('Warning.TLabelframe.Label', font=('TkDefaultFont', 14),foreground='red', anchor='center', justify='center')
        style.configure('LeftAligned.TButton', anchor='w', foreground='black', padding=(1, 1))
        
        # 金额设置框架
        amount_settings_frame = ttk.LabelFrame(scrollable_frame, text="Don't greedy! Do not intervene in the Automatic program!", padding=(2, 5), style='Warning.TLabelframe')
        amount_settings_frame.pack(fill="x", padx=5, pady=5)

        # 创建一个Frame来水平排列标题和警告
        title_frame = ttk.Frame(amount_settings_frame)
        title_frame.pack(fill="x", padx=5, pady=5)

        # 创建金额设置容器的内部框架
        settings_container = ttk.Frame(amount_settings_frame)
        settings_container.pack(fill=tk.X, anchor='w')
        
        # 创建两个独立的Frame
        amount_frame = ttk.Frame(settings_container)
        amount_frame.grid(row=0, column=0, sticky='w')
        trades_frame = ttk.Frame(settings_container)
        trades_frame.grid(row=1, column=0, sticky='w')

        # 初始金额
        initial_frame = ttk.Frame(amount_frame)
        initial_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(initial_frame, text="Initial").pack(side=tk.LEFT)
        self.initial_amount_entry = ttk.Entry(initial_frame, width=2)
        self.initial_amount_entry.pack(side=tk.LEFT)
        self.initial_amount_entry.insert(0, "1.5")
        
        # 反水一次设置
        first_frame = ttk.Frame(amount_frame)
        first_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(first_frame, text="Turn-1").pack(side=tk.LEFT)
        self.first_rebound_entry = ttk.Entry(first_frame, width=3)
        self.first_rebound_entry.pack(side=tk.LEFT)
        self.first_rebound_entry.insert(0, "220")
        
        # 反水N次设置
        n_frame = ttk.Frame(amount_frame)
        n_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(n_frame, text="Turn-N").pack(side=tk.LEFT)
        self.n_rebound_entry = ttk.Entry(n_frame, width=3)
        self.n_rebound_entry.pack(side=tk.LEFT)
        self.n_rebound_entry.insert(0, "125")

        # 利润率设置
        profit_frame = ttk.Frame(amount_frame)
        profit_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(profit_frame, text="Margin").pack(side=tk.LEFT)
        self.profit_rate_entry = ttk.Entry(profit_frame, width=4)
        self.profit_rate_entry.pack(side=tk.LEFT)
        self.profit_rate_entry.insert(0, "1.3%")

        # 翻倍天数
        weeks_frame = ttk.Frame(amount_frame)
        weeks_frame.pack(side=tk.LEFT, padx=2)
        self.doubling_weeks_entry = ttk.Entry(weeks_frame, width=2, style='Red.TEntry')
        self.doubling_weeks_entry.pack(side=tk.LEFT)
        self.doubling_weeks_entry.insert(0, "53")
        ttk.Label(weeks_frame, text="Double", style='Red.TLabel').pack(side=tk.LEFT)

        # 配置列权重使输入框均匀分布
        for i in range(4):
            settings_container.grid_columnconfigure(i, weight=1)

        """设置窗口大小和位置"""
        window_width = 460
        window_height = 800
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
        
        # 监控网站配置
        url_frame = ttk.Frame(scrollable_frame)
        url_frame.pack(fill="x", padx=2, pady=5)

        # 创建下拉列和输入框组合控件
        ttk.Label(url_frame, text="WEB:", font=('Arial', 10)).grid(row=0, column=1, padx=5, pady=5)
        self.url_entry = ttk.Combobox(url_frame, width=47, font=('TkDefaultFont', 12))
        self.url_entry.grid(row=0, column=2, padx=2, pady=5, sticky="ew")

        # 从配置文件加载历史记录
        if 'url_history' not in self.config:
            self.config['url_history'] = []
        self.url_entry['values'] = self.config['url_history']
        
        # 如果有当前URL，设置为默认值
        current_url = self.config.get('website', {}).get('url', '')
        if current_url:
            self.url_entry.set(current_url)
        
        # 控制按钮区域
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        
        # 开始按钮
        self.start_button = ttk.Button(button_frame, text="Start", 
                                          command=self.start_monitoring, width=4,
                                          style='LeftBlack.TButton')  # 默认使用黑色文字
        self.start_button.pack(side=tk.LEFT, padx=2)
        
        # 设置金额按钮
        self.set_amount_button = ttk.Button(button_frame, text="Set-AM", width=5,
                                            command=self.set_yes_no_cash,style='LeftAligned.TButton')  # 默认使用黑色文字
        self.set_amount_button.pack(side=tk.LEFT, padx=2)
        self.set_amount_button['state'] = 'disabled'  # 初始禁用

        # 添加币种选择下拉框
        coin_frame = ttk.Frame(button_frame)
        coin_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(coin_frame, text="").pack(side=tk.LEFT)
        self.coin_combobox = ttk.Combobox(coin_frame, width=3, values=['BTC', 'ETH', 'SOL'])
        self.coin_combobox.pack(side=tk.LEFT)
        self.coin_combobox.set('BTC')

        # 添加重启次数和显示
        restart_frame = ttk.Frame(button_frame)
        restart_frame.pack(fill="x", padx=2, pady=5)
        
        ttk.Label(restart_frame, text="Reset:").pack(side=tk.LEFT, padx=1)
        self.reset_count_label = ttk.Label(restart_frame, text="0", foreground='red')
        self.reset_count_label.pack(side=tk.LEFT, padx=1)
        
        # 添加日期显示
        self.date_label = ttk.Label(restart_frame, text="--")
        self.date_label.pack(side=tk.LEFT, padx=1)

        # 添加保存 CASH 记录
        cash_frame = ttk.Frame(restart_frame)
        cash_frame.pack(fill="x", padx=2, pady=5)
        ttk.Label(cash_frame, text="Cash:").pack(side=tk.LEFT, padx=1)
        self.cash_label_value = ttk.Label(cash_frame, text="0", foreground='red')
        self.cash_label_value.pack(side=tk.LEFT, padx=1)

        # 交易币对显示区域
        pair_frame = ttk.Frame(scrollable_frame)
        pair_frame.pack(fill="x", padx=2, pady=5)

        # 添加交易币对显示区域
        pair_container = ttk.Frame(pair_frame)
        pair_container.pack(anchor="center")

        # 交易币种及日期，颜色为黑色
        ttk.Label(pair_container, text="", 
                 font=('Arial', 14), foreground='black').pack(side=tk.LEFT, padx=2)
        self.trading_pair_label = ttk.Label(pair_container, text="--", 
                                        font=('Arial', 16), foreground='black')
        self.trading_pair_label.pack(side=tk.LEFT, padx=2)

        # 币安价格显示区域
        binance_frame = ttk.Frame(pair_frame)
        binance_frame.pack(anchor="center")

        # 币安零点时价格显示
        ttk.Label(binance_frame, text="", 
                 font=('Arial', 16), foreground='black').pack(side=tk.LEFT, padx=2)
        
        ttk.Label(binance_frame, text="00:00 Price:", 
                 font=('Arial', 14), foreground='black').pack(side=tk.LEFT, padx=2)
        self.binance_zero_price_label = ttk.Label(binance_frame, text="--", 
                                        font=('Arial', 16), foreground='blue')
        self.binance_zero_price_label.pack(side=tk.LEFT, padx=2)

        # 币安实时价格显示
        ttk.Label(binance_frame, text="Now Price:", 
                 font=('Arial', 14), foreground='black').pack(side=tk.LEFT, padx=2)
        self.binance_now_price_label = ttk.Label(binance_frame, text="--", 
                                        font=('Arial', 16), foreground='blue')
        self.binance_now_price_label.pack(side=tk.LEFT, padx=2)
        
        # 修改实时价格显示区域
        price_frame = ttk.Frame(scrollable_frame)
        price_frame.pack(padx=5, pady=5, fill="x")
        
        # 创建一个框架来水平排列所有价格信息
        prices_container = ttk.Frame(price_frame)
        prices_container.pack(expand=True)  # 添加expand=True使容器居中
        shares_container = ttk.Frame(price_frame)
        shares_container.pack(expand=True)

        # Yes实时价格显示
        self.yes_price_label = ttk.Label(prices_container, text="Up: waiting...", 
                                        font=('Arial', 18), foreground='#9370DB')
        self.yes_price_label.pack(side=tk.LEFT, padx=18)

        # up shares显示
        self.up_shares_label = ttk.Label(shares_container, text="Shares: waiting...",
                                        font=('Arial', 18), foreground='#9370DB')
        self.up_shares_label.pack(side=tk.LEFT, padx=18)

        # No实时价格显示
        self.no_price_label = ttk.Label(prices_container, text="Down: waiting...", 
                                       font=('Arial', 18), foreground='#9370DB')
        self.no_price_label.pack(side=tk.LEFT, padx=18)

        # down shares显示
        self.down_shares_label = ttk.Label(shares_container, text="Shares: waiting...",
                                        font=('Arial', 18), foreground='#9370DB')
        self.down_shares_label.pack(side=tk.LEFT, padx=18)

        # 修改实时资金显示区域
        balance_frame = ttk.Frame(scrollable_frame)
        balance_frame.pack(padx=5, pady=5, fill="x")
        
        # 创建一个框架来水平排列所有资金信息
        balance_container = ttk.Frame(balance_frame)
        balance_container.pack(expand=True)  # 添加expand=True使容器居中
        
        # Portfolio显示
        self.portfolio_label = ttk.Label(balance_container, text="Portfolio: waiting...", 
                                        font=('Arial', 18), foreground='#16A34A') # 修改为绿色
        self.portfolio_label.pack(side=tk.LEFT, padx=18)
        
        # Cash显示
        self.cash_label = ttk.Label(balance_container, text="Cash: waiting...", 
                                   font=('Arial', 18), foreground='#16A34A') # 修改为绿色
        self.cash_label.pack(side=tk.LEFT, padx=18)
        
        # 创建Yes/No
        config_frame = ttk.Frame(scrollable_frame)
        config_frame.pack(fill="x", padx=2, pady=5)
        
        # 左右分栏显示Yes/No配置
        # YES 区域配置
        self.yes_frame = ttk.Frame(config_frame)
        self.yes_frame.grid(row=0, column=0, padx=2, sticky="ew")
        config_frame.grid_columnconfigure(0, weight=1)

        # No 配置区域
        self.no_frame = ttk.Frame(config_frame)
        self.no_frame.grid(row=0, column=1, padx=2, sticky="ew")
        config_frame.grid_columnconfigure(1, weight=1)
        
        # YES1 价格
        ttk.Label(self.yes_frame, text="Yes1 Price($):", font=('Arial', 12)).grid(row=0, column=0, padx=2, pady=5)
        self.yes1_price_entry = ttk.Entry(self.yes_frame, width=12)
        self.yes1_price_entry.insert(0, str(self.config['trading']['Yes1']['target_price']))
        self.yes1_price_entry.grid(row=0, column=1, padx=2, pady=5, sticky="ew")

        # yes2 价格
        ttk.Label(self.yes_frame, text="Yes2 Price($):", font=('Arial', 12)).grid(row=2, column=0, padx=2, pady=5)
        self.yes2_price_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes2_price_entry.delete(0, tk.END)
        self.yes2_price_entry.insert(0, "0")
        self.yes2_price_entry.grid(row=2, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # yes3 价格
        ttk.Label(self.yes_frame, text="Yes3 Price($):", font=('Arial', 12)).grid(row=4, column=0, padx=2, pady=5)
        self.yes3_price_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes3_price_entry.delete(0, tk.END)
        self.yes3_price_entry.insert(0, "0")
        self.yes3_price_entry.grid(row=4, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # yes4 价格
        ttk.Label(self.yes_frame, text="Yes4 Price($):", font=('Arial', 12)).grid(row=6, column=0, padx=2, pady=5)
        self.yes4_price_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes4_price_entry.delete(0, tk.END)
        self.yes4_price_entry.insert(0, "0")
        self.yes4_price_entry.grid(row=6, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # yes5 价格
        ttk.Label(self.yes_frame, text="Yes5 Price($):", font=('Arial', 12)).grid(row=8, column=0, padx=2, pady=5)
        self.yes5_price_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes5_price_entry.delete(0, tk.END)
        self.yes5_price_entry.insert(0, "0")
        self.yes5_price_entry.grid(row=8, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # yes1 金额
        ttk.Label(self.yes_frame, text="Yes1 Amount:", font=('Arial', 12)).grid(row=1, column=0, padx=2, pady=5)
        self.yes1_amount_entry = ttk.Entry(self.yes_frame, width=12)
        self.yes1_amount_entry.insert(0, str(self.config['trading']['Yes1']['amount']))
        self.yes1_amount_entry.grid(row=1, column=1, padx=2, pady=5, sticky="ew")

        # yes2 金额
        ttk.Label(self.yes_frame, text="Yes2 Amount:", font=('Arial', 12)).grid(row=3, column=0, padx=2, pady=5)
        self.yes2_amount_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes2_amount_entry.insert(0, "0")
        self.yes2_amount_entry.grid(row=3, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # yes3 金额
        ttk.Label(self.yes_frame, text="Yes3 Amount:", font=('Arial', 12)).grid(row=5, column=0, padx=2, pady=5)
        self.yes3_amount_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes3_amount_entry.insert(0, "0")
        self.yes3_amount_entry.grid(row=5, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # yes4 金额
        ttk.Label(self.yes_frame, text="Yes4 Amount:", font=('Arial', 12)).grid(row=7, column=0, padx=2, pady=5)
        self.yes4_amount_entry = ttk.Entry(self.yes_frame, width=12)  # 添加self
        self.yes4_amount_entry.insert(0, "0")
        self.yes4_amount_entry.grid(row=7, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # No1 价格
        ttk.Label(self.no_frame, text="No1 Price($):", font=('Arial', 12)).grid(row=0, column=0, padx=2, pady=5)
        self.no1_price_entry = ttk.Entry(self.no_frame, width=12)
        self.no1_price_entry.insert(0, str(self.config['trading']['No1']['target_price']))
        self.no1_price_entry.grid(row=0, column=1, padx=2, pady=5, sticky="ew")

        # No2 价格
        ttk.Label(self.no_frame, text="No2 Price($):", font=('Arial', 12)).grid(row=2, column=0, padx=2, pady=5)
        self.no2_price_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no2_price_entry.delete(0, tk.END)
        self.no2_price_entry.insert(0, "0")
        self.no2_price_entry.grid(row=2, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # No3 价格
        ttk.Label(self.no_frame, text="No3 Price($):", font=('Arial', 12)).grid(row=4, column=0, padx=2, pady=5)
        self.no3_price_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no3_price_entry.delete(0, tk.END)
        self.no3_price_entry.insert(0, "0")
        self.no3_price_entry.grid(row=4, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # No4 价格
        ttk.Label(self.no_frame, text="No4 Price($):", font=('Arial', 12)).grid(row=6, column=0, padx=2, pady=5)
        self.no4_price_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no4_price_entry.delete(0, tk.END)
        self.no4_price_entry.insert(0, "0")
        self.no4_price_entry.grid(row=6, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # No5 价格
        ttk.Label(self.no_frame, text="No5 Price($):", font=('Arial', 12)).grid(row=8, column=0, padx=2, pady=5)
        self.no5_price_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no5_price_entry.delete(0, tk.END)
        self.no5_price_entry.insert(0, "0")
        self.no5_price_entry.grid(row=8, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # NO1 金额
        ttk.Label(self.no_frame, text="No1 Amount:", font=('Arial', 12)).grid(row=1, column=0, padx=2, pady=5)
        self.no1_amount_entry = ttk.Entry(self.no_frame, width=12)
        self.no1_amount_entry.insert(0, str(self.config['trading']['No1']['amount']))
        self.no1_amount_entry.grid(row=1, column=1, padx=2, pady=5, sticky="ew")

        # No2 金额
        ttk.Label(self.no_frame, text="No2 Amount:", font=('Arial', 12)).grid(row=3, column=0, padx=2, pady=5)
        self.no2_amount_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no2_amount_entry.insert(0, "0")
        self.no2_amount_entry.grid(row=3, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # No3 金额
        ttk.Label(self.no_frame, text="No 3 Amount:", font=('Arial', 12)).grid(row=5, column=0, padx=2, pady=5)
        self.no3_amount_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no3_amount_entry.insert(0, "0")
        self.no3_amount_entry.grid(row=5, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # No4 金额
        ttk.Label(self.no_frame, text="No4 Amount:", font=('Arial', 12)).grid(row=7, column=0, padx=2, pady=5)
        self.no4_amount_entry = ttk.Entry(self.no_frame, width=12)  # 添加self
        self.no4_amount_entry.insert(0, "0")
        self.no4_amount_entry.grid(row=7, column=1, padx=2, pady=5, sticky="ew")  # 修正grid位置

        # 创建买入按钮区域
        buy_frame = ttk.Frame(scrollable_frame)
        buy_frame.pack(fill="x", padx=(0,0), pady=2)

        # 创建按钮框架
        buy_button_frame = ttk.Frame(buy_frame)
        buy_button_frame.pack(side=tk.LEFT, padx=2)  # 添加expand=True使容器居中

        # 第一行按钮
        self.buy_button = ttk.Button(buy_button_frame, text="Buy", width=self.button_width,
                                    command=self.click_buy)
        self.buy_button.grid(row=0, column=0, padx=2, pady=5)

        self.buy_yes_button = ttk.Button(buy_button_frame, text="Buy-Yes", width=self.button_width,
                                        command=self.click_buy_yes)
        self.buy_yes_button.grid(row=0, column=1, padx=2, pady=5)

        self.buy_no_button = ttk.Button(buy_button_frame, text="Buy-No", width=self.button_width,
                                       command=self.click_buy_no)
        self.buy_no_button.grid(row=0, column=2, padx=2, pady=5)

        self.buy_confirm_button = ttk.Button(buy_button_frame, text="Buy-conf", width=self.button_width,
                                            command=self.click_buy_confirm_button)
        self.buy_confirm_button.grid(row=0, column=3, padx=2, pady=5)

        # 第二行按钮
        self.amount_yes1_button = ttk.Button(buy_button_frame, text="Amount-Y1", width=self.button_width)
        self.amount_yes1_button.bind('<Button-1>', self.click_amount)
        self.amount_yes1_button.grid(row=1, column=0, padx=2, pady=5)

        self.amount_yes2_button = ttk.Button(buy_button_frame, text="Amount-Y2", width=self.button_width)
        self.amount_yes2_button.bind('<Button-1>', self.click_amount)
        self.amount_yes2_button.grid(row=1, column=1, padx=2, pady=5)

        self.amount_yes3_button = ttk.Button(buy_button_frame, text="Amount-Y3", width=self.button_width)
        self.amount_yes3_button.bind('<Button-1>', self.click_amount)
        self.amount_yes3_button.grid(row=1, column=2, padx=2, pady=5)

        self.amount_yes4_button = ttk.Button(buy_button_frame, text="Amount-Y4", width=self.button_width)
        self.amount_yes4_button.bind('<Button-1>', self.click_amount)
        self.amount_yes4_button.grid(row=1, column=3, padx=2, pady=5)

        # 第三行
        self.amount_no1_button = ttk.Button(buy_button_frame, text="Amount-N1", width=self.button_width)
        self.amount_no1_button.bind('<Button-1>', self.click_amount)
        self.amount_no1_button.grid(row=2, column=0, padx=2, pady=5)
        
        self.amount_no2_button = ttk.Button(buy_button_frame, text="Amount-N2", width=self.button_width)
        self.amount_no2_button.bind('<Button-1>', self.click_amount)
        self.amount_no2_button.grid(row=2, column=1, padx=2, pady=5)

        self.amount_no3_button = ttk.Button(buy_button_frame, text="Amount-N3", width=self.button_width)
        self.amount_no3_button.bind('<Button-1>', self.click_amount)
        self.amount_no3_button.grid(row=2, column=2, padx=2, pady=5)

        self.amount_no4_button = ttk.Button(buy_button_frame, text="Amount-N4", width=self.button_width)
        self.amount_no4_button.bind('<Button-1>', self.click_amount)
        self.amount_no4_button.grid(row=2, column=3, padx=2, pady=5)

        # 第四行按钮
        self.position_sell_yes_button = ttk.Button(buy_button_frame, text="P-Sell-Yes", width=self.button_width,
                                                 command=self.click_position_sell_yes)
        self.position_sell_yes_button.grid(row=3, column=0, padx=2, pady=5)

        self.position_sell_no_button = ttk.Button(buy_button_frame, text="P-Sell-No", width=self.button_width,
                                                command=self.click_position_sell_no)
        self.position_sell_no_button.grid(row=3, column=1, padx=2, pady=5)

        self.sell_confirm_button = ttk.Button(buy_button_frame, text="Sell-conf", width=self.button_width,
                                           command=self.click_sell_confirm_button)
        self.sell_confirm_button.grid(row=3, column=2, padx=2, pady=5)
        
        # 配置列权重使按钮均匀分布
        for i in range(4):
            buy_button_frame.grid_columnconfigure(i, weight=1)    
    """以上代码从240行到 742 行是设置 GUI 界面的"""

    """以下代码从 745 行到行是程序交易逻辑"""
    def start_monitoring(self):
        """开始监控"""
        # 直接使用当前显示的网址
        self.target_url = self.url_entry.get()
        self.logger.info(f"\033[34m✅ 开始监控网址: {self.target_url}\033[0m")
        
        # 启用开始按钮，启用停止按钮
        self.start_button['state'] = 'disabled'
            
        # 将"开始监控"文字变为红色
        self.start_button.configure(style='Red.TButton')
        
        # 重置交易次数计数器
        self.trade_count = 0
            
        # 启动浏览器作线程
        threading.Thread(target=self._start_browser_monitoring, args=(self.target_url,), daemon=True).start()
        """到这里代码执行到了 995 行"""

        self.running = True

        # 获取当前日期并显示,此日期再次点击start按钮时会更新
        current_date = datetime.now().strftime("%d %B")
        self.date_label.config(text=current_date)

        # 启用设置金额按钮
        self.set_amount_button['state'] = 'normal'
        # 启动页面刷新
        self.root.after(40000, self.refresh_page)
        self.logger.info("\033[34m✅ 启动页面刷新成功!\033[0m")

        # 检查是否登录
        self.root.after(10000, self.start_login_monitoring)
        # 启动URL监控
        self.root.after(4000, self.start_url_monitoring)
        # 启动自动找币
        self.root.after(90000, self.schedule_auto_find_coin)
        # 启动币安零点时价格监控
        self.root.after(6000, self.get_binance_price)
        # 启动币安实时价格监控
        self.root.after(7000, self.get_now_price)
        # 启动 XPath 监控
        self.monitor_xpath_timer = self.root.after(120000, self.monitor_xpath_elements)

    def _start_browser_monitoring(self, new_url):
        """在新线程中执行浏览器操作"""
        try:
            if not self.driver:
                chrome_options = Options()
                chrome_options.debugger_address = "127.0.0.1:9222"
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                
                try:
                    self.driver = webdriver.Chrome(options=chrome_options)
                    
                except Exception as e:
                    self.logger.error(f"连接浏览器失败: {str(e)}")
                    self._show_error_and_reset("无法连接Chrome浏览器,请确保已运行start_chrome.sh")
                    return
            try:
                # 在当前标签页打开URL
                self.driver.get(new_url)
                
                # 等待页面加载
                WebDriverWait(self.driver, 60).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # 验证页面加载成功
                current_url = self.driver.current_url
                
                # 保存配置
                if 'website' not in self.config:
                    self.config['website'] = {}
                self.config['website']['url'] = new_url
                self.save_config()
                
                # 更新交易币对显示
                try:
                    pair = re.search(r'event/([^?]+)', new_url)
                    if pair:
                        self.trading_pair_label.config(text=pair.group(1))
                    else:
                        self.trading_pair_label.config(text="无识别事件名称")
                except Exception:
                    self.trading_pair_label.config(text="解析失败")
                #  开启监控
                self.running = True
                
                # 启动监控线程
                self.monitoring_thread = threading.Thread(target=self.monitor_prices, daemon=True)
                self.monitoring_thread.start()
                self.logger.info("\033[34m✅ 启动实时监控价格和资金线程\033[0m")
                
            except Exception as e:
                error_msg = f"加载网站失败: {str(e)}"
                self.logger.error(error_msg)
                self._show_error_and_reset(error_msg)  
        except Exception as e:
            error_msg = f"启动监控失败: {str(e)}"
            self.logger.error(error_msg)
            self._show_error_and_reset(error_msg)

    def _show_error_and_reset(self, error_msg):
        """显示错误并重置按钮状态"""
        # 用after方法确保在线程中执行GUI操作
        self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        self.root.after(0, lambda: self.start_button.config(state='normal'))
        self.running = False

    def monitor_prices(self):
        """检查价格变化"""
        try:
            # 确保浏览器连接
            if not self.driver:
                chrome_options = Options()
                chrome_options.debugger_address = "127.0.0.1:9222"
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                self.driver = webdriver.Chrome(options=chrome_options)
                
            target_url = self.url_entry.get()
            
            # 使用JavaScript创建并点击链接来打开新标签页
            js_script = """
                const a = document.createElement('a');
                a.href = arguments[0];
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            """
            self.driver.execute_script(js_script, target_url)
            
            # 等待新标签页打开
            time.sleep(1)
            
            # 切换到新打开的标签页
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
           
            # 开始监控价格
            while not self.stop_event.is_set():  # 改用事件判断
                try:
                    self.check_balance()
                    self.check_prices()
                    time.sleep(1)
                except Exception as e:
                    if not self.stop_event.is_set():  # 仅在未停止时记录错误
                        self.logger.error(f"监控失败: {str(e)}")
                    time.sleep(self.retry_interval)
        except Exception as e:
            if not self.stop_event.is_set():
                self.logger.error(f"加载页面失败: {str(e)}")
            self.stop_monitoring()
    
    def restart_browser(self):
        """自动修复: 尝试重新连接浏览器"""
        try:
            self.logger.info("正在尝试自动修复CHROME浏览器...")
            
            # 获取当前脚本的完整路径
            script_path = os.path.abspath('start_chrome.sh')
           # 直接在当前进程中执行脚本，而不是打开新终端
            try:
                # 使用subprocess直接执行脚本，不打开新终端
                subprocess.run(['bash', script_path], check=True)
                self.logger.info("\033[34m✅ 已重新启动Chrome浏览器\033[0m")
            except Exception as chrome_e:
                self.logger.error(f"启动Chrome浏览器失败: {str(chrome_e)}")

             # 等待Chrome启动并初始化driver
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # 重新初始化driver
                    chrome_options = Options()
                    chrome_options.debugger_address = "127.0.0.1:9222"
                    chrome_options.add_argument('--no-sandbox')
                    chrome_options.add_argument('--disable-dev-shm-usage')
                    self.driver = webdriver.Chrome(options=chrome_options)
                    
                    # 验证连接
                    self.driver.get('chrome://version/')  # 测试连接
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    self.logger.info("\033[34m✅ 浏览器驱动已成功重连\033[0m")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"浏览器连接尝试失败 ({attempt+1}/{max_retries}), 2秒后重试...")
                        time.sleep(2)
                    else:
                        raise
            # 加载目标URL
            target_url = self.url_entry.get()
            try:
                self.driver.get(target_url)
                WebDriverWait(self.driver, 15).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                self.logger.info(f"\033[34m✅ 成功加载目标页面: {target_url}\033[0m")
            except Exception as e:
                self.logger.error(f"加载目标页面失败: {str(e)}")
                return

            if self.find_login_button():
                self.logger.info("未登录,开始登录")

                # 点击登录按钮
                try:
                    login_button = self.driver.find_element(By.XPATH, XPathConfig.LOGIN_BUTTON[0])
                    login_button.click()
                except NoSuchElementException:
                    login_button = self._find_element_with_retry(
                        XPathConfig.LOGIN_BUTTON,
                        timeout=3,
                        silent=True
                    )
                    login_button.click()
                time.sleep(1)
                
                # 使用 XPath 定位并点击 google 按钮
                google_button = self._find_element_with_retry(XPathConfig.LOGIN_WITH_GOOGLE_BUTTON, timeout=3, silent=True)
                google_button.click()
                time.sleep(25)

                self.start_url_monitoring()
                self.start_login_monitoring()
                self.refresh_page()
                self.schedule_auto_find_coin()
        except Exception as e:
            self.logger.error(f"自动修复失败: {e}")
    
    def get_nearby_cents(self, retry_times=2):
        """获取spread附近的价格数字"""
        for attempt in range(retry_times):
            try:
                # 定位 Spread 元素
                try:
                    keyword_element = self.driver.find_element(By.XPATH, XPathConfig.SPREAD[0])
                    container = keyword_element.find_element(By.XPATH, './ancestor::div[3]') # 必须是 3 层 DIV
                except NoSuchElementException:
                    # 如果找不到元素，静默处理，不记录错误日志
                    time.sleep(1)
                    continue
                # 取兄弟节点
                above_elements = self.driver.execute_script(
                    'let e=arguments[0],r=[];while(e=e.previousElementSibling)r.push(e);return r;', container)
                below_elements = self.driver.execute_script(
                    'let e=arguments[0],r=[];while(e=e.nextElementSibling)r.push(e);return r;', container)
                
                # 提取上方的元素文本
                above_element_texts = []
                for el in above_elements: 
                    above_element_text = el.text.strip()
                    above_element_texts.append(above_element_text)
                
                # 提取下方的元素文本
                below_element_texts = []
                for el in below_elements:
                    below_element_text = el.text.strip()
                    below_element_texts.append(below_element_text)
                
                # 根据规律直接获取对应位置的值
                up_price = 0
                asks_shares = None
                down_price = 0
                bids_shares = None
                
                # 确保above_element_texts至少有4个元素
                if len(above_element_texts) >= 4:
                    # 提取第4个元素中的价格
                    if '¢' in above_element_texts[3]:
                        price_match = re.search(r'(\d+\.?\d*)¢', above_element_texts[3])
                        if price_match:
                            up_price = price_match.group(1)
                            #self.logger.info(f"\033[34m✅ 成功获取up_price: {up_price}\033[0m")
                    # 提取第3个元素作为asks_shares
                    if re.match(r'^\d+\.?\d*$', above_element_texts[2]):
                        asks_shares = above_element_texts[2]
                    elif re.search(r'(\d+\.?\d+)', above_element_texts[2]):
                        shares_match = re.search(r'(\d+[,\.]?\d*)', above_element_texts[2])
                        if shares_match:
                            asks_shares = shares_match.group(1)
                
                # 确保below_element_texts至少有5个元素
                if len(below_element_texts) >= 5:
                    # 提取第4个元素中的价格
                    if '¢' in below_element_texts[3]:
                        price_match = re.search(r'(\d+\.?\d*)¢', below_element_texts[3])
                        if price_match:
                            down_price = price_match.group(1)
                            #self.logger.info(f"\033[34m✅ 成功获取down_price: {down_price}\033[0m")
                    # 提取第5个元素作为bids_shares
                    if re.match(r'^\d+\.?\d*$', below_element_texts[4]):
                        bids_shares = below_element_texts[4]
                    elif re.search(r'(\d+\.?\d+)', below_element_texts[4]):
                        shares_match = re.search(r'(\d+[,\.]?\d*)', below_element_texts[4])
                        if shares_match:
                            bids_shares = shares_match.group(1)
                try:
                    asks_float = round(float(up_price), 2)
                    bids_float = round(float(down_price), 2)
                    
                    # 确保shares值是浮点数
                    if asks_shares is not None:
                        asks_shares = float(asks_shares.replace(',', ''))
                    
                    if bids_shares is not None:
                        bids_shares = float(bids_shares.replace(',', ''))
                    
                    # self.logger.info(f"asks_shares:{asks_shares}, bids_shares:{bids_shares}")
                    return asks_float, bids_float, asks_shares, bids_shares
                
                except ValueError as e:
                    self.logger.warning(f"价格转换错误: {e}")
                    continue
                
            except StaleElementReferenceException:
                time.sleep(1)  # 稍等一下再试
                continue
            except Exception as e:
                self.logger.logger.info(f"SPREAD其他异常,2秒后重试,忽略")
                time.sleep(2)
                if attempt < retry_times - 1:
                    time.sleep(2)
                    continue            
                break
        return None, None, None, None

    def check_prices(self):
        """检查价格变化"""
        try:
            # 检查浏览器连接
            if not self._is_browser_alive():
                self._reconnect_browser()

            if not self.driver:
                self.restart_browser()
            # 添加URL检查
            target_url = self.url_entry.get()
            current_url = self.driver.current_url

            if target_url != current_url:
                self.logger.warning(f"检测到URL变化,正在返回监控地址: {target_url}")
                self.driver.get(target_url)
                # 等待页面完全加载
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                      
            try:
                """buy_up_price就是yes price, buy_down_price就是no price"""
                # up = above = asks, down = below = bids
                above_price, below_price, asks_shares, bids_shares = self.get_nearby_cents()

                if above_price is not None and below_price is not None:
                    try:
                        up_price = float(above_price)
                        down_price = 100 - float(below_price)
                        up_shares = float(asks_shares)
                        down_shares = float(bids_shares)
                        
                        # 更新价格显示
                        self.yes_price_label.config(
                            text=f"Up: {up_price:.1f}¢"
                        )
                        self.no_price_label.config(
                            text=f"Down: {down_price:.1f}¢"
                        )
                        self.up_shares_label.config(
                            text=f"Up Shares: {up_shares:.2f}"
                        )
                        self.down_shares_label.config(
                            text=f"Down Shares: {down_shares:.2f}"
                        )
                       
                        # 执行所有交易检查函数
                        self.First_trade()
                        self.Second_trade()
                        self.Third_trade()
                        self.Forth_trade()
                        self.Sell_yes()
                        self.Sell_no() 
                    except ValueError as e:
                        self.logger.error(f"价格计算错误: {ValueError}")      
                else:
                    self.yes_price_label.config(text="Up: Fail", foreground='red')
                    self.no_price_label.config(text="Down: Fail", foreground='red')  
            except Exception as e:
                self.yes_price_label.config(text="Up: Fail", foreground='red')
                self.no_price_label.config(text="Down: Fail", foreground='red')
                #self.root.after(3000, self.check_prices)
        except Exception as e:
            self.logger.error(f"检查价格主流程失败: {str(e)}")
            time.sleep(1)
            
    def check_balance(self):
        """获取Portfolio和Cash值"""
        try:
            if not self.driver:
                self.restart_browser()

            # 等待页面完全加载
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            try:
                # 取Portfolio值
                try:
                    portfolio_element = self.driver.find_element(By.XPATH, XPathConfig.PORTFOLIO_VALUE[0])
                    self.portfolio_value = portfolio_element.text
                    
                except NoSuchElementException:
                    portfolio_element = self._find_element_with_retry(XPathConfig.PORTFOLIO_VALUE, timeout=3, silent=True)
                    self.portfolio_value = portfolio_element.text
            
                # 获取Cash值
                try:
                    cash_element = self.driver.find_element(By.XPATH, XPathConfig.CASH_VALUE[0])
                    self.cash_value = cash_element.text
                except NoSuchElementException:
                    cash_element = self._find_element_with_retry(XPathConfig.CASH_VALUE, timeout=3, silent=True)
                    self.cash_value = cash_element.text
                    
                # 更新Portfolio和Cash显示
                self.portfolio_label.config(text=f"Portfolio: {self.portfolio_value}")
                self.cash_label.config(text=f"Cash: {self.cash_value}")

                # 新增触发条件：首次获取到Cash值时安排设置金额
                if not hasattr(self, 'cash_initialized'):
                    self.cash_initialized = True
                    self.root.after(2000, self.schedule_update_amount)  # 延迟2秒确保数据稳定

            except Exception as e:
                self.logger.info(f"获取资金信息失败: {str(e)}")
                self.portfolio_label.config(text="Portfolio: Fail")
                self.cash_label.config(text="Cash: Fail")
                self.driver.refresh()
                #self.root.after(3000, self.check_balance)
                
        except Exception as e:
            self.logger.error(f"检查资金失败: {str(e)}")
            time.sleep(1)   
             
    """以上代码执行了监控价格和获取 CASH 的值。从这里开始程序返回到第 740 行"""  

    """以下代码是设置 YES/NO 金额的函数,直到第 1127 行"""
    def schedule_update_amount(self, retry_count=0):
        """设置金额,带重试机制"""
        try:
            if retry_count < 15:  # 最多重试15次
                # 1秒后执行
                self.root.after(1000, lambda: self.try_update_amount(retry_count))
            else:
                self.logger.warning("更新金额操作达到最大重试次数")
        except Exception as e:
            self.logger.error(f"安排更新金额操作失败: {str(e)}")

    def try_update_amount(self, current_retry=0):
        """尝试设置金额"""
        try:
            self.set_amount_button.invoke()
            self.root.after(1000, lambda: self.check_amount_and_set_price(current_retry))
        except Exception as e:
            self.logger.error(f"更新金额操作失败 (尝试 {current_retry + 1}/15): {str(e)}")
            # 如果失败，安排下一次重试
            self.schedule_update_amount(current_retry + 1)

    def check_amount_and_set_price(self, current_retry):
        """检查金额是否设置成功,成功后设置价格"""
        try:
            # 检查yes金额是否为非0值
            yes1_amount = self.yes1_amount_entry.get().strip()

            if yes1_amount and yes1_amount != '0':
                # 延迟1秒设置价格
                self.root.after(2000, lambda: self.set_yes_no_default_target_price())
                
            else:
                if current_retry < 15:  # 最多重试15次
                    self.logger.info("\033[31m❌ 金额未成功设置,2秒后重试\033[0m")
                    self.root.after(2000, lambda: self.check_amount_and_set_price(current_retry))
                else:
                    self.logger.warning("金额设置超时")
        except Exception as e:
            self.logger.error(f"检查金额设置状态失败: {str(e)}")

    def set_yes_no_default_target_price(self):
        """设置默认目标价格"""
        self.yes1_price_entry.delete(0, tk.END)
        self.yes1_price_entry.insert(0, self.default_target_price)
        self.no1_price_entry.delete(0, tk.END)
        self.no1_price_entry.insert(0, self.default_target_price)
        self.logger.info(f"\033[34m✅ 设置买入价格{self.default_target_price}成功\033[0m")
        self.close_windows()

    def set_yes_no_cash(self):
        """设置 Yes/No 各级金额"""
        if not hasattr(self, 'cash_initialized'):
            self.logger.warning("Cash数据尚未就绪,延迟设置金额")
            self.root.after(2000, self.set_yes_no_cash)
            return
        try:
            #设置重试参数
            max_retry = 15
            retry_count = 0
            self.cash = 0

            while retry_count < max_retry:
                try:
                    # 获取 Cash 值
                    cash_text = self.cash_value
                    
                    # 使用正则表达式提取数字
                    cash_match = re.search(r'\$?([\d,]+\.?\d*)', cash_text)
                    if not cash_match:
                        raise ValueError("无法从Cash值中提取数字")
                    # 移除逗号并转换为浮点数
                    self.cash = float(cash_match.group(1).replace(',', ''))
                    self.logger.info(f"\033[34m提取到Cash值: {self.cash}\033[0m")
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retry:
                        time.sleep(2)
                    else:
                        raise ValueError("获取Cash值失败")
            if self.cash is None:
                raise ValueError("获取Cash值失败")
            
            # 获取金额设置中的百分比值
            initial_percent = float(self.initial_amount_entry.get()) / 100  # 初始金额百分比
            first_rebound_percent = float(self.first_rebound_entry.get()) / 100  # 反水一次百分比
            n_rebound_percent = float(self.n_rebound_entry.get()) / 100  # 反水N次百分比

            # 设置 Yes1 和 No1金额
            base_amount = self.cash * initial_percent
            self.yes1_entry = self.yes_frame.grid_slaves(row=1, column=1)[0]
            self.yes1_amount_entry.delete(0, tk.END)
            self.yes1_amount_entry.insert(0, f"{base_amount:.2f}")
            self.no1_entry = self.no_frame.grid_slaves(row=1, column=1)[0]
            self.no1_amount_entry.delete(0, tk.END)
            self.no1_amount_entry.insert(0, f"{base_amount:.2f}")
            
            # 计算并设置 Yes2/No2金额
            self.yes2_amount = base_amount * first_rebound_percent
            self.yes2_entry = self.yes_frame.grid_slaves(row=3, column=1)[0]
            self.yes2_entry.delete(0, tk.END)
            self.yes2_entry.insert(0, f"{self.yes2_amount:.2f}")
            self.no2_entry = self.no_frame.grid_slaves(row=3, column=1)[0]
            self.no2_entry.delete(0, tk.END)
            self.no2_entry.insert(0, f"{self.yes2_amount:.2f}")
            
            # 计算并设置 YES3/NO3 金额
            self.yes3_amount = self.yes2_amount * n_rebound_percent
            self.yes3_entry = self.yes_frame.grid_slaves(row=5, column=1)[0]
            self.yes3_entry.delete(0, tk.END)
            self.yes3_entry.insert(0, f"{self.yes3_amount:.2f}")
            self.no3_entry = self.no_frame.grid_slaves(row=5, column=1)[0]
            self.no3_entry.delete(0, tk.END)
            self.no3_entry.insert(0, f"{self.yes3_amount:.2f}")

            # 计算并设置 Yes4/No4金额
            self.yes4_amount = self.yes3_amount * n_rebound_percent
            self.yes4_entry = self.yes_frame.grid_slaves(row=7, column=1)[0]
            self.yes4_entry.delete(0, tk.END)
            self.yes4_entry.insert(0, f"{self.yes4_amount:.2f}")
            self.no4_entry = self.no_frame.grid_slaves(row=7, column=1)[0]
            self.no4_entry.delete(0, tk.END)
            self.no4_entry.insert(0, f"{self.yes4_amount:.2f}")

            # 获取当前CASH并显示,此CASH再次点击start按钮时会更新
            current_cash = float(base_amount / initial_percent)
            self.cash_label_value.config(text=f"{current_cash:.2f}")
            self.logger.info("\033[34m✅ YES/NO 金额设置完成\033[0m")
            
        except Exception as e:
            self.logger.error(f"设置金额失败: {str(e)}")
            
            self.schedule_retry_update()

    def schedule_retry_update(self):
        """安排重试更新金额"""
        if hasattr(self, 'retry_timer'):
            self.root.after_cancel(self.retry_timer)
        self.retry_timer = self.root.after(3000, self.set_yes_no_cash)  # 3秒后重试
    """以上代码执行了设置 YES/NO 金额的函数,从 1000 行到 1127 行,程序执行返回到 745 行"""

    """以下代码是启动 URL 监控和登录状态监控的函数,直到第 1426 行"""
    def start_url_monitoring(self):
        """启动URL监控"""
        with self.url_monitoring_lock:
            if getattr(self, 'is_url_monitoring', False):
                self.logger.debug("URL监控已在运行中")
                return
            
            if not self.driver:
                self.restart_browser()

            self.url_monitoring_running = True
            self.logger.info("\033[34m✅ 启动URL监控\033[0m")

            def check_url():
                if self.running and self.driver:
                    try:
                        current_page_url = self.driver.current_url
                        target_url = self.target_url

                        if current_page_url != target_url:
                            self.logger.warning("检测到URL变化,正在恢复...")
                            self.driver.get(target_url)
                            self.logger.info("\033[34m✅ 已恢复到正确的监控网址\033[0m")

                    except Exception as e:
                        self.logger.error(f"URL监控出错: {str(e)}")
                        # 重新导航到目标URL
                        if self.driver and self._is_browser_alive():
                            self.driver.get(self.target_url)
                            self.logger.info("\033[34m✅ URL监控已自动修复\033[0m")
                    # 继续监控
                    if self.running:
                        self.url_check_timer = self.root.after(3000, check_url)  # 每3秒检查一次
            
            # 开始第一次检查
            self.url_check_timer = self.root.after(1000, check_url)
    
    def _is_browser_alive(self):
        """检查浏览器是否仍然活跃"""
        try:
            # 尝试执行一个简单的JavaScript命令来检查浏览器是否响应
            self.driver.execute_script("return navigator.userAgent")
            return True
        except Exception:
            return False
            
    def _reconnect_browser(self):
        """尝试重新连接浏览器"""
        try:
            # 关闭现有连接（如果有）
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                
            # 重新建立连接
            chrome_options = Options()
            chrome_options.debugger_address = "127.0.0.1:9222"
            chrome_options.add_argument('--disable-dev-shm-usage')
            self.driver = webdriver.Chrome(options=chrome_options)
            self.logger.info("\033[34m✅ 已重新连接到浏览器\033[0m")
            return True
        except Exception as e:
            self.logger.error(f"重新连接浏览器失败: {str(e)}")
            return False

    def stop_url_monitoring(self):
        """停止URL监控"""
        with self.url_monitoring_lock:
            # 检查是否有正在运行的URL监控
            if not hasattr(self, 'url_monitoring_running') or not self.url_monitoring_running:
                self.logger.debug("URL监控未在运行中,无需停止")
                return
            
            # 取消定时器
            if hasattr(self, 'url_check_timer') and self.url_check_timer:
                try:
                    self.root.after_cancel(self.url_check_timer)
                    self.url_check_timer = None
                    
                except Exception as e:
                    self.logger.error(f"取消URL监控定时器时出错: {str(e)}")
            
            # 重置监控状态
            self.url_monitoring_running = False
            
            self.logger.info("\033[31m❌ URL监控已停止\033[0m")

    def find_login_button(self):
        """查找登录按钮"""
        # 使用静默模式查找元素，并添加空值检查
        try:
            login_button = self.driver.find_element(By.XPATH, XPathConfig.LOGIN_BUTTON[0])
        except NoSuchElementException:
            login_button = self._find_element_with_retry(
                XPathConfig.LOGIN_BUTTON,
                timeout=3,
                silent=True
            )
        
        # 添加空值检查和安全访问
        if login_button is not None and "Log In" in login_button.text:
            self.logger.warning("检查到未登录,自动登录...")
            return True
        else:
            # 正常状态无需记录日志
            return False

    def start_login_monitoring(self):
        """启动登录状态监控"""
        self.logger.info("\033[34m✅ 启动登录状态监控\033[0m")
        if not self.driver:
            self.restart_browser()
            
        def check_login_status():
            if self.running and self.driver:
                try:
                    # 使用线程执行登录检查，避免阻塞主线程
                    threading.Thread(
                        target=self._check_login_status_thread,
                        daemon=True
                    ).start()
                except Exception as e:
                    self.logger.error(f"登录状态检查出错: {str(e)}")
                
                # 继续监控
                if self.running:
                    self.login_check_timer = self.root.after(10000, check_login_status)  # 每10秒检查一次
        
        # 开始第一次检查
        self.login_check_timer = self.root.after(10000, check_login_status)

    def _check_login_status_thread(self):
        """在单独线程中执行登录检查"""
        try:
            try:
                time.sleep(3)
                if self.find_login_button():
                    self.logger.warning("检测到❌未登录状态，执行登录")
                    # 在主线程中执行登录操作
                    self.root.after(0, self.check_and_handle_login)
                
            except NoSuchElementException:
                # 找不到登录按钮,说明已经登录
                pass   
        except Exception as e:
            self.logger.error(f"登录状态检查线程出错: {str(e)}")

    def check_and_handle_login(self):
        """执行登录操作"""
        try:
            self.logger.info("开始执行登录操作...")
            
            if not self.driver:
                self.restart_browser()
                
            self.start_login_monitoring_running = True
            self.login_running = True
            
            # 点击登录按钮
            try:
                login_button = self.driver.find_element(By.XPATH, XPathConfig.LOGIN_BUTTON[0])
                login_button.click()
            except NoSuchElementException:
                login_button = self._find_element_with_retry(
                    XPathConfig.LOGIN_BUTTON,
                    timeout=3,
                    silent=True
                )
                login_button.click()
            
            # 使用 XPath 定位并点击 google 按钮
            google_button = self._find_element_with_retry(XPathConfig.LOGIN_WITH_GOOGLE_BUTTON, timeout=3, silent=True)
            google_button.click()
            time.sleep(15)

            if not self.find_login_button():
                self.logger.info("\033[34m✅ 登录成功\033[0m")
                self.login_running = False
                self.driver.get(self.target_url)
                time.sleep(2)
                
            else:
                self.logger.warning("登录失败,等待2秒后重试")
                time.sleep(1)
                self.check_and_handle_login()
                
        except Exception as e:
            self.logger.error(f"登录失败: {str(e)}")
            self.driver.refresh()
        
    # 添加刷新方法
    def refresh_page(self):
        """定时刷新页面"""
        # 生成随机的5-10分钟（以毫秒为单位）
        random_minutes = random.uniform(2, 6)
        self.refresh_interval = int(random_minutes * 60000)  # 转换为毫秒

        with self.refresh_page_lock:
            self.refresh_page_running = True
            try:
                # 先取消可能存在的旧定时器
                if hasattr(self, 'refresh_page_timer') and self.refresh_page_timer:
                    try:
                        self.root.after_cancel(self.refresh_page_timer)
                        self.refresh_page_timer = None
                    except Exception as e:
                        self.logger.error(f"取消旧定时器失败: {str(e)}")

                if self.running and self.driver and not self.trading:
                    self.driver.refresh()
                    refresh_time = self.refresh_interval / 60000
                    self.logger.info(f"\033[34m{round(refresh_time, 2)} 分钟后再次刷新\033[0m")      
                else:
                    self.logger.info("刷新失败")
                    self.logger.info(f"trading={self.trading}")
                    
            except Exception as e:
                self.logger.error(f"页面刷新失败")
                # 无论是否执行刷新都安排下一次（确保循环持续）
                if hasattr(self, 'refresh_page_timer') and self.refresh_page_timer:
                    try:
                        self.root.after_cancel(self.refresh_page_timer)
                    except Exception as e:
                        self.logger.error(f"取消旧定时器失败")
            finally:
                self.refresh_page_timer = self.root.after(self.refresh_interval, self.refresh_page)
            
    def stop_refresh_page(self):
        """停止页面刷新"""
        with self.refresh_page_lock:
            
            if hasattr(self, 'refresh_page_timer') and self.refresh_page_timer:
                try:
                    self.root.after_cancel(self.refresh_page_timer)
                    self.refresh_page_timer = None
                    self.logger.info("\033[31m❌ 刷新定时器已停止\033[0m")
                except Exception as e:
                    self.logger.error("取消页面刷新定时器时出错")
            # 重置监控状态
            self.refresh_page_running = False
            self.logger.info("\033[31m❌ 刷新状态已停止\033[0m")
    """以上代码执行了登录操作的函数,直到第 1315 行,程序执行返回到 748 行"""

    """以下代码是监控买卖条件及执行交易的函数,程序开始进入交易阶段,从 1468 行直到第 2224200 行"""  
    def is_buy_accept(self):
        """检查是否存在"Accept"按钮"""
        try:
            accept_button = self.driver.find_element(By.XPATH, XPathConfig.ACCEPT_BUTTON[0])
            
        except NoSuchElementException:
            accept_button = self._find_element_with_retry(
                XPathConfig.ACCEPT_BUTTON,
                timeout=3,
                silent=True
            )
        
        if accept_button:
            self.logger.info("检测到ACCEPT弹窗")
            return True
        else:
            self.logger.info("没有检测到ACCEPT弹窗")
            return False
    
    def First_trade(self):
        """第一次交易价格设置为 0.52 买入"""
        try:
            asks_price, bids_price, asks_shares, bids_shares = self.get_nearby_cents()
                
            if asks_price is not None and asks_price > 20 and bids_price is not None and bids_price < 97:
                # 获取Yes1和No1的GUI界面上的价格
                yes1_price = float(self.yes1_price_entry.get())
                no1_price = float(self.no1_price_entry.get())
                self.trading = True  # 开始交易
                
                # 检查Yes1价格匹配
                if 0 <= round((asks_price - yes1_price), 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Up 1: {asks_price}¢ 价格匹配,执行自动交易")
                        # 执行现有的交易操作
                        self.amount_yes1_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            pyautogui.press('enter')
                            self.logger.info("\033[34m✅ 点击 ENTER 完成\033[0m")
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                            
                        time.sleep(0.5)
                        
                        if self.Verify_buy_yes():
                            # 增加交易次数
                            self.buy_yes1_amount = float(self.yes1_amount_entry.get())
                            self.trade_count += 1
                            
                            # 重置Yes1和No1价格为0
                            self.yes1_price_entry.delete(0, tk.END)
                            self.yes1_price_entry.insert(0, "0")
                            self.no1_price_entry.delete(0, tk.END)
                            self.no1_price_entry.insert(0, "0")
                                
                            # 设置No2价格为默认值
                            self.no2_price_entry = self.no_frame.grid_slaves(row=2, column=1)[0]
                            self.no2_price_entry.delete(0, tk.END)
                            self.no2_price_entry.insert(0, str(self.default_target_price))
                            self.no2_price_entry.configure(foreground='red')  # 添加红色设置

                            # 设置 Yes5和No5价格为0.98
                            self.yes5_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                            self.yes5_price_entry.delete(0, tk.END)
                            self.yes5_price_entry.insert(0, "99")
                            self.yes5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.no5_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                            self.no5_price_entry.delete(0, tk.END)
                            self.no5_price_entry.insert(0, "99")
                            self.no5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.logger.info("\033[34m✅ First_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up1",
                                price=self.buy_up_price,
                                amount=self.buy_yes1_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试

                # 检查No1价格匹配
                elif 0 <= round((100 - bids_price) - no1_price, 2) <= self.price_premium and (asks_shares > self.asks_shares):
                     while True:
                        self.logger.info(f"Down 1: {100 - bids_price}¢ 价格匹配,执行自动交易") 
                        # 执行现有的交易操作
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no1_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            pyautogui.press('enter')
                            time.sleep(0.5)
                            
                            self.logger.info("\033[34m✅ 点击 ENTER 完成\033[0m")
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                       
                        if self.Verify_buy_no():
                            self.buy_no1_amount = float(self.no1_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            
                            # 重置Yes1和No1价格为0
                            self.yes1_price_entry.delete(0, tk.END)
                            self.yes1_price_entry.insert(0, "0")
                            self.no1_price_entry.delete(0, tk.END)
                            self.no1_price_entry.insert(0, "0")
                            
                            # 设置Yes2价格为默认值
                            self.yes2_price_entry = self.yes_frame.grid_slaves(row=2, column=1)[0]
                            self.yes2_price_entry.delete(0, tk.END)
                            self.yes2_price_entry.insert(0, str(self.default_target_price))
                            self.yes2_price_entry.configure(foreground='red')  # 添加红色设置

                            # 设置 Yes5和No5价格为0.98
                            self.yes5_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                            self.yes5_price_entry.delete(0, tk.END)
                            self.yes5_price_entry.insert(0, "99")
                            self.yes5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.no5_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                            self.no5_price_entry.delete(0, tk.END)
                            self.no5_price_entry.insert(0, "99")
                            self.no5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.logger.info("\033[34m✅ First_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down1",
                                price=self.buy_down_price,
                                amount=self.buy_no1_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试                           
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"First_trade执行失败: {str(e)}")
            
        finally:
            self.trading = False
            
    def Second_trade(self):
        """处理Yes2/No2的自动交易"""
        try:
            asks_price, bids_price, asks_shares, bids_shares = self.get_nearby_cents()

            if asks_price is not None and asks_price > 20 and bids_price is not None and bids_price < 97:
                
                # 获Yes2和No2的价格输入框
                yes2_price = float(self.yes2_price_entry.get())
                no2_price = float(self.no2_price_entry.get())
                self.trading = True  # 开始交易
                
                # 检查Yes2价格匹配
                if 0 <= round((asks_price - yes2_price), 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Up 2: {asks_price}¢ 价格匹配,执行自动交易")
                        # 执行现有的交易操作
                        self.amount_yes2_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            pyautogui.press('enter')
                            time.sleep(0.5)
                            
                            self.logger.info("\033[34m✅ 点击 ENTER 完成\033[0m")
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                   
                        if self.Verify_buy_yes():
                            
                            # 重置Yes2和No2价格为0
                            self.yes2_price_entry.delete(0, tk.END)
                            self.yes2_price_entry.insert(0, "0")
                            self.no2_price_entry.delete(0, tk.END)
                            self.no2_price_entry.insert(0, "0")
                            
                            # 设置No3价格为默认值
                            self.no3_price_entry = self.no_frame.grid_slaves(row=4, column=1)[0]
                            self.no3_price_entry.delete(0, tk.END)
                            self.no3_price_entry.insert(0, str(self.default_target_price))
                            self.no3_price_entry.configure(foreground='red')  # 添加红色设置
                            self.buy_yes2_amount = float(self.yes2_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up2",
                                price=self.buy_up_price,
                                amount=self.buy_yes2_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Second_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
                # 检查No2价格匹配
                elif 0 <= round((100 - bids_price) - no2_price, 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Down 2: {100 - bids_price}¢ 价格匹配,执行自动交易")
                        
                        # 执行现有的交易操作
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no2_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                            
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            time.sleep(0.5)
                            pyautogui.press('enter')
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                            self.logger.info("\033[34m✅ 点击 ENTER 完成\033[0m")
                       
                        if self.Verify_buy_no():

                            # 重置Yes2和No2价格为0
                            self.yes2_price_entry.delete(0, tk.END)
                            self.yes2_price_entry.insert(0, "0")
                            self.no2_price_entry.delete(0, tk.END)
                            self.no2_price_entry.insert(0, "0")
                            
                            # 设置Yes3价格为默认值
                            self.yes3_price_entry = self.yes_frame.grid_slaves(row=4, column=1)[0]
                            self.yes3_price_entry.delete(0, tk.END)
                            self.yes3_price_entry.insert(0, str(self.default_target_price))
                            self.yes3_price_entry.configure(foreground='red')  # 添加红色设置
                            self.buy_no2_amount = float(self.no2_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down2",
                                price=self.buy_down_price,
                                amount=self.buy_no2_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Second_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Second_trade执行失败: {str(e)}")
            
        finally:
            self.trading = False
            
    def Third_trade(self):
        """处理Yes3/No3的自动交易"""
        try:
            asks_price, bids_price, asks_shares, bids_shares = self.get_nearby_cents()
                
            if asks_price is not None and asks_price > 20 and bids_price is not None and bids_price < 97:
                
                # 获取Yes3和No3的价格输入框
                yes3_price = float(self.yes3_price_entry.get())
                no3_price = float(self.no3_price_entry.get())
                self.trading = True  # 开始交易
            
                # 检查Yes3价格匹配
                if 0 <= round((asks_price - yes3_price), 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Up 3: {asks_price}¢ 价格匹配,执行自动交易")
                        # 执行交易操作
                        self.amount_yes3_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            time.sleep(0.5)
                            pyautogui.press('enter')
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                            self.logger.info("✅ 点击 ACCEPT 完成")
                    
                        if self.Verify_buy_yes():

                            # 重置Yes3和No3价格为0
                            self.yes3_price_entry.delete(0, tk.END)
                            self.yes3_price_entry.insert(0, "0")
                            self.no3_price_entry.delete(0, tk.END)
                            self.no3_price_entry.insert(0, "0")
                            
                            # 设置No4价格为默认值
                            self.no4_price_entry = self.no_frame.grid_slaves(row=6, column=1)[0]
                            self.no4_price_entry.delete(0, tk.END)
                            self.no4_price_entry.insert(0, str(self.default_target_price))
                            self.no4_price_entry.configure(foreground='red')  # 添加红色设置
                            self.buy_yes3_amount = float(self.yes3_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up3",
                                price=self.buy_up_price,
                                amount=self.buy_yes3_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )   
                            self.logger.info("\033[34m✅ Third_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
                # 检查No3价格匹配
                elif 0 <= round((100 - bids_price) - no3_price, 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Down 3: {100 - bids_price}¢ 价格匹配,执行自动交易")
                        # 执行交易操作
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no3_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            time.sleep(0.5)
                            pyautogui.press('enter')
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                            self.logger.info("\033[34m✅ 点击 ENTER 完成\033[0m")
                     
                        if self.Verify_buy_no():
                            
                            # 重置Yes3和No3价格为0
                            self.yes3_price_entry.delete(0, tk.END)
                            self.yes3_price_entry.insert(0, "0")
                            self.no3_price_entry.delete(0, tk.END)
                            self.no3_price_entry.insert(0, "0")
                            
                            # 设置Yes4价格为默认值
                            self.yes4_price_entry = self.yes_frame.grid_slaves(row=6, column=1)[0]
                            self.yes4_price_entry.delete(0, tk.END)
                            self.yes4_price_entry.insert(0, str(self.default_target_price))
                            self.yes4_price_entry.configure(foreground='red')  # 添加红色设置
                            self.buy_no3_amount = float(self.no3_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down3",
                                price=self.buy_down_price,
                                amount=self.buy_no3_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Third_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Third_trade执行失败: {str(e)}")
            
        finally:
            self.trading = False
            
    def Forth_trade(self):
        """处理Yes4/No4的自动交易"""
        try:
            asks_price, bids_price, asks_shares, bids_shares = self.get_nearby_cents()
                
            if asks_price is not None and asks_price > 20 and bids_price is not None and bids_price < 97:
                
                # 获取Yes4和No4的价格输入框
                yes4_price = float(self.yes4_price_entry.get())
                no4_price = float(self.no4_price_entry.get())
                self.trading = True  # 开始交易
            
                # 检查Yes4价格匹配
                if 0 <= round((asks_price - yes4_price), 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Up 4: {asks_price}¢ 价格匹配,执行自动交易")
                        # 执行交易操作
                        self.amount_yes4_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            pyautogui.press('enter')
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                            self.logger.info("✅ 点击 ENTER 完成")
                      
                        if self.Verify_buy_yes():

                            # 重置Yes4和No4价格为0
                            self.yes4_price_entry.delete(0, tk.END)
                            self.yes4_price_entry.insert(0, "0")
                            self.no4_price_entry.delete(0, tk.END)
                            self.no4_price_entry.insert(0, "0")

                            """当买了 4次后预防第 5 次反水，所以价格到了 51 时就平仓，然后再自动开"""
                            # 设置 Yes5和No5价格为0.85
                            self.yes5_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                            self.yes5_price_entry.delete(0, tk.END)
                            self.yes5_price_entry.insert(0, "99")
                            self.yes5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.no5_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                            self.no5_price_entry.delete(0, tk.END)
                            self.no5_price_entry.insert(0, "51")
                            self.no5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.buy_yes4_amount = float(self.yes4_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up4",
                                price=self.buy_up_price,
                                amount=self.buy_yes4_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Forth_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
                # 检查No4价格匹配
                elif 0 <= round((100 - bids_price) - no4_price, 2) <= self.price_premium and (asks_shares > self.asks_shares):
                    while True:
                        self.logger.info(f"Down 4: {100 - bids_price}¢ 价格匹配,执行自动交易")
                        # 执行交易操作
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no4_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        time.sleep(1)
                        if self.is_buy_accept():
                            # 点击 "Accept" 按钮
                            pyautogui.press('enter')
                            time.sleep(1)
                            self.buy_confirm_button.invoke()
                            self.logger.info("\033[34m✅ 点击 ENTER 完成\033[0m")
                    
                        if self.Verify_buy_no():
                            # 重置Yes4和No4价格为0
                            self.yes4_price_entry.delete(0, tk.END)
                            self.yes4_price_entry.insert(0, "0")
                            self.no4_price_entry.delete(0, tk.END)
                            self.no4_price_entry.insert(0, "0")

                            """当买了 4次后预防第 5 次反水，所以价格到了 52 时就平仓，然后再自动开"""
                            # 设置 Yes5和No5价格为0.98
                            self.yes5_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                            self.yes5_price_entry.delete(0, tk.END)
                            self.yes5_price_entry.insert(0, "51")
                            self.yes5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.no5_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                            self.no5_price_entry.delete(0, tk.END)
                            self.no5_price_entry.insert(0, "99")
                            self.no5_price_entry.configure(foreground='red')  # 添加红色设置
                            self.buy_no4_amount = float(self.no4_amount_entry.get())
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down4",
                                price=self.buy_down_price,
                                amount=self.buy_no4_amount,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Forth_trade执行成功\033[0m")
                            self.root.after(30000, self.driver.refresh)
                            break
                        else:
                            self.logger.warning("交易失败,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Forth_trade执行失败: {str(e)}")
            
        finally:
            self.trading = False
            
    def Sell_yes(self):
        """当YES5价格等于实时Yes价格时自动卖出"""
        try:
            if not self.driver:
                self.restart_browser()
            if self.find_login_button():
                self.check_and_handle_login()
                
            asks_price, bids_price, asks_shares, bids_shares = self.get_nearby_cents()

            if asks_price is not None and bids_price is not None and (bids_price > 10):
                
                # 获取Yes5价格
                yes5_price = float(self.yes5_price_entry.get())
                self.trading = True  # 开始交易

                # 检查Yes5价格匹配
                if 0 <= round((bids_price - yes5_price), 2) <= 1.1 and (bids_shares > self.bids_shares):
                    self.logger.info(f"Up 5: {asks_price}¢ 价格匹配,执行自动卖出")
                    
                    self.yes5_target_price = yes5_price
                            
                    while True:
                        # 执行卖出YES操作
                        self.only_sell_yes()
                        self.logger.info("卖完 Up 后，再卖 Down")
                        time.sleep(1)
                        self.driver.refresh()
                        # 卖 Down 之前先检查是否有 Down 标签
                        if self.find_position_label_no():
                            self.only_sell_no()
                        else:
                            pass

                        # 重置所有价格
                        for i in range(1,6):  # 1-5
                            yes_entry = getattr(self, f'yes{i}_price_entry', None)
                            no_entry = getattr(self, f'no{i}_price_entry', None)
                            if yes_entry:
                                yes_entry.delete(0, tk.END)
                                yes_entry.insert(0, "0")
                            if no_entry:
                                no_entry.delete(0, tk.END)
                                no_entry.insert(0, "0")
                        # 在所有操作完成后,重置交易
                        self.root.after(1000, self.reset_trade)
                        break
                    else:
                        self.logger.warning("卖出sell_yes验证失败,重试")
                        time.sleep(2)
                
        except Exception as e:
            self.logger.error(f"Sell_yes执行失败: {str(e)}")
            
        finally:
            self.trading = False
            
    def Sell_no(self):
        """当NO4价格等于实时No价格时自动卖出"""
        try:
            if not self.driver:
                self.restart_browser()
            if self.find_login_button():
                self.check_and_handle_login()

            asks_price, bids_price, asks_shares, bids_shares = self.get_nearby_cents()
            
            if asks_price is not None and (0 < asks_price < 90) and bids_price is not None:
                # 获取No5价格
                no5_price = float(self.no5_price_entry.get())
                self.trading = True  # 开始交易
            
                # 检查No5价格匹配
                if 0 <= round(100 - asks_price - no5_price, 2) <= 1.1 and (bids_shares > self.bids_shares):
                    self.logger.info(f"Down 5: {100 - asks_price}¢ 价格匹配,执行自动卖出")

                    self.no5_target_price = no5_price
                    
                    while True:
                        # 卖完 Down 后，自动再卖 Up                      
                        self.only_sell_no()
                        self.logger.info("卖完 Down 后，再卖 Up")
                        time.sleep(2)
                        self.driver.refresh()
                        if self.find_position_label_yes():
                            self.only_sell_yes()
                        else:
                            pass

                        # 重置所有价格
                        for i in range(1,6):  # 1-5
                            yes_entry = getattr(self, f'yes{i}_price_entry', None)
                            no_entry = getattr(self, f'no{i}_price_entry', None)
                            if yes_entry:
                                yes_entry.delete(0, tk.END)
                                yes_entry.insert(0, "0")
                            if no_entry:
                                no_entry.delete(0, tk.END)
                                no_entry.insert(0, "0")
                        # 在所有操作完成后,重置交易
                        self.root.after(1000, self.reset_trade)
                        break
                    else:
                        self.logger.warning("卖出sell_no验证失败,重试")
                        time.sleep(2)
                
        except Exception as e:
            self.logger.info(f"Sell_no执行失败: {str(e)}")
            
        finally:
            self.trading = False

    def reset_trade(self):
        """重置交易"""
        # 在所有操作完成后,重置交易
        time.sleep(2)
        self.set_yes_no_cash()
        
        # 检查属性是否存在，如果不存在则使用默认值
        yes5_price = getattr(self, 'yes5_target_price', 0)
        no5_price = getattr(self, 'no5_target_price', 0)

        if (yes5_price > 90) or (no5_price > 90):
            self.reset_trade_count = 0
        else:
            self.reset_trade_count += 1
        
        self.sell_count = 0
        self.trade_count = 0
        # 重置Yes1和No1价格为53
        self.set_yes_no_default_target_price()
        self.reset_count_label.config(text=str(self.reset_trade_count))
        self.logger.info(f"第\033[32m{self.reset_trade_count}\033[0m次重置交易")

    def only_sell_yes(self):
        """只卖出YES"""
        self.position_sell_yes_button.invoke()
        time.sleep(0.5)
        self.sell_confirm_button.invoke()
        time.sleep(0.5)

        if self.is_sell_accept():
            # 点击 "Accept" 按钮
            pyautogui.press('enter')
            time.sleep(1)
            self.sell_confirm_button.invoke()
            self.logger.info("\033[34m✅ 点击 ACCEPT 完成\033[0m")

        if self.Verify_sold_yes():
             # 增加卖出计数
            self.sell_count += 1
            # 发送交易邮件 - 卖出YES
            self.send_trade_email(
                trade_type="Sell Up",
                price=self.sell_up_price,
                amount=self.position_yes_cash(),  # 卖出时金额为总持仓
                trade_count=self.sell_count,
                cash_value=self.cash_value,
                portfolio_value=self.portfolio_value
            )
            
        else:
            self.logger.warning("卖出only_sell_yes验证失败,重试")
            return self.only_sell_yes()        
       
    def only_sell_no(self):
        """只卖出Down"""
        self.position_sell_no_button.invoke()
        time.sleep(0.5)
        self.sell_confirm_button.invoke()
        time.sleep(1)

        if self.is_sell_accept():
            # 点击 "Accept" 按钮
            pyautogui.press('enter')
            time.sleep(1)
            self.sell_confirm_button.invoke()
            self.logger.info("\033[34m✅ 点击 ACCEPT 完成\033[0m")
        
        if self.Verify_sold_no():
            # 增加卖出计数
            self.sell_count += 1
            
            # 发送交易邮件 - 卖出NO
            self.send_trade_email(
                trade_type="Sell Down",
                price=self.sell_down_price,
                amount=self.position_no_cash(),  # 卖出时金额为总持仓
                trade_count=self.sell_count,
                cash_value=self.cash_value,
                portfolio_value=self.portfolio_value
            )
            
        else:
            self.logger.warning("卖出only_sell_no验证失败,重试")
            return self.only_sell_no()
              
    def is_sell_accept(self):
        """检查是否存在"Accept"按钮"""
        try:
            accept_button = self.driver.find_element(By.XPATH, XPathConfig.ACCEPT_BUTTON[0])
            
        except NoSuchElementException:
            accept_button = self._find_element_with_retry(
                XPathConfig.ACCEPT_BUTTON,
                timeout=3,
                silent=True
            )
           
        if accept_button:
            
            return True
        else:
            
            return False
        
    """以上代码是交易主体函数 1-4,从第 1370 行到第 2418行"""

    """以下代码是交易过程中的各种点击方法函数，涉及到按钮的点击，从第 2419 行到第 2528 行"""
    def click_buy_confirm_button(self):
        try:
            buy_confirm_button = self.driver.find_element(By.XPATH, XPathConfig.BUY_CONFIRM_BUTTON[0])
            buy_confirm_button.click()
        except NoSuchElementException:
            
            buy_confirm_button = self._find_element_with_retry(
                XPathConfig.BUY_CONFIRM_BUTTON,
                timeout=3,
                silent=True
            )
            buy_confirm_button.click()
    
    def click_position_sell_no(self):
        """点击 Positions-Sell-No 按钮"""
        try:
            if not self.driver:
                self.restart_browser()

            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            position_value = self.find_position_label_yes()
            # position_value 的值是true 或 false
            # 根据position_value的值决定点击哪个按钮
            if position_value:
                # 如果第一行是Up，点击第二的按钮
                try:
                    button = self.driver.find_element(By.XPATH, XPathConfig.POSITION_SELL_NO_BUTTON[0])
                except NoSuchElementException:
                    button = self._find_element_with_retry(
                        XPathConfig.POSITION_SELL_NO_BUTTON,
                        timeout=3,
                        silent=True
                    )
            else:
                # 如果第一行不存在或不是Up，使用默认的第一行按钮
                try:
                    button = self.driver.find_element(By.XPATH, XPathConfig.POSITION_SELL_BUTTON[0])
                except NoSuchElementException:
                    button = self._find_element_with_retry(
                        XPathConfig.POSITION_SELL_BUTTON,
                        timeout=3,
                        silent=True
                    )
            # 执行点击
            self.driver.execute_script("arguments[0].click();", button)
            
        except Exception as e:
            error_msg = f"点击 Positions-Sell-No 按钮失败: {str(e)}"
            self.logger.error(error_msg)
            
    def click_position_sell_yes(self):
        """点击 Positions-Sell-Yes 按钮"""
        try:
            if not self.driver:
                self.restart_browser()

            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            position_value = self.find_position_label_no()
            
            # 根据position_value的值决定点击哪个按钮
            
            if position_value:
                # 如果第二行是No，点击第一行YES 的 SELL的按钮
                try:
                    button = self.driver.find_element(By.XPATH, XPathConfig.POSITION_SELL_YES_BUTTON[0])
                except NoSuchElementException:
                    button = self._find_element_with_retry(
                        XPathConfig.POSITION_SELL_YES_BUTTON,
                        timeout=3,
                        silent=True
                    )
            else:
                # 如果第二行不存在或不是No，使用默认的第一行按钮
                try:
                    button = self.driver.find_element(By.XPATH, XPathConfig.POSITION_SELL_BUTTON[0])
                except NoSuchElementException:
                    button = self._find_element_with_retry(
                        XPathConfig.POSITION_SELL_BUTTON,
                        timeout=3,
                        silent=True
                    )
            # 执行点击
            self.driver.execute_script("arguments[0].click();", button)  
        except Exception as e:
            error_msg = f"点击 Positions-Sell-Yes 按钮失败: {str(e)}"
            self.logger.error(error_msg)        

    def click_sell_confirm_button(self):
        """点击sell-卖出按钮"""
        try:
            if not self.driver:
                self.restart_browser()
            # 点击Sell-卖出按钮
            try:
                sell_confirm_button = self.driver.find_element(By.XPATH, XPathConfig.SELL_CONFIRM_BUTTON[0])
            except NoSuchElementException:
                sell_confirm_button = self._find_element_with_retry(
                    XPathConfig.SELL_CONFIRM_BUTTON,
                    timeout=3,
                    silent=True
                )
            sell_confirm_button.click()
            
        except Exception as e:
            error_msg = f"卖出操作失败: {str(e)}"
            self.logger.error(error_msg)

    def click_buy(self):
        try:
            if not self.driver:
                self.restart_browser()
            try:
                button = self.driver.find_element(By.XPATH, XPathConfig.BUY_BUTTON[0])
            except NoSuchElementException:
                button = self._find_element_with_retry(
                    XPathConfig.BUY_BUTTON,
                    timeout=3,
                    silent=True
                )
            button.click()
            
        except Exception as e:
            self.logger.error(f"点击 Buy 按钮失败: {str(e)}")

    def click_buy_yes(self):
        """点击 Buy-Yes 按钮"""
        try:
            if not self.driver:
                self.restart_browser()
            
            try:
                button = self.driver.find_element(By.XPATH, XPathConfig.BUY_YES_BUTTON[0])
            except NoSuchElementException:
                button = self._find_element_with_retry(
                    XPathConfig.BUY_YES_BUTTON,
                    timeout=3,
                    silent=True
                )
            button.click()
            
        except Exception as e:
            self.logger.error(f"点击 Buy-Yes 按钮失败: {str(e)}")

    def click_buy_no(self):
        """点击 Buy-No 按钮"""
        try:
            if not self.driver:
                self.restart_browser()
            try:
                button = self.driver.find_element(By.XPATH, XPathConfig.BUY_NO_BUTTON[0])
            except NoSuchElementException:
                button = self._find_element_with_retry(
                    XPathConfig.BUY_NO_BUTTON,
                    timeout=3,
                    silent=True
                )
            button.click()
            
        except Exception as e:
            self.logger.error(f"点击 Buy-No 按钮失败: {str(e)}")

    def click_amount(self, event=None):
        """点击 Amount 按钮并输入数量"""
        try:
            if not self.driver:
                self.restart_browser()
            
            # 获取触发事件的按钮
            button = event.widget if event else self.amount_button
            button_text = button.cget("text")
            # 找到输入框
            try:
                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
            except NoSuchElementException:
                amount_input = self._find_element_with_retry(
                    XPathConfig.AMOUNT_INPUT,
                    timeout=3,
                    silent=True
                )

            # 清空输入框
            amount_input.clear()
            # 根据按钮文本获取对应的金额
            if button_text == "Amount-Y1":
                amount = self.yes1_amount_entry.get()
            elif button_text == "Amount-Y2":
                yes2_amount_entry = self.yes_frame.grid_slaves(row=3, column=1)[0]
                amount = yes2_amount_entry.get()
            elif button_text == "Amount-Y3":
                yes3_amount_entry = self.yes_frame.grid_slaves(row=5, column=1)[0]
                amount = yes3_amount_entry.get()
            elif button_text == "Amount-Y4":
                yes4_amount_entry = self.yes_frame.grid_slaves(row=7, column=1)[0]
                amount = yes4_amount_entry.get()
            
            # No 按钮
            elif button_text == "Amount-N1":
                no1_amount_entry = self.no_frame.grid_slaves(row=1, column=1)[0]
                amount = no1_amount_entry.get()
            elif button_text == "Amount-N2":

                no2_amount_entry = self.no_frame.grid_slaves(row=3, column=1)[0]
                amount = no2_amount_entry.get()
            elif button_text == "Amount-N3":
                no3_amount_entry = self.no_frame.grid_slaves(row=5, column=1)[0]
                amount = no3_amount_entry.get()
            elif button_text == "Amount-N4":
                no4_amount_entry = self.no_frame.grid_slaves(row=7, column=1)[0]
                amount = no4_amount_entry.get()
            else:
                amount = "0"
            # 输入金额
            amount_input.send_keys(str(amount))
              
        except Exception as e:
            self.logger.error(f"Amount操作失败: {str(e)}")
    """以下代码是交易过程中的功能性函数,买卖及确认买卖成功,从第 2529 行到第 2703 行"""
    def Verify_buy_yes(self):
        """
        验证交易是否成功完成Returns:bool: 交易是否成功
        """
        max_retries = 3
        retry_delay = 2
        time.sleep(2)
        for attempt in range(max_retries):
            try:
                # 首先验证浏览器状态
                if not self.driver:
                    self.restart_browser()
                
                if self.find_login_button():
                    self.check_and_handle_login()

                try:
                    yes_element = self.driver.find_element(By.XPATH, XPathConfig.HISTORY[0])
                except NoSuchElementException:
                    yes_element = self._find_element_with_retry(
                        XPathConfig.HISTORY,
                        timeout=3,
                        silent=True
                    )
                text = yes_element.text
                trade_type = re.search(r'\b(Bought)\b', text)  # 匹配单词 Bought
                yes_match = re.search(r'\b(Up)\b', text)  # 匹配单词 Up
                amount_match = re.search(r'\$(\d+\.?\d*)', text)  # 匹配 $数字 格式
                price_match = re.search(r'(\d+)¢', text)  # 匹配 数字¢ 格式

                if trade_type.group(1) == "Bought" and yes_match.group(1) == "Up":
                    self.trade_type = trade_type.group(1)  # 获取 "Bought"
                    self.buy_yes_value = yes_match.group(1)  # 获取 "Up"
                    self.buy_yes_amount = float(amount_match.group(1))  # 获取数字部分并转为浮点数
                    self.buy_up_price = float(price_match.group(1))# 获取数字部分并转为浮点数
                    self.logger.info(f"交易验证成功: {self.trade_type}-{self.buy_yes_value}-${self.buy_yes_amount}")
                    return True, self.buy_yes_amount 
                return False       
            except Exception as e:
                self.logger.warning(f"Verify_buy_yes执行失败: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                
                return False
            finally:
                self.driver.refresh()
        
    def Verify_buy_no(self):
        """
        验证交易是否成功完成
        Returns:
        bool: 交易是否成功
        """
        max_retries = 3
        retry_delay = 2
        time.sleep(2)
        for attempt in range(max_retries):
            try:
                # 首先验证浏览器状态
                if not self.driver:
                    self.restart_browser()
                if self.find_login_button():
                    self.check_and_handle_login()
                # 等待并检查是否存在 No 标签
                try:
                    no_element = self.driver.find_element(By.XPATH, XPathConfig.HISTORY[0])
                except NoSuchElementException:
                    no_element = self._find_element_with_retry(
                        XPathConfig.HISTORY,
                        timeout=3,
                        silent=True
                    )
                text = no_element.text

                trade_type = re.search(r'\b(Bought)\b', text)  # 匹配单词 Bought
                no_match = re.search(r'\b(Down)\b', text)  # 匹配单词 Down
                amount_match = re.search(r'\$(\d+\.?\d*)', text)  # 匹配 $数字 格式
                price_match = re.search(r'(\d+)¢', text)  # 匹配 数字¢ 格式

                if trade_type.group(1) == "Bought" and no_match.group(1) == "Down":
                    self.trade_type = trade_type.group(1)  # 获取 "Bought"
                    self.buy_no_value = no_match.group(1)  # 获取 "Down"
                    self.buy_no_amount = float(amount_match.group(1))  # 获取数字部分并转为浮点数
                    self.buy_down_price = float(price_match.group(1)) # 获取数字部分并转为浮点数
                    self.logger.info(f"交易验证成功: {self.trade_type}-{self.buy_no_value}-${self.buy_no_amount}")
                    return True, self.buy_no_amount
                return False        
            except Exception as e:
                self.logger.warning(f"Verify_buy_no执行失败: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                return False
            finally:
                self.driver.refresh()
    
    def Verify_sold_yes(self):
        """
        验证交易是否成功完成Returns:bool: 交易是否成功
        """
        max_retries = 2
        retry_delay = 1
        time.sleep(2)
        for attempt in range(max_retries):
            try:
                # 首先验证浏览器状态
                if not self.driver:
                    self.restart_browser()  
                if self.find_login_button():
                    self.check_and_handle_login()          # 等待并检查是否存在 Yes 交易记录
                try:
                    yes_element = self.driver.find_element(By.XPATH, XPathConfig.HISTORY[0])
                except NoSuchElementException:
                    yes_element = self._find_element_with_retry(
                        XPathConfig.HISTORY,
                        timeout=3,
                        silent=True
                    )
                text = yes_element.text
                trade_type = re.search(r'\b(Sold)\b', text)  # 匹配单词 Sold
                yes_match = re.search(r'\b(Up)\b', text)  # 匹配单词 Up
                amount_match = re.search(r'\$(\d+\.?\d*)', text)  # 匹配 $数字 格式
                price_match = re.search(r'(\d+)¢', text)  # 匹配 数字¢ 格式

                if trade_type.group(1) == "Sold" and yes_match.group(1) == "Up":
                    self.trade_type = trade_type.group(1)  # 获取 "Sold"
                    self.buy_yes_value = yes_match.group(1)  # 获取 "Up"
                    self.sell_yes_amount = float(amount_match.group(1))  # 获取数字部分并转为浮点数
                    self.sell_up_price = float(price_match.group(1)) # 获取数字部分并转为浮点数
                    self.logger.info(f"交易验证成功: {self.trade_type}-{self.buy_yes_value}-${self.sell_yes_amount}")
                    return True, self.sell_yes_amount
                return False       
            except Exception as e:
                self.logger.warning(f"Verify_sold_yes执行失败: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    
                return False
            finally:
                self.driver.refresh()
        
    def Verify_sold_no(self):
        """
        验证交易是否成功完成
        Returns:
        bool: 交易是否成功
        """
        max_retries = 2
        retry_delay = 1
        time.sleep(2)
        for attempt in range(max_retries):
            try:
                # 首先验证浏览器状态
                if not self.driver:
                    self.restart_browser()
                if self.find_login_button():
                    self.check_and_handle_login() 
                try:
                    no_element = self.driver.find_element(By.XPATH, XPathConfig.HISTORY[0])
                except NoSuchElementException:
                    no_element = self._find_element_with_retry(
                        XPathConfig.HISTORY,
                        timeout=3,
                        silent=True
                    )
                text = no_element.text

                trade_type = re.search(r'\b(Sold)\b', text)  # 匹配单词 Sold
                no_match = re.search(r'\b(Down)\b', text)  # 匹配单词 Down
                amount_match = re.search(r'\$(\d+\.?\d*)', text)  # 匹配 $数字 格式
                price_match = re.search(r'(\d+)¢', text)  # 匹配 数字¢ 格式

                if trade_type.group(1) == "Sold" and no_match.group(1) == "Down":
                    self.trade_type = trade_type.group(1)  # 获取 "Sold"
                    self.buy_no_value = no_match.group(1)  # 获取 "Down"
                    self.sell_no_amount = float(amount_match.group(1))  # 获取数字部分并转为浮点数
                    self.sell_down_price = float(price_match.group(1)) # 获取数字部分并转为浮点数
                    self.logger.info(f"交易验证成功: {self.trade_type}-{self.buy_no_value}-${self.sell_no_amount}")
                    return True, self.sell_no_amount
                return False        
            except Exception as e:
                self.logger.info(f"Verify_sold_no执行失败: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                return False
            finally:
                self.driver.refresh()

    def position_yes_cash(self):
        """获取当前持仓YES的金额"""
        try:
            yes_element = self.driver.find_element(By.XPATH, XPathConfig.HISTORY[0])
        except NoSuchElementException:
            yes_element = self._find_element_with_retry(
                XPathConfig.HISTORY,
                timeout=3,
                silent=True
            )
        text = yes_element.text
        amount_match = re.search(r'\$(\d+\.?\d*)', text)  # 匹配 $数字 格式
        yes_value = float(amount_match.group(1))
        self.logger.info(f"当前持仓YES的金额: {yes_value}")
        return yes_value
    
    def position_no_cash(self):
        """获取当前持仓NO的金额"""
        try:
            no_element = self.driver.find_element(By.XPATH, XPathConfig.HISTORY[0])
        except NoSuchElementException:
            no_element = self._find_element_with_retry(
                XPathConfig.HISTORY,
                timeout=3,
                silent=True
            )
        text = no_element.text
        amount_match = re.search(r'\$(\d+\.?\d*)', text)  # 匹配 $数字 格式
        no_value = float(amount_match.group(1))
        self.logger.info(f"当前持仓NO的金额: {no_value}")
        return no_value

    def auto_start_monitor(self):
        """自动点击开始监控按钮"""
        try:
            self.logger.info("准备阶段：重置按钮状态")
            # 强制启用开始按钮
            self.start_button['state'] = 'normal'
            # 清除可能存在的锁定状态
            self.running = False

            # 强制点击按钮（即使状态为disabled）
            self.start_button.invoke()
            time.sleep(5)
            self.close_windows()
               
        except Exception as e:
            self.logger.error(f"自动点击失败: {str(e)}")
            self.root.after(10000, self.auto_start_monitor)
    def close_windows(self):
        """关闭多余窗口"""
        # 检查并关闭多余的窗口，只保留一个
        all_handles = self.driver.window_handles
        
        if len(all_handles) > 1:
            self.logger.info(f"当前窗口数: {len(all_handles)}，准备关闭多余窗口")
            # 保留最后一个窗口，关闭其他所有窗口
            current_handle = all_handles[-1]  # 使用最后一个窗口
            
            # 关闭除了最后一个窗口外的所有窗口
            for handle in all_handles[:-1]:
                self.driver.switch_to.window(handle)
                self.driver.close()
            
            # 切换到保留的窗口
            self.driver.switch_to.window(current_handle)
            
        else:
            self.logger.warning("❗ 当前窗口数不足2个,无需切换")

    def set_default_price(self, price):
        """设置默认目标价格"""
        try:
            self.default_target_price = float(price)
            self.yes1_price_entry.delete(0, tk.END)
            self.yes1_price_entry.insert(0, str(self.default_target_price))
            self.no1_price_entry.delete(0, tk.END)
            self.no1_price_entry.insert(0, str(self.default_target_price))
            self.logger.info(f"默认目标价格已更新为: {price}")
        except ValueError:
            self.logger.error("价格设置无效，请输入有效数字")

    def send_trade_email(self, trade_type, price, amount, trade_count,
                         cash_value, portfolio_value):
        """发送交易邮件"""
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                hostname = socket.gethostname()
                sender = 'huacaihuijin@126.com'
                receiver = 'huacaihuijin@126.com'
                app_password = 'YUwsXZ8SYSW6RcTf'  # 有效期 180 天，请及时更新，下次到期日 2025-06-29
                
                # 获取交易币对信息
                full_pair = self.trading_pair_label.cget("text")
                trading_pair = full_pair.split('-')[0]
                if not trading_pair or trading_pair == "--":
                    trading_pair = "未知交易币对"
                
                # 根据交易类型选择显示的计数
                count_in_subject = self.sell_count if "Sell" in trade_type else trade_count
                
                msg = MIMEMultipart()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                subject = f'{hostname}重启{self.reset_trade_count}次第{count_in_subject}次{trade_type}-{trading_pair}'
                msg['Subject'] = Header(subject, 'utf-8')
                msg['From'] = sender
                msg['To'] = receiver

                # 修复格式化字符串问题，确保cash_value和portfolio_value是字符串
                str_cash_value = str(cash_value)
                str_portfolio_value = str(portfolio_value)
                
                content = f"""
                交易价格: {price:.2f}¢
                交易金额: ${amount:.2f}
                当前买入次数: {self.trade_count}
                当前卖出次数: {self.sell_count}
                当前 CASH 值: {str_cash_value}
                当前 PORTFOLIO 值: {str_portfolio_value}
                交易时间: {current_time}
                """
                msg.attach(MIMEText(content, 'plain', 'utf-8'))
                
                # 使用126.com的SMTP服务器
                server = smtplib.SMTP_SSL('smtp.126.com', 465, timeout=5)  # 使用SSL连接
                server.set_debuglevel(0)
                
                try:
                    server.login(sender, app_password)
                    server.sendmail(sender, receiver, msg.as_string())
                    self.logger.info(f"邮件发送成功: {trade_type}")
                    return  # 发送成功,退出重试循环
                except Exception as e:
                    self.logger.error(f"SMTP操作失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                finally:
                    try:
                        server.quit()
                    except Exception:
                        pass          
            except Exception as e:
                self.logger.error(f"邮件准备失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)     
        # 所有重试都失败
        error_msg = f"发送邮件失败,已重试{max_retries}次"
        self.logger.error(error_msg)

    def stop_monitoring(self):
        """停止监控"""
        try:
            self.running = False
            self.stop_event.set()  # 设置停止事件
            # 取消所有定时器
            for timer in [self.url_check_timer, self.login_check_timer, self.refresh_timer]:
                if timer:
                    self.root.after_cancel(timer)
            # 停止URL监控
            if self.url_check_timer:
                self.root.after_cancel(self.url_check_timer)
                self.url_check_timer = None
            # 停止登录状态监控
            if self.login_check_timer:
                self.root.after_cancel(self.login_check_timer)
                self.login_check_timer = None
            
            self.start_button['state'] = 'normal'
            
            self.set_amount_button['state'] = 'disabled'  # 禁用更新金额按钮
            
            # 恢复"开始监控"文字为蓝色
            self.start_button.configure(style='Black.TButton')
            if self.driver:
                self.driver.quit()
                self.driver = None
            # 记录最终交易次数
            final_trade_count = self.trade_count
            self.logger.info(f"本次监控共执行 {final_trade_count} 次交易")

            # 取消页面刷新定时器
            if self.refresh_timer:
                self.root.after_cancel(self.refresh_timer)
                self.refresh_timer = None

            if hasattr(self, 'monitor_prices_timer'):
                self.root.after_cancel(self.monitor_prices_timer)  # 取消定时器
                self.monitor_prices_timer = None

        except Exception as e:
            self.logger.error(f"停止监控失败: {str(e)}")

    def retry_operation(self, operation, *args, **kwargs):
        """通用重试机制"""
        for attempt in range(self.retry_count):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"{operation.__name__} 失败，尝试 {attempt + 1}/{self.retry_count}: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_interval)
                else:
                    raise

    """以下代码是自动找币功能,从第 2981 行到第 35320 行"""
    # 自动找币第一步:判断是否持仓,是否到了找币时间
    def find_position_label_yes(self):
        """查找Yes持仓标签"""
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not self.driver:
                    self.restart_browser()
                    
                # 等待页面加载完成
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # 尝试获取Up标签
                try:
                    position_label_up = None
                    position_label_up = self.driver.find_element(By.XPATH, XPathConfig.POSITION_UP_LABEL[0])
                    if position_label_up is not None and position_label_up:
                        self.logger.info(f"找到了Up持仓标签: {position_label_up.text}")
                        return True
                    else:
                        self.logger.info("USE FIND-element,未找到Up持仓标签")
                        return False
                except NoSuchElementException:
                    position_label_up = self._find_element_with_retry(XPathConfig.POSITION_UP_LABEL, timeout=3, silent=True)
                    if position_label_up is not None and position_label_up:
                        self.logger.info(f"找到了Up持仓标签: {position_label_up.text}")
                        return True
                    else:
                        self.logger.info("use with-retry,未找到Up持仓标签")
                        return False
                         
            except TimeoutException:
                self.logger.debug(f"第{attempt + 1}次尝试未找到UP标签,正常情况!")
            
            if attempt < max_retries - 1:
                self.logger.info(f"等待{retry_delay}秒后重试...")
                time.sleep(retry_delay)
                self.driver.refresh()
        return False
        
    def find_position_label_no(self):
        """查找Down持仓标签"""
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not self.driver:
                    self.restart_browser()
                    
                # 等待页面加载完成
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # 尝试获取Down标签
                try:
                    position_label_down = None
                    position_label_down = self.driver.find_element(By.XPATH, XPathConfig.POSITION_DOWN_LABEL[0])
                    if position_label_down is not None and position_label_down:
                        self.logger.info(f"use find-element,找到了Down持仓标签: {position_label_down.text}")
                        return True
                    else:
                        self.logger.info("use find-element,未找到Down持仓标签")
                        return False
                except NoSuchElementException:
                    position_label_down = self._find_element_with_retry(XPathConfig.POSITION_DOWN_LABEL, timeout=3, silent=True)
                    if position_label_down is not None and position_label_down:
                        self.logger.info(f"use with-retry,找到了Down持仓标签: {position_label_down.text}")
                        return True
                    else:
                        self.logger.info("use with-retry,未找到Down持仓标签")
                        return False
                               
            except TimeoutException:
                self.logger.warning(f"第{attempt + 1}次尝试未找到Down标签")
                
            if attempt < max_retries - 1:
                self.logger.info(f"等待{retry_delay}秒后重试...")
                time.sleep(retry_delay)
                self.driver.refresh()
        return False
      
    def _find_element_with_retry(self, xpaths, timeout=3, silent=False):
        """优化版XPATH元素查找(增强空值处理)"""
        try:
            for i, xpath in enumerate(xpaths, 1):
                try:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    return element
                except TimeoutException:
                    if not silent:
                        self.logger.warning(f"第{i}个XPATH定位超时: {xpath}")
                    continue
        except Exception as e:
            if not silent:
                raise
        return None
    
    def switch_to_frame_containing_element(self, xpath, timeout=10):
        """
        自动切换到包含指定xpath元素的iframe。
        - xpath: 你要找的元素的xpath,比如 '(//span[@class="c-ggujGL"])[2]'
        """
        self.driver.switch_to.default_content()  # 先回到主文档
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")  # 找到所有 iframe

        for i, frame in enumerate(frames):
            self.driver.switch_to.frame(frame)
            try:
                WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
                self.logger.info(f"成功切换到第 {i} 个 iframe")
                return True
            except:
                self.driver.switch_to.default_content()  # 如果没找到，切回主文档，继续下一个
                continue

        self.logger.info("没有找到包含元素的 iframe")
        return False

    def monitor_xpath_elements(self):
        """使用当前浏览器实例监控 XPath 元素"""
        if not self.driver:
            self.logger.warning("浏览器未启动，无法监控 XPath")
            return
            
        try:
            # 获取 XPathConfig 中的所有属性
            xpath_config = XPathConfig()
            # 定义要排除的 XPath 属性
            excluded_attrs = ['ACCEPT_BUTTON', 'LOGIN_BUTTON', 'LOGIN_WITH_GOOGLE_BUTTON','HISTORY',
                              'POSITION_SELL_BUTTON', 'POSITION_SELL_YES_BUTTON', 'POSITION_SELL_NO_BUTTON',
                              'POSITION_UP_LABEL', 'POSITION_DOWN_LABEL', 'POSITION_YES_VALUE', 'POSITION_NO_VALUE',
                              'SEARCH_CONFIRM_BUTTON','SEARCH_INPUT','SPREAD'
                              ]
            # 获取所有 XPath 属性，排除指定的属性
            xpath_attrs = [attr for attr in dir(xpath_config) 
                        if not attr.startswith('__') 
                        and isinstance(getattr(xpath_config, attr), list)
                        and attr not in excluded_attrs]
            failed_xpaths = []
            
            # 只检查每个 XPath 列表的第一个元素
            for attr in xpath_attrs:
                xpath_list = getattr(xpath_config, attr)
                if xpath_list:  # 确保列表不为空
                    first_xpath = xpath_list[0]  # 只获取第一个 XPath
                    try:
                        # 尝试定位元素，设置超时时间为 5 秒
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, first_xpath))
                        )
                    except (TimeoutException, NoSuchElementException):
                        self.logger.warning(f"❌ {attr} 定位失败: {first_xpath}")
                        failed_xpaths.append((attr, first_xpath))
            
            # 如果有失败的 XPath，发送邮件
            if failed_xpaths:
                subject = f"⚠️ XPath 监控警告: {len(failed_xpaths)} 个 XPath 定位失败"
                body = "以下 XPath 无法正常定位到元素:\n\n"
                
                for name, xpath in failed_xpaths:
                    body += f"{name}: {xpath}\n"
                
                body += "\n请尽快检查并更新 xpath_config.py 文件。"
                
                # 使用 send_trade_email 方法发送邮件
                self.send_trade_email(
                                trade_type="XPATH检查",
                                price=0,
                                amount=0,
                                trade_count=0,
                                cash_value=subject,
                                portfolio_value=body
                            )
                
                self.logger.warning(f"发现 {len(failed_xpaths)} 个 XPath 定位失败，已发送邮件通知")
            else:
                self.logger.info("所有 XPath 定位正常")
        
        except Exception as e:
            self.logger.error(f"监控 XPath 元素时发生错误: {str(e)}")
        finally:
            # 每隔 30 分钟检查一次,先关闭之前的定时器
            self.root.after_cancel(self.monitor_xpath_timer)
            self.root.after(1800000, self.monitor_xpath_elements)

    def schedule_auto_find_coin(self):
        """安排每天1点2分执行自动找币"""
        now = datetime.now()
        # 计算下一个3点2分的时间
        next_run = now.replace(hour=0, minute=5, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        
        # 计算等待时间(毫秒)
        wait_time = (next_run - now).total_seconds() * 1000
        wait_time_hours = wait_time / 3600000
        
        # 设置定时器
        selected_coin = self.coin_combobox.get()
        self.root.after(int(wait_time), lambda: self.find_54_coin(selected_coin))
        self.logger.info(f"{round(wait_time_hours,2)} 小时后,开始自动找币")

    def find_54_coin(self,coin_type):
        """自动找币"""
        self.logger.info("✅ 开始自动找币")
        try:
            self.stop_url_monitoring()
            self.stop_refresh_page()
            # 保存原始窗口句柄，确保在整个过程中有一个稳定的引用
            self.original_window = self.driver.current_window_handle
            
            # 设置搜索关键词
            coins = [coin_type]
            for coin in coins:
                try:  # 为每个币种添加单独的异常处理
                    
                    coin_new_weekly_url = self.find_new_weekly_url(coin)
                    
                    if coin_new_weekly_url:
                        self.driver.get(coin_new_weekly_url)
                        # 保存当前 URL 到 config
                        self.config['website']['url'] = coin_new_weekly_url
                        self.save_config()
                        
                        # 清除url_entry中的url
                        self.url_entry.delete(0, tk.END)
                        # 把保存到config的url放到self.url_entry中
                        self.url_entry.insert(0, coin_new_weekly_url)

                        self.target_url = self.url_entry.get()
                        new_url = self.url_entry.get()
                        pair = re.search(r'event/([^?]+)', new_url)
                        self.trading_pair_label.config(text=pair.group(1))
                        self.logger.info(f"\033[34m✅ {self.target_url} 已插入到主界面上\033[0m")
                        self.start_url_monitoring()
                        self.refresh_page()
                        self.schedule_auto_find_coin()
                        return     
                except Exception as e:
                    self.logger.error(f"处理{coin}时出错: {str(e)}")

            self.root.after(5000, self.start_url_monitoring)
        except Exception as e:
            self.logger.error(f"自动找币异常: {str(e)}")

    def find_new_weekly_url(self, coin):
        """在Polymarket市场搜索指定币种的周合约地址,只返回周合约地址"""
        try:
            if self.trading:
                return

            # 保存当前窗口句柄作为局部变量，用于本方法内部使用
            original_tab = self.driver.current_window_handle
            
            base_url = "https://polymarket.com/markets/crypto?_s=start_date%3Adesc"
            self.driver.switch_to.new_window('tab')
            self.driver.get(base_url)

            # 定义search_tab变量，保存搜索标签页的句柄
            search_tab = self.driver.current_window_handle

            # 等待页面加载完成
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)  # 等待页面渲染完成
            
            # 设置搜索关键词
            if coin == 'BTC':
                search_text = 'Bitcoin Up or Down on'
            elif coin == 'ETH':
                search_text = 'Ethereum Up or Down on'
            elif coin == 'SOL':
                search_text = 'Solana Up or Down on'   
            
            try:
                # 使用确定的XPath查找搜索框
                try:
                    search_box = self.driver.find_element(By.XPATH, XPathConfig.SEARCH_INPUT[0])
                except NoSuchElementException:
                    search_box = self._find_element_with_retry(
                        XPathConfig.SEARCH_INPUT,
                        timeout=3,
                        silent=True
                    )
                
                # 创建ActionChains对象
                actions = ActionChains(self.driver)
                
                # 清除搜索框并输入搜索词
                search_box.clear()
                search_box.send_keys(search_text)
                time.sleep(0.5)
                # 把搜索词保存到self.search_text
                self.search_text = search_text
                # 按ENTER键开始搜索
                actions.send_keys(Keys.RETURN).perform()
                time.sleep(2)  # 等待搜索结果加载
                
                self.click_today_card()
                
                # 切换到新标签页获取完整URL
                time.sleep(2)  
        
                # 获取所有窗口句柄
                all_handles = self.driver.window_handles
                
                # 切换到最新打开的标签页
                if len(all_handles) > 2:  # 原始窗口 + 搜索标签页 + coin标签页
                    
                    self.driver.switch_to.window(all_handles[-1])
                    WebDriverWait(self.driver, 20).until(EC.url_contains('/event/'))
                    
                    # 获取当前URL
                    new_weekly_url = self.driver.current_url
                    time.sleep(5)

                    # 这里如果价格是 52,那么会触发自动交易
                    if self.trading == True:
                        time.sleep(50)
                        # 保存当前 URL 到 config
                        self.config['website']['url'] = new_weekly_url
                        self.save_config()
                        self.logger.info(f"✅ {coin}:符合要求, 正在交易,已保存到 config")
                        
                        # 把保存到config的url放到self.url_entry中
                        # 保存前,先清楚现有的url
                        self.url_entry.delete(0, tk.END)
                        self.url_entry.insert(0, new_weekly_url)
                        self.target_url = self.url_entry.get()
                        new_url = self.url_entry.get()
                        pair = re.search(r'event/([^?]+)', new_url)
                        self.trading_pair_label.config(text=pair.group(1))
                        self.logger.info(f"✅ {self.target_url}:已插入到主界面上")

                        self.target_url_window = self.driver.current_window_handle
                        time.sleep(2)

                        # 关闭原始和搜索窗口
                        self.driver.switch_to.window(search_tab)
                        self.driver.close()
                        self.driver.switch_to.window(original_tab)
                        self.driver.close()
                        self.driver.switch_to.window(self.target_url_window)

                        self.start_url_monitoring()
                        self.refresh_page()

                        return False
                    else:
                        # 关闭当前详情URL标签页
                        self.driver.close()
                        
                        # 切换回搜索标签页
                        self.driver.switch_to.window(search_tab)
                        
                        # 关闭搜索标签页
                        self.driver.close()
                        
                        # 切换回原始窗口
                        self.driver.switch_to.window(original_tab)
                        
                        return new_weekly_url
                else:
                    self.logger.warning(f"未能打开{coin}的详情页")
                    # 关闭搜索标签页
                    self.driver.close()
                    # 切换回原始窗口
                    self.driver.switch_to.window(original_tab)
                    return None
                
            except NoSuchElementException as e:
                self.logger.warning(f"未找到{coin}周合约链接: {str(e)}")
                # 关闭搜索标签页
                self.driver.close()
                # 切换回原始窗口
                self.driver.switch_to.window(original_tab)
                return None
            
        except Exception as e:
            self.logger.error(f"操作失败: {str(e)}")

    def click_today_card(self):
        """使用Command/Ctrl+Click点击包含今天日期的卡片,打开新标签页"""
        try:
            # 获取当前日期字符串，比如 "April 18"
            today_str = datetime.now().strftime("%B %-d")  # macOS/Linux
            
            self.logger.info(f"🔍 查找包含日期 [{today_str}] 的链接...")

            # 获取所有含 "Bitcoin Up or Down on" 的卡片元素
            try:
                cards = self.driver.find_elements(By.XPATH, XPathConfig.SEARCH_CONFIRM_BUTTON[0])
            except NoSuchElementException:
                cards = self._find_element_with_retry(
                    XPathConfig.SEARCH_CONFIRM_BUTTON,
                    timeout=3,
                    silent=True
                )

            for card in cards:
                expected_text = self.search_text + " " + today_str + "?"
                if card.text.strip() == expected_text:
                    self.logger.info(f"\033[34m✅ 找到包含日期的卡片: {card.text.strip()}\033[0m")

                    # Command 键（macOS）或 Control 键（Windows/Linux）
                    modifier_key = Keys.COMMAND if sys.platform == 'darwin' else Keys.CONTROL

                    # 使用 ActionChains 执行 Command/Ctrl + Click
                    actions = ActionChains(self.driver)
                    actions.key_down(modifier_key).click(card).key_up(modifier_key).perform()

                    self.logger.info("\033[34m🆕 成功用快捷键打开新标签页！\033[0m")
                    return True

            self.logger.warning("\033[31m❌ 没有找到包含今天日期的卡片\033[0m")
            return False

        except Exception as e:
            self.logger.error(f"查找并点击今天日期卡片失败: {str(e)}")
            self.click_today_card()

    def get_binance_price(self):
        """获取币安BTC实时价格,并在中国时区00:00触发"""
        self.logger.info(f"✅ 获取币安 \033[34m{self.coin_combobox.get()}USDT\033[0m 价格")
        try:
            # 获取当前币安BTC价格
            selected_coin = self.coin_combobox.get()
            coin = selected_coin + 'USDT'
            response = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={coin}')
            if response.status_code == 200:
                data = response.json()
                price = round(float(data['price']),2)
                self.last_coin_price = price
                self.logger.info(f"✅ 币安 {coin} 价格: \033[34m{price}\033[0m")
                self.binance_zero_price_label.config(text=f"${price}")
                return price
            else:
                self.logger.error(f"❌ 获取币安价格失败: HTTP {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ 获取币安价格异常: {str(e)}")
        finally:
            # 计算下一个00:00的时间
            now = datetime.now()
            tomorrow = now.replace(hour=0, minute=0, second=5, microsecond=0) + timedelta(days=1)
            seconds_until_midnight = (tomorrow - now).total_seconds()
            # 取消已有的定时器（如果存在）
            if hasattr(self, 'binance_price_timer') and self.binance_price_timer:
                self.binance_price_timer.cancel()
            # 设置下一次执行的定时器
            if self.running and not self.stop_event.is_set():
                self.binance_price_timer = threading.Timer(seconds_until_midnight, self.get_binance_price)
                self.binance_price_timer.daemon = True
                self.binance_price_timer.start()
                self.logger.info(f"{round(seconds_until_midnight / 3600,2)}小时后再次获取价格")
    
    def get_now_price(self):
        """获取当前价格"""
        # 获取当前币安价格
        try:
            selected_coin = self.coin_combobox.get()
            coin = selected_coin + 'USDT'
            response = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={coin}')
            if response.status_code == 200:
                data = response.json()
                price = round(float(data['price']),2)
                self.binance_now_price_label.config(text=f"${price}")
                #self.logger.info(f"币安 {coin} 价格: \033[34m{price}\033[0m")
        except Exception as e:
            self.logger.info(f"❌ 获取币安价格异常: {str(e)}")
        finally:
            # 取消已有的定时器（如果存在）
            if hasattr(self, 'get_now_price_timer') and self.get_now_price_timer:
                self.get_now_price_timer.cancel()
            # 设置下一次执行的定时器
            if self.running and not self.stop_event.is_set():
                self.get_now_price_timer = threading.Timer(5, self.get_now_price)
                self.get_now_price_timer.daemon = True
                self.get_now_price_timer.start()

if __name__ == "__main__":
    try:
        # 打印启动参数，用于调试
        
        # 初始化日志
        logger = Logger("main")
            
        # 创建并运行主程序
        app = CryptoTrader()
        app.root.mainloop()
        
    except Exception as e:
        print(f"程序启动失败: {str(e)}")
        if 'logger' in locals():
            logger.error(f"程序启动失败: {str(e)}")
        sys.exit(1)
    
