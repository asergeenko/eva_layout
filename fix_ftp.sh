#!/bin/bash
# Quick FTP fix script - run this on the server if FTP is not working

set -e

echo "=== FTP Quick Fix Script ==="
echo ""

# Get server public IP
echo "Detecting server public IP..."
SERVER_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "UNKNOWN")
echo "Server IP: $SERVER_IP"
echo ""

# Install vsftpd if not installed
if ! command -v vsftpd &> /dev/null; then
    echo "Installing vsftpd..."
    sudo apt update
    sudo apt install -y vsftpd
fi

# Create data directory
echo "Creating data directory..."
sudo mkdir -p /home/eva/eva_layout/data
sudo chown eva:eva /home/eva/eva_layout/data
sudo chmod 755 /home/eva/eva_layout/data

# Create vsftpd secure directory
echo "Creating vsftpd secure directory..."
sudo mkdir -p /var/run/vsftpd/empty

# Update vsftpd config with actual server IP
echo "Updating vsftpd configuration..."
sudo tee /etc/vsftpd.conf > /dev/null <<EOF
# FTP Server Configuration
listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
local_umask=022
dirmessage_enable=YES
use_localtime=YES
xferlog_enable=YES
xferlog_file=/var/log/vsftpd.log
connect_from_port_20=YES
chroot_local_user=YES
secure_chroot_dir=/var/run/vsftpd/empty
pam_service_name=vsftpd
ssl_enable=NO
pasv_enable=YES
pasv_min_port=40000
pasv_max_port=50000
pasv_address=$SERVER_IP
user_sub_token=\$USER
local_root=/home/eva/eva_layout/data
allow_writeable_chroot=YES
userlist_enable=YES
userlist_file=/etc/vsftpd.userlist
userlist_deny=NO
file_open_mode=0666
local_max_rate=0
EOF

# Create userlist
echo "Creating userlist..."
echo "eva" | sudo tee /etc/vsftpd.userlist > /dev/null

# Set password for eva user
echo ""
echo "Setting password for eva user..."
echo "Please enter a password for FTP user 'eva':"
sudo passwd eva

# Configure firewall
echo ""
echo "Configuring firewall..."
sudo ufw allow 21/tcp
sudo ufw allow 40000:50000/tcp

# Restart vsftpd
echo ""
echo "Restarting vsftpd service..."
sudo systemctl restart vsftpd
sudo systemctl enable vsftpd

# Show status
echo ""
echo "=== FTP Service Status ==="
sudo systemctl status vsftpd --no-pager

echo ""
echo "=== FTP Configuration Complete ==="
echo "Server IP: $SERVER_IP"
echo "FTP Port: 21"
echo "Username: eva"
echo "Directory: /data (auto-navigates here on login)"
echo "Passive ports: 40000-50000"
echo ""
echo "Test connection:"
echo "  ftp $SERVER_IP"
echo ""
echo "Or use FileZilla with these settings:"
echo "  - Host: $SERVER_IP"
echo "  - Port: 21"
echo "  - Protocol: FTP"
echo "  - Transfer mode: Passive"
echo "  - Username: eva"
echo "  - Password: (the one you just set)"
