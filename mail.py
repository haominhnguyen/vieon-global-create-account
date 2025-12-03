import requests
import random
import string
import time
import os
import csv

API = "https://api.mail.tm"

def random_string(length=10):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

def create_account():
    email = random_string() + "@comfythings.com"
    password = random_string(12)

    # Tạo tài khoản
    r = requests.post(f"{API}/accounts", json={
        "address": email,
        "password": password
    })

    if r.status_code != 201:
        print("❌ Lỗi tạo tài khoản:", r.text)
        return None

    # Lấy token đăng nhập
    token_res = requests.post(f"{API}/token", json={
        "address": email,
        "password": password
    })

    if token_res.status_code != 200:
        print("❌ Lỗi lấy token:", token_res.text)
        return None

    token = token_res.json()["token"]

    return {
        "email": email,
        "password": password,
        "token": token
    }
def write_file(username, password, filename="emailrrors.csv"):
   file_exists = os.path.isfile(filename)
   with open(filename, mode="a", newline='', encoding="utf-8") as f:
       writer = csv.DictWriter(f, fieldnames=["username", "password"])
       if not file_exists:
           writer.writeheader()
       writer.writerow({
           "username": username,
           "password": password,
       })

def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    inbox = requests.get(f"{API}/messages", headers=headers).json()
    return inbox

# --- MAIN ---
number_of_emails = 2000  # đổi số lượng tại đây
accounts = []

for i in range(number_of_emails):
    print(f"\n===== Tạo email thứ {i+1} =====")
    acc = create_account()
    if acc:
        print("📧 Email:", acc["email"])
        print("🔑 Pass:", acc["password"])
        print("🪪 Token:", acc["token"])
        accounts.append(acc)
        write_file(acc['email'],acc['password'])
    time.sleep(0.5)

print("\n🎉 Hoàn tất tạo email!")
print("Danh sách tài khoản:")
for acc in accounts:
    print(f"- {acc['email']},{acc['password']}")


