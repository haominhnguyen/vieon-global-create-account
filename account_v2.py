# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, simpledialog
import csv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import threading
import os
import ssl
import requests
import re
import secrets
import string
from datetime import datetime
import sys
import codecs
import subprocess
try:
    import winsound
except Exception:
    winsound = None
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up UTF-8 output stream
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

ssl._create_default_https_context = ssl._create_unverified_context

# ==================== MAIL.TM API ====================
API_MAIL = "https://api.mail.tm"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

# ==================== GLOBAL VARIABLES ====================
stop_flag = False
log_output = None
active_threads = 0
max_concurrent = 1
proxy_list = []  # Danh sách proxy (để xoay vòng)
proxy_index = 0  # Index hiện tại khi xoay vòng proxy
seen_otp_ids = set()  # Global set to track OTP message IDs across all account creations

# Queue for async logging (non-blocking)
import queue
log_queue = queue.Queue(maxsize=1000)

# Statistics
success_count = 0
error_count = 0
start_time = None
stats_label = None
progress_var = None
progress_bar = None

# Theme
current_theme = "dark"  # dark or light
THEMES = {
    "dark": {
        "bg": "#0a0e27",
        "fg": "#ffffff",
        "primary": "#1a1f3a",
        "secondary": "#2a2f4a",
        "accent": "#00ff88",
        "success": "#00ff88",
        "error": "#ff4444",
        "warning": "#ffaa00",
        "info": "#00ff00",
    },
    "light": {
        "bg": "#f5f5f5",
        "fg": "#1a1a1a",
        "primary": "#ffffff",
        "secondary": "#e0e0e0",
        "accent": "#00aa44",
        "success": "#00aa44",
        "error": "#dd0000",
        "warning": "#ff8800",
        "info": "#0088ff",
    }
}

# Thread lock for safe counter updates
import threading as threading_module
stats_lock = threading_module.Lock()

# ==================== LOGGING ====================
def log_message(message, level="INFO"):
    """Non-blocking async logging via queue"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_text = f"[{timestamp}] [{level}] {message}"
    
    # Console output (fast, unbuffered)
    print(log_text, flush=True)
    
    # Queue for GUI (non-blocking)
    try:
        log_queue.put_nowait((log_text, level))
    except queue.Full:
        pass  # Drop if queue full (prevents deadlock)

def process_log_queue():
    """Process queued logs and update GUI (called from main thread)"""
    if not log_output:
        return
    
    processed = 0
    max_per_cycle = 10  # Process max 10 logs per cycle to keep UI responsive
    
    while processed < max_per_cycle:
        try:
            log_text, level = log_queue.get_nowait()
            try:
                log_output.config(state=tk.NORMAL)
                log_output.insert(tk.END, log_text + "\n", level)
                log_output.see(tk.END)
                log_output.config(state=tk.DISABLED)
            except:
                pass
            processed += 1
        except queue.Empty:
            break
    
    # Schedule next check
    if log_output:
        log_output.after(100, process_log_queue)  # Check every 100ms

def update_stats():
    """Cập nhật thông tin thống kê (optimized - no lock)"""
    global success_count, error_count, start_time
    if stats_label and start_time:
        elapsed = int(time.time() - start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        text = f"Thành công: {success_count}  |  Lỗi: {error_count}  |  Thời gian: {hours:02d}:{minutes:02d}:{seconds:02d}"
        
        try:
            stats_label.config(text=text)
        except:
            pass

# ==================== MAIL.TM FUNCTIONS ====================
def random_string(n=12):
    """Tạo chuỗi ngẫu nhiên"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def get_domains():
    """Lấy danh sách domain từ mail.tm"""
    try:
        r = SESSION.get(f"{API_MAIL}/domains")
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("hydra:member", [])
    except Exception as e:
        log_message(f"Lỗi lấy domain: {e}", "ERROR")
        return []

