"""
Create a new mail.tm temporary email account and fetch its token.

Requires: pip install requests
"""

import requests, secrets, string, time, csv, os, re

BASE = "https://api.mail.tm"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

def random_string(n=12):
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def get_domains():
    """Return list of domain dicts from /domains (hydra:member)."""
    r = SESSION.get(f"{BASE}/domains")
    r.raise_for_status()
    data = r.json()
    # Handle both dict and list responses
    if isinstance(data, list):
        return data
    return data.get("hydra:member", [])

def create_account(address, password):
    """POST /accounts to create account. Returns JSON account object."""
    payload = {"address": address, "password": password}
    r = SESSION.post(f"{BASE}/accounts", json=payload)
    # 201 expected on success; raise for other HTTP errors
    r.raise_for_status()
    return r.json()

def get_token(address, password):
    """POST /token to obtain {id, token}"""
    payload = {"address": address, "password": password}
    r = SESSION.post(f"{BASE}/token", json=payload)
    r.raise_for_status()
    return r.json()  # contains 'token' and 'id'

def list_messages(token, page=1):
    """GET /messages authenticated — returns hydra:member list"""
    headers = {"Authorization": f"Bearer {token}"}
    r = SESSION.get(f"{BASE}/messages", headers=headers, params={"page": page})
    r.raise_for_status()
    return r.json()

def get_message_content(token, message_id):
    """GET /messages/{id} to fetch full message content"""
    headers = {"Authorization": f"Bearer {token}"}
    r = SESSION.get(f"{BASE}/messages/{message_id}", headers=headers)
    r.raise_for_status()
    return r.json().get("text", "")

def extract_otp(text):
    """Extract OTP (4-6 digits) from email content"""
    otp = re.search(r"\b\d{4,6}\b", text)
    return otp.group() if otp else None

def save_to_csv(email, password, filename="email_accounts.csv"):
    """Save email and password to CSV file"""
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "password"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "email": email,
            "password": password,
        })
    print(f"✅ Saved to {filename}: {email}")

def wait_for_otp(token, timeout=60):
    """Wait for and extract OTP from email"""
    print(f"⏳ Đang đợi email OTP (tối đa {timeout} giây)...")
    for attempt in range(timeout):
        try:
            msgs = list_messages(token)
            if isinstance(msgs, list):
                messages = msgs
            else:
                messages = msgs.get("hydra:member", [])
            
            for msg in messages:
                content = get_message_content(token, msg["id"])
                otp = extract_otp(content)
                if otp:
                    print(f"✅ Tìm thấy OTP: {otp}")
                    return otp
        except Exception as e:
            print(f"Lỗi kiểm tra email: {e}")
        
        time.sleep(1)
    
    print("❌ Không tìm thấy OTP trong thời gian chờ.")
    return None

def create_full_account(email_filename="email_accounts.csv", otp_filename="otp_accounts.csv"):
    """
    Tổng hợp toàn bộ luồng:
    1. Tạo mới email
    2. Lấy user và password từ email
    3. Lưu vào file email_accounts.csv
    4. Chờ nhận email OTP
    5. Lấy OTP từ email
    6. Lưu OTP vào file otp_accounts.csv
    """
    try:
        print("\n" + "="*60)
        print("🚀 BẮT ĐẦU LUỒNG TẠO ACCOUNT")
        print("="*60)
        
        # 1) Lấy domain
        print("\n📌 Bước 1: Lấy domain...")
        domains = get_domains()
        if not domains:
            raise SystemExit("❌ Không có domain nào từ mail.tm")
        domain = domains[0]["domain"]
        print(f"✅ Domain: {domain}")
        
        # 2) Tạo email và password
        print("\n📌 Bước 2: Tạo email ngẫu nhiên...")
        username = random_string(10)
        password = random_string(16)
        email = f"{username}@{domain}"
        print(f"📧 Email: {email}")
        print(f"🔐 Password: {password}")
        
        # 3) Tạo account email
        print("\n📌 Bước 3: Tạo account trên mail.tm...")
        try:
            account = create_account(email, password)
            account_id = account.get("id")
            print(f"✅ Account tạo thành công. ID: {account_id}")
        except requests.HTTPError as e:
            print(f"❌ Lỗi tạo account: {e.response.status_code} - {e.response.text}")
            raise
        
        # 4) Lấy token
        print("\n📌 Bước 4: Lấy token để truy cập email...")
        for attempt in range(3):
            try:
                token_resp = get_token(email, password)
                break
            except requests.HTTPError as exc:
                print(f"⚠️  Lần {attempt + 1}: Token request lỗi {exc.response.status_code}, đang retry...")
                time.sleep(1)
        else:
            raise SystemExit("❌ Không lấy được token sau 3 lần thử")
        
        token = token_resp["token"]
        print(f"✅ Token lấy thành công: {token[:24]}...")
        
        # 5) Lưu email và password vào file
        print("\n📌 Bước 5: Lưu email và password...")
        save_to_csv(email, password, email_filename)
        
        # 6) Chờ và lấy OTP từ email
        print("\n📌 Bước 6: Chờ nhận OTP từ email...")
        otp = wait_for_otp(token, timeout=120)
        
        if otp:
            # Lưu OTP vào file
            file_exists = os.path.isfile(otp_filename)
            with open(otp_filename, mode="a", newline='', encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["email", "password", "otp"])
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "email": email,
                    "password": password,
                    "otp": otp,
                })
            print(f"✅ Lưu OTP vào {otp_filename}: {otp}")
            
            print("\n" + "="*60)
            print("✅ HOÀN THÀNH TOÀN BỘ LUỒNG")
            print("="*60)
            print(f"📧 Email: {email}")
            print(f"🔐 Password: {password}")
            print(f"🔑 OTP: {otp}")
            print("="*60 + "\n")
            
            return {
                "email": email,
                "password": password,
                "otp": otp,
                "token": token,
                "account_id": account_id
            }
        else:
            print("⚠️  Không tìm thấy OTP nhưng email đã được tạo")
            return {
                "email": email,
                "password": password,
                "otp": None,
                "token": token,
                "account_id": account_id
            }
            
    except Exception as e:
        print(f"\n❌ LỖI: {e}")
        return None

if __name__ == "__main__":
    # Chạy luồng tạo account toàn bộ
    result = create_full_account()
    
    # Để chạy nhiều account, có thể gọi lặp lại:
    # for i in range(5):
    #     print(f"\n\n>>> Tạo account lần {i+1} <<<")
    #     result = create_full_account()
