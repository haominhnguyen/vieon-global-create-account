import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import threading
import os
import ssl
import concurrent.futures
ssl._create_default_https_context = ssl._create_unverified_context
import requests
import re
import time

#pyinstaller --onefile --windowed --icon=icon_2.ico account.py


API = "https://api.mail.tm"

users = []  # Danh sách accounts

# Cờ dừng bot
def update_status(listbox, index, status):
   def update():
       username = users[index]['username']
       text = f"{index}. {username}: {status}"
       listbox.delete(index)
       listbox.insert(index, text)
       if status == "Đang tao... ⏳":
           listbox.itemconfig(index, fg="yellow")
       elif status == "Đã tạo ✅":
           listbox.itemconfig(index, fg="green")
       elif status.startswith("Lỗi ❌"):
           listbox.itemconfig(index, fg="red")
       else:
           listbox.itemconfig(index, fg="white")
       listbox.update()
   listbox.after(0, update)

def get_all_otps(token):
    otp_list = []
    messages = get_messages(token)
    for msg in messages:
        content = get_message_content(token, msg["id"])
        otps = re.findall(r"\b\d{4}\b", content)  # tất cả OTP 4 chữ số
        otp_list.extend(otps)
    return otp_list

# --- ĐĂNG NHẬP ---
def login_mailtm(email, password):
    res = requests.post(f"{API}/token", json={
        "address": email,
        "password": password
    })

    if res.status_code != 200:
        print("❌ Lỗi đăng nhập:", res.text)
        return None

    print("✅ Đăng nhập thành công!")
    token = res.json()["token"]

    if token:
        print("\n⏳ Đang đợi email OTP...")
        for _ in range(60):
            inbox = get_messages(token)
            if inbox:
                for msg in inbox:
                    content = get_message_content(token, msg["id"])
                    otp = extract_otp(content)
                    if otp:
                        # Chuyển OTP thành list các số
                        otp_array = [int(digit) for digit in otp]
                        return otp_array
            time.sleep(1)
        print("❌ Không tìm thấy OTP trong thời gian chờ.")
        return None
    


# --- LẤY DANH SÁCH EMAIL ---
def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{API}/messages", headers=headers)

    if res.status_code != 200:
        print("❌ Lỗi lấy inbox:", res.text)
        return []

    return res.json()["hydra:member"]


# --- LẤY NỘI DUNG EMAIL ---
def get_message_content(token, message_id):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{API}/messages/{message_id}", headers=headers)

    if res.status_code != 200:
        print("❌ Lỗi lấy nội dung email:", res.text)
        return None

    return res.json()["text"]


# --- TRÍCH OTP ---
def extract_otp(text):
    otp = re.search(r"\b\d{4,6}\b", text)
    return otp.group() if otp else None



def create_account(account, index, listbox, proxy, sec):
    try:
        update_status(listbox, index, "Đang tao... ⏳")
        username = account['username']
        password = account['password']
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_experimental_option("prefs", {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False
            })
        prefs = {
            "profile.default_content_setting_values.notifications": 2,  # 2 = Block, 1 = Allow
            "translate": {"enabled": False}, 
        }
        options.add_experimental_option("prefs", prefs)
        options.add_argument(f"--proxy-server=http://{proxy}:3128")
        driver = uc.Chrome(headless=False, options=options, use_subprocess=True)
        driver.set_window_size(900, 650)
        driver.set_window_position(0, 0)
        driver.get("https://vieon.global/auth/?destination=/&page=/")
        wait = WebDriverWait(driver, 10)
        
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id='userName']")))
        input_box.send_keys(username)
        time.sleep(1)
        input_box.send_keys(Keys.ENTER)
        time.sleep(5)
        arr = login_mailtm(username,password)
        print(arr)
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id=':r0:']")))
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id=':r0:']")))
        input_box.send_keys(int(arr[0]))
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id=':r1:']")))
        input_box.send_keys(int(arr[1]))
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id=':r2:']")))
        input_box.send_keys(int(arr[2]))
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id=':r3:']")))
        input_box.send_keys(int(arr[3]))
        time.sleep(2)
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id='password']")))
        input_box.send_keys('201098')
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id='confirmPassword']")))
        input_box.send_keys('201098')
        checkbox = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span[class='Style_checkMark__CzYF7']")))
        checkbox.click()
        time.sleep(int(sec))
        write_file(username, password, 1, "acc-global.csv")
        update_status(listbox, index, "Đã tạo ✅")
        driver.quit()
    except Exception as e:
        print(e)
        update_status(listbox, index, "Lỗi ❌")
        driver.quit()


# Ghi file lỗi
def write_file(username, password, vote, filename="errors.csv"):
   file_exists = os.path.isfile(filename)
   with open(filename, mode="a", newline='', encoding="utf-8") as f:
       writer = csv.DictWriter(f, fieldnames=["username", "password", "vote", "password_email"])
       if not file_exists:
           writer.writeheader()
       writer.writerow({
           "username": username,
           "password": "201098",
           "vote": vote,
           "password_email": password,
       })

