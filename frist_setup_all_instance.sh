#!/bin/bash
set -e

# --- Config ---
USERNAME="${1:-ubuntu}"
PASSWORD="${2:-123456}"
SQUID_PORT=3128
FILE_LIMIT=500000

# ===========================
# STEP 0: Detect VPS Public IP
# ===========================
echo "=== Detecting VPS Public IP ==="
IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip || true)
[ -z "$IP" ] && IP=$(curl -s http://ipinfo.io/ip)
echo "Public IP detected: $IP"

# ===========================
# STEP 1: Create user & set password
# ===========================
echo "=== Creating user $USERNAME (if not exists) and setting password ==="
if id "$USERNAME" &>/dev/null; then
    echo "User $USERNAME exists, setting password..."
else
    echo "Creating user $USERNAME..."
    sudo adduser --disabled-password --gecos "" "$USERNAME"
fi
echo "$USERNAME:$PASSWORD" | sudo chpasswd
echo "User $USERNAME password set to $PASSWORD"

# ===========================
# STEP 1.1: Fix cloud-init override
# ===========================
echo "=== Fix cloud-init SSH override ==="
sudo mkdir -p /etc/cloud/cloud.cfg.d
sudo bash -c 'cat > /etc/cloud/cloud.cfg.d/99-disable-ssh-password.cfg <<EOF
ssh_pwauth: true
disable_root: false
EOF'

# ===========================
# STEP 2: Update Ubuntu
# ===========================
echo "=== Updating Ubuntu ==="
sudo apt update -y && sudo apt upgrade -y

# ===========================
# STEP 3: Install Squid + Nano + UFW
# ===========================
echo "=== Installing Squid + Nano + UFW ==="
sudo apt install -y squid nano ufw

# ===========================
# STEP 4: Increase file descriptors
# ===========================
echo "=== Increasing system file descriptors ==="
echo "fs.file-max = $FILE_LIMIT" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

sudo bash -c "cat > /etc/security/limits.conf <<EOF
* soft nofile $FILE_LIMIT
* hard nofile $FILE_LIMIT
root soft nofile $FILE_LIMIT
root hard nofile $FILE_LIMIT
EOF"

sudo mkdir -p /etc/systemd/system/squid.service.d
sudo bash -c "cat > /etc/systemd/system/squid.service.d/override.conf <<EOF
[Service]
LimitNOFILE=$FILE_LIMIT
EOF"

sudo systemctl daemon-reload

# ===========================
# STEP 5: Configure Squid
# ===========================
echo "=== Configuring Squid ==="
sudo bash -c "cat > /etc/squid/squid.conf <<EOF
max_filedescriptors $FILE_LIMIT
http_port 0.0.0.0:$SQUID_PORT
client_persistent_connections on
server_persistent_connections on
tcp_outgoing_address 0.0.0.0
# Allow all
acl all src 0.0.0.0/0
http_access allow all
EOF"

sudo systemctl restart squid
sleep 2

# ===========================
# STEP 6: Enable and configure UFW
# ===========================
echo "=== Enabling UFW and allowing Squid port ==="
sudo ufw allow $SQUID_PORT/tcp
sudo ufw --force enable
sudo ufw status

# ===========================
# STEP 7: SSH configuration - enable password login, disable key
# ===========================
echo "=== Configuring SSH ==="
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PubkeyAuthentication .*/PubkeyAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?ChallengeResponseAuthentication .*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?UsePAM .*/UsePAM yes/' /etc/ssh/sshd_config

for f in /etc/ssh/sshd_config.d/*.conf; do
    [ -e "$f" ] || continue
    echo "Fixing $f"
    sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' "$f"
    sudo sed -i 's/^#\?PubkeyAuthentication .*/PubkeyAuthentication no/' "$f"
done

sudo systemctl restart ssh

# ===========================
# STEP 8: Check Squid open files
# ===========================
echo "=== Checking Squid Max Open Files ==="
PID=$(pidof squid)
cat /proc/$PID/limits | grep 'Max open files'

# ===========================
# STEP 9: Finish
# ===========================
echo
echo "===================================================="
echo "🎉 FULL VPS SETUP COMPLETE!"
echo "User: $USERNAME"
echo "Password: $PASSWORD"
echo "SSH password login ENABLED, key login DISABLED"
echo "Squid proxy: http://$IP:$SQUID_PORT"
echo "===================================================="

# Test proxy
echo "=== Testing proxy with curl ==="
curl -x http://$IP:$SQUID_PORT http://ipinfo.io --max-time 5 || echo "Proxy test failed"
echo "===================================================="