def create_email_account(address, password):
    """Tạo account trên mail.tm"""
    try:
        payload = {"address": address, "password": password}
        r = SESSION.post(f"{API_MAIL}/accounts", json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_message(f"Lỗi tạo email account: {e}", "ERROR")
        return None

def get_token(email, password):
    """Lấy token để truy cập email"""
    try:
        payload = {"address": email, "password": password}
        r = SESSION.post(f"{API_MAIL}/token", json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_message(f"Lỗi lấy token: {e}", "ERROR")
        return None

def list_messages(token, page=1):
    """Lấy danh sách tin nhắn"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = SESSION.get(f"{API_MAIL}/messages", headers=headers, params={"page": page})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_message(f"Lỗi lấy danh sách tin: {e}", "ERROR")
        return []

def get_message_content(token, message_id):
    """Lấy nội dung tin nhắn"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = SESSION.get(f"{API_MAIL}/messages/{message_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
        # mail.tm may include text, html, intro, subject, from
        parts = []
        if isinstance(data, dict):
            for k in ("subject", "from", "text", "html", "intro"):
                v = data.get(k)
                if isinstance(v, dict):
                    # 'from' may be an object with 'address' or similar
                    addr = v.get("address") or v.get("name") or str(v)
                    parts.append(str(addr))
                elif v:
                    parts.append(str(v))

        return "\n".join(parts)
    except Exception as e:
        log_message(f"Lỗi lấy nội dung tin: {e}", "ERROR")
        return ""

def extract_otp(text):
    """Trích OTP từ email"""
    if not text:
        return None
    # search for 4-6 consecutive digits
    otp = re.search(r"\b\d{4,6}\b", text)
    if otp:
        return otp.group()
    # fallback: search anywhere for digits (handles HTML with tags between digits)
    compact = re.sub(r"\D+", "", text)
    if 4 <= len(compact) <= 6:
        return compact
    return None

def wait_for_otp(token, timeout=120):
    """Chờ và lấy OTP từ email - chỉ kiểm tra email mới (tạo sau khi hàm này được gọi)"""
    global seen_otp_ids
    log_message(f"Cho OTP (toi da {timeout}s)...", "INFO")
    start_time = datetime.now()

    for attempt in range(timeout):
        if stop_flag:
            log_message("Bi dung khi cho OTP", "WARNING")
            return None

        try:
            msgs = list_messages(token)
            if isinstance(msgs, list):
                messages = msgs
            else:
                messages = msgs.get("hydra:member", [])

            # iterate newest first
            for msg in messages:
                mid = msg.get("id")
                if not mid or mid in seen_otp_ids:
                    # Skip if we've already processed this message ID
                    continue

                seen_otp_ids.add(mid)
                # log basic info about the incoming message so user sees live activity
                subj = msg.get("subject") or msg.get("from") or "(no subject)"
                log_message(f"Mới: id={mid} | subject={subj}", "INFO")

                content = get_message_content(token, mid)
                # Log full content when OTP is found
                otp = extract_otp(content)
                if otp:
                    log_message(f"=== TOÀN BỘ NỘI DUNG EMAIL ===", "INFO")
                    log_message(f"{content}", "SUCCESS")
                    log_message(f"Tim thay OTP: {otp}", "SUCCESS")
                    log_message(f"=== HẾT NỘI DUNG ===", "INFO")
                    return otp
                else:
                    preview = content[:300].replace("\n", " ")
                    log_message(f"Nội dung (preview, chưa có OTP): {preview}", "INFO")
        except Exception as e:
            log_message(f"Loi kiem tra email: {e}", "ERROR")

        time.sleep(1)

    log_message("Timeout cho OTP", "ERROR")
    return None

def create_email_with_token():
    """Tao email mail.tm va lay token"""
    try:
        log_message("Buoc 1: Lay domain...", "INFO")
        domains = get_domains()
        if not domains:
            log_message("Khong co domain nao", "ERROR")
            return None
        
        domain = domains[0]["domain"]
        log_message(f"Domain: {domain}", "SUCCESS")
        
        log_message("Buoc 2: Tao email...", "INFO")
        username = random_string(10)
        password = random_string(16)
        email = f"{username}@{domain}"
        log_message(f"Email: {email}", "SUCCESS")
        log_message(f"Password: {password}", "SUCCESS")
        
        log_message("Buoc 3: Tao account mail.tm...", "INFO")
        account = create_email_account(email, password)
        if not account:
            return None
        
        log_message("Buoc 4: Lay token...", "INFO")
        for attempt in range(3):
            token_resp = get_token(email, password)
            if token_resp:
                break
            log_message(f"Retry token ({attempt + 1}/3)...", "WARNING")
            time.sleep(1)
        else:
            log_message("Khong lay duoc token", "ERROR")
            return None
        
        token = token_resp["token"]
        log_message(f"Token: {token}", "SUCCESS")
        
        save_to_csv(email, password, "email_accounts.csv")
        
        return {
            "email": email,
            "password": password,
            "token": token,
        }
    except Exception as e:
        log_message(f"LOI: {e}", "ERROR")
        return None

def save_to_csv(email, password, filename="email_accounts.csv"):
    """Lưu email và password vào CSV"""
    try:
        file_exists = os.path.isfile(filename)
        with open(filename, mode="a", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["email", "password"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({"email": email, "password": password})
    except Exception as e:
        log_message(f"Lỗi lưu CSV: {e}", "ERROR")

def save_otp_to_csv(email, password_email, otp, filename="otp_accounts.csv"):
    """Lưu email, password và OTP vào CSV"""
    try:
        file_exists = os.path.isfile(filename)
        with open(filename, mode="a", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["email", "password_email", "otp"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({"email": email, "password_email": password_email, "otp": otp})
    except Exception as e:
        log_message(f"Lỗi lưu OTP: {e}", "ERROR")


def verbose_check_email(email, password):
    """Fetch full raw messages for an email account and log headers/body and extracted OTPs."""
    try:
        log_message(f"Verbose check cho {email}", "INFO")
        # get token
        r = SESSION.post(f"{API_MAIL}/token", json={"address": email, "password": password})
        r.raise_for_status()
        token = r.json().get("token")
        if not token:
            log_message("Không lấy được token", "ERROR")
            return
        log_message(f"Token: {token}", "INFO")

        msgs = list_messages(token)
        if not msgs:
            log_message("Inbox trống", "WARNING")
            return

        import json
        for msg in msgs:
            mid = msg.get("id")
            if not mid:
                continue
            try:
                r2 = SESSION.get(f"{API_MAIL}/messages/{mid}", headers={"Authorization": f"Bearer {token}"})
                r2.raise_for_status()
                data = r2.json()
                pretty = json.dumps(data, ensure_ascii=False, indent=2)
                # Truncate to avoid extremely long logs
                preview = pretty[:4000]
                log_message(f"RAW message id={mid}:\n{preview}", "INFO")

                # Try extract OTP from combined JSON text
                otp = extract_otp(pretty)
                if otp:
                    log_message(f"Tìm thấy OTP: {otp}", "SUCCESS")
                    try:
                        save_otp_to_csv(email, password, otp)
                    except:
                        pass
            except Exception as e:
                log_message(f"Lỗi lấy message {mid}: {e}", "ERROR")

        # Log user/pass for convenience
        log_message(f"User/Pass: {email} / {password}", "INFO")
    except Exception as e:
        log_message(f"Verbose check error: {e}", "ERROR")


def verbose_check_email_dialog():
    """Prompt user for email and password then run verbose check in background."""
    email = simpledialog.askstring("Email (mail.tm)", "Nhập địa chỉ email mail.tm:")
    if not email:
        log_message("Không có email nhập", "WARNING")
        return
    password = simpledialog.askstring("Password", "Nhập password của email:", show='*')
    if not password:
        log_message("Không có password nhập", "WARNING")
        return

    # run in background thread to avoid blocking GUI
    t = threading.Thread(target=verbose_check_email, args=(email, password), daemon=True)
    t.start()

# ==================== PROXY CHECKER ====================
API_GEONODE = "https://proxylist.geonode.com/api/proxy-list?limit=200&sort_by=lastChecked&sort_type=desc&protocols=http"

def get_next_proxy():
    """Lấy proxy tiếp theo từ danh sách (xoay vòng)"""
    global proxy_list, proxy_index
    
    if not proxy_list:
        return None, None
    
    proxy = proxy_list[proxy_index]
    proxy_index = (proxy_index + 1) % len(proxy_list)
    return proxy["ip"], proxy["port"]

def build_proxy_list(custom_proxy, custom_port, use_internet_search):
    """
    Xây dựng danh sách proxy từ các nguồn khác nhau (EXCLUSIVE OR logic)
    - custom_proxy: proxy chỉ định
    - custom_port: port chỉ định
    - use_internet_search: dùng search từ internet (nếu True: IGNORE custom proxy)
    """
    global proxy_list
    proxy_list = []
    
    # EXCLUSIVE OR: Nếu check internet search, KHÔNG dùng custom proxy
    if use_internet_search:
        # Trường hợp 1: Search proxy từ internet (PRIMARY)
        log_message("Đang tìm kiếm proxy từ Geonode...", "INFO")
        internet_proxies = fetch_geonode_proxies()
        
        if internet_proxies:
            # Dùng port từ proxy (không có port custom khi dùng internet)
            for proxy in internet_proxies[:30]:  # Lấy 30 proxy đầu tiên
                port = proxy.get("port", "80")
                
                proxy_list.append({
                    "ip": proxy["ip"],
                    "port": port,
                    "url": f"http://{proxy['ip']}:{port}",
                    "country": proxy.get("country", "N/A"),
                    "uptime": proxy.get("uptime", 0),
                    "source": "internet"
                })
            log_message(f"Tìm được {len(internet_proxies[:30])} proxy từ internet", "SUCCESS")
    else:
        # Trường hợp 2: Dùng custom proxy (khi KHÔNG check internet search)
        if custom_proxy and custom_proxy.strip():
            custom_proxy = custom_proxy.strip()
            port = custom_port.strip() if custom_port and custom_port.strip() else "3128"
            proxy_list.append({
                "ip": custom_proxy,
                "port": port,
                "url": f"http://{custom_proxy}:{port}",
                "source": "custom"
            })
            log_message(f"Thêm proxy chỉ định: {custom_proxy}:{port}", "INFO")
    
    # Trường hợp 3: Không có proxy nào
    if not proxy_list:
        log_message("Không có proxy nào được chọn (sẽ chạy không dùng proxy)", "WARNING")
    else:
        log_message(f"Tổng cộng có {len(proxy_list)} proxy để sử dụng", "INFO")
    
    return proxy_list

def fetch_geonode_proxies():
    """Lay proxy tu Geonode API"""
    try:
        log_message("Dang lay proxy tu Geonode...", "INFO")
        response = requests.get(API_GEONODE, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            proxies = []
            
            for item in data.get("data", []):
                ip = item.get("ip")
                port = item.get("port")
                
                if ip and port:
                    proxy_url = f"http://{ip}:{port}"
                    proxies.append({
                        "url": proxy_url,
                        "ip": ip,
                        "port": port,
                        "uptime": item.get("upTime", 0),
                        "latency": item.get("latency", 0),
                        "country": item.get("country", "N/A"),
                        "city": item.get("city", "N/A")
                    })
            
            log_message(f"Lay duoc {len(proxies)} proxy tu Geonode", "SUCCESS")
            return proxies
        else:
            log_message(f"Geonode API loi: {response.status_code}", "ERROR")
            return []
    
    except Exception as e:
        log_message(f"Loi lay Geonode: {e}", "ERROR")
        return []

def check_single_proxy(proxy_info, port=None, timeout=3):
    """Robust proxy check:
    - Try multiple endpoints (httpbin, ipinfo, ifconfig.me)
    - Use a requests.Session with trust_env=False to avoid env proxy interference
    - Validate that response contains an IP address
    Returns True if any endpoint returns a body containing an IPv4 address.
    """
    test_port = port if port else str(proxy_info.get("port", "80"))
    # prefer full url if present
    proxy_url = proxy_info.get("url") or f"http://{proxy_info.get('ip')}:{test_port}"
    if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
        proxy_url = "http://" + proxy_url

    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {"User-Agent": "curl/7.68.0"}

    endpoints = [
        "http://httpbin.org/ip",
        "http://ipinfo.io/ip",
        "https://ifconfig.me/ip",
    ]

    session = requests.Session()
    session.trust_env = False
    session.headers.update(headers)

    for url in endpoints:
        try:
            r = session.get(url, proxies=proxies, timeout=timeout, allow_redirects=True)
            if r is None:
                continue
            # Accept any 2xx-3xx response; prefer explicit IP in body but accept non-empty body
            if 200 <= r.status_code < 400:
                text = r.text.strip()
                if not text:
                    continue

                # basic IPv4 detection
                if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
                    return True

                # sometimes JSON like {"ip":"x.x.x.x"}
                try:
                    j = r.json()
                    if isinstance(j, dict):
                        for v in j.values():
                            if isinstance(v, str) and re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", v):
                                return True
                except Exception:
                    pass

                # Fallback: non-empty response body -> consider proxy working
                return True
        except Exception:
            # ignore and try next endpoint
            continue

    return False

def test_all_proxies(proxy_entry=None, port_entry=None, internet_search_var=None):
    """Test proxy với EXCLUSIVE OR + real-time progress (tối ưu hiệu suất)"""
    use_internet_search = internet_search_var.get() if internet_search_var else False
    
    # BƯỚC 1: Xác định nguồn proxy
    if use_internet_search:
        log_message("🔍 Tìm proxy từ Geonode Internet...", "INFO")
        proxies = fetch_geonode_proxies()
        port = None
        
        if not proxies:
            log_message("❌ Không lấy được proxy nào từ Geonode", "ERROR")
            return []
    else:
        custom_proxy = proxy_entry.get().strip() if proxy_entry else None
        custom_port = port_entry.get().strip() if port_entry else None
        
        if not custom_proxy:
            log_message("⚠️ Vui lòng nhập proxy custom để kiểm tra", "WARNING")
            return []
        
        proxies = [{
            "ip": custom_proxy,
            "port": custom_port if custom_port else "3128",
            "url": f"http://{custom_proxy}:{custom_port if custom_port else '3128'}",
            "country": "Custom",
            "uptime": 100,
            "source": "custom"
        }]
        port = custom_port if custom_port else "3128"
        log_message(f"🔍 Kiểm tra proxy custom: {custom_proxy}:{port}", "INFO")
    
    # BƯỚC 2: Kiểm tra proxy với ThreadPoolExecutor + progress tracking
    check_count = min(10, len(proxies))  # Reduced from 30 to 10 for speed
    log_message(f"⏳ Bắt đầu kiểm tra {check_count} proxy (20 threads, 2s timeout)...", "INFO")
    
    live_proxies = []
    dead_proxies = []
    lock = threading.Lock()
    checked_count = [0]  # Use list to allow modification in nested function
    start_time = time.time()
    
    def check_worker(proxy_info):
        test_port = port if port else proxy_info.get("port", "80")
        result = check_single_proxy(proxy_info, test_port, timeout=2)  # Reduced from 3s to 2s
        
        with lock:
            checked_count[0] += 1
            current = checked_count[0]
            
            if result:
                live_proxies.append(proxy_info)
                status = "✅"
                level = "SUCCESS"
            else:
                dead_proxies.append(proxy_info)
                status = "❌"
                level = "INFO"
            
            # Real-time progress (every proxy) - NOW LOGGED
            progress_pct = (current / check_count) * 100
            log_msg = f"{status} [{current}/{check_count}] {progress_pct:.0f}% | {proxy_info['ip']}:{test_port}"
            log_message(log_msg, level)
    
    # Dùng ThreadPoolExecutor (optimized)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(check_worker, p) for p in proxies[:check_count]]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                pass  # Silent fail, progress continues
    
    elapsed = time.time() - start_time
    
    # BƯỚC 3: Kết quả tóm tắt
    speed = check_count / elapsed if elapsed > 0 else 0
    log_message(f"\n✅ HOÀN THÀNH: {len(live_proxies)} sống | {len(dead_proxies)} chết", "SUCCESS")
    log_message(f"⚡ Tốc độ: {elapsed:.2f}s | {speed:.1f} proxy/s", "INFO")
    
    if live_proxies:
        log_message(f"🏆 Top proxy live:", "SUCCESS")
        sorted_proxies = sorted(live_proxies, key=lambda x: x.get("uptime", 0), reverse=True)
        for i, proxy in enumerate(sorted_proxies[:3], 1):
            country = proxy.get("country", "N/A")
            uptime = proxy.get("uptime", "N/A")
            log_message(f"  {i}. {proxy['url']} ({country}) - {uptime}%", "SUCCESS")
    
    return live_proxies

# ==================== VIEON ACCOUNT CREATION ====================
def create_vieon_account(email_data, proxy, proxy_port, sec):
    """Tạo account Vieon với email"""
    global active_threads, success_count, error_count, stop_flag
    
    driver = None
    try:
        if not email_data:
            log_message(f"⚠️  Email data trống", "WARNING")
            with stats_lock:
                error_count += 1
            return False
        
        email = email_data["email"]
        email_password = email_data["password"]
        token = email_data["token"]
        
        log_message(f"Tao Vieon: {email}", "INFO")
        
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")  # Faster startup
        options.add_argument("--no-sandbox")  # Faster init
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        # Consolidated prefs: allow images (needed for captcha), but keep notifications blocked
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values": {
                "notifications": 2,
                "images": 1
            },
            "translate": {"enabled": False},
        }
        options.add_experimental_option("prefs", prefs)
        
        if proxy:
            options.add_argument(f"--proxy-server=http://{proxy}:{proxy_port}")
            log_message(f"Proxy: {proxy}:{proxy_port}", "INFO")
        
        # Force cleanup of any lingering Chrome processes before starting new one
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except:
            pass
        
        time.sleep(1)  # Give OS time to cleanup
        driver = uc.Chrome(headless=False, options=options, use_subprocess=True)
        driver.set_page_load_timeout(15)  # Timeout trang sau 15s
        
        log_message(f"Truy cap Vieon...", "INFO")
        try:
            driver.get("https://vieon.global/auth/?destination=/&page=/")
        except Exception as e:
            # Nếu timeout, vẫn tiếp tục (page đã load được phần nào)
            log_message(f"⚠️  Page load timeout (tiếp tục): {str(e)[:50]}", "WARNING")
        
        # Wait for page to be interactive - wait for button or form elements
        page_ready = False
        for attempt in range(3):  # Try up to 3 times
            try:
                # Check if register button or form elements exist
                WebDriverWait(driver, 2).until(lambda driver: 
                    driver.find_elements(By.CSS_SELECTOR, ".Style_button__T_Eqf.Style_primary__7QMpR") or
                    driver.find_elements(By.TAG_NAME, "button")
                )
                page_ready = True
                log_message(f"✓ Page đã sẵn sàng (attempt {attempt + 1})", "INFO")
                break
            except:
                if attempt < 2:
                    time.sleep(1)  # Wait before retrying
                continue
        
        if not page_ready:
            log_message(f"⚠️  Page không fully ready, cố gắng tiếp tục...", "WARNING")
        
        # Step 1: Attempt a robust click on the register button if present
        try:
            def try_click_register(retry_count=0):
                """Try to click register button with multiple strategies and retries"""
                max_retries = 2
                
                # Scroll to bottom to ensure button is visible
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.3)
                
                selectors = [
                    ".Style_button__T_Eqf.Style_primary__7QMpR",  # Most reliable, try first
                    "button[class*='Style_button'][class*='Style_primary']",
                    "//button[contains(text(), 'Đăng ký tài khoản')]",
                    "//button[contains(text(), 'Đăng ký')]",
                    "//button[contains(text(), 'Đăng ky')]",
                ]
                
                for sel in selectors:
                    try:
                        # Try to find element with short timeout
                        if sel.startswith("//"):
                            elem = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.XPATH, sel)))
                        else:
                            elem = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                        
                        # bring into view
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                        time.sleep(0.2)
                        
                        # Try multiple click strategies
                        click_strategies = [
                            ("click()", lambda: elem.click()),
                            ("JS click", lambda: driver.execute_script("arguments[0].click();", elem)),
                            ("ActionChains", lambda: ActionChains(driver).move_to_element(elem).click().perform()),
                            ("remove pointer-events", lambda: (
                                driver.execute_script("arguments[0].style.pointerEvents = 'auto';", elem),
                                elem.click()
                            )),
                        ]
                        
                        for strategy_name, strategy_func in click_strategies:
                            try:
                                strategy_func()
                                log_message(f"✅ CLICKED REGISTER BUTTON ({strategy_name}): {sel[:40]}", "SUCCESS")
                                return True
                            except Exception as e:
                                continue  # Try next strategy
                        
                    except Exception as e:
                        # Element not found or other error, try next selector
                        continue
                
                # If all selectors failed and retries remain, wait longer and retry
                if retry_count < max_retries:
                    log_message(f"⚠️  Button not found (retry {retry_count + 1}/{max_retries}), waiting...", "INFO")
                    time.sleep(2)
                    return try_click_register(retry_count + 1)
                
                log_message("❌ Could not click register button with any selector", "ERROR")
                return False

            if try_click_register():
                time.sleep(1)  # wait after clicking for page to update
            else:
                log_message("⚠️  Register button click failed - proceeding anyway", "WARNING")
                time.sleep(0.5)
        except Exception as e:
            log_message(f"Không thể auto-click register: {e}", "WARNING")

        if stop_flag:
            log_message("Bi dung", "WARNING")
            with stats_lock:
                error_count += 1
            return False
        
        wait = WebDriverWait(driver, 3)
        
        # Step 2: Input email
        log_message(f"Nhap email", "INFO")
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id='userName']")))
        input_box.send_keys(email)
        input_box.send_keys(Keys.ENTER)
        time.sleep(2)

        # Step 3: CAPTCHA DETECTION & WAIT (after email is submitted)
        def detect_and_wait_captcha():
            """Detect CAPTCHA and wait for user to solve it"""
            initial_wait = 15
            solve_wait = 120
            poll_interval = 1
            appearance_selectors = [
                "iframe[src*='recaptcha']",
                "iframe[src*='hcaptcha']",
                "iframe[src*='api2/anchor']",
                "div[class*='g-recaptcha']",
                "div[class*='grecaptcha']",
                "div[class*='h-captcha']",
                "div[data-sitekey]",
                "#rc-imageselect",
            ]
            
            log_message(f"🔍 Kiểm tra CAPTCHA...", "INFO")
            
            # First: wait for CAPTCHA to appear (give it time to load after email submission)
            widget_found = False
            for _ in range(initial_wait * 2):  # check twice per second
                try:
                    for sel in appearance_selectors:
                        try:
                            els = driver.find_elements(By.CSS_SELECTOR, sel)
                            if any(e.is_displayed() for e in els):
                                widget_found = True
                                log_message(f"🔐 CAPTCHA widget xuất hiện (selector: {sel})", "INFO")
                                break
                        except:
                            pass
                    if widget_found:
                        break
                except:
                    pass
                time.sleep(0.5)
            
            if not widget_found:
                log_message("✓ Không phát hiện CAPTCHA (không thấy widget) - tiếp tục", "INFO")
                return False
            
            # 2) Poll for solved state using multiple reliable checks
            def check_solved_js():
                js = '''
                try {
                    // reCAPTCHA v2 / invisible
                    if (typeof grecaptcha !== 'undefined') {
                        try { var r = grecaptcha.getResponse(); if (r) return r; } catch(e) {}
                    }
                    // hCaptcha
                    if (typeof hcaptcha !== 'undefined') {
                        try { var r2 = hcaptcha.getResponse(); if (r2) return r2; } catch(e) {}
                    }
                    // textarea token
                    var ta = document.querySelector('textarea[g-recaptcha-response], textarea[name="g-recaptcha-response"]');
                    if (ta && ta.value && ta.value.trim().length>0) return ta.value;
                    // checkbox green indicators
                    if (document.querySelector('.recaptcha-checkbox-checked') || document.querySelector('.rc-anchor-checkbox-checked')) return 'checked';
                    // aria-checked
                    var a = document.querySelector('[aria-checked="true"]'); if (a) return 'aria_checked';
                    return '';
                } catch(e) { return ''; }
                '''
                try:
                    return driver.execute_script(js)
                except:
                    return ''
            
            elapsed = 0
            while elapsed < solve_wait:
                try:
                    token_or_flag = check_solved_js()
                    if token_or_flag:
                        log_message("✅ CAPTCHA được giải (token/flag detected)", "SUCCESS")
                        return True
            
                    # fallback: if widget disappears, consider it solved
                    still_visible = False
                    for sel in appearance_selectors:
                        try:
                            els = driver.find_elements(By.CSS_SELECTOR, sel)
                            if any(e.is_displayed() for e in els):
                                still_visible = True
                                break
                        except:
                            pass
                    if not still_visible:
                        log_message("✅ CAPTCHA widget đã biến mất (th treat as solved)", "SUCCESS")
                        return True
                except:
                    pass
            
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            log_message(f"⚠️ CAPTCHA không được giải trong {solve_wait}s", "WARNING")
            return False
            
        
        # Check for CAPTCHA after email input
        captcha_detected = detect_and_wait_captcha()
        # If CAPTCHA was detected and solved, automatically click register again to proceed
        if captcha_detected:
            log_message(f"✅ CAPTCHA detected as solved — attempting automatic re-click of register...", "INFO")
            try:
                # Try a direct JS click on the expected register button
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, ".Style_button__T_Eqf.Style_primary__7QMpR")
                    driver.execute_script("arguments[0].click();", btn)
                    log_message(f"✓ Click lại button thành công (JS)", "SUCCESS")
                except Exception:
                    # Fallback: use the robust click routine if available
                    try:
                        try_click_register()
                        log_message(f"✓ Click lại button thành công (fallback)", "SUCCESS")
                    except Exception as e:
                        log_message(f"⚠️  Không thể click lại button tự động: {str(e)[:120]}", "WARNING")
                time.sleep(2)
            except Exception as e:
                log_message(f"⚠️  Lỗi khi cố gắng click lại nút sau CAPTCHA: {str(e)[:120]}", "WARNING")
                time.sleep(1)
            # After re-clicking, wait for the next-step UI (OTP input/form) to appear
            log_message("⏳ Waiting for OTP input/form to appear after re-click...", "INFO")
            otp_form_selectors = [
                "input[id^=':r']",   # OTP digit inputs like :r0: :r1: etc.
                "input[name='otp']",
                "input[id='otp']",
                "form input[type='tel']",
                "form input[type='number']",
                "div[class*='otp']",
            ]
            otp_form_found = False
            for wait_iter in range(20):  # wait up to ~20s
                try:
                    for sel in otp_form_selectors:
                        try:
                            elems = driver.find_elements(By.CSS_SELECTOR, sel)
                            if any(e.is_displayed() for e in elems):
                                otp_form_found = True
                                break
                        except:
                            pass
                    if otp_form_found:
                        log_message(f"✓ OTP input/form appeared (selector matched).", "SUCCESS")
                        break
                except:
                    pass
                time.sleep(1)
            if not otp_form_found:
                log_message("⚠️ OTP input/form did not appear within timeout — proceeding to poll email anyway.", "WARNING")
        else:
            # No CAPTCHA detected — ensure we submitted the email by clicking the start/register button
            log_message("ℹ️ Không có CAPTCHA — sẽ cố gắng nhấn nút 'Bắt đầu' / 'Đăng ký' để gửi email...", "INFO")
            # More robust submit attempt when no captcha present — try CSS selectors, then XPath by visible text
            css_candidates = [
                ".Style_button__T_Eqf.Style_primary__7QMp",
                ".Style_button__T_Eqf.Style_primary__7QMpR",
                "button[type='submit']",
                "button[class*='Style_button']",
                "button[class*='primary']",
            ]
            xpath_texts = [
                "Bắt đầu",
                "Bat dau",
                "Bắt dau",
                "Đăng ký",
                "Dang ky",
                "Bắt đầu đăng ký",
            ]

            def try_click_element(el):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                except:
                    pass
                time.sleep(0.2)

                # Try normal click
                try:
                    el.click()
                    return True
                except:
                    pass

                # Try JS click
                try:
                    driver.execute_script("arguments[0].click();", el)
                    return True
                except:
                    pass

                # Try dispatching mouse events (for tricky button handlers)
                try:
                    driver.execute_script("var el=arguments[0]; el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true})); el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true})); el.click();", el)
                    return True
                except:
                    pass

                # Try elementFromPoint click fallback (click at center)
                try:
                    box = el.rect
                    x = box['x'] + box['width']/2
                    y = box['y'] + box['height']/2
                    driver.execute_script(
                        "var ev = new MouseEvent('click', {bubbles:true, clientX: arguments[1], clientY: arguments[2]}); document.elementFromPoint(arguments[1], arguments[2]).dispatchEvent(ev);",
                        el, int(x), int(y)
                    )
                    return True
                except:
                    pass

                return False

            clicked_ok = False
            # Try CSS candidates first
            for sel in css_candidates:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        if not el.is_displayed():
                            continue
                        if try_click_element(el):
                            log_message(f"✓ Clicked submit button (css: {sel})", "SUCCESS")
                            clicked_ok = True
                            break
                    if clicked_ok:
                        break
                except Exception:
                    continue

            # If not found, try XPath searches by visible text
            if not clicked_ok:
                for txt in xpath_texts:
                    try:
                        xpath = f"//button[contains(normalize-space(string(.)), '{txt}')]"
                        elems = driver.find_elements(By.XPATH, xpath)
                        for el in elems:
                            if not el.is_displayed():
                                continue
                            if try_click_element(el):
                                log_message(f"✓ Clicked submit button (xpath text: {txt})", "SUCCESS")
                                clicked_ok = True
                                break
                        if clicked_ok:
                            break
                    except Exception:
                        continue

            if not clicked_ok:
                # As a last resort, try to remove potential overlays and retry a simple body send_keys(ENTER)
                try:
                    driver.execute_script("document.querySelectorAll('*').forEach(e=>{ if(getComputedStyle(e).position==='fixed' && (e.offsetHeight>0 && e.offsetWidth>0)){ e.style.pointerEvents='none'; } });")
                    time.sleep(0.3)
                    try:
                        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ENTER)
                        log_message("✓ Sent ENTER key to body as fallback", "SUCCESS")
                        clicked_ok = True
                    except:
                        pass
                except:
                    pass

            if not clicked_ok:
                log_message("⚠️ Không tìm thấy hoặc click nút submit thành công. Tiếp tục polling OTP...", "WARNING")
        
        # Cho OTP
        log_message(f"Cho OTP tu Vieon...", "INFO")
        otp = wait_for_otp(token, timeout=120)
        
        if not otp:
            log_message(f"Khong lay duoc OTP", "ERROR")
            with stats_lock:
                error_count += 1
            driver.quit()
            return False
        
        log_message(f"OTP: {otp}", "SUCCESS")
        
        # Log HTML form structure for debugging
        try:
            html_form = driver.find_element(By.TAG_NAME, "form").get_attribute("outerHTML")
            log_message(f"=== HTML FORM NHẬP OTP ===", "INFO")
            log_message(html_form[:1000], "INFO")  # Log first 1000 chars
            log_message(f"=== HẾT HTML ===", "INFO")
        except:
            pass
        
        # Nhap OTP
        log_message(f"Nhap OTP", "INFO")
        otp_digits = [int(digit) for digit in otp]
        
        for idx, digit in enumerate(otp_digits):
            try:
                input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"input[id=':r{idx}:']")))
                input_box.send_keys(digit)
            except:
                pass
        
        # Nhap password
        log_message(f"Nhap password", "INFO")
        time.sleep(1)
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id='password']")))
        input_box.send_keys('201098')
        
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id='confirmPassword']")))
        input_box.send_keys('201098')
        
        # Click checkbox
        checkbox = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span[class='Style_checkMark__CzYF7']")))
        checkbox.click()
        
        # Click submit/create account button
        log_message(f"Nhan nut tao account...", "INFO")
        try:
            # Try to find and click submit button
            submit_selectors = [
                ("CSS", ".Style_button__T_Eqf.Style_primary__7QMpR"),  # Primary button
                ("CSS", "button[type='submit']"),  # Submit button type
                ("CSS", "button[class*='Style_button'][class*='primary']"),  # Button with primary class
                ("XPATH", "//button[contains(text(), 'Tạo tài khoản')]"),
                ("XPATH", "//button[contains(text(), 'Tao tai khoan')]"),
                ("XPATH", "//button[contains(translate(., 'ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴĐÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỠ', 'aaaaaaaaaaaaaaaaaadeeeeeeeeeeiiiiiooooooooooooooooooouuuuuuuuuuuyyyyo'), ' t')]"),  # Vietnamese chars fallback
            ]
            
            submit_clicked = False
            for strategy, selector in submit_selectors:
                try:
                    log_message(f"  Thử: {strategy} - {selector[:40]}...", "INFO")
                    
                    if strategy == "XPATH":
                        btn = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.XPATH, selector)))
                    else:
                        btn = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    
                    # Scroll to button
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.3)
                    
                    # Try regular click
                    try:
                        btn.click()
                        log_message(f"✓ Clicked submit button: {selector[:40]}", "SUCCESS")
                        submit_clicked = True
                        break
                    except:
                        pass
                    
                    # Try JS click if regular click fails
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        log_message(f"✓ Clicked submit button with JS: {selector[:40]}", "SUCCESS")
                        submit_clicked = True
                        break
                    except:
                        pass
                    
                except:
                    continue
            
            if not submit_clicked:
                log_message(f"⚠️  Could not find submit button, trying JS to click any primary button...", "WARNING")
                try:
                    # Try to find button with JS
                    driver.execute_script("""
                        let buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            if (btn.classList.contains('Style_primary__7QMpR') || 
                                btn.innerText.includes('Tạo') || 
                                btn.innerText.includes('tao') ||
                                btn.type === 'submit') {
                                btn.click();
                                console.log('Clicked button: ' + btn.innerText);
                                break;
                            }
                        }
                    """)
                    log_message(f"✓ Clicked button with JS (any primary)", "SUCCESS")
                    submit_clicked = True
                except Exception as js_err:
                    log_message(f"⚠️  JS click error: {str(js_err)[:50]}", "WARNING")
            
            if not submit_clicked:
                log_message(f"⚠️  Could not click button, trying Enter key...", "WARNING")
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
        except Exception as e:
            log_message(f"⚠️  Submit error: {str(e)[:50]}", "WARNING")
        
        # Wait for form submission success - specifically check for the known success URL
        log_message(f"Chờ xác nhận tạo account (kiểm tra URL xác nhận)...", "INFO")
        submit_success = False
        success_url_fragment = "/ca-nhan/nguoi-dung/"
        expected_full_url = "https://vieon.global/ca-nhan/nguoi-dung/?destination=/&from=login"
        for attempt in range(45):  # Try for ~45 seconds
            try:
                current_url = driver.current_url
                # Direct match or fragment match
                if current_url == expected_full_url or success_url_fragment in current_url:
                    log_message(f"✓ Form submitted successfully (redirected to: {current_url})", "SUCCESS")
                    submit_success = True
                    break

                # Also allow other success indicators (message text)
                try:
                    success_elem = driver.find_element(By.XPATH, "//*[contains(translate(., 'THÀNHCÔNGthành côngSUCCESSsuccess', 'thànhcongsuccessthànhcong'), 'thành công') or contains(translate(., 'THÀNHCÔNGthành côngSUCCESSsuccess', 'thànhcongsuccessthànhcong'), 'success')]")
                    log_message(f"✓ Success message found", "SUCCESS")
                    submit_success = True
                    break
                except:
                    pass

                time.sleep(1)
            except Exception:
                time.sleep(1)

        if not submit_success:
            log_message(f"⚠️  Timeout waiting for confirmation URL ({expected_full_url}), nhưng tiếp tục...", "WARNING")
        
        time.sleep(int(sec))
        
        # Luu
        write_vieon_file(email, email_password, otp, "acc-global.csv")
        save_otp_to_csv(email, email_password, otp, "otp_accounts.csv")
        
        log_message(f"Tao thanh cong: {email}", "SUCCESS")
        with stats_lock:
            success_count += 1
        
        driver.quit()
        return True
        
    except Exception as e:
        log_message(f"Loi: {e}", "ERROR")
        
        # Hien thi dialog hoi tiep tuc khong
        try:
            if driver:
                driver.quit()
        except:
            pass
        
        # Show popup ask user
        def ask_user():
            result = messagebox.askyesno(
                "Chrome Error",
                f"Loi: {str(e)[:100]}\n\nBan co muon tiep tuc khong?",
                icon=messagebox.ERROR
            )
            return result
        
        if not ask_user():
            log_message("Nguoi dung chon dung", "WARNING")
            stop_flag = True
            with stats_lock:
                error_count += 1
            return False
        else:
            log_message("Nguoi dung chon tiep tuc", "INFO")
            with stats_lock:
                error_count += 1
            return False
    finally:
        global active_threads
        with stats_lock:
            active_threads -= 1
        update_stats()

