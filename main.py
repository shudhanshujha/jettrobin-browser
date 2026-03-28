import sys
import os
import json
import traceback
from PyQt6.QtCore import QUrl, QSize, Qt, pyqtSignal, QEvent, QTimer, QStandardPaths
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QLineEdit, QComboBox, 
                             QPushButton, QVBoxLayout, QWidget, QTabWidget, QMenu, QLabel, QMessageBox)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (QWebEngineProfile, QWebEnginePage, QWebEngineSettings, 
                                   QWebEngineUrlRequestInterceptor)
from adblockparser import AdblockRules

# --- Configuration & Logging ---
APP_NAME = "Jett-Robin"
LOG_FILE = "jettrobin.log"
HISTORY_FILE = "history.json"
SETTINGS_FILE = "settings.json"

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{msg}\n")
    print(msg)

# --- Ad Blocker Rules (Expanded) ---
RAW_RULES = [
    "||doubleclick.net^", "||googleadservices.com^", "||googlesyndication.com^",
    "||adsystem.com^", "||facebook.com/plugins/*", "||twitter.com/widgets/*",
    "||analytics.google.com^", "||ads.youtube.com^", "||popads.net^", "||adnxs.com^"
]
rules = AdblockRules(RAW_RULES)

class WebEngineUrlRequestInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if rules.should_block(url):
            info.block(True)
            log(f"[🛡️ Blocked]: {url}")

# --- UI Stylesheet ---
DARK_THEME = """
    QMainWindow {
        background-color: #121212;
    }
    QTabWidget::pane {
        border-top: 1px solid #333;
        background-color: #1e1e1e;
    }
    QTabBar::tab {
        background: #252526;
        color: #d4d4d4;
        padding: 10px 15px;
        border-right: 1px solid #121212;
        min-width: 120px;
    }
    QTabBar::tab:selected {
        background: #1e1e1e;
        color: #ffffff;
        border-bottom: 2px solid #007acc;
    }
    QTabBar::tab:hover {
        background: #2d2d2d;
    }
    QToolBar {
        background-color: #1e1e1e;
        border: none;
        padding: 5px;
        spacing: 10px;
    }
    QLineEdit {
        background-color: #333333;
        color: #ffffff;
        border: 1px solid #444;
        border-radius: 15px;
        padding: 5px 15px;
        font-size: 14px;
    }
    QLineEdit:focus {
        border: 1px solid #007acc;
    }
    QComboBox {
        background-color: #333333;
        color: #ffffff;
        border: 1px solid #444;
        border-radius: 5px;
        padding: 5px;
    }
    QComboBox::drop-down {
        border: none;
    }
    QPushButton {
        background-color: transparent;
        color: #d4d4d4;
        font-size: 18px;
        border-radius: 5px;
        padding: 5px;
    }
    QPushButton:hover {
        background-color: #333333;
        color: #ffffff;
    }
"""