# Cờ dừng bot
def stop_bot():
    global stop_flag
    stop_flag = True
    start_btn.config(state="normal")
    proxy.config(state="normal")

# Hàm bắt đầu bot
def start_bot(listbox, start_btn, proxy, sec):
    def run():
        global stop_flag
        stop_flag = False
        if not users:
            messagebox.showerror("Lỗi", "Chưa upload file CSV!")
            start_btn.config(state="normal")
            proxy.config(state="normal")
            return
        if proxy.get() == '':
            messagebox.showerror("Lỗi", "Hãy thêm proxy!")
            start_btn.config(state="normal")
            proxy.config(state="normal")
            return
        start_btn.config(state="disabled")
        proxy.config(state="disabled")
        for index, account in enumerate(users):
            create_account(account, index, listbox, proxy.get(), sec.get())
        if not stop_flag:
            messagebox.showinfo("Hoàn thành", "Đã tạo xong tất cả tài khoản!")
        else:
            messagebox.showinfo("Đã dừng", "Bot đã dừng giữa chừng!")
        start_btn.config(state="normal")
        proxy.config(state="normal")
    t = threading.Thread(target=run)
    t.start()

# Hàm upload file CSV
def upload_file(listbox, total_label):
   global users
   file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
   if file_path:
       with open(file_path, newline='', encoding='utf-8') as csvfile:
           reader = csv.DictReader(csvfile)
           users = list(reader)
       total_label.config(text=f"Tổng số account: {len(users)}")
       listbox.delete(0, tk.END)
       for i, account in enumerate(users):
           listbox.insert(tk.END, f"{i}. {account['username']}: Chưa tạo ⏳")

# ---------- GUI ----------
root = tk.Tk()

root.title("Tạo account")

root.geometry("500x700")

root.configure(bg="#1e1e2f")

header = tk.Label(root, text="Em Linh Say Hi", font=(
   "Arial", 24, "bold"), bg="#1e1e2f", fg="#ffffff")

header.pack(pady=10)

upload_btn = tk.Button(root, text="📂 Upload CSV", font=("Arial", 12, "bold"), bg="#4caf50", fg="#ffffff",
                      activebackground="#45a049", padx=10, pady=5, command=lambda: upload_file(listbox, total_label))

upload_btn.pack(pady=5)

total_label = tk.Label(root, text="Tổng số account: 0",
                      font=("Arial", 12), bg="#1e1e2f", fg="#ffffff")

total_label.pack(pady=5)

total_label.pack(pady=5)

workers_frame = tk.Frame(root)
workers_frame.pack(pady=(10, 10))

workers_label = tk.Label(workers_frame, text="Nhập proxy:")
workers_label.pack(side=tk.LEFT, padx=(0, 10))

proxy = tk.Entry(workers_frame, width=35)
proxy.insert(0, "")
proxy.pack(side=tk.LEFT)


se_frame = tk.Frame(root)
se_frame.pack(pady=(10, 10))

se_label = tk.Label(se_frame, text="Nhập số giây:")
se_label.pack(side=tk.LEFT, padx=(0, 10))

sec = tk.Entry(se_frame, width=10)
sec.insert(0, "15")
sec.pack(side=tk.LEFT)

listbox_frame = tk.Frame(root, bg="#1e1e2f")

listbox_frame.pack(pady=5, expand=True, fill=tk.BOTH)

listbox = tk.Listbox(listbox_frame, font=("Arial", 14), bg="#2e2e3e", fg="#ffffff", selectbackground="#555555", width=80, height=15)

listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10, pady=10)

scrollbar = tk.Scrollbar(listbox_frame)

scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

listbox.config(yscrollcommand=scrollbar.set)

scrollbar.config(command=listbox.yview)

button_frame = tk.Frame(root, bg="#1e1e2f")

button_frame.pack(pady=10)

button_frame = tk.Frame(root, bg="#1e1e2f")

button_frame.pack(pady=10)

start_btn = tk.Button(
   button_frame, text="🚀 Bắt đầu Tao",
   font=("Arial", 12, "bold"),
   bg="#2196f3", fg="#ffffff",
   activebackground="#1e88e5",
   padx=10, pady=5,
   command=lambda: start_bot(listbox, start_btn, proxy, sec),
   width=15  # chiều ngang bằng nhau
)
start_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
stop_btn = tk.Button(
   button_frame, text="🛑 Stop",
   font=("Arial", 12, "bold"),
   bg="#2196f3", fg="#ffffff",
   activebackground="#e53935",
   padx=10, pady=5,
   command=stop_bot,
   width=15  # chiều ngang bằng nhau
)
stop_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
root.mainloop()
