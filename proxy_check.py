# -*- coding: utf-8 -*-
import requests
import threading
import time
from datetime import datetime
import sys
import codecs
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up UTF-8 output stream
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# API Geonode
API_URL = "https://proxylist.geonode.com/api/proxy-list?limit=200&sort_by=lastChecked&sort_type=desc&protocols=http"
TIMEOUT = 3  # Timeout ngắn hơn để check nhanh
MAX_WORKERS = 20  # Số thread đồng thời

def log_message(msg, status="INFO"):
    """Hiển thị thông báo với timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{status}] {msg}")

def fetch_proxies():
    """Lấy danh sách proxy từ Geonode API"""
    try:
        log_message("Đang lấy proxy từ Geonode API...", "INFO")
        response = requests.get(API_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            proxies = []
            
            for item in data.get("data", []):
                ip = item.get("ip")
                port = item.get("port")
                uptime = item.get("upTime", 0)
                latency = item.get("latency", 0)
                
                if ip and port:
                    proxy_url = f"http://{ip}:{port}"
                    proxies.append({
                        "url": proxy_url,
                        "ip": ip,
                        "port": port,
                        "uptime": uptime,
                        "latency": latency,
                        "country": item.get("country", "N/A"),
                        "city": item.get("city", "N/A")
                    })
            
            log_message(f"Lấy được {len(proxies)} proxy", "SUCCESS")
            return proxies
        else:
            log_message(f"API trả về lỗi: {response.status_code}", "ERROR")
            return []
    
    except Exception as e:
        log_message(f"Lỗi khi lấy proxy: {e}", "ERROR")
        return []

def check_proxy(proxy_info, timeout=TIMEOUT):
    """Kiểm tra proxy có live không"""
    try:
        proxy_url = proxy_info["url"]
        response = requests.get(
            "http://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=timeout
        )
        is_live = response.status_code == 200
        
        # Log real-time
        status = "Live" if is_live else "Dead"
        if is_live:
            country = proxy_info.get("country", "N/A")
            city = proxy_info.get("city", "N/A")
            uptime = proxy_info.get("uptime", 0)
            log_message(f"✓ {proxy_info['ip']}:{proxy_info['port']} - {country}/{city} - Uptime: {uptime}%", "SUCCESS")
        else:
            log_message(f"✗ {proxy_info['ip']}:{proxy_info['port']}", "ERROR")
        
        return is_live
    except Exception as e:
        log_message(f"✗ {proxy_info['ip']}:{proxy_info['port']} - Lỗi: {str(e)[:30]}", "ERROR")
        return False

def test_proxies_concurrent(proxies, max_threads=MAX_WORKERS):
    """Kiểm tra proxy với ThreadPoolExecutor (nhanh hơn)"""
    live_proxies = []
    dead_proxies = []
    total = len(proxies)
    tested = 0
    lock = threading.Lock()
    
    def worker(proxy_info):
        nonlocal tested
        result = check_proxy(proxy_info, timeout=TIMEOUT)
        with lock:
            tested += 1
            if result:
                live_proxies.append(proxy_info)
            else:
                dead_proxies.append(proxy_info)
            # Hiển thị tiến độ
            if tested % 5 == 0:
                log_message(f"Đã kiểm tra: {tested}/{total}", "INFO")
        return result
    
    # Dùng ThreadPoolExecutor để quản lý threads hiệu quả
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(worker, p) for p in proxies]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log_message(f"Lỗi trong thread: {e}", "ERROR")
    
    return live_proxies, dead_proxies

def save_proxies_to_file(live_proxies, filename="live_proxies.txt"):
    """Lưu proxy live vào file"""
    try:
        with open(filename, "w") as f:
            for proxy in live_proxies:
                f.write(f"{proxy['url']}\n")
        
        log_message(f"Đã lưu {len(live_proxies)} proxy vào {filename}", "SUCCESS")
    except Exception as e:
        log_message(f"Lỗi khi lưu file: {e}", "ERROR")

def main():
    print("\n" + "="*60)
    print("PROXY CHECKER - Geonode API")
    print("="*60 + "\n")
    
    # Bước 1: Lấy proxy từ API
    log_message("Bước 1: Lấy proxy từ Geonode API", "INFO")
    proxies = fetch_proxies()
    
    if not proxies:
        log_message("Không lấy được proxy nào", "ERROR")
        return
    
    # Bước 2: Kiểm tra proxy
    check_count = min(50, len(proxies))  # Check tối đa 50 proxy
    log_message(f"Bước 2: Kiểm tra {check_count} proxy (timeout: {TIMEOUT}s, {MAX_WORKERS} thread)...", "INFO")
    start_time = time.time()
    live_proxies, dead_proxies = test_proxies_concurrent(proxies[:check_count], max_threads=MAX_WORKERS)
    elapsed = time.time() - start_time
    
    # Bước 3: Kết quả
    print("\n" + "="*60)
    print("KẾT QUẢ")
    print("="*60)
    live_count = len(live_proxies)
    dead_count = len(dead_proxies)
    speed = check_count / elapsed if elapsed > 0 else 0
    log_message(f"Live: {live_count} proxy | Dead: {dead_count} proxy", "SUCCESS")
    log_message(f"Thời gian: {elapsed:.2f}s | Tốc độ: {speed:.1f} proxy/s", "INFO")
    
    if live_proxies:
        print("\nTop 10 proxy live:")
        # Sắp xếp theo uptime cao nhất
        sorted_proxies = sorted(live_proxies, key=lambda x: x.get("uptime", 0), reverse=True)
        for i, proxy in enumerate(sorted_proxies[:10], 1):
            print(f"  {i}. {proxy['url']} ({proxy['country']}/{proxy['city']}) - Uptime: {proxy['uptime']}%")
    
    # Bước 4: Lưu file
    log_message("Bước 4: Lưu proxy vào file", "INFO")
    save_proxies_to_file(live_proxies)
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()