class JettRobinBrowser(QMainWindow):
    def __init__(self, is_private=False):
        super().__init__()
        self.is_private = is_private
        self.setWindowTitle(f"{APP_NAME} Browser" + (" 🕵️ (Private)" if is_private else ""))
        self.resize(1280, 800)
        self.setStyleSheet(DARK_THEME)
        
        # --- Engine & Optimization ---
        # Optimization: Use a dedicated storage path for the non-private profile
        if self.is_private:
            self.profile = QWebEngineProfile(self)
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        else:
            self.profile = QWebEngineProfile.defaultProfile()
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)

        settings = self.profile.settings()
        # High-Performance settings
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False) # Pop-up blocker
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, True)
        
        # Ad Blocker
        self.interceptor = WebEngineUrlRequestInterceptor()
        self.profile.setUrlRequestInterceptor(self.interceptor)

        # --- UI Setup ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_ui_on_tab_change)
        self.setCentralWidget(self.tabs)

        # Search Engines
        self.search_engines = {
            "Google": "https://www.google.com/search?q={}",
            "DuckDuckGo": "https://duckduckgo.com/?q={}",
            "Bing": "https://www.bing.com/search?q={}"
        }
        
        # Load Settings (Preferred Search Engine)
        self.current_search_engine = self.load_settings().get("search_engine", "Google")
        if self.is_private:
            self.current_search_engine = "DuckDuckGo"

        # Toolbar
        self.navbar = QToolBar("Navigation")
        self.navbar.setMovable(False)
        self.addToolBar(self.navbar)

        # Buttons
        self.back_btn = QAction("◀", self)
        self.back_btn.triggered.connect(lambda: self.current_browser().back())
        self.navbar.addAction(self.back_btn)

        self.forward_btn = QAction("▶", self)
        self.forward_btn.triggered.connect(lambda: self.current_browser().forward())
        self.navbar.addAction(self.forward_btn)

        self.reload_btn = QAction("🔄", self)
        self.reload_btn.triggered.connect(lambda: self.current_browser().reload())
        self.navbar.addAction(self.reload_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.navbar.addWidget(self.url_bar)

        self.engine_selector = QComboBox()
        self.engine_selector.addItems(self.search_engines.keys())
        self.engine_selector.setCurrentText(self.current_search_engine)
        self.engine_selector.currentTextChanged.connect(self.change_search_engine)
        self.navbar.addWidget(self.engine_selector)

        self.navbar.addAction(QAction("➕", self, triggered=self.add_new_tab_action))
        self.navbar.addAction(QAction("🕵️", self, triggered=self.open_private_window))

        # --- History Initialization ---
        self.history = []
        if not self.is_private:
            self.load_history()

        # Start
        start_home = "https://www.google.com"
        if self.current_search_engine == "DuckDuckGo": start_home = "https://duckduckgo.com"
        elif self.current_search_engine == "Bing": start_home = "https://www.bing.com"
        
        self.add_new_tab(QUrl(start_home), "Home")
        self.private_windows = []

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_new_tab_action(self):
        engine = self.engine_selector.currentText()
        home_url = "https://www.google.com"
        if engine == "DuckDuckGo": home_url = "https://duckduckgo.com"
        elif engine == "Bing": home_url = "https://www.bing.com"
        self.add_new_tab(QUrl(home_url), "New Tab")

    def add_new_tab(self, qurl=None, label="Blank"):
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        browser.setPage(page)
        browser.setUrl(qurl if qurl else QUrl("about:blank"))
        
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)

        browser.urlChanged.connect(lambda qurl, b=browser: self.on_url_changed(qurl, b))
        browser.titleChanged.connect(lambda title, b=browser: self.tabs.setTabText(self.tabs.indexOf(b), title))

    def on_url_changed(self, qurl, browser):
        url_str = qurl.toString()
        if browser == self.current_browser():
            self.url_bar.setText(url_str)
        
        if not self.is_private and url_str != "about:blank":
            self.save_to_history(url_str)

    def navigate_to_url(self):
        text = self.url_bar.text().strip()
        if "." in text and " " not in text:
            url = QUrl(text if text.startswith("http") else "https://" + text)
        else:
            url = QUrl(self.search_engines[self.engine_selector.currentText()].format(text.replace(" ", "+")))
        self.current_browser().setUrl(url)

    def change_search_engine(self, engine_name):
        self.current_search_engine = engine_name
        if not self.is_private:
            self.save_settings({"search_engine": engine_name})

    def close_tab(self, i):
        if self.tabs.count() > 1:
            self.tabs.removeTab(i)
        else:
            self.close()

    def update_ui_on_tab_change(self, i):
        browser = self.current_browser()
        if browser:
            self.url_bar.setText(browser.url().toString())

    def open_private_window(self):
        win = JettRobinBrowser(is_private=True)
        win.show()
        self.private_windows.append(win)

    # --- Settings Logic ---
    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_settings(self, settings_dict):
        try:
            current = self.load_settings()
            current.update(settings_dict)
            with open(SETTINGS_FILE, "w") as f:
                json.dump(current, f)
        except: pass

    # --- History Logic ---
    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    self.history = json.load(f)
            except: self.history = []

    def save_to_history(self, url):
        if not self.history or self.history[-1] != url:
            self.history.append(url)
            # Keep last 500 entries
            if len(self.history) > 500: self.history.pop(0)
            try:
                with open(HISTORY_FILE, "w") as f:
                    json.dump(self.history, f)
            except: pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    
    # Optimization: Set high performance flags if available
    # app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    
    window = JettRobinBrowser()
    window.show()
    sys.exit(app.exec())