def write_vieon_file(email, password_email, otp, filename="acc-global.csv"):
    """Lưu account Vieon vào file"""
    try:
        file_exists = os.path.isfile(filename)
        with open(filename, mode="a", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["email", "password", "otp", "password_email"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "email": email,
                "password": "201098",
                "otp": otp,
                "password_email": password_email,
            })
    except Exception as e:
        log_message(f"Lỗi lưu account: {e}", "ERROR")

# ==================== WORKER THREAD ====================
def worker_thread(thread_id, sec):
    """Worker thread xử lý tạo account với xoay vòng proxy"""
    global active_threads, stop_flag
    
    with stats_lock:
        active_threads += 1
    
    log_message(f"Luồng {thread_id} bắt đầu", "INFO")
    
    while not stop_flag:
        log_message(f"Luồng {thread_id}: Tạo email mới...", "INFO")
        email_data = create_email_with_token()
        
        if email_data:
            # Lấy proxy tiếp theo (xoay vòng)
            proxy, proxy_port = get_next_proxy()
            
            if proxy:
                log_message(f"Luồng {thread_id}: Sử dụng proxy {proxy}:{proxy_port}", "INFO")
            else:
                log_message(f"Luồng {thread_id}: Không dùng proxy", "INFO")
            
            # Create one Vieon account per newly generated mail.tm email
            create_vieon_account(email_data, proxy, proxy_port, sec)
        else:
            log_message("Không tạo được email", "WARNING")
            with stats_lock:
                error_count += 1
        
        if stop_flag:
            break
        
        time.sleep(2)
    
    log_message(f"Luồng {thread_id} kết thúc", "INFO")
    with stats_lock:
        active_threads -= 1

