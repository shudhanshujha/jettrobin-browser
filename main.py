import sys
import os
from PyQt6.QtCore import QUrl, QSize, Qt, pyqtSignal, QEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QLineEdit, QComboBox, 
                             QPushButton, QVBoxLayout, QWidget, QTabWidget, QMenu, QAction, QLabel)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (QWebEngineProfile, QWebEnginePage, QWebEngineSettings, 
                                   QWebEngineUrlRequestInterceptor)
from adblockparser import AdblockRules

# A simple rule set for ad blocking and cookie protection to simulate the feature
RAW_RULES = [
    "||doubleclick.net^",
    "||googleadservices.com^",
    "||googlesyndication.com^",
    "||adsystem.com^",
    "||facebook.com/plugins/*",
    "||twitter.com/widgets/*",
    "||analytics.google.com^",
    "||ads.youtube.com^"
]
rules = AdblockRules(RAW_RULES)

class WebEngineUrlRequestInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if rules.should_block(url):
            info.block(True)
            print(f"[🛡️ Ad/Tracker Blocked]: {url}")

class JettRobinBrowser(QMainWindow):
    def __init__(self, is_private=False):
        super().__init__()
        self.is_private = is_private
        
        # Setup Window
        title = "JettRobin Browser"
        if is_private:
            title += " 🕵️ (Private Browsing - Cookie Protector Active)"
        self.setWindowTitle(title)
        self.resize(1280, 800)
        
        # --- Engine & Optimization Settings ---
        if self.is_private:
            # OffTheRecord profile (completely in-memory, no cache, no persistent cookies)
            self.profile = QWebEngineProfile()
        else:
            self.profile = QWebEngineProfile.defaultProfile()

        settings = self.profile.settings()
        
        # 1. Pop-up Blocker: Disable JavaScript from opening windows
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        
        # 2. Optimization: Hardware acceleration, WebGL, LocalStorage
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        
        # 3. Cookie Protector
        if self.is_private:
             # Force zero persistent cookies
             self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        else:
             self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        
        # 4. Ad Blocker Integration
        self.interceptor = WebEngineUrlRequestInterceptor()
        self.profile.setUrlRequestInterceptor(self.interceptor)

        # --- UI Setup ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_url_bar)
        
        self.setCentralWidget(self.tabs)

        # --- Search Engines ---
        self.search_engines = {
            "Google": "https://www.google.com/search?q={}",
            "DuckDuckGo (Secure)": "https://duckduckgo.com/?q={}",
            "Bing": "https://www.bing.com/search?q={}",
            "Ecosia": "https://www.ecosia.org/search?q={}"
        }
        self.current_search_engine = "Google"
        if self.is_private:
            self.current_search_engine = "DuckDuckGo (Secure)"

        # --- Navbar ---
        self.navbar = QToolBar("Navigation")
        self.navbar.setMovable(False)
        self.addToolBar(self.navbar)

        # Navigation Buttons
        back_btn = QAction("◀ Back", self)
        back_btn.triggered.connect(lambda: self.current_browser().back() if self.current_browser() else None)
        self.navbar.addAction(back_btn)

        forward_btn = QAction("▶ Forward", self)
        forward_btn.triggered.connect(lambda: self.current_browser().forward() if self.current_browser() else None)
        self.navbar.addAction(forward_btn)

        reload_btn = QAction("🔄 Reload", self)
        reload_btn.triggered.connect(lambda: self.current_browser().reload() if self.current_browser() else None)
        self.navbar.addAction(reload_btn)

        # URL Bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL or search...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.navbar.addWidget(self.url_bar)

        # Search Engine Selector
        self.navbar.addWidget(QLabel(" Search: "))
        self.engine_selector = QComboBox()
        self.engine_selector.addItems(self.search_engines.keys())
        self.engine_selector.setCurrentText(self.current_search_engine)
        self.engine_selector.currentTextChanged.connect(self.change_search_engine)
        self.navbar.addWidget(self.engine_selector)

        # Actions
        new_tab_btn = QAction("➕ New Tab", self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab(QUrl("https://www.google.com"), "New Tab"))
        self.navbar.addAction(new_tab_btn)

        private_btn = QAction("🕵️ Private Browsing", self)
        private_btn.triggered.connect(self.open_private_window)
        self.navbar.addAction(private_btn)

        # Start with one tab
        start_url = "https://duckduckgo.com" if self.is_private else "https://www.google.com"
        self.add_new_tab(QUrl(start_url), "Home")

        # Keep references to private windows to prevent garbage collection
        self.private_windows = []

    def change_search_engine(self, engine_name):
        self.current_search_engine = engine_name

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_new_tab(self, qurl=None, label="Blank"):
        if qurl is None:
            qurl = QUrl("about:blank")
            
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        browser.setPage(page)
        browser.setUrl(qurl)
        
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)

        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_url(qurl, browser))
        browser.titleChanged.connect(lambda title, browser=browser: self.update_title(title, browser))

    def update_url(self, q, browser):
        if browser == self.current_browser():
            self.url_bar.setText(q.toString())

    def update_title(self, title, browser):
        i = self.tabs.indexOf(browser)
        if i >= 0:
            self.tabs.setTabText(i, title)

    def close_tab(self, i):
        if self.tabs.count() < 2:
            self.close()
        else:
            self.tabs.removeTab(i)

    def update_url_bar(self, i):
        if self.current_browser():
            q = self.current_browser().url()
            self.url_bar.setText(q.toString())

    def navigate_to_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text:
            return
            
        # Basic URL detection heuristic
        if "." in url_text and " " not in url_text:
            if not url_text.startswith("http"):
                url_text = "https://" + url_text
            self.current_browser().setUrl(QUrl(url_text))
        else:
            # Use Search Engine
            search_query = url_text.replace(" ", "+")
            search_url = self.search_engines[self.current_search_engine].format(search_query)
            self.current_browser().setUrl(QUrl(search_url))

    def open_private_window(self):
        private_window = JettRobinBrowser(is_private=True)
        private_window.show()
        self.private_windows.append(private_window)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("JettRobin")
    
    window = JettRobinBrowser()
    window.show()
    
    sys.exit(app.exec())