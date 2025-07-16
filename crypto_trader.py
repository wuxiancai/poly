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
import logging
from datetime import datetime, timedelta
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
import random
import websocket


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
        
        self.get_zero_time_cash_timer = None
        self.get_binance_zero_time_price_timer = None
        self.get_binance_price_websocket_timer = None
        self.comparison_binance_price_timer = None
        self.schedule_auto_find_coin_timer = None
        
        # 添加URL and refresh_page监控锁
        self.url_monitoring_lock = threading.Lock()
        self.refresh_page_lock = threading.Lock()
        self.login_attempt_lock = threading.Lock()
        self.restart_lock = threading.Lock()  # 添加重启锁
        self.is_restarting = False  # 重启状态标志

        # 初始化本金
        self.initial_amount = 2.2
        self.first_rebound = 265
        self.n_rebound = 140
        self.profit_rate = 2
        self.doubling_weeks = 35

        # 默认买价
        self.default_target_price = 57 # 不修改
        # 默认反水卖价
        self.default_sell_price_backwater = 46 # 不修改
        # 默认卖价
        self.default_sell_price = 1 # 不修改

        # 默认卖价
        self.default_normal_sell_price = 99 # 不修改

        # 买入价格冗余
        self.price_premium = 3 # 不修改

        # 买入触发条件之一:最少成交数量SHARES
        self.asks_shares = 1 # 不修改
        self.bids_shares = 1 # 不修改
        
        # 按钮区域按键 WIDTH
        self.button_width = 8 # 不修改

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
                'url_history': [],
                'selected_coin': 'BTC'  # 默认选择的币种
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
            
            # 保存自动找币时间设置
            if hasattr(self, 'auto_find_time_combobox'):
                self.config['auto_find_time'] = self.auto_find_time_combobox.get()
            
            # 保存币种选择设置
            if hasattr(self, 'coin_combobox'):
                self.config['selected_coin'] = self.coin_combobox.get()
            
            # 保存配置到文件，使用indent=4确保格式化
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f)
                
        except Exception as e:
            self.logger.error(f"保存配置失败: {str(e)}")
            raise

    def setup_gui(self):
        """优化后的GUI界面设置"""

        self.root = tk.Tk()
        self.root.title("Polymarket Automatic Trading System Power by @wuxiancai")
        
        # 创建主滚动框架
        main_canvas = tk.Canvas(self.root, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        
        # 创建内容Frame，放在Canvas里
        scrollable_frame = ttk.Frame(main_canvas)
        
        # 让Frame成为Canvas的一个window
        canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # 让scrollable_frame宽度始终和canvas一致
        def _on_canvas_configure(event):
            main_canvas.itemconfig(canvas_window, width=event.width)
        main_canvas.bind('<Configure>', _on_canvas_configure)

        # 让canvas的scrollregion始终覆盖全部内容
        def _on_frame_configure(event):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        scrollable_frame.bind('<Configure>', _on_frame_configure)

        # pack布局，保证canvas和scrollbar都能自适应
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 优化的滚动事件处理
        def _on_mousewheel(event):
            try:
                system = platform.system()
                if system == 'Linux':
                    delta = -1 if event.num == 4 else 1 if event.num == 5 else 0
                elif system == 'Darwin':
                    delta = -int(event.delta)
                else:  # Windows
                    delta = -int(event.delta/120)
                if delta:
                    main_canvas.yview_scroll(delta, "units")
            except Exception as e:
                self.logger.error(f"滚动事件处理错误: {str(e)}")
        
        def _on_arrow_key(event):
            try:
                delta = -1 if event.keysym == 'Up' else 1 if event.keysym == 'Down' else 0
                if delta:
                    main_canvas.yview_scroll(delta, "units")
            except Exception as e:
                self.logger.error(f"键盘滚动事件处理错误: {str(e)}")
        
        # 绑定滚动事件
        if platform.system() == 'Linux':
            main_canvas.bind_all("<Button-4>", _on_mousewheel)
            main_canvas.bind_all("<Button-5>", _on_mousewheel)
        else:
            main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        main_canvas.bind_all("<Up>", _on_arrow_key)
        main_canvas.bind_all("<Down>", _on_arrow_key)
        
        # 创建统一的样式配置
        style = ttk.Style()
        
        # 根据系统设置字体
        if platform.system() == 'Darwin':
            small_font = ('SF Pro Display', 10, 'normal')
            base_font = ('SF Pro Display', 12, 'normal')
            bold_font = ('SF Pro Display', 12, 'bold')
            large_font = ('SF Pro Display', 14, 'normal')
            title_font = ('SF Pro Display', 14, 'bold')
        else:  # Linux and others
            small_font = ('DejaVu Sans', 10, 'normal')
            base_font = ('DejaVu Sans', 11, 'normal')
            bold_font = ('DejaVu Sans', 11, 'bold')
            large_font = ('DejaVu Sans', 13, 'normal')
            title_font = ('DejaVu Sans', 14, 'bold')
        
        # 配置样式
        styles_config = {
            'Red.TButton': {'foreground': '#dc3545', 'font': bold_font},
            'Black.TButton': {'foreground': '#212529', 'font': base_font},
            'Blue.TButton': {'foreground': '#0d6efd', 'font': base_font},
            'Red.TLabel': {'foreground': '#dc3545', 'font': large_font},
            'Black.TLabel': {'foreground': '#212529', 'font': base_font},
            'Top.TLabel': {'foreground': '#212529', 'font': base_font},
            'Warning.TLabelframe': {'font': title_font, 'foreground': '#FF0000', 'anchor': 'center'},
            'LeftAligned.TButton': {'anchor': 'w', 'foreground': '#212529', 'padding': (1, 1)},
            'Black.TLabelframe': {'font': small_font, 'foreground': '#212529', 'anchor': 'center'},
            'Centered.TLabelframe': {'font': base_font, 'foreground': '#212529'}
            
        }
        
        for style_name, config in styles_config.items():
            style.configure(style_name, **config)
        
        # 金额设置框架
        amount_settings_frame = ttk.LabelFrame(scrollable_frame, text="⚠️ 娟娟细流,终入大海! 宁静致远,财富自由!", 
                                             padding=(10, 8), style='Warning.TLabelframe')
        amount_settings_frame.pack(fill="x", padx=8, pady=6)

        # 创建主要设置容器
        settings_container = ttk.Frame(amount_settings_frame)
        settings_container.pack(fill=tk.X, pady=5)
        
        # 金额设置区域
        amount_frame = ttk.Frame(settings_container)
        amount_frame.pack(fill=tk.X, pady=2)

        # 设置金额配置
        settings_items = [
            ("Initial", "initial_amount_entry", self.initial_amount, 3),
            ("Turn-1", "first_rebound_entry", self.first_rebound, 3),
            ("Turn-N", "n_rebound_entry", self.n_rebound, 3),
            ("Margin", "profit_rate_entry", f"{self.profit_rate}%", 4)
        ]
        
        for i, (label_text, entry_attr, default_value, width) in enumerate(settings_items):
            item_frame = ttk.Frame(amount_frame)
            item_frame.pack(side=tk.LEFT, padx=2)
            
            ttk.Label(item_frame, text=label_text, style='Top.TLabel').pack(side=tk.LEFT, padx=(0, 2))
            entry = ttk.Entry(item_frame, width=width, font=base_font)
            entry.pack(side=tk.LEFT)
            entry.insert(0, str(default_value))
            setattr(self, entry_attr, entry)

        # 翻倍天数设置
        double_frame = ttk.Frame(amount_frame)
        double_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(double_frame, text="Double", style='Top.TLabel').pack(side=tk.LEFT, padx=(0, 2))
        self.doubling_weeks_entry = ttk.Entry(double_frame, width=3)
        self.doubling_weeks_entry.pack(side=tk.LEFT)
        self.doubling_weeks_entry.insert(0, str(self.doubling_weeks))
        
        # 监控网站配置
        url_frame = ttk.LabelFrame(scrollable_frame, text="Website Monitoring", padding=(8, 5))
        url_frame.pack(fill="x", padx=8, pady=6)
        
        url_container = ttk.Frame(url_frame)
        url_container.pack(fill="x", pady=2)
        
        ttk.Label(url_container, text="", style='Black.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Combobox(url_container, font=base_font, width=2)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 从配置文件加载历史记录
        if 'url_history' not in self.config:
            self.config['url_history'] = []
        self.url_entry['values'] = self.config['url_history']
        
        # 如果有当前URL，设置为默认值
        current_url = self.config.get('website', {}).get('url', '')
        if current_url:
            self.url_entry.set(current_url)
        
        # 控制按钮区域
        control_frame = ttk.LabelFrame(scrollable_frame, text="Control Panel", padding=(8, 5))
        control_frame.pack(fill="x", padx=8, pady=6)
        
        # 主控制按钮行
        main_controls = ttk.Frame(control_frame)
        main_controls.pack(fill="x", pady=2)
        
        # 开始按钮
        self.start_button = ttk.Button(main_controls, text="Start", 
                                      command=self.start_monitoring, width=4,
                                      style='Blue.TButton')
        self.start_button.pack(side=tk.LEFT, padx=1)
        
        # 设置金额按钮
        self.set_amount_button = ttk.Button(main_controls, text="Set Amount", width=10,
                                           command=self.set_yes_no_cash, style='LeftAligned.TButton')
        self.set_amount_button.pack(side=tk.LEFT, padx=3)
        self.set_amount_button['state'] = 'disabled'

        # 币种选择
        ttk.Label(main_controls, text="Coin:", style='Black.TLabel').pack(side=tk.LEFT, padx=(2, 2))
        self.coin_combobox = ttk.Combobox(main_controls, values=['BTC', 'ETH', 'SOL', 'XRP'], width=3)
        self.coin_combobox.pack(side=tk.LEFT, padx=2)
        
        # 从配置文件加载保存的币种选择
        saved_coin = self.config.get('selected_coin', 'BTC')
        self.coin_combobox.set(saved_coin)
        
        # 绑定币种选择变化事件
        self.coin_combobox.bind('<<ComboboxSelected>>', self.on_coin_changed)
        
        # CASH 显示
        ttk.Label(main_controls, text="Cash:", style='Black.TLabel').pack(side=tk.LEFT, padx=(0, 2))
        self.zero_time_cash_label = ttk.Label(main_controls, text="0", style='Red.TLabel')
        self.zero_time_cash_label.pack(side=tk.LEFT)

         # 重启次数显示
        ttk.Label(main_controls, text="Reset:", style='Black.TLabel').pack(side=tk.LEFT, padx=(10, 2))
        self.reset_count_label = ttk.Label(main_controls, text="0", style='Red.TLabel')
        self.reset_count_label.pack(side=tk.LEFT, padx=(0, 15))
        
        # 自动找币时间选择
        auto_find_frame = ttk.Frame(main_controls)
        auto_find_frame.pack(fill="x", pady=2)
        
        #ttk.Label(auto_find_frame, text="Auto Find Coin Time:", style='Black.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.auto_find_time_combobox = ttk.Combobox(auto_find_frame, values=['1:00', '2:00', '3:00', '4:00'], width=5, state='readonly')
        self.auto_find_time_combobox.pack(side=tk.LEFT, padx=2)
        
        # 从配置文件加载保存的时间设置
        saved_time = self.config.get('auto_find_time', '2:00')
        self.auto_find_time_combobox.set(saved_time)
        
        # 绑定时间选择变化事件
        self.auto_find_time_combobox.bind('<<ComboboxSelected>>', self.on_auto_find_time_changed)

        # 交易币对显示
        pair_container = ttk.Frame(scrollable_frame)
        pair_container.pack(fill="x", pady=2)
        
        ttk.Label(pair_container, text="Trading Pair:", style='Black.TLabel').pack(side=tk.LEFT, padx=(8, 5))
        self.trading_pair_label = ttk.Label(pair_container, text="----", style='Black.TLabel')
        self.trading_pair_label.pack(side=tk.LEFT)

        # 币安价格信息
        binance_price_frame = ttk.LabelFrame(scrollable_frame, text="Binance Price", padding=(8, 5), style='Centered.TLabelframe')
        binance_price_frame.pack(fill="x", padx=8, pady=6)

        binance_container = ttk.Frame(binance_price_frame)
        binance_container.pack(pady=2)
        
        # 币安价格信息网格布局
        price_info_items = [
            ("Midnight:", "binance_zero_price_label", "0"),
            ("Now:", "binance_now_price_label", "0"),
            ("Rate:", "binance_rate_display", "0%")
        ]
        
        for i, (label_text, attr_name, default_value) in enumerate(price_info_items):
            item_frame = ttk.Frame(binance_container)
            item_frame.pack(side=tk.LEFT, padx=5)
            
            ttk.Label(item_frame, text=label_text, style='Black.TLabel').pack(side=tk.LEFT)
            
            if attr_name == "binance_rate_display":
                # 创建涨跌显示容器
                rate_frame = ttk.Frame(item_frame)
                rate_frame.pack(side=tk.LEFT, padx=(2, 0))
                
                self.binance_rate_label = ttk.Label(rate_frame, text="0", style='Black.TLabel')
                self.binance_rate_label.pack(side=tk.LEFT)
                
                self.binance_rate_symbol_label = ttk.Label(rate_frame, text="%", style='Black.TLabel')
                self.binance_rate_symbol_label.pack(side=tk.LEFT)
            else:
                label = ttk.Label(item_frame, text=default_value, font=large_font, foreground='blue')
                label.pack(side=tk.LEFT, padx=(2, 0))
                setattr(self, attr_name, label)
        
        # 实时价格显示区域
        price_frame = ttk.LabelFrame(scrollable_frame, text="Live Prices", padding=(8, 5))
        price_frame.pack(fill="x", padx=8, pady=6)
        
        # 价格显示容器
        prices_container = ttk.Frame(price_frame)
        prices_container.pack(fill="x", pady=2)
        
        # Up/Down 价格和份额显示
        price_items = [
            ("Up:", "yes_price_label", "Up: waiting..."),
            ("Down:", "no_price_label", "Down: waiting...")
        ]
        
        for i, (icon_text, attr_name, default_text) in enumerate(price_items):
            item_container = ttk.Frame(prices_container)
            item_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # 价格显示
            price_frame_item = ttk.Frame(item_container)
            price_frame_item.pack(fill="x", pady=1)
            
            price_label = ttk.Label(price_frame_item, text=default_text, 
                                   font=(base_font[0], 16, 'bold'), foreground='#9370DB')
            price_label.pack()
            setattr(self, attr_name, price_label)
            
            # 份额显示
            shares_frame_item = ttk.Frame(item_container)
            shares_frame_item.pack(fill="x", pady=1)
            
            shares_attr = "up_shares_label" if "yes_price_label" == attr_name else "down_shares_label"
            shares_label = ttk.Label(shares_frame_item, text="Shares: waiting...",
                                   font=(base_font[0], 14, 'normal'), foreground='#9370DB')
            shares_label.pack()
            setattr(self, shares_attr, shares_label)

        # 资金显示区域
        balance_frame = ttk.LabelFrame(scrollable_frame, text="Account Balance", padding=(8, 5))
        balance_frame.pack(fill="x", padx=8, pady=6)
        
        balance_container = ttk.Frame(balance_frame)
        balance_container.pack(fill="x", pady=2)
        
        # Portfolio 和 Cash 显示
        balance_items = [
            ("Portfolio:", "portfolio_label", "Portfolio: waiting..."),
            ("Cash:", "cash_label", "Cash: waiting...")
        ]
        
        for i, (label_text, attr_name, default_text) in enumerate(balance_items):
            item_frame = ttk.Frame(balance_container)
            item_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            
            balance_label = ttk.Label(item_frame, text=default_text, 
                                     font=(base_font[0], 14, 'normal'), foreground='#16A34A')
            balance_label.pack()
            setattr(self, attr_name, balance_label)
        
        # 创建UP 和 DOWN 价格和金额左右分栏
        config_container = ttk.Frame(scrollable_frame)
        config_container.pack(fill="x", pady=2)
        
        # Up 区域配置
        self.yes_frame = ttk.LabelFrame(config_container, text="Up Positions", padding=(5, 3))
        self.yes_frame.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        config_container.grid_columnconfigure(0, weight=1)

        # Down 配置区域
        self.no_frame = ttk.LabelFrame(config_container, text="Down Positions", padding=(5, 3))
        self.no_frame.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        config_container.grid_columnconfigure(1, weight=1)
        
        # Up 配置项
        up_configs = [
            ("Up1", "yes1_price_entry", "yes1_amount_entry", "0", "0"),
            ("Up2", "yes2_price_entry", "yes2_amount_entry", "0", "0"),
            ("Up3", "yes3_price_entry", "yes3_amount_entry", "0", "0"),
            ("Up4", "yes4_price_entry", "yes4_amount_entry", "0", "0"),
            ("Up5", "yes5_price_entry", None, "0", "0")
        ]
        
        for i, (label, price_attr, amount_attr, price_val, amount_val) in enumerate(up_configs):
            row_base = i * 2
            
            # 价格标签和输入框
            ttk.Label(self.yes_frame, text=f"{label} Price(¢):", style='Black.TLabel').grid(
                row=row_base, column=0, padx=3, pady=2, sticky="w")
            price_entry = ttk.Entry(self.yes_frame, font=base_font)
            price_entry.insert(0, price_val)
            price_entry.grid(row=row_base, column=1, padx=3, pady=2, sticky="ew")
            setattr(self, price_attr, price_entry)
            
            # 金额标签和输入框（仅当amount_attr不为None时创建）
            if amount_attr is not None:
                ttk.Label(self.yes_frame, text=f"{label} Amount:", style='Black.TLabel').grid(
                    row=row_base+1, column=0, padx=3, pady=2, sticky="w")
                amount_entry = ttk.Entry(self.yes_frame, font=base_font)
                amount_entry.insert(0, amount_val)
                amount_entry.grid(row=row_base+1, column=1, padx=3, pady=2, sticky="ew")
                setattr(self, amount_attr, amount_entry)
        
        # 配置列权重
        self.yes_frame.grid_columnconfigure(1, weight=1)

        # Down 配置项
        down_configs = [
            ("Down1", "no1_price_entry", "no1_amount_entry", "0", "0"),
            ("Down2", "no2_price_entry", "no2_amount_entry", "0", "0"),
            ("Down3", "no3_price_entry", "no3_amount_entry", "0", "0"),
            ("Down4", "no4_price_entry", "no4_amount_entry", "0", "0"),
            ("Down5", "no5_price_entry", None, "0", "0")
        ]
        
        for i, (label, price_attr, amount_attr, price_val, amount_val) in enumerate(down_configs):
            row_base = i * 2
            
            # 价格标签和输入框
            ttk.Label(self.no_frame, text=f"{label} Price(¢):", style='Black.TLabel').grid(
                row=row_base, column=0, padx=3, pady=2, sticky="w")
            price_entry = ttk.Entry(self.no_frame, font=base_font)
            price_entry.insert(0, price_val)
            price_entry.grid(row=row_base, column=1, padx=3, pady=2, sticky="ew")
            setattr(self, price_attr, price_entry)
            
            # 金额标签和输入框（仅当amount_attr不为None时创建）
            if amount_attr is not None:
                ttk.Label(self.no_frame, text=f"{label} Amount:", style='Black.TLabel').grid(
                    row=row_base+1, column=0, padx=3, pady=2, sticky="w")
                amount_entry = ttk.Entry(self.no_frame, font=base_font)
                amount_entry.insert(0, amount_val)
                amount_entry.grid(row=row_base+1, column=1, padx=3, pady=2, sticky="ew")
                setattr(self, amount_attr, amount_entry)
        
        # 配置列权重
        self.no_frame.grid_columnconfigure(1, weight=1)

        # 创建按钮区域
        trade_frame = ttk.LabelFrame(scrollable_frame, text="Buttons", style='Black.TLabelframe')
        trade_frame.pack(fill="x", padx=2, pady=2)
        
        # 按钮配置
        button_configs = [
            # 第一行：主要交易按钮
            [("buy_button", "Buy", self.click_buy),
             ("buy_yes_button", "Buy-Up", self.click_buy_yes),
             ("buy_no_button", "Buy-Down", self.click_buy_no)],
            # 第二行：确认和金额按钮
            [("buy_confirm_button", "Buy-confirm", self.click_buy_confirm_button),
             ("amount_yes1_button", "Amount-Up1", None),
             ("amount_yes2_button", "Amount-Up2", None)],
            # 第三行：Yes金额按钮
            [("amount_yes3_button", "Amount-Up3", None),
             ("amount_yes4_button", "Amount-Up4", None),
             ("amount_no1_button", "Amount-Down1", None)],
            # 第四行：No金额按钮
            [("amount_no2_button", "Amount-Down2", None),
             ("amount_no3_button", "Amount-Down3", None),
             ("amount_no4_button", "Amount-Down4", None)],
            # 第五行：卖出按钮
            [("position_sell_yes_button", "Positions-Sell-Up", self.click_position_sell_yes),
             ("position_sell_no_button", "Positions-Sell-Down", self.click_position_sell_no),
             ("sell_confirm_button", "Sell-confirm", self.click_sell_confirm_button)]
        ]
        
        for row, button_row in enumerate(button_configs):
            for col, (attr_name, text, command) in enumerate(button_row):
                if attr_name:  # 跳过占位符
                    button = ttk.Button(trade_frame, text=text, width=self.button_width)
                    
                    if command:
                        button.configure(command=command)
                    else:
                        # 金额按钮使用特殊绑定
                        button.bind('<Button-1>', self.click_amount)
                    
                    button.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
                    setattr(self, attr_name, button)
        
        # 配置列权重使按钮均匀分布
        for i in range(3):
            trade_frame.grid_columnconfigure(i, weight=1)
            
        # 窗口自适应内容大小
        self.root.update_idletasks()
        
        content_height = scrollable_frame.winfo_reqheight()
        
        # 计算并设置窗口的初始大小
        final_width = 550
        # 高度自适应，确保能显示所有内容
        final_height = max(300, content_height)

        self.root.geometry(f'{final_width}x{final_height}+0+0')
        self.root.minsize(300, final_height)
        
        # 最后一次更新确保布局正确
        self.root.update_idletasks()
    
    def start_monitoring(self):
        """开始监控"""
        # 直接使用当前显示的网址
        target_url = self.url_entry.get().strip()
        self.logger.info(f"\033[34m✅ 开始监控网址: {target_url}\033[0m")
        
        # 启用开始按钮，启用停止按钮
        self.start_button['state'] = 'disabled'
            
        # 将"开始监控"文字变为红色
        self.start_button.configure(style='Red.TButton')
        
        # 重置交易次数计数器
        self.trade_count = 0
            
        # 启动浏览器作线程
        threading.Thread(target=self._start_browser_monitoring, args=(target_url,), daemon=True).start()

        self.running = True

        # 启用设置金额按钮
        self.set_amount_button['state'] = 'normal'

        # 检查是否登录
        self.login_check_timer = self.root.after(4000, self.start_login_monitoring)

        # 启动URL监控
        self.url_check_timer = self.root.after(8000, self.start_url_monitoring)

        # 启动零点 CASH 监控
        self.get_zero_time_cash_timer = self.root.after(3000, self.get_zero_time_cash)

        # 启动币安零点时价格监控
        self.get_binance_zero_time_price_timer = self.root.after(14000, self.get_binance_zero_time_price)
        
        # 启动币安实时价格监控
        self.get_binance_price_websocket_timer = self.root.after(16000, self.get_binance_price_websocket)

        # 启动币安价格对比
        self.comparison_binance_price_timer = self.root.after(20000, self.comparison_binance_price)

        # 启动自动找币
        self.root.after(30000, self.schedule_auto_find_coin)

        # 启动设置 YES1/NO1价格为 52
        self.schedule_price_setting_timer = self.root.after(36000, self.schedule_price_setting)
        
        # 启动页面刷新
        self.refresh_page_timer = self.root.after(40000, self.refresh_page)
        self.logger.info("\033[34m✅ 40秒后启动页面刷新!\033[0m")
        
    def _start_browser_monitoring(self, new_url):
        """在新线程中执行浏览器操作"""
        try:
            if not self.driver and not self.is_restarting:
                chrome_options = Options()
                chrome_options.debugger_address = "127.0.0.1:9222"
                chrome_options.add_argument('--disable-dev-shm-usage')
                
                system = platform.system()
                if system == 'Linux':
                    # 添加与启动脚本一致的所有参数
                    chrome_options.add_argument('--no-sandbox')
                    chrome_options.add_argument('--disable-gpu')
                    chrome_options.add_argument('--disable-software-rasterizer')
                    chrome_options.add_argument('--disable-dev-shm-usage')
                    chrome_options.add_argument('--disable-background-networking')
                    chrome_options.add_argument('--disable-default-apps')
                    chrome_options.add_argument('--disable-extensions')
                    chrome_options.add_argument('--disable-sync')
                    chrome_options.add_argument('--metrics-recording-only')
                    chrome_options.add_argument('--no-first-run')
                    chrome_options.add_argument('--disable-session-crashed-bubble')
                    chrome_options.add_argument('--disable-translate')
                    chrome_options.add_argument('--disable-background-timer-throttling')
                    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
                    chrome_options.add_argument('--disable-renderer-backgrounding')
                    chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees,SitePerProcess,IsolateOrigins')
                    chrome_options.add_argument('--noerrdialogs')
                    chrome_options.add_argument('--disable-infobars')
                    chrome_options.add_argument('--disable-notifications')
                    chrome_options.add_argument('--test-type')

                self.driver = webdriver.Chrome(options=chrome_options)
            try:
                # 在当前标签页打开URL
                self.driver.get(new_url)
                
                # 等待页面加载
                WebDriverWait(self.driver, 60).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                self.logger.info("\033[34m✅ 浏览器启动成功!\033[0m")
                
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
            error_msg = f"启动浏览器失败: {str(e)}"
            self.logger.error(f"启动监控失败: {str(e)}")
            self.logger.error(error_msg)
            self._show_error_and_reset(error_msg)

    def _show_error_and_reset(self, error_msg):
        """显示错误并重置按钮状态"""
        # 用after方法确保在线程中执行GUI操作
        # 在尝试显示消息框之前，检查Tkinter主窗口是否仍然存在
        if self.root and self.root.winfo_exists():
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
            self.root.after(0, lambda: self.start_button.config(state='normal'))
        else:
            # 如果主窗口不存在，则直接记录错误到日志
            self.logger.error(f"GUI主窗口已销毁,无法显示错误消息: {error_msg}")
        self.running = False

    def monitor_prices(self):
        """检查价格变化"""
        try:
            # 确保浏览器连接
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
            
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
    
    def restart_browser(self,force_restart=True):
        """统一的浏览器重启/重连函数
        Args:
            force_restart: True=强制重启Chrome进程,False=尝试重连现有进程
        """
        # 先关闭浏览器
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.warning(f"关闭浏览器失败: {str(e)}")
                
        # 彻底关闭所有Chrome进程
        if force_restart:
            try:
                import platform
                import subprocess
                
                system = platform.system()
                if system == "Windows":
                    subprocess.run("taskkill /f /im chrome.exe", shell=True)
                    subprocess.run("taskkill /f /im chromedriver.exe", shell=True)
                elif system == "Darwin":  # macOS
                    subprocess.run("pkill -9 'Google Chrome'", shell=True)
                    subprocess.run("pkill -9 'chromedriver'", shell=True)
                else:  # Linux
                    subprocess.run("pkill -9 chrome", shell=True)
                    subprocess.run("pkill -9 chromedriver", shell=True)
                    
                self.logger.info("已强制关闭所有Chrome进程")
            except Exception as e:
                self.logger.error(f"强制关闭Chrome进程失败: {str(e)}")
                
        self.driver = None

        # 检查是否已在重启中
        with self.restart_lock:
            if self.is_restarting:
                self.logger.info("浏览器正在重启中，跳过重复重启")
                return True
            self.is_restarting = True

        try:
            self.logger.info(f"正在{'重启' if force_restart else '重连'}浏览器...")
            
            # 1. 清理现有连接
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
            
            # 2. 如果需要强制重启，启动新的Chrome进程
            if force_restart:
                try:
                    # 根据操作系统选择启动脚本
                    script_path = ('start_chrome_macos.sh' if platform.system() == 'Darwin' 
                                else 'start_chrome_ubuntu.sh')
                    script_path = os.path.abspath(script_path)
                    
                    # 检查脚本是否存在
                    if not os.path.exists(script_path):
                        raise FileNotFoundError(f"启动脚本不存在: {script_path}")
                    
                    # 启动Chrome进程（异步）
                    process = subprocess.Popen(['bash', script_path], 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE)
                    
                    # 等待Chrome调试端口可用
                    max_wait_time = 30
                    wait_interval = 1
                    for wait_time in range(0, max_wait_time, wait_interval):
                        time.sleep(wait_interval)
                        try:
                            # 检查调试端口是否可用
                            import requests
                            response = requests.get('http://127.0.0.1:9222/json', timeout=2)
                            if response.status_code == 200:
                                self.logger.info(f"✅ Chrome浏览器已重新启动,调试端口可用 (等待{wait_time+1}秒)")
                                break
                        except:
                            continue
                    else:
                        raise Exception("Chrome调试端口在30秒内未能启动")
                    
                except Exception as e:
                    self.logger.error(f"启动Chrome失败: {e}")
                    self.restart_browser(force_restart=True)
                    return False
            
            # 3. 重新连接浏览器（带重试机制）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    chrome_options = Options()
                    chrome_options.debugger_address = "127.0.0.1:9222"
                    chrome_options.add_argument('--disable-dev-shm-usage')
                    
                    # Linux特定配置
                    if platform.system() == 'Linux':
                        
                        # 添加与启动脚本一致的所有参数
                        chrome_options.add_argument('--no-sandbox')
                        chrome_options.add_argument('--disable-gpu')
                        chrome_options.add_argument('--disable-software-rasterizer')
                        chrome_options.add_argument('--disable-dev-shm-usage')
                        chrome_options.add_argument('--disable-background-networking')
                        chrome_options.add_argument('--disable-default-apps')
                        chrome_options.add_argument('--disable-extensions')
                        chrome_options.add_argument('--disable-sync')
                        chrome_options.add_argument('--metrics-recording-only')
                        chrome_options.add_argument('--no-first-run')
                        chrome_options.add_argument('--disable-session-crashed-bubble')
                        chrome_options.add_argument('--disable-translate')
                        chrome_options.add_argument('--disable-background-timer-throttling')
                        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
                        chrome_options.add_argument('--disable-renderer-backgrounding')
                        chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees,SitePerProcess,IsolateOrigins')
                        chrome_options.add_argument('--noerrdialogs')
                        chrome_options.add_argument('--disable-infobars')
                        chrome_options.add_argument('--disable-notifications')
                        chrome_options.add_argument('--test-type')
                        
                    self.driver = webdriver.Chrome(options=chrome_options)
                    
                    # 验证连接
                    self.driver.execute_script("return navigator.userAgent")
                    
                    # 加载目标URL
                    target_url = self.url_entry.get()
                    if target_url:
                        self.driver.get(target_url)
                        WebDriverWait(self.driver, 15).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )
                        self.logger.info(f"✅ 成功加载页面: {target_url}")
                    
                    self.logger.info("✅ 浏览器连接成功")

                    # 连接成功后，重置监控线程
                    self._restore_monitoring_state()
                    return True
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"连接失败 ({attempt+1}/{max_retries}),2秒后重试: {e}")
                        time.sleep(2)
                    else:
                        self.logger.error(f"浏览器连接最终失败: {e}")
                        return False
            return False
            
        except Exception as e:
            self.logger.error(f"浏览器重启失败: {e}")
            self._send_chrome_alert_email()
            return False
        
        finally:
            with self.restart_lock:
                self.is_restarting = False

    def restart_browser_after_auto_find_coin(self):
        """重连浏览器后自动检查并更新URL中的日期"""
        try:
            # 从GUI获取当前监控的URL
            current_url = self.url_entry.get().strip()
            if not current_url:
                self.logger.info("📅 URL为空,跳过日期检查")
                return
            
            self.logger.info(f"📅 检查URL中的日期: {current_url}")
            
            # 从URL中提取日期 (例如: july-13)
            date_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)-(\d{1,2})'
            match = re.search(date_pattern, current_url.lower())
            
            if not match:
                self.logger.info("📅 URL中未找到日期格式,跳过日期检查")
                return
            
            url_month = match.group(1)
            url_day = int(match.group(2))
            
            # 获取当前日期并格式化为相同格式
            current_date = datetime.now()
            current_month = current_date.strftime("%B").lower()  # 获取完整月份名称并转小写
            current_day = current_date.day
            
            current_date_str = f"{current_month}-{current_day}"
            url_date_str = f"{url_month}-{url_day}"
            
            self.logger.info(f"URL日期: {url_date_str}, 当前日期: {current_date_str}")
            
            # 比较日期
            if url_date_str == current_date_str:
                self.logger.info("📅 日期匹配,无需更新URL")
                return
            
            # 日期不匹配，需要更新URL
            self.logger.info(f"\033[31m日期不匹配,更新URL中的日期从 {url_date_str} 到 {current_date_str}\033[0m")
            
            # 替换URL中的日期
            old_date_pattern = f"{url_month}-{url_day}"
            new_date_pattern = f"{current_month}-{current_day}"
            updated_url = current_url.replace(old_date_pattern, new_date_pattern)
            
            # 更新GUI中的URL
            self.url_entry.delete(0, 'end')
            self.url_entry.insert(0, updated_url)
            
            # 保存到配置文件
            if 'website' not in self.config:
                self.config['website'] = {}
            self.config['website']['url'] = updated_url
            
            # 更新URL历史记录
            if 'url_history' not in self.config:
                self.config['url_history'] = []
            if updated_url not in self.config['url_history']:
                self.config['url_history'].insert(0, updated_url)
                # 保持历史记录不超过10条
                self.config['url_history'] = self.config['url_history'][:10]
                self.url_entry['values'] = self.config['url_history']
            
            self.save_config()
            
            self.logger.info(f"✅ \033[34mURL已更新为: {updated_url}\033[0m")
            
            # 如果浏览器已经打开，导航到新URL
            if self.driver:
                try:
                    self.driver.get(updated_url)
                    self.logger.info(f"✅ \033[34m浏览器已导航到新URL\033[0m")
                except Exception as e:
                    self.logger.error(f"导航到新URL失败: {e}")
            
        except Exception as e:
            self.logger.error(f"日期检查和更新失败: {e}")

    def _restore_monitoring_state(self):
        """恢复监控状态 - 重新同步监控逻辑，确保所有监控功能正常工作"""
        try:
            self.logger.info("🔄 恢复监控状态...")
            
            # 确保运行状态正确
            self.running = True
            
            # 重连浏览器后自动检查并更新URL中的日期
            self.restart_browser_after_auto_find_coin()
            
            # 重新启动各种监控功能（不是重新创建定时器，而是确保监控逻辑正常）
            # 1. 重新启动登录监控（如果当前没有运行）
            if hasattr(self, 'login_check_timer') and self.login_check_timer:
                self.root.after_cancel(self.login_check_timer)
            self.start_login_monitoring()
            
            # 2. 重新启动URL监控（如果当前没有运行）
            if hasattr(self, 'url_check_timer') and self.url_check_timer:
                self.root.after_cancel(self.url_check_timer) 
            self.start_url_monitoring()

            # 3. 重新启动页面刷新监控（如果当前没有运行）
            if hasattr(self, 'refresh_page_timer') and self.refresh_page_timer:
                self.root.after_cancel(self.refresh_page_timer)     
            self.refresh_page()

            # 重启设置 YES1/NO1 价格为 52
            if hasattr(self,'schedule_price_setting_timer') and self.schedule_price_setting_timer:
                self.root.after_cancel(self.schedule_price_setting_timer)
            self.schedule_price_setting()

            # 6.重新开始价格比较
            if hasattr(self,'comparison_binance_price_timer') and self.comparison_binance_price_timer:
                self.root.after_cancel(self.comparison_binance_price_timer)
            self.comparison_binance_price()

            # 7.重新启动自动找币功能
            if hasattr(self,'schedule_auto_find_coin_timer') and self.schedule_auto_find_coin_timer:
                self.root.after_cancel(self.schedule_auto_find_coin_timer)
            self.schedule_auto_find_coin()
            
            # 智能恢复时间敏感类定时器
            current_time = datetime.now()
            
            # 8. binance_zero_timer: 计算到下一个零点的时间差
            next_zero_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            if current_time >= next_zero_time:
                next_zero_time += timedelta(days=1)
            
            seconds_until_next_run = int((next_zero_time - current_time).total_seconds() * 1000)  # 转换为毫秒
            
            # 只在合理的时间范围内恢复零点价格定时器
            if seconds_until_next_run > 0:
                self.get_binance_zero_time_price_timer = self.root.after(seconds_until_next_run, self.get_binance_zero_time_price)
                self.logger.info(f"✅ 恢复获取币安零点价格定时器，{round(seconds_until_next_run / 3600000, 2)} 小时后执行")
            
            # 9. zero_cash_timer: 类似的计算逻辑
            # 现金监控可以稍微提前一点，比如在23:59:30开始
            next_cash_time = current_time.replace(hour=23, minute=59, second=30, microsecond=0)
            if current_time >= next_cash_time:
                next_cash_time += timedelta(days=1)
            
            seconds_until_cash_run = int((next_cash_time - current_time).total_seconds() * 1000)
            
            if seconds_until_cash_run > 0:
                self.get_zero_time_cash_timer = self.root.after(seconds_until_cash_run, self.get_zero_time_cash)
                self.logger.info(f"✅ 恢复获取零点 CASH定时器,{round(seconds_until_cash_run / 3600000, 2)} 小时后执行")
            
            self.logger.info("✅ 监控状态恢复完成")
            
        except Exception as e:
            self.logger.error(f"恢复监控状态失败: {e}")

    def get_nearby_cents(self):
        """获取份额"""
        try:
            try:
                up_shares_element = self.driver.find_element(By.XPATH, XPathConfig.ASKS_SHARES[0])
                up_shares_text = up_shares_element.text
            except (NoSuchElementException, StaleElementReferenceException):
                
                return None, None
            
            try:
                down_shares_element = self.driver.find_element(By.XPATH, XPathConfig.BIDS_SHARES[0])
                down_shares_text = down_shares_element.text
            except (NoSuchElementException, StaleElementReferenceException):
                
                return None, None
            
            # 解析份额
            up_shares_val = float(up_shares_text.replace(',', '')) if up_shares_text else None
            down_shares_val = float(down_shares_text.replace(',', '')) if down_shares_text else None
            
            return up_shares_val, down_shares_val
            
        except Exception as e:
            self.logger.error(f"获取价格数据失败: {str(e)}")
            return None, None

    def check_prices(self):
        """检查价格变化"""
        # 直接检查driver是否存在，不存在就重启
        if not self.driver and not self.is_restarting:
            self.logger.warning("浏览器未初始化，尝试重启...")
            if not self.restart_browser(force_restart=True):
                self.logger.error("浏览器重启失败，跳过本次检查")
                return

        try:
            # 验证浏览器连接是否正常
            self.driver.execute_script("return navigator.userAgent")

            # 使用JavaScript直接获取价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {up: null, down: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Up') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.up = parseFloat(match[1]);
                        }
                        if (text.includes('Down') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.down = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
            asks_shares_val, bids_shares_val = self.get_nearby_cents()

            if prices['up'] is not None and prices['down'] is not None and asks_shares_val is not None and bids_shares_val is not None:
                # 获取价格
                up_price_val = float(prices['up'])
                down_price_val = float(prices['down'])

                # 更新GUI价格显示
                self.yes_price_label.config(text=f"Up: {up_price_val:.1f}¢")
                self.no_price_label.config(text=f"Down: {down_price_val:.1f}¢")
                self.up_shares_label.config(text=f"Up Shares: {asks_shares_val:.1f}")
                self.down_shares_label.config(text=f"Down Shares: {bids_shares_val:.1f}")
                
                # 执行所有交易检查函数（仅在没有交易进行时）
                if not self.trading:
                    self.First_trade(up_price_val, down_price_val, asks_shares_val, bids_shares_val)
                    self.Second_trade(up_price_val, down_price_val, asks_shares_val, bids_shares_val)
                    self.Third_trade(up_price_val, down_price_val, asks_shares_val, bids_shares_val)
                    self.Forth_trade(up_price_val, down_price_val, asks_shares_val, bids_shares_val)
                    self.Sell_yes(up_price_val, down_price_val, asks_shares_val, bids_shares_val)
                    self.Sell_no(up_price_val, down_price_val, asks_shares_val, bids_shares_val)
                    
            else:
                self.yes_price_label.config(text="Up: N/A")
                self.no_price_label.config(text="Down: N/A")
                self.up_shares_label.config(text="Up Shares: N/A")
                self.down_shares_label.config(text="Down Shares: N/A")
                
        except Exception as e:
            
            if "'NoneType' object has no attribute" in str(e):
                if not self.is_restarting:
                    self.restart_browser()
                return
            self.yes_price_label.config(text="Up: Fail")
            self.no_price_label.config(text="Down: Fail")
            self.up_shares_label.config(text="Up Shares: Fail")
            self.down_shares_label.config(text="Down Shares: Fail")
            time.sleep(1)
            
    def check_balance(self):
        """获取Portfolio和Cash值"""
        if not self.driver and not self.is_restarting:
            self.restart_browser(force_restart=True)
            return

        try:
            # 验证浏览器连接是否正常
            self.driver.execute_script("return navigator.userAgent")
            # 等待页面完全加载
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
        except Exception as e:
            self.logger.error(f"浏览器连接异常: {str(e)}")
            if not self.is_restarting:
                self.restart_browser()
            return
        
        try:
            # 取Portfolio值和Cash值
            self.cash_value = None
            self.portfolio_value = None

            # 获取Portfolio和Cash值
            try:
                portfolio_element = self.driver.find_element(By.XPATH, XPathConfig.PORTFOLIO_VALUE[0])
            except (NoSuchElementException, StaleElementReferenceException):
                portfolio_element = self._find_element_with_retry(XPathConfig.PORTFOLIO_VALUE, timeout=2, silent=True)
                
            
            try:
                cash_element = self.driver.find_element(By.XPATH, XPathConfig.CASH_VALUE[0])
            except (NoSuchElementException, StaleElementReferenceException):
                cash_element = self._find_element_with_retry(XPathConfig.CASH_VALUE, timeout=2, silent=True)
            
            if portfolio_element and cash_element:
                self.cash_value = cash_element.text
                self.portfolio_value = portfolio_element.text
            else:
                self.cash_value = "获取失败"
                self.portfolio_value = "获取失败"
        
            # 更新Portfolio和Cash显示
            self.portfolio_label.config(text=f"Portfolio: {self.portfolio_value}")
            self.cash_label.config(text=f"Cash: {self.cash_value}")

        except Exception as e:
            self.portfolio_label.config(text="Portfolio: Fail")
            self.cash_label.config(text="Cash: Fail")
    
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
            
        except Exception as e:
            self.logger.error(f"更新金额操作失败 (尝试 {current_retry + 1}/15): {str(e)}")
            # 如果失败，安排下一次重试
            self.schedule_update_amount(current_retry + 1)

    def set_yes_no_cash(self):
        """设置 Yes/No 各级金额"""
        try:
            #设置重试参数
            max_retry = 15
            retry_count = 0
            cash_value = 0

            while retry_count < max_retry:
                try:
                    # 获取 Cash 值
                    cash_value = float(self.zero_time_cash_value)
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retry:
                        time.sleep(2)
                    else:
                        raise ValueError("获取Cash值失败")
            if cash_value is None:
                raise ValueError("获取Cash值失败")
            
            # 获取金额设置中的百分比值
            initial_percent = float(self.initial_amount_entry.get()) / 100  # 初始金额百分比
            first_rebound_percent = float(self.first_rebound_entry.get()) / 100  # 反水一次百分比
            n_rebound_percent = float(self.n_rebound_entry.get()) / 100  # 反水N次百分比

            # 设置 Yes1 和 No1金额
            base_amount = cash_value * initial_percent
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
            self.logger.info("\033[34m✅ YES/NO 金额设置完成\033[0m")
            
        except Exception as e:
            self.logger.error(f"设置金额失败: {str(e)}")
            
            self.schedule_retry_update()

    def schedule_retry_update(self):
        """安排重试更新金额"""
        if hasattr(self, 'retry_timer'):
            self.root.after_cancel(self.retry_timer)
        self.retry_timer = self.root.after(3000, self.set_yes_no_cash)  # 3秒后重试
    
    def start_url_monitoring(self):
        """启动URL监控"""
        with self.url_monitoring_lock:
            if getattr(self, 'is_url_monitoring', False):
                self.logger.debug("URL监控已在运行中")
                return
            
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)

            self.url_monitoring_running = True
            self.logger.info("\033[34m✅ 启动URL监控\033[0m")

            def check_url():
                if self.running and self.driver:
                    try:
                        # 验证浏览器连接是否正常
                        self.driver.execute_script("return navigator.userAgent")
                        current_page_url = self.driver.current_url # 获取当前页面URL
                        target_url = self.url_entry.get().strip() # 获取输入框中的URL,这是最原始的URL

                        # 去除URL中的查询参数(?后面的部分)
                        def clean_url(url):
                            return url.split('?')[0].rstrip('/')
                            
                        clean_current = clean_url(current_page_url)
                        clean_target = clean_url(target_url)
                        
                        # 如果URL基础部分不匹配，重新导航
                        if clean_current != clean_target:
                            self.logger.info(f"❌ URL不匹配,重新导航到: {target_url}")
                            self.driver.get(target_url)

                    except Exception as e:
                        self.logger.error(f"URL监控出错: {str(e)}")

                        # 重新导航到目标URL
                        if self.driver:
                            try:
                                self.driver.get(target_url)
                                self.logger.info(f"\033[34m✅ URL监控已自动修复: {target_url}\033[0m")
                            except Exception:
                                self.restart_browser(force_restart=True)
                        else:
                            self.restart_browser(force_restart=True)
                    # 继续监控
                    if self.running:
                        self.url_check_timer = self.root.after(10000, check_url)  # 每10秒检查一次
            
            # 开始第一次检查
            self.url_check_timer = self.root.after(1000, check_url)

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

    def start_login_monitoring(self):
        """监控登录状态"""
        if not self.driver and not self.is_restarting:
            self.restart_browser(force_restart=True)

        # 检查是否已经登录
        try:
            # 查找登录按钮
            try:
                login_button = self.driver.find_element(By.XPATH, XPathConfig.LOGIN_BUTTON[0])
            except (NoSuchElementException, StaleElementReferenceException):
                login_button = self._find_element_with_retry(XPathConfig.LOGIN_BUTTON, timeout=2, silent=True)
                
            if login_button:
                self.logger.info("✅ 已发现登录按钮,尝试登录")
                self.stop_url_monitoring()
                self.stop_refresh_page()

                login_button.click()
                time.sleep(1)
                
                # 查找Google登录按钮
                try:
                    google_login_button = self.driver.find_element(By.XPATH, XPathConfig.LOGIN_WITH_GOOGLE_BUTTON[0])
                except (NoSuchElementException, StaleElementReferenceException):
                    google_login_button = self._find_element_with_retry(XPathConfig.LOGIN_WITH_GOOGLE_BUTTON, timeout=2, silent=True)
                    
                if google_login_button:
                    google_login_button.click()
                    self.logger.info("✅ 已点击Google登录按钮")
                    
                    # 不再固定等待15秒，而是循环检测CASH值
                    max_attempts = 10  # 最多检测10次
                    check_interval = 2  # 每2秒检测一次
                    cash_value = None
                    
                    for attempt in range(max_attempts):
                        try:
                            # 获取CASH值
                            try:
                                cash_element = self.driver.find_element(By.XPATH, XPathConfig.CASH_VALUE[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                cash_element = self._find_element_with_retry(XPathConfig.CASH_VALUE, timeout=2, silent=True)
                                
                            if cash_element:
                                cash_value = cash_element.text
                                self.logger.info(f"✅ 已找到CASH值: {cash_value}, 登录成功.")
                                self.driver.get(self.url_entry.get().strip())
                                time.sleep(2)
                                break
                        except NoSuchElementException:
                            self.logger.info(f"⏳ 第{attempt+1}次尝试: 等待登录完成...")                       
                        # 等待指定时间后再次检测
                        time.sleep(check_interval)
                    self.url_check_timer = self.root.after(10000, self.start_url_monitoring)
                    self.refresh_page_timer = self.root.after(240000, self.refresh_page)
                    self.logger.info("✅ 已重新启用URL监控和页面刷新")
        except NoSuchElementException:
            # 未找到登录按钮，可能已经登录
            pass          
        finally:
            # 每15秒检查一次登录状态
            self.login_check_timer = self.root.after(15000, self.start_login_monitoring)

    def find_accept_button(self):
        """查找 ACCEPT_BUTTON"""
        try:
            self.accept_button = self.driver.find_element(By.XPATH, XPathConfig.ACCEPT_BUTTON[0])
        except (NoSuchElementException, StaleElementReferenceException):
            self.accept_button = self._find_element_with_retry(XPathConfig.ACCEPT_BUTTON, timeout=2, silent=True)

        if self.accept_button:
            self.logger.info("✅ 已发现ACCEPT按钮")
            return True
        else:
            self.logger.info("❌ 未发现ACCEPT按钮")
            return False

    def entry_accept(self):
        """敲击回车键"""
        try:
            self.accept_button.click()
            self.logger.info("✅ 已通过敲击 ENTRY 按键,敲击了ACCEPT按钮")
            self.root.after(1000, self.driver.refresh())
        except Exception as e:
            self.logger.info(f"❌ 敲击 ENTRY 按键失败,重新点击ACCEPT按钮")
            self.click_accept()
            self.root.after(2000, self.driver.refresh())
            self.logger.info("✅ 已使用 坐标法 鼠标点击ACCEPT按钮成功")

    def click_accept(self):
        """点击ACCEPT按钮"""
        self.logger.info("开始执行点击ACCEPT按钮")
        try:
            screen_width, screen_height = pyautogui.size()
            
            target_x = 0
            target_y = 0

            if platform.system() == "Linux": # 分辨率 2560X1600
                # Linux 系统下的特定坐标
                target_x = screen_width - 630
                target_y = 969
                
            else:
                # 其他操作系统的默认坐标分辨率 1920x1080
                target_x = screen_width - 520
                target_y = 724
                
            # 移动鼠标到目标位置并点击
            pyautogui.moveTo(target_x, target_y, duration=0.2) # 可选，平滑移动
            pyautogui.click(target_x, target_y)
            
            self.logger.info("✅ 点击ACCEPT成功")
            self.driver.refresh()

        except Exception as e:
            self.logger.error(f"执行 click_accept 点击操作失败: {str(e)}")

    def refresh_page(self):
        """定时刷新页面"""
        # 生成随机的5-10分钟（以毫秒为单位）
        random_minutes = random.uniform(2, 7)
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
                    try:
                        # 验证浏览器连接是否正常
                        self.driver.execute_script("return navigator.userAgent")
                        refresh_time = self.refresh_interval / 60000 # 转换为分钟,用于输入日志
                        self.driver.refresh()
                    except Exception as e:
                        self.logger.warning(f"浏览器连接异常，无法刷新页面")
                        # 尝试重启浏览器
                        if not self.is_restarting:
                            self.restart_browser()
                else:
                    self.logger.info("刷新失败(else)")
                    self.logger.info(f"trading={self.trading}")
                    
            except Exception as e:
                self.logger.warning(f"页面刷新失败(except)")
                # 无论是否执行刷新都安排下一次（确保循环持续）
                if hasattr(self, 'refresh_page_timer') and self.refresh_page_timer:
                    try:
                        self.root.after_cancel(self.refresh_page_timer)
                    except Exception as e:
                        self.logger.error(f"取消旧定时器失败")
            finally:
                self.refresh_page_timer = self.root.after(self.refresh_interval, self.refresh_page)
                #self.logger.info(f"\033[34m{round(refresh_time, 2)} 分钟后再次刷新\033[0m")

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
 
    def First_trade(self, up_price, down_price, up_shares, down_shares):
        """第一次交易价格设置为 0.52 买入,最多重试3次,失败发邮件"""
        try:
            if (up_price is not None and up_price > 10) and (down_price is not None and down_price > 10):
                yes1_price = float(self.yes1_price_entry.get())
                no1_price = float(self.no1_price_entry.get())
                self.trading = True
                # 检查Yes1价格匹配
                if 0 <= round((up_price - yes1_price), 2) <= self.price_premium and (up_shares > self.asks_shares) and up_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[32mUp 1: {up_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        self.amount_yes1_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()

                        time.sleep(2)
                        if self.Verify_buy_yes():
                            self.buy_yes1_amount = float(self.yes1_amount_entry.get())
                            self.yes1_shares = self.shares # 获取 YES1 的 shares
                            # 增加交易次数
                            self.trade_count += 1
                            # 重置Yes1和No1价格为0
                            self.yes1_price_entry.configure(foreground='black')
                            self.yes1_price_entry.delete(0, tk.END)
                            self.yes1_price_entry.insert(0, "0")
                            self.no1_price_entry.configure(foreground='black')
                            self.no1_price_entry.delete(0, tk.END)
                            self.no1_price_entry.insert(0, "0")
                            self.logger.info("\033[34m✅ Yes1和No1价格已重置为{self.yes1_price_entry.get()}和{self.no1_price_entry.get()}\033[0m")
                            # 设置No2价格为默认值
                            self.no2_price_entry = self.no_frame.grid_slaves(row=2, column=1)[0]
                            self.no2_price_entry.delete(0, tk.END)
                            self.no2_price_entry.insert(0, str(self.default_target_price))
                            self.no2_price_entry.configure(foreground='red')
                            # 设置 Yes5和No5价格为99
                            self.yes5_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                            self.yes5_price_entry.delete(0, tk.END)
                            self.yes5_price_entry.insert(0, str(self.default_normal_sell_price))
                            self.yes5_price_entry.configure(foreground='red')
                            self.no5_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                            self.no5_price_entry.delete(0, tk.END)
                            self.no5_price_entry.insert(0, str(self.default_normal_sell_price))
                            self.no5_price_entry.configure(foreground='red')
                            self.logger.info("\033[34m✅ Yes5和No5价格已重置为{self.yes5_price_entry.get()}和{self.no5_price_entry.get()}\033[0m")
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up1",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ First_trade执行BUY UP1成功\033[0m")
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Up1 交易失败,第{retry+1}次,等待1秒后重试")
                            time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Buy Up1失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
                elif 0 <= round((down_price - no1_price), 2) <= self.price_premium and (down_shares > self.bids_shares) and down_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[31mDown 1: {down_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no1_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()

                        time.sleep(0.5)
                        self.buy_yes_button.invoke()
                        time.sleep(2)
                        if self.Verify_buy_no():
                            self.buy_no1_amount = float(self.no1_amount_entry.get())
                            self.no1_shares = self.shares # 获取 NO1 的 shares
                            # 增加交易次数
                            self.trade_count += 1
                            # 重置Yes1和No1价格为0
                            self.yes1_price_entry.delete(0, tk.END)
                            self.yes1_price_entry.insert(0, "0")
                            self.yes1_price_entry.configure(foreground='black')
                            self.no1_price_entry.delete(0, tk.END)
                            self.no1_price_entry.insert(0, "0")
                            self.no1_price_entry.configure(foreground='black')
                            self.logger.info("\033[34m✅ Yes1和No1价格已重置为{self.yes1_price_entry.get()}和{self.no1_price_entry.get()}\033[0m")
                            # 设置Yes2价格为默认值
                            self.yes2_price_entry = self.yes_frame.grid_slaves(row=2, column=1)[0]
                            self.yes2_price_entry.delete(0, tk.END)
                            self.yes2_price_entry.insert(0, str(self.default_target_price))
                            self.yes2_price_entry.configure(foreground='red')
                            self.logger.info("\033[34m✅ Yes2价格已重置为{self.yes2_price_entry.get()}\033[0m")
                            # 设置 Yes5和No5价格为99
                            self.yes5_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                            self.yes5_price_entry.delete(0, tk.END)
                            self.yes5_price_entry.insert(0, str(self.default_normal_sell_price))
                            self.yes5_price_entry.configure(foreground='red')
                            self.no5_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                            self.no5_price_entry.delete(0, tk.END)
                            self.no5_price_entry.insert(0, str(self.default_normal_sell_price))
                            self.no5_price_entry.configure(foreground='red')
                            self.logger.info("\033[34m✅ Yes5和No5价格已重置为{self.yes5_price_entry.get()}和{self.no5_price_entry.get()}\033[0m")
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down1",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ First_trade执行BUY DOWN1成功\033[0m")
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Down1 交易失败,第{retry+1}次,等待1秒后重试")
                            time.sleep(1)
                    else:
                        self.send_trade_email(
                            trade_type="Buy Down1失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"First_trade执行失败: {str(e)}")
        finally:
            self.trading = False
            
    def Second_trade(self, up_price, down_price, up_shares, down_shares):
        """处理Yes2/No2的自动交易"""
        try:
            if (up_price is not None and up_price > 10) and (down_price is not None and down_price > 10):
                # 获Yes2和No2的价格输入框
                yes2_price = float(self.yes2_price_entry.get())
                no2_price = float(self.no2_price_entry.get())
                self.trading = True
                # 检查Yes2价格匹配
                if 0 <= round((up_price - yes2_price), 2) <= self.price_premium and (up_shares > self.asks_shares) and up_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅  \033[32mUp 2: {up_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        self.amount_yes2_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()

                        time.sleep(2)
                        if self.Verify_buy_yes():
                            self.buy_yes2_amount = float(self.yes2_amount_entry.get())
                            self.yes2_shares = self.shares # 获取 YES2 的 shares
                            # 重置Yes2和No2价格为0
                            self.yes2_price_entry.delete(0, tk.END)
                            self.yes2_price_entry.insert(0, "0")
                            self.yes2_price_entry.configure(foreground='black')
                            self.no2_price_entry.delete(0, tk.END)
                            self.no2_price_entry.insert(0, "0")
                            self.no2_price_entry.configure(foreground='black')
                            
                            # 设置No3价格为默认值
                            self.no3_price_entry = self.no_frame.grid_slaves(row=4, column=1)[0]
                            self.no3_price_entry.delete(0, tk.END)
                            self.no3_price_entry.insert(0, str(self.default_target_price))
                            self.no3_price_entry.configure(foreground='red')  # 添加红色设置
                            
                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up2",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Second_trade执行BUY UP2成功\033[0m")
                            # 增加刷新,因为不刷新,POSITIONS 上不显示刚刚购买的
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Up2 交易失败,第{retry+1}次,等待1秒后重试")
                            time.sleep(1)
                    else:
                        self.send_trade_email(
                            trade_type="Buy Up2失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
                # 检查No2价格匹配
                elif 0 <= round((down_price - no2_price), 2) <= self.price_premium and (down_shares > self.bids_shares) and down_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[31mDown 2: {down_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no2_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()

                        # 点击 BUY_YES 按钮,目的是刷新页面,否则实时价格就不对了
                        self.buy_yes_button.invoke() 
                        time.sleep(2)

                        if self.Verify_buy_no():
                            self.buy_no2_amount = float(self.no2_amount_entry.get())
                            self.no2_shares = self.shares # 获取 NO2 的 shares
                            # 重置Yes2和No2价格为0
                            self.yes2_price_entry.delete(0, tk.END)
                            self.yes2_price_entry.insert(0, "0")
                            self.yes2_price_entry.configure(foreground='black')
                            self.no2_price_entry.delete(0, tk.END)
                            self.no2_price_entry.insert(0, "0")
                            self.no2_price_entry.configure(foreground='black')
                            
                            # 设置YES3价格为默认值
                            self.yes3_price_entry = self.yes_frame.grid_slaves(row=4, column=1)[0]
                            self.yes3_price_entry.delete(0, tk.END)
                            self.yes3_price_entry.insert(0, str(self.default_target_price))
                            self.yes3_price_entry.configure(foreground='red')  # 添加红色设置
                            
                            # 增加交易次数
                            self.trade_count += 1
                            self.send_trade_email(
                                trade_type="Buy Down2",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Second_trade执行BUY DOWN2成功\033[0m")
                            # 增加刷新,因为不刷新,POSITIONS 上不显示刚刚购买的
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Down2 交易失败,第{retry+1}次,等待1秒后重试")
                            time.sleep(1)
                    else:
                        self.send_trade_email(
                            trade_type="Buy Down2失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Second_trade执行失败: {str(e)}")
        finally:
            self.trading = False
    
    def Third_trade(self, up_price, down_price, up_shares, down_shares):
        """处理Yes3/No3的自动交易"""
        try:
            if (up_price is not None and up_price > 10) and (down_price is not None and down_price > 10):              
                # 获取Yes3和No3的价格输入框
                yes3_price = float(self.yes3_price_entry.get())
                no3_price = float(self.no3_price_entry.get())
                self.trading = True  # 开始交易
            
                # 检查Yes3价格匹配
                if 0 <= round((up_price - yes3_price), 2) <= self.price_premium and (up_shares > self.asks_shares) and up_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[32mUp 3: {up_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        # 执行交易操作
                        self.amount_yes3_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()

                        time.sleep(2)
                        if self.Verify_buy_yes():
                            # 获取 YES3 的金额
                            self.buy_yes3_amount = float(self.yes3_amount_entry.get())
                            self.yes3_shares = self.shares # 获取 YES3 的 shares
                            # 重置Yes3和No3价格为0
                            self.yes3_price_entry.delete(0, tk.END)
                            self.yes3_price_entry.insert(0, "0")
                            self.yes3_price_entry.configure(foreground='black')
                            self.no3_price_entry.delete(0, tk.END)
                            self.no3_price_entry.insert(0, "0")
                            self.no3_price_entry.configure(foreground='black')
                            
                            # 设置No4价格为默认值
                            self.no4_price_entry = self.no_frame.grid_slaves(row=6, column=1)[0]
                            self.no4_price_entry.delete(0, tk.END)
                            self.no4_price_entry.insert(0, str(self.default_target_price))
                            self.no4_price_entry.configure(foreground='red')  # 添加红色设置

                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up3",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )   
                            self.logger.info("\033[34m✅ Third_trade执行BUY UP3成功\033[0m")
                            # 增加刷新,因为不刷新,POSITIONS 上不显示刚刚购买的
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning("❌  Buy Up3 交易失败,等待1秒后重试")
                            time.sleep(1)  # 添加延时避免过于频繁的重试
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Buy UP3失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )   
                # 检查No3价格匹配
                elif 0 <= round((down_price - no3_price), 2) <= self.price_premium and (down_shares > self.bids_shares) and down_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[31mDown 3: {down_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        # 执行交易操作
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no3_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()
                            
                        # 点击 BUY_YES 按钮,目的是刷新页面,否则实时价格就不对了
                        self.buy_yes_button.invoke()
                        time.sleep(2)
                        if self.Verify_buy_no():
                            self.no3_shares = self.shares # 获取 NO3 的 shares
                            self.buy_no3_amount = float(self.no3_amount_entry.get())
                            
                            # 重置Yes3和No3价格为0
                            self.yes3_price_entry.delete(0, tk.END)
                            self.yes3_price_entry.insert(0, "0")
                            self.yes3_price_entry.configure(foreground='black')
                            self.no3_price_entry.delete(0, tk.END)
                            self.no3_price_entry.insert(0, "0")
                            self.no3_price_entry.configure(foreground='black')
                            
                            # 设置Yes4价格为默认值
                            self.yes4_price_entry = self.yes_frame.grid_slaves(row=6, column=1)[0]
                            self.yes4_price_entry.delete(0, tk.END)
                            self.yes4_price_entry.insert(0, str(self.default_target_price))
                            self.yes4_price_entry.configure(foreground='red')  # 添加红色设置

                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down3",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Third_trade执行BUY DOWN3成功\033[0m")
                            # 增加刷新,因为不刷新,POSITIONS 上不显示刚刚购买的
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Down3 交易失败,第{retry+1}次,等待1秒后重试")
                            time.sleep(1)  # 添加延时避免过于频繁的重试
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Buy Down3失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )   
            
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Third_trade执行失败: {str(e)}")    
        finally:
            self.trading = False

    def Forth_trade(self, up_price, down_price, up_shares, down_shares):
        """处理Yes4/No4的自动交易"""
        try:
            if (up_price is not None and up_price > 10) and (down_price is not None and down_price > 10):  
                # 获取Yes4和No4的价格输入框
                yes4_price = float(self.yes4_price_entry.get())
                no4_price = float(self.no4_price_entry.get())
                self.trading = True  # 开始交易
            
                # 检查Yes4价格匹配
                if 0 <= round((up_price - yes4_price), 2) <= self.price_premium and (up_shares > self.asks_shares) and up_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[32mUp 4: {up_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        # 执行交易操作
                        self.amount_yes4_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()
                            
                        time.sleep(2)
                        if self.Verify_buy_yes():
                            self.yes4_amount = float(self.yes4_amount_entry.get())
                            self.yes4_shares = self.shares # 获取 YES4 的 shares
                            # 重置Yes4的价格为反水价格也就是 46 
                            self.yes4_price_entry.delete(0, tk.END)
                            self.yes4_price_entry.insert(0, str(self.default_sell_price_backwater)) # 设置为反水卖出价格也就是 46
                            self.yes4_price_entry.configure(foreground='red')

                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Up4",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Forth_trade执行BUY UP4成功\033[0m")
                            # 增加刷新,因为不刷新,POSITIONS 上不显示刚刚购买的
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Up4 交易失败,第{retry+1}次,等待2秒后重试")
                            time.sleep(2)  # 添加延时避免过于频繁的重试
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Buy Up4失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
                # 检查No4价格匹配
                elif 0 <= round((down_price - no4_price), 2) <= self.price_premium and (down_shares > self.bids_shares) and down_price > 50:
                    for retry in range(3):
                        self.logger.info(f"✅ \033[31mDown 4: {down_price}¢\033[0m 价格匹配,执行自动买入,第{retry+1}次尝试")
                        # 执行交易操作
                        self.buy_no_button.invoke()
                        time.sleep(0.5)
                        self.amount_no4_button.event_generate('<Button-1>')
                        time.sleep(0.5)
                        self.buy_confirm_button.invoke()
                        if self.find_accept_button():
                            self.entry_accept()
                            self.buy_confirm_button.invoke()
                            
                        # 点击 BUY_YES 按钮,目的是刷新页面,否则实时价格就不对了
                        self.buy_yes_button.invoke()

                        time.sleep(2)
                        if self.Verify_buy_no():
                            self.no4_shares = self.shares # 获取 NO4 的 shares
                            self.no4_amount = float(self.no4_amount_entry.get())
                            # 重置No4的价格为反水卖出价格也就是 46
                            self.no4_price_entry.delete(0, tk.END)
                            self.no4_price_entry.insert(0, str(self.default_sell_price_backwater)) # 设置为反水卖出价格也就是 46
                            self.no4_price_entry.configure(foreground='red')

                            # 增加交易次数
                            self.trade_count += 1
                            # 发送交易邮件
                            self.send_trade_email(
                                trade_type="Buy Down4",
                                price=self.price,
                                amount=self.amount,
                                shares=self.shares,
                                trade_count=self.trade_count,
                                cash_value=self.cash_value,
                                portfolio_value=self.portfolio_value
                            )
                            self.logger.info("\033[34m✅ Forth_trade执行BUY DOWN4成功\033[0m")
                            # 增加刷新,因为不刷新,POSITIONS 上不显示刚刚购买的
                            self.root.after(30000, lambda: self.driver.refresh())
                            break
                        else:
                            self.logger.warning(f"❌  Buy Down4 交易失败,第{retry+1}次,等待1秒后重试")
                            time.sleep(1)  # 添加延时避免过于频繁的重试
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Buy Down4失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.trade_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )   
            
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Forth_trade执行失败: {str(e)}")  
        finally:
            self.trading = False
       
    def Sell_yes(self, up_price, down_price, up_shares, down_shares):
        """当YES5价格等于实时Yes价格时自动卖出"""
        try:
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
              
            if up_price is not None and down_price is not None and up_shares is not None and down_shares is not None:
                
                # 获取Up5价格
                up5_price = float(self.yes5_price_entry.get())
                up4_price = float(self.yes4_price_entry.get())
                up3_price = float(self.yes3_price_entry.get())
                up2_price = float(self.yes2_price_entry.get())
                up1_price = float(self.yes1_price_entry.get())
                self.trading = True  # 开始交易

                price_diff = round(up_price - up5_price, 2) # 47-47=0;;46-47=-1;

                # 增加一个当 YES1==99 时,自动卖出 YES1 的shares
                if (10 <= up1_price <= 46) and (-2 <= up_price - up1_price <= 1) and (up_shares > self.asks_shares):
                    self.logger.info(f"✅ \033[31mUp 1: {up_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"✅ 执行自动卖出UP1,第{retry+1}次尝试")
                        try:
                            # 卖出 UP1 的shares
                            self.position_sell_yes_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.yes1_shares
                                amount_input.send_keys(str(self.yes1_shares))

                            time.sleep(0.5)
                            # 第三步:点击sell_confirm_button
                            self.sell_confirm_button.invoke()
                            if self.find_accept_button():
                                self.entry_accept()
                                self.sell_confirm_button.invoke()

                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)

                                if self.Verify_sold_yes():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    
                                    # 设置 YES1 价格为0
                                    self.yes1_price_entry.delete(0, tk.END)
                                    self.yes1_price_entry.insert(0, "0")
                                    self.yes1_price_entry.configure(foreground='black')

                                    # 设置 YES5 价格为 0  
                                    self.yes5_price_entry.delete(0, tk.END)
                                    self.yes5_price_entry.insert(0, "0")
                                    self.yes5_price_entry.configure(foreground='black')

                                    # 设置 NO5 价格为 0  
                                    self.no5_price_entry.delete(0, tk.END)
                                    self.no5_price_entry.insert(0, "0")
                                    self.no5_price_entry.configure(foreground='black')

                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell Yes1",
                                        price=up_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell Yes1 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell Yes1失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )

                # 增加一个当 YES2==46 时,自动卖出 YES2 的shares
                elif (10 <= up2_price <= 46) and (-2 <= up_price - up2_price <= 1) and (up_shares > self.asks_shares):
                    self.logger.info(f"✅ \033[31mUp 2: {up_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出UP2,第{retry+1}次尝试")
                        try:
                            # 卖出 UP2 的shares
                            self.position_sell_yes_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.yes2_shares
                                amount_input.send_keys(str(self.yes2_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()

                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)

                                if self.Verify_sold_yes():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    # 设置 NO1 价格为反水卖出价格
                                    self.no1_price_entry.delete(0, tk.END)
                                    self.no1_price_entry.insert(0, str(self.default_sell_price_backwater))
                                    self.no1_price_entry.configure(foreground='red')  # 添加红色设置
                                    
                                    # 设置 YES2 价格为0
                                    self.yes2_price_entry.delete(0, tk.END)
                                    self.yes2_price_entry.insert(0, "0")
                                    self.yes2_price_entry.configure(foreground='black')  

                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell Yes2",
                                        price=up_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell Yes2 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell Yes2失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )

                # 增加一个当 YES3==46 时,自动卖出 YES3 的shares
                elif (10 <= up3_price <= 46) and (-2 <= up_price - up3_price <= 1) and (up_shares > self.asks_shares):
                    self.logger.info(f"✅ \033[31mUp 3: {up_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出UP3,第{retry+1}次尝试")
                        try:
                            # 卖出 UP3 的shares
                            self.position_sell_yes_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.yes3_shares
                                amount_input.send_keys(str(self.yes3_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()
                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)

                                if self.Verify_sold_yes():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    # 设置 NO2 价格为反水卖出价格
                                    self.no2_price_entry.delete(0, tk.END)
                                    self.no2_price_entry.insert(0, str(self.default_sell_price_backwater))
                                    self.no2_price_entry.configure(foreground='red')  # 添加红色设置
                                    
                                    # 设置 YES3 价格为0
                                    self.yes3_price_entry.delete(0, tk.END)
                                    self.yes3_price_entry.insert(0, "0")
                                    self.yes3_price_entry.configure(foreground='black')  

                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell Yes3",
                                        price=up_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell Yes3 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell Yes3失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )

                # 增加一个当 YES4==46 时,自动卖出 YES4 的shares
                elif (10 <= up4_price <= 46) and (-2 <= up_price - up4_price <= 1) and (up_shares > self.asks_shares):
                    self.logger.info(f"✅ \033[31mUp 4: {up_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出UP4,第{retry+1}次尝试")
                        try:
                            # 卖出 UP4 的shares
                            self.position_sell_yes_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.yes4_shares
                                amount_input.send_keys(str(self.yes4_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()
                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)

                                if self.Verify_sold_yes():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    
                                    # 设置 NO3 价格为反水卖出价格
                                    self.no3_price_entry.delete(0, tk.END)
                                    self.no3_price_entry.insert(0, str(self.default_sell_price_backwater))
                                    self.no3_price_entry.configure(foreground='red')  # 添加红色设置
                                    
                                    # 设置 YES4 价格为0
                                    self.yes4_price_entry.delete(0, tk.END)
                                    self.yes4_price_entry.insert(0, "0")
                                    self.yes4_price_entry.configure(foreground='black')  

                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell Yes4",
                                        price=up_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell Yes4 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell Yes4失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )

                elif up5_price >= 70 and 0 <= price_diff <= 1 and (up_shares > self.asks_shares):
                    self.logger.info(f"✅ \033[32mUp 5: {up_price}¢\033[0m 价格匹配,执行自动卖出")
   
                    for retry in range(3):
                        self.logger.info(f"执行自动卖出UP5==99,第{retry+1}次尝试")
                        try:
                            # 执行卖出YES操作
                            self.only_sell_yes()
                            
                            self.logger.info("卖完 Up 后，再卖 Down")
                            # 卖 Down 之前先检查是否有 Down 标签
                            if self.find_position_label_no():
                                self.only_sell_no()
                                
                            # 重置所有价格
                            for i in range(1,6):  # 1-5
                                yes_entry = getattr(self, f'yes{i}_price_entry', None)
                                no_entry = getattr(self, f'no{i}_price_entry', None)

                                if yes_entry:
                                    yes_entry.delete(0, tk.END)
                                    yes_entry.insert(0, "0")
                                    yes_entry.configure(foreground='black')
                                if no_entry:
                                    no_entry.delete(0, tk.END)
                                    no_entry.insert(0, "0")
                                    no_entry.configure(foreground='black')

                            # 设置 YES1 和 NO1 价格为默认值
                            self.set_yes1_no1_default_target_price()

                            break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell Yes5=99 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell Yes5==99 失败",
                            price=up_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
                    
        except Exception as e:
            self.logger.error(f"❌ Sell_yes执行失败: {str(e)}")
            
        finally:
            self.trading = False
       
    def Sell_no(self, up_price, down_price, up_shares, down_shares):
        """当NO4价格等于实时No价格时自动卖出"""    
        try:
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
            
            if up_price is not None and down_price is not None and up_shares is not None and down_shares is not None:
                # 获取价格
                down5_price = float(self.no5_price_entry.get())
                down3_price = float(self.no3_price_entry.get())
                down4_price = float(self.no4_price_entry.get())
                down2_price = float(self.no2_price_entry.get())
                down1_price = float(self.no1_price_entry.get())
                self.trading = True  # 开始交易
                price_diff = round(down_price - down5_price, 2)

                # 增加一个当 NO1==46 时,自动卖出 NO1 的金额 
                if (10 <= down1_price <= 46) and (-2 <= down_price - down1_price <= 1) and (down_shares > self.bids_shares):
                    self.logger.info(f"✅ \033[31mDown 1: {down_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出DOWN1,第{retry+1}次尝试")
                        try:
                            # 卖出 DOWN1 的shares
                            self.position_sell_no_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.no1_shares
                                amount_input.send_keys(str(self.no1_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()
                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)
                                if self.Verify_sold_no():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    # 设置 NO1 价格为0
                                    self.no1_price_entry.delete(0, tk.END)
                                    self.no1_price_entry.insert(0, "0")
                                    self.no1_price_entry.configure(foreground='black')  

                                    # 设置 NO5 价格为 0  
                                    self.no5_price_entry.delete(0, tk.END)
                                    self.no5_price_entry.insert(0, "0")
                                    self.no5_price_entry.configure(foreground='black')

                                    # 设置 YES5 价格为 0  
                                    self.yes5_price_entry.delete(0, tk.END)
                                    self.yes5_price_entry.insert(0, "0")
                                    self.yes5_price_entry.configure(foreground='black')

                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell No1",
                                        price=down_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell No1 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell No1失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
            
                # 增加一个当 NO1==46 时,自动卖出 NO1 的金额 
                elif (10 <= down2_price <= 46) and (-2 <= down_price - down2_price <= 1) and (down_shares > self.bids_shares):
                    self.logger.info(f"✅ \033[31mDown 2: {down_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出DOWN2,第{retry+1}次尝试")
                        try:
                            # 卖出 DOWN2 的shares
                            self.position_sell_no_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.no2_shares
                                amount_input.send_keys(str(self.no2_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()
                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)
                                if self.Verify_sold_no():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    # 设置 YES1 价格为反水卖出价格
                                    self.yes1_price_entry.delete(0, tk.END)
                                    self.yes1_price_entry.insert(0, str(self.default_sell_price_backwater))
                                    self.yes1_price_entry.configure(foreground='red')  # 添加红色设置
                                    
                                    # 设置 NO2 价格为0
                                    self.no2_price_entry.delete(0, tk.END)
                                    self.no2_price_entry.insert(0, "0")
                                    self.no2_price_entry.configure(foreground='black')  
                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell No2",
                                        price=down_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell No2 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell No2失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )

                # 增加一个当 NO3==46 时,自动卖出 NO3 的金额 
                elif (10 <= down3_price <= 46) and (-2 <= down_price - down3_price <= 1) and (down_shares > self.bids_shares):
                    self.logger.info(f"✅ \033[31mDown 3: {down_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出DOWN3,第{retry+1}次尝试")
                        try:
                            # 卖出 DOWN3 的shares
                            self.position_sell_no_button.invoke()
                            time.sleep(0.5)
                            # 找到输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.no3_shares
                                amount_input.send_keys(str(self.no3_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()
                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)
                                if self.Verify_sold_no():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    # 设置 YES2 价格为反水卖出价格
                                    self.yes2_price_entry.delete(0, tk.END)
                                    self.yes2_price_entry.insert(0, str(self.default_sell_price_backwater))
                                    self.yes2_price_entry.configure(foreground='red')  # 添加红色设置
                                    
                                    # 设置 NO3 价格为0
                                    self.no3_price_entry.delete(0, tk.END)
                                    self.no3_price_entry.insert(0, "0")
                                    self.no3_price_entry.configure(foreground='black')  
                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell No3",
                                        price=down_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell No3 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell No3失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )

                # 增加一个当 NO4==46 时,自动卖出 NO4 的金额 
                elif (10 <= down4_price <= 46) and (-2 <= down_price - down4_price <= 1) and (down_shares > self.bids_shares):
                    self.logger.info(f"✅ \033[31mDown 4: {down_price}¢\033[0m 价格匹配,执行自动卖出")

                    for retry in range(3):
                        self.logger.info(f"执行自动卖出DOWN4,第{retry+1}次尝试")
                        try:
                            # 卖出 DOWN4 的shares
                            self.position_sell_no_button.invoke()
                            time.sleep(0.5)
                            # 找到amount输入框
                            try:
                                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
                            except (NoSuchElementException, StaleElementReferenceException):
                                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

                            if amount_input:
                                # 先清除 AMOUNT 输入框
                                amount_input.clear()
                                time.sleep(0.5)
                                # 然后输入 self.no4_shares
                                amount_input.send_keys(str(self.no4_shares))

                                time.sleep(0.5)
                                # 第三步:点击sell_confirm_button
                                self.sell_confirm_button.invoke()
                                if self.find_accept_button():
                                    self.entry_accept()
                                    self.sell_confirm_button.invoke()
                                time.sleep(0.5)
                                # 第四步:刷新页面
                                self.driver.refresh()
                                time.sleep(2)

                                if self.Verify_sold_no():
                                    # 增加交易次数
                                    self.sell_count += 1
                                    # 更新 GUI 上的交易次数
                                    self.reset_count_label.config(text=str(self.sell_count))
                                    # 设置 YES3 价格为反水卖出价格
                                    self.yes3_price_entry.delete(0, tk.END)
                                    self.yes3_price_entry.insert(0, str(self.default_sell_price_backwater))
                                    self.yes3_price_entry.configure(foreground='red')  # 添加红色设置
                                    
                                    # 设置 NO4 价格为0
                                    self.no4_price_entry.delete(0, tk.END)
                                    self.no4_price_entry.insert(0, "0")
                                    self.no4_price_entry.configure(foreground='black')  
                                    # 发送交易邮件
                                    self.send_trade_email(
                                        trade_type="Sell No4",
                                        price=down_price,
                                        amount=0,
                                        shares=0,
                                        trade_count=self.sell_count,
                                        cash_value=self.cash_value,
                                        portfolio_value=self.portfolio_value
                                    )
                                    break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell No4 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell No4失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
                
                elif down5_price >= 70 and (0 <= price_diff <= 1) and (down_shares > self.bids_shares):
                    self.logger.info(f"✅ \033[31mDown 5: {down_price}¢\033[0m 价格匹配,执行自动卖出")
                    
                    for retry in range(3):
                        self.logger.info(f"执行自动卖出DOWN5,第{retry+1}次尝试")
                        try:
                            # 先卖 Down                      
                            self.only_sell_no()
                            
                            # 再卖 Up
                            if self.find_position_label_yes():
                                self.only_sell_yes()
                                
                            # 重置所有价格
                            for i in range(1,6):  # 1-5
                                yes_entry = getattr(self, f'yes{i}_price_entry', None)
                                no_entry = getattr(self, f'no{i}_price_entry', None)
                                if yes_entry:
                                    yes_entry.delete(0, tk.END)
                                    yes_entry.insert(0, "0")
                                    yes_entry.configure(foreground='black')
                                if no_entry:
                                    no_entry.delete(0, tk.END)
                                    no_entry.insert(0, "0")
                                    no_entry.configure(foreground='black')

                            # 设置 YES1 和 NO1 价格为默认值
                            self.set_yes1_no1_default_target_price()
                            
                            break
                        except Exception as e:
                            self.logger.warning(f"❌ Sell No5 第{retry+1}次失败: {str(e)}")
                            if retry < 2:
                                time.sleep(1)
                    else:
                        # 3次失败后发邮件
                        self.send_trade_email(
                            trade_type="Sell No5失败",
                            price=down_price,
                            amount=0,
                            shares=0,
                            trade_count=self.sell_count,
                            cash_value=self.cash_value,
                            portfolio_value=self.portfolio_value
                        )
                
        except Exception as e:
            self.logger.error(f"❌ Sell_no执行失败: {str(e)}")
            
        finally:
            self.trading = False

    def only_sell_yes(self):
        """只卖出YES,且验证交易是否成功"""
        # 重试 3 次
        for retry in range(4):
            self.logger.info("\033[32m执行only_sell_yes\033[0m")
            self.position_sell_yes_button.invoke()
            time.sleep(0.5)
            self.sell_confirm_button.invoke()
            time.sleep(0.5)
            if self.find_accept_button():
                self.entry_accept()
                self.sell_confirm_button.invoke()

            if self._verify_trade('Sold', 'Up')[0]:
                # 增加卖出计数
                self.sell_count += 1
                # 发送交易邮件 - 卖出YES
                self.send_trade_email(
                    trade_type="Sell Up",
                    price=self.price,
                    amount=self.amount,
                    shares=self.shares,
                    trade_count=self.sell_count,
                    cash_value=self.cash_value,
                    portfolio_value=self.portfolio_value
                )
                self.logger.info(f"卖出 Up 成功")
                self.driver.refresh()
                break
            else:
                self.logger.warning(f"❌ 卖出only_sell_yes第{retry+1}次验证失败,重试")
                time.sleep(1)
      
    def only_sell_no(self):
        """只卖出Down,且验证交易是否成功"""
        # 重试 3 次
        for retry in range(3): 
            self.logger.info("\033[32m执行only_sell_no\033[0m")
            self.position_sell_no_button.invoke()
            time.sleep(0.5)
            self.sell_confirm_button.invoke()
            time.sleep(0.5)
            if self.find_accept_button():
                self.entry_accept()
                self.sell_confirm_button.invoke()

            if self._verify_trade('Sold', 'Down')[0]:
                # 增加卖出计数
                self.sell_count += 1
                
                # 发送交易邮件 - 卖出NO
                self.send_trade_email(
                    trade_type="Sell Down",
                    price=self.price,
                    amount=self.amount,
                    shares=self.shares,
                    trade_count=self.sell_count,
                    cash_value=self.cash_value,
                    portfolio_value=self.portfolio_value
                )
                self.logger.info(f"卖出 Down 成功")
                self.driver.refresh()
                break
            else:
                self.logger.warning(f"❌ 卖出only_sell_no第{retry+1}次验证失败,重试")
                time.sleep(1)

    def Verify_buy_yes(self):
        """
        验证买入YES交易是否成功完成
        
        Returns:
            bool: 交易是否成功
        """
        return self._verify_trade('Bought', 'Up')[0]
        
    def Verify_buy_no(self):
        """
        验证买入NO交易是否成功完成
        
        Returns:
            bool: 交易是否成功
        """
        return self._verify_trade('Bought', 'Down')[0]
    
    def Verify_sold_yes(self):
        """
        验证卖出YES交易是否成功完成
        
        Returns:
            bool: 交易是否成功
        """
        return self._verify_trade('Sold', 'Up')[0]
        
    def Verify_sold_no(self):
        """
        验证卖出NO交易是否成功完成
        
        Returns:
            bool: 交易是否成功
        """
        return self._verify_trade('Sold', 'Down')[0]

    def _verify_trade(self, action_type, direction):
        """
        验证交易是否成功完成
        基于时间的循环:在6秒时间窗口内不断查找,时间到了就刷新,循环2次
        
        Args:
            action_type: 'Bought' 或 'Sold'
            direction: 'Up' 或 'Down'
            
        Returns:
            tuple: (是否成功, 价格, 金额)
        """
        try:
            for attempt in range(2):
                self.logger.info(f"开始第{attempt + 1}次验证尝试（基于次数重试）")
                # 检查 4次,每次等待1秒检查交易记录
                max_retries = 3  # 最大重试次数
                wait_interval = 1  # 检查间隔
                
                for retry in range(max_retries):
                    self.logger.info(f"第{retry + 1}次检查交易记录（共{max_retries}次）")
                    
                    try:
                        # 等待历史记录元素出现                  
                        try:
                            # 将元素查找超时时间从默认值减少到0.5秒，加快查找速度
                            history_element = WebDriverWait(self.driver, 0.5).until(
                                EC.presence_of_element_located((By.XPATH, XPathConfig.HISTORY[0]))
                            )
                        except (NoSuchElementException, StaleElementReferenceException, TimeoutException):
                            # 将重试查找超时时间从2秒减少到0.5秒
                            history_element = self._find_element_with_retry(XPathConfig.HISTORY, timeout=0.5, silent=True)
                        
                        if history_element:
                            # 获取历史记录文本
                            history_text = history_element.text
                            self.logger.info(f"找到交易记录: \033[34m{history_text}\033[0m")
                            
                            # 分别查找action_type和direction，避免同时匹配导致的问题
                            action_found = re.search(rf"\b{action_type}\b", history_text, re.IGNORECASE)
                            direction_found = re.search(rf"\b{direction}\b", history_text, re.IGNORECASE)
                            
                            if action_found and direction_found:
                                # 提取价格和金额 - 优化正则表达式
                                price_match = re.search(r'at\s+(\d+\.?\d*)¢', history_text)
                                amount_match = re.search(r'\(\$(\d+\.\d+)\)', history_text)
                                # 提取SHARES - shares是Bought/Sold后的第一个数字
                                shares_match = re.search(r'(?:Bought|Sold)\s+(\d+(?:\.\d+)?)', history_text, re.IGNORECASE)
                                
                                self.price = float(price_match.group(1)) if price_match else 0
                                self.amount = float(amount_match.group(1)) if amount_match else 0
                                # shares可能是浮点数，先转为float再转为int
                                self.shares = int(float(shares_match.group(1))) if shares_match else 0

                                self.logger.info(f"✅ \033[31m交易验证成功: {action_type} {direction} 价格: {self.price} 金额: {self.amount} Shares: {self.shares}\033[0m")
                                return True, self.price, self.amount, self.shares
                    
                    except StaleElementReferenceException:
                        self.logger.warning(f"检测到stale element错误,重新定位元素（第{retry + 1}次重试）")
                        continue  # 继续下一次重试，不退出循环
                    except Exception as e:
                        self.logger.warning(f"元素操作异常: {str(e)}")
                        continue
                    
                    # 如果不是最后一次重试，等待1秒后继续
                    if retry < max_retries - 1:
                        
                        time.sleep(wait_interval)
                    
                # 4次重试结束，刷新页面
                # self.logger.info(f"第{attempt + 1}次尝试的4次重试结束,刷新页面")
                self.driver.refresh()
                time.sleep(2)  # 刷新后等待页面加载
            
            # 超时未找到匹配的交易记录
            self.logger.warning(f"❌ 交易验证失败: 未找到 {action_type} {direction} (已尝试2轮,每轮4次重试)")
            return False, 0, 0
                
        except Exception as e:
            self.logger.error(f"交易验证失败: {str(e)}")
            return False, 0, 0

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
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)

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
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)

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
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
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
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
            # 查找买按钮
            try:
                button = self.driver.find_element(By.XPATH, XPathConfig.BUY_BUTTON[0])
            except (NoSuchElementException, StaleElementReferenceException):
                button = self._find_element_with_retry(XPathConfig.BUY_BUTTON, timeout=2, silent=True)

            button.click()
            
        except Exception as e:
            self.logger.error(f"点击 Buy 按钮失败: {str(e)}")

    def click_buy_yes(self):
        """点击 Buy-Yes 按钮"""
        try:
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
            
            # 查找买YES按钮
            try:
                button = self.driver.find_element(By.XPATH, XPathConfig.BUY_YES_BUTTON[0])
            except (NoSuchElementException, StaleElementReferenceException):
                button = self._find_element_with_retry(XPathConfig.BUY_YES_BUTTON, timeout=2, silent=True)
                
            button.click()
            
        except Exception as e:
            self.logger.error(f"点击 Buy-Yes 按钮失败: {str(e)}")

    def click_buy_no(self):
        """点击 Buy-No 按钮"""
        try:
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
            # 查找买NO按钮
            try:
                button = self.driver.find_element(By.XPATH, XPathConfig.BUY_NO_BUTTON[0])
            except (NoSuchElementException, StaleElementReferenceException):
                button = self._find_element_with_retry(XPathConfig.BUY_NO_BUTTON, timeout=2, silent=True)
                
            button.click()
            
        except Exception as e:
            self.logger.error(f"点击 Buy-No 按钮失败: {str(e)}")

    def click_amount(self, event=None):
        """点击 Amount 按钮并输入数量"""
        try:
            if not self.driver and not self.is_restarting:
                self.restart_browser(force_restart=True)
            
            # 获取触发事件的按钮
            button = event.widget if event else self.amount_button
            button_text = button.cget("text")

            # 找到输入框
            try:
                amount_input = self.driver.find_element(By.XPATH, XPathConfig.AMOUNT_INPUT[0])
            except (NoSuchElementException, StaleElementReferenceException):
                amount_input = self._find_element_with_retry(XPathConfig.AMOUNT_INPUT, timeout=2, silent=True)

            # 清空输入框
            amount_input.clear()
            # 根据按钮文本获取对应的金额
            if button_text == "Amount-Up1":
                amount = self.yes1_amount_entry.get()
            elif button_text == "Amount-Up2":
                yes2_amount_entry = self.yes_frame.grid_slaves(row=3, column=1)[0]
                amount = yes2_amount_entry.get()
            elif button_text == "Amount-Up3":
                yes3_amount_entry = self.yes_frame.grid_slaves(row=5, column=1)[0]
                amount = yes3_amount_entry.get()
            elif button_text == "Amount-Up4":
                yes4_amount_entry = self.yes_frame.grid_slaves(row=7, column=1)[0]
                amount = yes4_amount_entry.get()
            
            # No 按钮
            elif button_text == "Amount-Down1":
                no1_amount_entry = self.no_frame.grid_slaves(row=1, column=1)[0]
                amount = no1_amount_entry.get()
            elif button_text == "Amount-Down2":

                no2_amount_entry = self.no_frame.grid_slaves(row=3, column=1)[0]
                amount = no2_amount_entry.get()
            elif button_text == "Amount-Down3":
                no3_amount_entry = self.no_frame.grid_slaves(row=5, column=1)[0]
                amount = no3_amount_entry.get()
            elif button_text == "Amount-Down4":
                no4_amount_entry = self.no_frame.grid_slaves(row=7, column=1)[0]
                amount = no4_amount_entry.get()
            else:
                amount = "0"
            # 输入金额
            amount_input.send_keys(str(amount))
              
        except Exception as e:
            self.logger.error(f"Amount操作失败: {str(e)}")
    
    def close_windows(self):
        """关闭多余窗口"""
        try:
            # 检查浏览器是否可用
            if not self.driver:
                self.logger.warning("浏览器驱动不可用，跳过窗口关闭")
                return
                
            # 检查并关闭多余的窗口，只保留一个
            all_handles = self.driver.window_handles
            
            if len(all_handles) > 1:
                # self.logger.info(f"当前窗口数: {len(all_handles)}，准备关闭多余窗口")
                
                # 获取目标URL
                target_url = self.url_entry.get() if hasattr(self, 'url_entry') else None
                target_handle = None
                
                # 查找包含目标URL的窗口
                if target_url:
                    for handle in all_handles:
                        try:
                            self.driver.switch_to.window(handle)
                            current_url = self.driver.current_url
                            # 检查当前窗口是否包含目标URL的关键部分
                            if target_url in current_url or any(key in current_url for key in ['polymarket.com/event', 'up-or-down-on']):
                                target_handle = handle
                                break
                        except Exception as e:
                            self.logger.warning(f"检查窗口URL失败: {e}")
                            continue
                
                # 如果没有找到目标窗口，使用最后一个窗口作为备选
                if not target_handle:
                    target_handle = all_handles[-1]
                    self.logger.warning("未找到目标URL窗口,使用最后一个窗口")
                
                # 关闭除了目标窗口外的所有窗口
                for handle in all_handles:
                    if handle != target_handle:
                        try:
                            self.driver.switch_to.window(handle)
                            self.driver.close()
                        except Exception as e:
                            self.logger.warning(f"关闭窗口失败: {e}")
                            continue
                
                # 切换到保留的目标窗口
                try:
                    self.driver.switch_to.window(target_handle)
                    self.logger.info(f"✅ 已保留目标窗口，关闭了 {len(all_handles)-1} 个多余窗口")
                except Exception as e:
                    self.logger.warning(f"切换到目标窗口失败: {e}")
                
            else:
                self.logger.warning("❗ 当前窗口数不足2个,无需切换")
                
        except Exception as e:
            self.logger.error(f"关闭窗口操作失败: {e}")
            # 如果窗口操作失败，可能是浏览器会话已失效，不需要重启浏览器
            # 因为调用此方法的上层代码通常会处理浏览器重启

    def send_trade_email(self, trade_type, price, amount, shares, trade_count,
                         cash_value, portfolio_value):
        """发送交易邮件"""
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                hostname = socket.gethostname()
                sender = 'huacaihuijin@126.com'
                
                # 根据HOSTNAME决定邮件接收者
                receivers = ['2049330@qq.com']  # 默认接收者，必须接收所有邮件
                if 'ZZY' in hostname:
                    receivers.append('2049330@qq.com')  # 如果HOSTNAME包含ZZY，添加QQ邮箱 # 272763832@qq.com
                
                app_password = 'PUaRF5FKeKJDrYH7'  # 有效期 180 天，请及时更新，下次到期日 2025-11-29
                
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
                msg['To'] = ', '.join(receivers)

                # 修复格式化字符串问题，确保cash_value和portfolio_value是字符串
                str_cash_value = str(cash_value)
                str_portfolio_value = str(portfolio_value)
                
                content = f"""
                交易价格: {price:.2f}¢
                交易金额: ${amount:.2f}
                SHARES: {shares}
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
                    server.sendmail(sender, receivers, msg.as_string())
                    self.logger.info(f"✅ \033[34m邮件发送成功: {trade_type} -> {', '.join(receivers)}\033[0m")
                    return  # 发送成功,退出重试循环
                except Exception as e:
                    self.logger.error(f"❌ SMTP操作失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                finally:
                    try:
                        server.quit()
                    except Exception:
                        pass          
            except Exception as e:
                self.logger.error(f"❌ 邮件准备失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)     
        # 所有重试都失败
        error_msg = f"发送邮件失败,已重试{max_retries}次"
        self.logger.error(error_msg)

    def _send_chrome_alert_email(self):
        """发送Chrome异常警报邮件"""
        try:
            hostname = socket.gethostname()
            sender = 'huacaihuijin@126.com'
            receiver = 'huacaihuijin@126.com'
            app_password = 'PUaRF5FKeKJDrYH7'
            
            # 获取交易币对信息
            full_pair = self.trading_pair_label.cget("text")
            trading_pair = full_pair.split('-')[0] if full_pair and '-' in full_pair else "未知交易币对"
            
            msg = MIMEMultipart()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            subject = f'🚨{hostname}-Chrome异常-{trading_pair}-需要手动介入'
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = sender
            msg['To'] = receiver
            
            # 获取当前状态信息
            try:
                cash_value = self.cash_label.cget("text")
                portfolio_value = self.portfolio_label.cget("text")
            except:
                cash_value = "无法获取"
                portfolio_value = "无法获取"
            
            content = f"""
            🚨 Chrome浏览器异常警报 🚨

            异常时间: {current_time}
            主机名称: {hostname}
            交易币对: {trading_pair}
            当前买入次数: {self.trade_count}
            当前卖出次数: {self.sell_count}
            重启次数: {self.reset_trade_count}
            当前 CASH 值: {cash_value}
            当前 PORTFOLIO 值: {portfolio_value}

            ⚠️  请立即手动检查并介入处理！
            """
            
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP_SSL('smtp.126.com', 465, timeout=5)
            server.set_debuglevel(0)
            
            try:
                server.login(sender, app_password)
                server.sendmail(sender, receiver, msg.as_string())
                self.logger.info(f"✅ Chrome异常警报邮件发送成功")
            except Exception as e:
                self.logger.error(f"❌ Chrome异常警报邮件发送失败: {str(e)}")
            finally:
                try:
                    server.quit()
                except Exception:
                    pass
                    
        except Exception as e:
            self.logger.error(f"发送Chrome异常警报邮件时出错: {str(e)}")

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

    def find_position_label_yes(self):
        """查找Yes持仓标签"""
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not self.driver and not self.is_restarting:
                    self.restart_browser(force_restart=True)
                    
                # 等待页面加载完成
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # 尝试获取Up标签
                try:
                    position_label_up = None
                    try:
                        position_label_up = self.driver.find_element(By.XPATH, XPathConfig.POSITION_UP_LABEL[0])
                    except (NoSuchElementException, StaleElementReferenceException):
                        position_label_up = self._find_element_with_retry(XPathConfig.POSITION_UP_LABEL, timeout=3, silent=True)
                        
                    if position_label_up is not None and position_label_up:
                        self.logger.info("✅ find-element,找到了Up持仓标签: {position_label_up.text}")
                        return True
                    else:
                        self.logger.info("❌ find_element,未找到Up持仓标签")
                        return False
                except NoSuchElementException:
                    position_label_up = self._find_element_with_retry(XPathConfig.POSITION_UP_LABEL, timeout=3, silent=True)
                    if position_label_up is not None and position_label_up:
                        self.logger.info(f"✅ with-retry,找到了Up持仓标签: {position_label_up.text}")
                        return True
                    else:
                        self.logger.info("❌ use with-retry,未找到Up持仓标签")
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
                if not self.driver and not self.is_restarting:
                    self.restart_browser(force_restart=True)
                    
                # 等待页面加载完成
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # 尝试获取Down标签
                try:
                    position_label_down = None
                    try:
                        position_label_down = self.driver.find_element(By.XPATH, XPathConfig.POSITION_DOWN_LABEL[0])
                    except (NoSuchElementException, StaleElementReferenceException):
                        position_label_down = self._find_element_with_retry(XPathConfig.POSITION_DOWN_LABEL, timeout=3, silent=True)
                        
                    if position_label_down is not None and position_label_down:
                        self.logger.info(f"✅ find-element,找到了Down持仓标签: {position_label_down.text}")
                        return True
                    else:
                        self.logger.info("❌ find-element,未找到Down持仓标签")
                        return False
                except NoSuchElementException:
                    position_label_down = self._find_element_with_retry(XPathConfig.POSITION_DOWN_LABEL, timeout=3, silent=True)
                    if position_label_down is not None and position_label_down:
                        self.logger.info(f"✅ with-retry,找到了Down持仓标签: {position_label_down.text}")
                        return True
                    else:
                        self.logger.info("❌ with-retry,未找到Down持仓标签")
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
                    # 使用presence_of_element_located而不是element_to_be_clickable以减少等待时间
                    # element_to_be_clickable需要额外检查元素是否可见且可交互
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
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

    def schedule_price_setting(self):
        """安排每天指定时间执行价格设置"""
        now = datetime.now()
        
        # 从GUI获取选择的时间
        selected_time = self.auto_find_time_combobox.get()
        hour = int(selected_time.split(':')[0])
        
        # 计算下一个指定时间的时间点（在选择时间的02分执行）
        next_run = now.replace(hour=hour, minute=2, second=0, microsecond=0)
        
        # 如果当前时间已经超过了今天的指定时间，则直接安排到明天
        # 为了确保绝对不会在同一天重复执行，我们检查当前时间是否已经过了指定的小时
        if now.hour >= hour:
            next_run += timedelta(days=1)
        
        # 计算等待时间(毫秒)
        wait_time = (next_run - now).total_seconds() * 1000
        wait_time_hours = wait_time / 3600000
        
        # 设置定时器
        self.set_yes1_no1_default_target_price_timer = self.root.after(int(wait_time), lambda: self.set_yes1_no1_default_target_price())
        self.logger.info(f"✅ \033[34m{round(wait_time_hours,2)}\033[0m小时后开始设置 YES1/NO1 价格为52")

    def on_auto_find_time_changed(self, event=None):
        """当时间选择改变时的处理函数"""
        # 保存新的时间设置到配置文件
        self.save_config()
        
        if hasattr(self, 'set_yes1_no1_default_target_price_timer') and self.set_yes1_no1_default_target_price_timer:
            # 取消当前的定时器
            self.root.after_cancel(self.set_yes1_no1_default_target_price_timer)
            self.logger.info("🔄 设置 YES1/NO1 价格时间已更改，重新安排定时任务")
            # 使用新的时间设置重新安排定时任务，确保使用正确的时间计算
            self.schedule_price_setting()
    
    def set_yes1_no1_default_target_price(self):
        """设置默认目标价格52"""
        self.yes1_price_entry.delete(0, tk.END)
        self.yes1_price_entry.insert(0, "52")
        self.yes1_price_entry.configure(foreground='red')

        self.no1_price_entry.delete(0, tk.END)
        self.no1_price_entry.insert(0, "52")
        self.no1_price_entry.configure(foreground='red')
        self.logger.info(f"\033[34m✅ 设置买入价格52成功\033[0m")
        self.close_windows()
        
        # 价格设置完成后，重新安排下一次的价格设置定时任务
        # 使用schedule_price_setting确保与GUI时间选择保持一致
        self.logger.info("🔄 价格设置完成，重新安排下一次定时任务")
        self.schedule_price_setting()
        
    def on_coin_changed(self, event=None):
        """当币种选择改变时的处理函数"""
        # 保存新的币种选择到配置文件
        self.save_config()
        selected_coin = self.coin_combobox.get()
        self.logger.info(f"💰 币种选择已更改为: {selected_coin}")

    def schedule_auto_find_coin(self):
        """安排每天指定时间执行自动找币"""
        now = datetime.now()
        self.logger.info(f"当前时间: {now}")
        # 计算下一个指定时间的时间点
        next_run = now.replace(hour=0, minute=6, second=0, microsecond=0)
        self.logger.info(f"自动找币下次执行时间: {next_run}")
        if now >= next_run:
            next_run += timedelta(days=1)
        
        # 计算等待时间(毫秒)
        wait_time = (next_run - now).total_seconds() * 1000
        wait_time_hours = wait_time / 3600000
        
        # 设置定时器
        selected_coin = self.coin_combobox.get()
        self.schedule_auto_find_coin_timer = self.root.after(int(wait_time), lambda: self.find_54_coin(selected_coin))
        self.logger.info(f"✅ \033[34m{round(wait_time_hours,2)}\033[0m小时后,开始自动找币")
        
    def find_54_coin(self, coin_type, retry_count=0):
        """自动找币"""
        self.logger.info("✅ 开始自动找币")

        # 设置 YES1/NO1价格为 0
        self.yes1_price_entry.configure(foreground='black')
        self.yes1_price_entry.delete(0, tk.END)
        self.yes1_price_entry.insert(0, "0")
        self.no1_price_entry.configure(foreground='black')
        self.no1_price_entry.delete(0, tk.END)
        self.no1_price_entry.insert(0, "0")

        if retry_count > 0:
            self.logger.info(f"这是第 {retry_count}/5 次重试")
            
        try:
            # 检查浏览器状态，如果为None则尝试重启
            if self.driver is None:
                self.logger.warning("浏览器未初始化，尝试重启...")
                if not self.restart_browser(force_restart=True):
                    self.logger.error("浏览器重启失败，无法执行自动找币")
                    return
            
            # 验证浏览器连接是否正常
            try:
                self.driver.execute_script("return navigator.userAgent")
            except Exception as e:
                self.logger.warning(f"浏览器连接异常: {e}，尝试重启...")
                if not self.restart_browser(force_restart=True):
                    self.logger.error("浏览器重启失败，无法执行自动找币")
                    return
            
            self.stop_url_monitoring()
            self.stop_refresh_page()
            # 保存原始窗口句柄，确保在整个过程中有一个稳定的引用
            self.original_window = self.driver.current_window_handle
            
            # 设置搜索关键词
            coins = [coin_type]
            for coin in coins:
                try:  # 为每个币种添加单独的异常处理 
                    new_url = self.find_new_weekly_url(coin)

                    def save_new_url(new_url):
                        if new_url:
                            self.driver.get(new_url)
                            # 保存当前 URL 到 config
                            self.config['website']['url'] = new_url
                            self.save_config()
                            
                            # 清除url_entry中的url
                            self.url_entry.delete(0, tk.END)
                            # 把保存到config的url放到self.url_entry中
                            self.url_entry.insert(0, new_url)

                            # 获取trader_pair,用于显示在主界面上
                            pair = re.search(r'event/([^?]+)', new_url)
                            self.trading_pair_label.config(text=pair.group(1))
                            self.logger.info(f"\033[34m✅ 新URL已插入到主界面上: {new_url} \033[0m")
                            self.trade_count = 0
                            self.sell_count = 0
                    save_new_url(new_url)

                except Exception as e:
                    self.logger.error(f"处理{coin}时出错: {str(e)}")
                    save_new_url(new_url)

            self.start_url_monitoring()
            self.refresh_page()
            
            # 自动找币完成后，重新安排下一次的自动找币定时任务
            self.logger.info("🔄 自动找币完成，重新安排下一次定时任务")
            self.schedule_auto_find_coin()
            # 检查 URL 是否是当天的
            self.restart_browser_after_auto_find_coin()

        except Exception as e:
            self.logger.error(f"自动找币异常: {str(e)}")
            # 避免无限递归，使用延迟重试而不是直接递归调用
            if retry_count < 10:  # 最多重试10次
                retry_delay = min(5 * (retry_count + 1), 60)  # 逐渐增加重试间隔，最多60秒
                self.logger.info(f"{retry_delay}秒后将重试自动找币...")
                self.root.after(retry_delay * 1000, lambda: self.find_54_coin(coin_type, retry_count + 1))
            else:
                self.logger.critical(f"自动找币已达到最大重试次数(10次)，停止重试")
                # 即使重试失败，也要重新安排下一次的自动找币定时任务
                self.logger.info("🔄 重试失败，但仍重新安排下一次定时任务")
                self.schedule_auto_find_coin()
                
    def find_new_weekly_url(self, coin, retry_count=0):
        """在Polymarket市场搜索指定币种的合约地址,只返回URL"""
        try:
            if self.trading:
                return

            # 检查浏览器状态
            if self.driver is None:
                self.logger.error("浏览器未初始化，无法执行搜索")
                return None
            
            # 验证浏览器连接是否正常
            try:
                self.driver.execute_script("return navigator.userAgent")
            except Exception as e:
                self.logger.error(f"浏览器连接异常: {e}，无法执行搜索")
                # 尝试重启浏览器
                if not self.restart_browser(force_restart=True):
                    return None

            # 保存当前窗口句柄作为局部变量，用于本方法内部使用
            original_tab = self.driver.current_window_handle
            original_handles = set(self.driver.window_handles)
            # 打开新标签页并访问搜索页面
            try:
                base_url = "https://polymarket.com/markets/crypto?_s=start_date%3Adesc"
                self.driver.switch_to.new_window('tab')
                self.driver.get(base_url)
                time.sleep(2)  # 等待页面加载完成

                # 定义search_tab变量，保存搜索标签页的句柄
                search_tab = self.driver.current_window_handle

                # 等待页面加载完成
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2)  # 等待页面渲染完成
            except Exception as e:
                self.logger.error(f"打开搜索页面失败: {str(e)}")
                # 关闭可能打开的新标签页
                try:
                    current_handles = set(self.driver.window_handles)
                    for handle in current_handles - original_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                    self.driver.switch_to.window(original_tab)
                except:
                    pass
                return None

            # 设置搜索关键词
            if coin == 'BTC':
                search_text = 'Bitcoin Up or Down on'
            elif coin == 'ETH':
                search_text = 'Ethereum Up or Down on'
            elif coin == 'SOL':
                search_text = 'Solana Up or Down on'
            elif coin == 'XRP':
                search_text = 'XRP Up or Down on'
            
            try:
                # 查找搜索框
                try:
                    search_box = self.driver.find_element(By.XPATH, XPathConfig.SEARCH_INPUT[0])
                except (NoSuchElementException, StaleElementReferenceException):
                    search_box = self._find_element_with_retry(XPathConfig.SEARCH_INPUT, timeout=2, silent=True)
                    if not search_box:
                        raise Exception("无法找到搜索框")

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
                
                # 点击今天的卡片
                card_clicked = self.click_today_card()
                if not card_clicked:
                    self.logger.warning(f"❌ 未能找到{coin}今天的卡片")
                    # 关闭搜索标签页
                    self.driver.close()
                    # 切换回原始窗口
                    self.driver.switch_to.window(original_tab)
                    return None
                
                # 切换到新标签页获取完整URL
                time.sleep(2)  
        
                # 获取所有窗口句柄
                try:
                    all_handles = self.driver.window_handles
                except Exception as e:
                    self.logger.error(f"获取窗口句柄失败: {str(e)}")
                    # 尝试重启浏览器
                    self.restart_browser(force_restart=True)
                    return None
                
                # 切换到最新打开的标签页
                if len(all_handles) > 2:  # 原始窗口 + 搜索标签页 + coin标签页
                    try:
                        self.driver.switch_to.window(all_handles[-1])
                        WebDriverWait(self.driver, 40).until(EC.url_contains('/event/'))
                        
                        # 获取当前URL
                        new_url = self.driver.current_url
                        self.logger.info(f"✅ 成功获取URL: {new_url}")
                        time.sleep(8)

                        # 这里如果价格是 52,那么会触发自动交易
                        if self.trading == True:
                            time.sleep(5)
                            
                            # 保存当前 URL 到 config
                            self.config['website']['url'] = new_url
                            self.save_config()
                            self.logger.info(f"✅ {coin}:符合要求, 正在交易,已保存到 config")
                            
                            # 把保存到config的url放到self.url_entry中
                            # 保存前,先删除现有的url
                            self.url_entry.delete(0, tk.END)
                            self.url_entry.insert(0, new_url)
                            
                            pair = re.search(r'event/([^?]+)', new_url)
                            self.trading_pair_label.config(text=pair.group(1))
                            self.logger.info(f"✅ {new_url}:已插入到主界面上")

                            target_url_window = self.driver.current_window_handle
                            time.sleep(2)

                            # 安全关闭其他标签页
                            try:
                                self.driver.switch_to.window(search_tab)
                                self.driver.close()
                                self.driver.switch_to.window(original_tab)
                                self.driver.close()
                                self.driver.switch_to.window(target_url_window)
                            except Exception as e:
                                self.logger.warning(f"关闭标签页时出错: {str(e)}，尝试恢复")
                                # 如果出错，尝试切换到目标窗口
                                try:
                                    self.driver.switch_to.window(target_url_window)
                                except:
                                    # 如果切换失败，尝试重启浏览器并加载URL
                                    self.restart_browser(force_restart=True)
                                    if self.driver:
                                        self.driver.get(new_url)

                            self.start_url_monitoring()
                            self.refresh_page()
                            return new_url
                        else:
                            # 安全关闭标签页
                            try:
                                # 关闭当前详情URL标签页
                                self.driver.close()
                                
                                # 切换回搜索标签页
                                self.driver.switch_to.window(search_tab)
                                
                                # 关闭搜索标签页
                                self.driver.close()
                                
                                # 切换回原始窗口
                                self.driver.switch_to.window(original_tab)
                            except Exception as e:
                                self.logger.warning(f"关闭标签页时出错: {str(e)}")
                                # 尝试切换回原始窗口
                                try:
                                    self.driver.switch_to.window(original_tab)
                                except:
                                    # 如果切换失败，尝试重启浏览器
                                    self.restart_browser(force_restart=True)
                            
                            self.logger.info(f"✅ find_new_weekly_url return:{new_url}")
                            return new_url
                    except Exception as e:
                        self.logger.error(f"处理新标签页时出错: {str(e)}")
                        # 尝试安全关闭所有新打开的标签页
                        try:
                            current_handles = set(self.driver.window_handles)
                            for handle in current_handles - original_handles:
                                self.driver.switch_to.window(handle)
                                self.driver.close()
                            self.driver.switch_to.window(original_tab)
                        except:
                            # 如果关闭失败，尝试重启浏览器
                            self.restart_browser(force_restart=True)
                        return None
                else:
                    self.logger.warning(f"❌未能打开{coin}的详情页")
                    # 关闭搜索标签页
                    try:
                        self.driver.close()
                        # 切换回原始窗口
                        self.driver.switch_to.window(original_tab)
                    except:
                        # 如果关闭失败，尝试重启浏览器
                        self.restart_browser(force_restart=True)
                    return None
                
            except NoSuchElementException as e:
                self.logger.error(f"搜索过程中出错: {str(e)}")
                # 尝试安全关闭所有新打开的标签页
                try:
                    current_handles = set(self.driver.window_handles)
                    for handle in current_handles - original_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                    self.driver.switch_to.window(original_tab)
                except:
                    # 如果关闭失败，尝试重启浏览器
                    self.restart_browser(force_restart=True)
                return None
            
        except Exception as e:
            self.logger.error(f"操作失败: {str(e)}")
            # 尝试重启浏览器
            self.restart_browser(force_restart=True)
            # 限制最大重试次数为10次，避免无限递归
            if retry_count < 10:
                retry_delay = min(5 * (retry_count + 1), 60)  # 逐渐增加重试时间，最多60秒
                self.logger.info(f"{retry_delay}秒后重试自动找币...")
                self.root.after(retry_delay * 1000, lambda: self.find_54_coin(coin, retry_count + 1))
            else:
                self.logger.critical(f"自动找币已达到最大重试次数(10次)，停止重试")
                
    def click_today_card(self):
        """使用Command/Ctrl+Click点击包含今天日期的卡片,打开新标签页"""
        try:
            # 检查浏览器状态
            if self.driver is None:
                self.logger.error("浏览器未初始化，无法点击卡片")
                return False
            
            # 验证浏览器连接是否正常
            try:
                self.driver.execute_script("return navigator.userAgent")
            except Exception as e:
                self.logger.error(f"浏览器连接异常: {e}，无法点击卡片")
                return False
            
            # 获取当前日期字符串，比如 "April 18"
            if platform.system() == 'Darwin':  # macOS
                today_str = datetime.now().strftime("%B %-d")  # macOS格式
            else:  # Linux (Ubuntu)
                today_str = datetime.now().strftime("%B %d").replace(" 0", " ")  # Linux格式，去掉前导零
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
            return False

    def get_zero_time_cash(self):
        """获取币安BTC实时价格,并在中国时区00:00触发"""
        try:
            # 获取零点CASH值
            try:
                cash_element = self.driver.find_element(By.XPATH, XPathConfig.CASH_VALUE[0])
            except (NoSuchElementException, StaleElementReferenceException):
                cash_element = self._find_element_with_retry(XPathConfig.CASH_VALUE, timeout=2, silent=True)
                
            if cash_element:
                cash_value = cash_element.text
            else:
                self.logger.warning("无法找到CASH值元素")
                return
            
            # 使用正则表达式提取数字
            cash_match = re.search(r'\$?([\d,]+\.?\d*)', cash_value)

            if not cash_match:
                self.logger.error("❌ 无法从Cash值中提取数字")
                return

            # 移除逗号并转换为浮点数
            self.zero_time_cash_value = round(float(cash_match.group(1).replace(',', '')), 2)
            self.zero_time_cash_label.config(text=f"{self.zero_time_cash_value}")
            self.logger.info(f"✅ 获取到原始CASH值:\033[34m${self.zero_time_cash_value}\033[0m")

            # 设置 YES/NO 金额,延迟5秒确保数据稳定
            self.root.after(5000, self.schedule_update_amount)
            self.logger.info("✅ 设置 YES/NO 金额成功!")
            # 设置 YES1/NO1价格为 0
            self.yes1_price_entry.delete(0, tk.END)
            self.yes1_price_entry.insert(0, "0")
            self.no1_price_entry.delete(0, tk.END)
            self.no1_price_entry.insert(0, "0")
            
        except Exception as e:
            self.logger.error(f"获取零点CASH值时发生错误: {str(e)}")
        finally:
            # 计算下一个00:10的时间
            now = datetime.now()
            tomorrow = now.replace(hour=0, minute=3, second=0, microsecond=0) + timedelta(days=1)
            seconds_until_midnight = (tomorrow - now).total_seconds()

            # 取消已有的定时器（如果存在）
            if hasattr(self, 'get_zero_time_cash_timer') and self.get_zero_time_cash_timer:
                self.root.after_cancel(self.get_zero_time_cash_timer)

            # 设置下一次执行的定时器
            if self.running and not self.stop_event.is_set():
                self.get_zero_time_cash_timer = threading.Timer(seconds_until_midnight, self.get_zero_time_cash)
                self.get_zero_time_cash_timer.daemon = True
                self.get_zero_time_cash_timer.start()
                self.logger.info(f"✅ \033[34m{round(seconds_until_midnight / 3600,2)}\033[0m小时后再次获取 \033[34mCASH\033[0m 值")
    
    def get_binance_zero_time_price(self):
        """获取币安BTC实时价格,并在中国时区00:00触发。此方法在threading.Timer的线程中执行。"""
        api_data = None
        coin_form_websocket = ""
        max_retries = 10 # 最多重试次数
        retry_delay = 2  # 重试间隔（秒）

        for attempt in range(max_retries):
            try:
                # 1. 获取币种信息
                selected_coin = self.coin_combobox.get() 
                coin_form_websocket = selected_coin + 'USDT'

                # --- 新增 websocket 获取价格逻辑 ---
                ws_url = f"wss://stream.binance.com:9443/ws/{coin_form_websocket.lower()}@ticker"
                price_holder = {'price': None}
                ws_error = {'error': None}

                def on_message(ws, message):
                    try:
                        data = json.loads(message)
                        price = round(float(data['c']), 3)
                        price_holder['price'] = price
                        ws.close()  # 收到一次价格后立即关闭连接
                    except Exception as e:
                        ws_error['error'] = e
                        ws.close()
                def on_error(ws, error):
                    ws_error['error'] = error
                    ws.close()
                def on_close(ws, close_status_code, close_msg):
                    pass
                # 获取币安价格
                ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close)
                ws_thread = threading.Thread(target=ws.run_forever)
                ws_thread.start()
                
                # 等待 websocket 获取到价格或超时
                ws_thread.join(timeout=5)
                if ws_error['error']:
                    raise Exception(ws_error['error'])
                if price_holder['price'] is None:
                    raise Exception("WebSocket 未能获取到价格")
                price = price_holder['price']
                # --- websocket 获取价格逻辑结束 ---

                api_data = {"price": price, "coin": coin_form_websocket, "original_selected_coin": selected_coin}
                self.logger.info(f"✅ ({attempt + 1}/{max_retries}) 成功获取到币安 \033[34m{api_data['coin']}\033[0m 价格: \033[34m{api_data['price']}\033[0m")
                
                break # 获取成功，跳出重试循环

            except Exception as e:
                self.logger.warning(f"❌ (尝试 {attempt + 1}/{max_retries}) 获取币安 \033[34m{coin_form_websocket}\033[0m 价格时发生错误: {e}")
                if attempt < max_retries - 1: # 如果不是最后一次尝试
                    self.logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay) # 等待后重试
                else: # 最后一次尝试仍然失败
                    self.logger.error(f"❌ 获取币安 \033[34m{coin_form_websocket}\033[0m 价格失败，已达到最大重试次数 ({max_retries})。")
        
        # 3. 如果成功获取数据 (即try块没有异常且api_data不为None)，则安排GUI更新到主线程
        if api_data:
            def update_gui():
                try:
                    # 获取到币安价格,并更新到GUI
                    self.zero_time_price = api_data["price"]
                    self.binance_zero_price_label.config(text=f"{self.zero_time_price}")
                except Exception as e_gui:
                    self.logger.debug(f"❌ 更新零点价格GUI时出错: {e_gui}")
            
            self.root.after(0, update_gui)

        # 设置定时器,每天00:00获取一次币安价格
        now = datetime.now()
        next_run_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= next_run_time:
            next_run_time += timedelta(days=1)

        seconds_until_next_run = (next_run_time - now).total_seconds()

        if hasattr(self, 'binance_zero_price_timer_thread') and self.binance_zero_price_timer and self.binance_zero_price_timer.is_alive():
            self.binance_zero_price_timer.cancel()

        if self.running and not self.stop_event.is_set():
            coin_for_next_log = self.coin_combobox.get() + 'USDT'
            self.binance_zero_price_timer = threading.Timer(seconds_until_next_run, self.get_binance_zero_time_price)
            self.binance_zero_price_timer.daemon = True
            self.binance_zero_price_timer.start()
            self.logger.info(f"✅ \033[34m{round(seconds_until_next_run / 3600,2)}\033[0m 小时后重新获取{coin_for_next_log} 零点价格")
    
    def get_binance_price_websocket(self):
        """获取币安价格,并计算上涨或下跌幅度"""
        # 获取币种信息
        selected_coin = self.coin_combobox.get()
        coin_form_websocket = selected_coin.lower() + 'usdt'
        # 获取币安价格
        ws_url = f"wss://stream.binance.com:9443/ws/{coin_form_websocket}@ticker"

        def on_message(ws, message):
            try:
                data = json.loads(message)
                # 获取最新成交价格
                now_price = round(float(data['c']), 3)
                # 计算上涨或下跌幅度
                zero_time_price_for_calc = getattr(self, 'zero_time_price', None)
                binance_rate_text = "--"
                rate_color = "blue"

                if zero_time_price_for_calc:
                    binance_rate = ((now_price - zero_time_price_for_calc) / zero_time_price_for_calc) * 100
                    binance_rate_text = f"{binance_rate:.3f}"
                    rate_color = "#1AAD19" if binance_rate >= 0 else "red"

                def update_gui():
                    try:
                        self.binance_now_price_label.config(text=f"{now_price}")
                        self.binance_rate_label.config(
                            text=f"{binance_rate_text}",
                            foreground=rate_color,
                            font=("Arial", 18, "bold")
                        )
                    except Exception as e:
                        self.logger.debug("❌ 更新GUI时发生错误:", e)

                self.root.after(0, update_gui)
            except Exception as e:
                self.logger.warning(f"WebSocket 消息处理异常: {e}")

        def on_error(ws, error):
            self.logger.warning(f"WebSocket 错误: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.logger.info("WebSocket 连接已关闭")

        def run_ws():
            while self.running and not self.stop_event.is_set():
                try:
                    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close)
                    ws.run_forever()
                except Exception as e:
                    self.logger.warning(f"WebSocket 主循环异常: {e}")
                time.sleep(5)  # 出错后延迟重连

        self.ws_thread = threading.Thread(target=run_ws, daemon=True)
        self.ws_thread.start()

    def _perform_price_comparison(self):
        """执行价格比较"""
        try:
            # 获取当前选择的币种
            selected_coin = self.coin_combobox.get()
            # 获取0点当天的币安价格
            zero_time_price = round(float(self.binance_zero_price_label.cget('text').replace('$', '')),2)
            # 获取当前价格
            now_price = round(float(self.binance_now_price_label.cget('text').replace('$', '')),2)
            # 计算上涨或下跌幅度
            price_change = round(((now_price - zero_time_price) / zero_time_price) * 100,3)
            # 比较价格
            if 0 <= price_change <= 0.01 or -0.01 <= price_change <= 0:
                price_change = f"{round(price_change,3)}%"
                self.logger.info(f"✅ \033[34m{selected_coin}USDT当前价格上涨或下跌幅度小于{price_change},请立即关注\033[0m")
                self.send_trade_email(
                                trade_type=f"{selected_coin}USDT当前价格上涨或下跌幅度小于{price_change}",
                                price=zero_time_price,
                                amount=now_price,
                                trade_count=price_change,
                                cash_value=0,
                                portfolio_value=0
                            )
            
        except Exception as e:
            pass
        finally:
            self.comparison_binance_price()

    def comparison_binance_price(self):
        """设置定时器以在每天23点比较币安价格和当前价格"""
        now = datetime.now()
        # 设置目标时间为当天的23点
        target_time_today = now.replace(hour=23, minute=0, second=0, microsecond=0)

        if now < target_time_today:
            # 如果当前时间早于今天的23点，则在今天的23点执行
            next_run_time = target_time_today
        else:
            # 如果当前时间晚于或等于今天的23点，则在明天的23点执行
            next_run_time = target_time_today + timedelta(days=1)

        seconds_until_next_run = (next_run_time - now).total_seconds()
        # 取消已有的定时器（如果存在）
        if hasattr(self, 'comparison_binance_price_timer') and self.comparison_binance_price_timer:
            self.root.after_cancel(self.comparison_binance_price_timer)

        # 设置下一次执行的定时器
        if self.running and not self.stop_event.is_set():
                selected_coin = self.coin_combobox.get()
                self.comparison_binance_price_timer = threading.Timer(seconds_until_next_run, self._perform_price_comparison)
                self.comparison_binance_price_timer.daemon = True
                self.comparison_binance_price_timer.start()
                self.logger.info(f"\033[34m{round(seconds_until_next_run / 3600,2)}\033[0m小时后比较\033[34m{selected_coin}USDT\033[0m币安价格")

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
    