# ==================== GUI ====================
def start_bot(start_btn, stop_btn, proxy_entry, port_entry, sec_entry, threads_entry, 
              internet_search_var):
    """Bắt đầu bot với xử lý proxy từ nhiều nguồn"""
    global stop_flag, max_concurrent, start_time, success_count, error_count, proxy_index
    
    custom_proxy = proxy_entry.get().strip()
    custom_port = port_entry.get().strip()
    sec = sec_entry.get().strip()
    threads_str = threads_entry.get().strip()
    use_internet_search = internet_search_var.get()
    
    # Validate thông tin
    if not sec or not sec.isdigit():
        messagebox.showerror("Lỗi", "Vui lòng nhập số giây hợp lệ!")
        return
    
    if threads_str == "" or threads_str == "0":
        max_concurrent = 1
    elif threads_str.isdigit():
        max_concurrent = int(threads_str)
    else:
        messagebox.showerror("Lỗi", "Số luồng phải là số nguyên dương!")
        return
    
    # Xây dựng danh sách proxy từ các nguồn (EXCLUSIVE OR logic)
    if use_internet_search:
        build_proxy_list("", "", True)  # Dùng internet proxy only
    else:
        build_proxy_list(custom_proxy, custom_port, False)  # Dùng custom proxy only
    
    # Nếu không có proxy nào được chọn và không search internet
    if not proxy_list and not use_internet_search:
        log_message("Chuyển sang chế độ không dùng proxy", "WARNING")
    
    success_count = 0
    error_count = 0
    start_time = time.time()
    stop_flag = False
    proxy_index = 0
    
    start_btn.config(state="disabled")
    stop_btn.config(state="normal")
    proxy_entry.config(state="disabled")
    port_entry.config(state="disabled")
    sec_entry.config(state="disabled")
    threads_entry.config(state="disabled")
    
    log_message("=" * 70, "INFO")
    log_message("BẮT ĐẦU TẠO ACCOUNT", "INFO")
    if proxy_list:
        log_message(f"Sử dụng {len(proxy_list)} proxy (xoay vòng)", "INFO")
        for idx, p in enumerate(proxy_list[:5], 1):
            log_message(f"  {idx}. {p['ip']}:{p['port']} ({p.get('source', 'N/A')})", "INFO")
        if len(proxy_list) > 5:
            log_message(f"  ... và {len(proxy_list) - 5} proxy khác", "INFO")
    else:
        log_message("Chế độ: Không dùng proxy", "INFO")
    log_message(f"Thời gian chờ: {sec}s", "INFO")
    log_message(f"Số luồng: {max_concurrent}", "INFO")
    log_message("=" * 70, "INFO")
    
    for i in range(max_concurrent):
        t = threading.Thread(target=worker_thread, args=(i+1, int(sec)), daemon=True)
        t.start()
        log_message(f"Luồng {i+1} khởi động", "INFO")

def stop_bot_func(start_btn, stop_btn, proxy_entry, port_entry, sec_entry, threads_entry, 
                  internet_search_var):
    """Dừng bot gracefully"""
    global stop_flag, active_threads, start_time
    
    stop_flag = True
    
    log_message("", "INFO")
    log_message("DỪNG BOT - Chờ luồng hoàn thành...", "WARNING")
    
    stop_btn.config(state="disabled")
    
    # Chờ tất cả luồng kết thúc
    max_wait = 300  # 5 phút tối đa
    waited = 0
    while active_threads > 0 and waited < max_wait:
        with stats_lock:
            remaining = active_threads
        log_message(f"Chờ {remaining} luồng hoàn thành...", "WARNING")
        time.sleep(2)
        waited += 2
    
    log_message("", "INFO")
    log_message("=" * 70, "INFO")
    log_message("BOT ĐÃ DỪNG", "SUCCESS")
    log_message(f"Thành công: {success_count}", "SUCCESS")
    log_message(f"Lỗi: {error_count}", "ERROR")
    
    if start_time:
        elapsed = int(time.time() - start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        secs = elapsed % 60
        log_message(f"Tổng thời gian: {hours:02d}:{minutes:02d}:{secs:02d}", "INFO")
    
    log_message("=" * 70, "INFO")
    
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")
    proxy_entry.config(state="normal")
    port_entry.config(state="normal")
    sec_entry.config(state="normal")
    threads_entry.config(state="normal")
    
    messagebox.showinfo("Hoàn thành", f"Bot đã dừng!\n\nThành công: {success_count}\nLỗi: {error_count}")

# ==================== MAIN GUI ====================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("🚀 Vieon Account Creator v2")
    root.geometry("1100x850")
    root.configure(bg=THEMES["dark"]["bg"])
    root.resizable(True, True)
    
    # Ensure window is properly initialized
    root.update_idletasks()
    
    # Store references for theme switching
    theme_elements = {
        "root": root,
        "labels": [],
        "entries": [],
        "buttons": [],
        "frames": [],
    }
    
    def toggle_theme():
        """Thay đổi giao diện sáng/tối"""
        global current_theme
        current_theme = "light" if current_theme == "dark" else "dark"
        apply_theme()
        log_message(f"🎨 Đã chuyển sang theme: {'☀️ Sáng' if current_theme == 'light' else '🌙 Tối'}", "SUCCESS")
    
    def apply_theme():
        """Áp dụng theme cho toàn bộ giao diện"""
        theme = THEMES[current_theme]
        
        root.configure(bg=theme["bg"])
        
        # Update headers
        header_frame.configure(bg=theme["primary"])
        header.configure(bg=theme["primary"], fg=theme["accent"])
        theme_btn.configure(bg=theme["accent"], fg=theme["primary"], 
                           activebackground=theme["secondary"], activeforeground=theme["accent"])
        
        # Update control frames
        control_frame.configure(bg=theme["primary"])
        proxy_frame.configure(bg=theme["primary"])
        params_frame.configure(bg=theme["primary"])
        button_frame.configure(bg=theme["bg"])
        stats_frame.configure(bg=theme["primary"])
        log_frame.configure(bg=theme["bg"])
        
        # Update labels
        proxy_label.configure(bg=theme["primary"], fg=theme["accent"])
        sec_label.configure(bg=theme["primary"], fg=theme["accent"])
        port_label.configure(bg=theme["primary"], fg=theme["accent"])
        threads_label.configure(bg=theme["primary"], fg=theme["accent"])
        
        for label in theme_elements["labels"]:
            label.configure(bg=theme["primary"], fg=theme["accent"])
        
        # Update entries
        proxy_entry.configure(bg=theme["secondary"], fg=theme["fg"], insertbackground=theme["accent"])
        port_entry.configure(bg=theme["secondary"], fg=theme["fg"], insertbackground=theme["accent"])
        sec_entry.configure(bg=theme["secondary"], fg=theme["fg"], insertbackground=theme["accent"])
        threads_entry.configure(bg=theme["secondary"], fg=theme["fg"], insertbackground=theme["accent"])
        
        # Update buttons
        start_btn.configure(bg=theme["success"], fg=theme["primary"],
                           activebackground=theme["secondary"], activeforeground=theme["accent"])
        stop_btn.configure(bg=theme["error"], fg=theme["primary"],
                          activebackground=theme["secondary"], activeforeground=theme["accent"])
        
        # Update log output
        if current_theme == "light":
            log_output.configure(bg=theme["bg"], fg=theme["fg"], insertbackground=theme["info"])
            log_output.tag_config("INFO", foreground=theme["info"])
            log_output.tag_config("SUCCESS", foreground=theme["success"])
            log_output.tag_config("WARNING", foreground=theme["warning"])
            log_output.tag_config("ERROR", foreground=theme["error"])
        else:
            log_output.configure(bg=theme["bg"], fg=theme["info"], insertbackground=theme["info"])
            log_output.tag_config("INFO", foreground=theme["info"])
            log_output.tag_config("SUCCESS", foreground=theme["success"])
            log_output.tag_config("WARNING", foreground=theme["warning"])
            log_output.tag_config("ERROR", foreground=theme["error"])
        
        stats_label.configure(bg=theme["primary"], fg=theme["accent"])
    
    # ========== HEADER ==========
    header_frame = tk.Frame(root, bg=THEMES["dark"]["primary"], relief=tk.RAISED, bd=2)
    header_frame.pack(fill=tk.X)
    
    header_inner = tk.Frame(header_frame, bg=THEMES["dark"]["primary"])
    header_inner.pack(fill=tk.X, padx=10, pady=10)
    
    header = tk.Label(header_inner, text="🚀 VIEON ACCOUNT CREATOR", font=("Arial", 22, "bold"), 
                     bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"])
    header.pack(side=tk.LEFT, expand=True)
    
    theme_btn = tk.Button(header_inner, text="🌙 Theme", font=("Arial", 10, "bold"),
                         bg=THEMES["dark"]["accent"], fg=THEMES["dark"]["primary"],
                         command=toggle_theme, padx=10, pady=5, relief=tk.RAISED, bd=2)
    theme_btn.pack(side=tk.RIGHT, padx=5)
    
    # ========== CONTROL FRAME ==========
    control_frame = tk.Frame(root, bg=THEMES["dark"]["primary"], relief=tk.SUNKEN, bd=1)
    control_frame.pack(pady=10, padx=10, fill=tk.X)
    
    # Proxy Input
    proxy_frame = tk.Frame(control_frame, bg=THEMES["dark"]["primary"])
    proxy_frame.pack(pady=8, padx=15, fill=tk.X)
    
    proxy_label = tk.Label(proxy_frame, text="Proxy:", font=("Arial", 11, "bold"), 
                          bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"])
    proxy_label.pack(side=tk.LEFT, padx=5)
    
    proxy_entry = tk.Entry(proxy_frame, font=("Arial", 11), width=25, bg=THEMES["dark"]["secondary"], 
                          fg=THEMES["dark"]["fg"], insertbackground=THEMES["dark"]["accent"])
    proxy_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    port_label = tk.Label(proxy_frame, text="Port:", font=("Arial", 11, "bold"), 
                         bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"])
    port_label.pack(side=tk.LEFT, padx=(20, 5))
    
    port_entry = tk.Entry(proxy_frame, font=("Arial", 11), width=8, bg=THEMES["dark"]["secondary"], 
                         fg=THEMES["dark"]["fg"], insertbackground=THEMES["dark"]["accent"])
    port_entry.insert(0, "3128")
    port_entry.pack(side=tk.LEFT, padx=5)
    
    proxy_hint = tk.Label(proxy_frame, text="(để trống = không dùng)", font=("Arial", 9), 
                         bg=THEMES["dark"]["primary"], fg="#888888")
    proxy_hint.pack(side=tk.LEFT, padx=5)
    
    # Internet Search Option
    internet_frame = tk.Frame(control_frame, bg=THEMES["dark"]["primary"])
    internet_frame.pack(pady=8, padx=15, fill=tk.X)
    
    internet_search_var = tk.BooleanVar(value=False)
    internet_search_check = tk.Checkbutton(
        internet_frame, text="Search proxy on Internet",
        variable=internet_search_var,
        font=("Arial", 11, "bold"),
        bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"],
        activebackground=THEMES["dark"]["secondary"],
        activeforeground=THEMES["dark"]["accent"],
        selectcolor=THEMES["dark"]["secondary"],
        command=lambda: toggle_internet_proxy()
    )
    internet_search_check.pack(side=tk.LEFT, padx=5)
    
    def toggle_internet_proxy():
        """Bật/tắt proxy entry khi check/uncheck internet search"""
        if internet_search_var.get():
            # Nếu check internet: DISABLE proxy fields (dùng internet proxy only)
            proxy_entry.config(state="disabled")
            port_entry.config(state="disabled")
        else:
            # Nếu uncheck internet: ENABLE proxy fields (dùng custom proxy only)
            proxy_entry.config(state="normal")
            port_entry.config(state="normal")
    
    def toggle_internet_port():
        """Bật/tắt proxy entry khi check/uncheck internet search"""
        pass  # Hàm này đã được thay thế bởi toggle_internet_proxy()
    
    # Delay & Threads
    params_frame = tk.Frame(control_frame, bg=THEMES["dark"]["primary"])
    params_frame.pack(pady=8, padx=15, fill=tk.X)
    
    sec_label = tk.Label(params_frame, text="Delay (s):", font=("Arial", 11, "bold"), 
                        bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"])
    sec_label.pack(side=tk.LEFT, padx=5)
    
    sec_entry = tk.Entry(params_frame, font=("Arial", 11), width=8, bg=THEMES["dark"]["secondary"], 
                        fg=THEMES["dark"]["fg"], insertbackground=THEMES["dark"]["accent"])
    sec_entry.insert(0, "15")
    sec_entry.pack(side=tk.LEFT, padx=5)
    
    threads_label = tk.Label(params_frame, text="Luồng:", font=("Arial", 11, "bold"), 
                            bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"])
    threads_label.pack(side=tk.LEFT, padx=20)
    
    threads_entry = tk.Entry(params_frame, font=("Arial", 11), width=8, bg=THEMES["dark"]["secondary"], 
                            fg=THEMES["dark"]["fg"], insertbackground=THEMES["dark"]["accent"])
    threads_entry.insert(0, "1")
    threads_entry.pack(side=tk.LEFT, padx=5)
    
    threads_hint = tk.Label(params_frame, text="(mac dinh: 1)", font=("Arial", 9), 
                           bg=THEMES["dark"]["primary"], fg="#888888")
    threads_hint.pack(side=tk.LEFT, padx=5)
    
    # ========== BUTTONS ==========
    button_frame = tk.Frame(root, bg=THEMES["dark"]["bg"])
    button_frame.pack(pady=12)
    
    start_btn = tk.Button(
        button_frame, text="BẮT ĐẦU",
        font=("Arial", 12, "bold"),
        bg=THEMES["dark"]["success"], fg=THEMES["dark"]["primary"],
        activebackground=THEMES["dark"]["secondary"],
        padx=20, pady=10,
        command=lambda: start_bot(start_btn, stop_btn, proxy_entry, port_entry, sec_entry, threads_entry,
                                 internet_search_var),
        width=16,
        relief=tk.RAISED,
        bd=2
    )
    start_btn.pack(side=tk.LEFT, padx=8)
    
    stop_btn = tk.Button(
        button_frame, text="DỪNG",
        font=("Arial", 12, "bold"),
        bg=THEMES["dark"]["error"], fg=THEMES["dark"]["primary"],
        activebackground=THEMES["dark"]["secondary"],
        padx=20, pady=10,
        command=lambda: stop_bot_func(start_btn, stop_btn, proxy_entry, port_entry, sec_entry, threads_entry,
                                     internet_search_var),
        width=16,
        state="disabled",
        relief=tk.RAISED,
        bd=2
    )
    stop_btn.pack(side=tk.LEFT, padx=8)
    
    check_proxy_btn = tk.Button(
        button_frame, text="CHECK PROXY",
        font=("Arial", 12, "bold"),
        bg=THEMES["dark"]["warning"], fg=THEMES["dark"]["primary"],
        activebackground=THEMES["dark"]["secondary"],
        padx=15, pady=10,
        command=lambda: threading.Thread(target=test_all_proxies, args=(proxy_entry, port_entry, internet_search_var), daemon=True).start(),
        relief=tk.RAISED,
        bd=2
    )
    check_proxy_btn.pack(side=tk.LEFT, padx=8)
    
    verbose_btn = tk.Button(
        button_frame, text="VERBOSE OTP",
        font=("Arial", 12, "bold"),
        bg=THEMES["dark"]["secondary"], fg=THEMES["dark"]["primary"],
        activebackground=THEMES["dark"]["secondary"],
        padx=15, pady=10,
        command=lambda: verbose_check_email_dialog(),
        relief=tk.RAISED,
        bd=2
    )
    verbose_btn.pack(side=tk.LEFT, padx=8)
    
    # ========== STATS FRAME ==========
    stats_frame = tk.Frame(root, bg=THEMES["dark"]["primary"], relief=tk.SUNKEN, bd=1)
    stats_frame.pack(pady=8, padx=10, fill=tk.X)
    
    stats_label = tk.Label(stats_frame, 
                          text="Thành công: 0  |  Lỗi: 0  |  Thời gian: 00:00:00",
                          font=("Arial", 11, "bold"), bg=THEMES["dark"]["primary"], fg=THEMES["dark"]["accent"])
    stats_label.pack(pady=8)
    
    # ========== PROGRESS BAR ==========
    progress_var = tk.IntVar()
    progress_bar = ttk.Progressbar(root, length=200, mode='indeterminate',
                                   variable=progress_var)
    progress_bar.pack(pady=5, padx=10, fill=tk.X)
    
    # ========== OUTPUT LOG ==========
    log_label = tk.Label(root, text="📋 OUTPUT LOG", font=("Arial", 12, "bold"), 
                        bg=THEMES["dark"]["bg"], fg=THEMES["dark"]["accent"])
    log_label.pack(pady=(10, 5), padx=10, anchor="w")
    
    log_frame = tk.Frame(root, bg=THEMES["dark"]["bg"], relief=tk.SUNKEN, bd=2)
    log_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
    
    # Assign to global variable (declared at top of file)
    import sys
    this_module = sys.modules[__name__]
    this_module.log_output = scrolledtext.ScrolledText(
        log_frame, font=("Courier", 9), 
        bg=THEMES["dark"]["bg"], fg=THEMES["dark"]["info"],
        insertbackground=THEMES["dark"]["info"],
        state=tk.DISABLED,
        wrap=tk.WORD
    )
    log_output.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
    
    # Start async log processor
    process_log_queue()
    
    # Configure text tags for colors
    log_output.tag_config("INFO", foreground=THEMES["dark"]["info"])
    log_output.tag_config("SUCCESS", foreground=THEMES["dark"]["success"])
    log_output.tag_config("WARNING", foreground=THEMES["dark"]["warning"])
    log_output.tag_config("ERROR", foreground=THEMES["dark"]["error"])
    
    # ========== STATS UPDATE LOOP ==========
    def update_stats_loop():
        try:
            update_stats()
        except:
            pass
        root.after(2000, update_stats_loop)  # Increased to 2s to reduce CPU
    
    update_stats_loop()
    
    # Ensure window is visible and focused
    root.update()
    root.deiconify()  # Make sure window is shown
    root.lift()  # Bring to front
    root.focus()  # Set focus
    
    log_message("Ứng dụng sẵn sàng", "SUCCESS")
    log_message("Điền thông tin và nhấn 'BẮT ĐẦU'", "INFO")
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.quit()
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        root.quit()
