#!/bin/bash
# Setup SFTP with automatic chroot to /data directory

set -e

echo "=== SFTP Setup Script ==="
echo "This will configure SFTP access with automatic navigation to /data"
echo ""

# Get server IP
SERVER_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "UNKNOWN")
echo "Server IP: $SERVER_IP"
echo ""

# Create SFTP chroot structure
echo "Creating SFTP directory structure..."
sudo mkdir -p /home/eva_sftp/data

# Backup and move existing data
if [ -d /home/eva/eva_layout/data ]; then
    echo "Moving existing data..."
    sudo rsync -av /home/eva/eva_layout/data/ /home/eva_sftp/data/ || true
    sudo rm -rf /home/eva/eva_layout/data
fi

# Create symlink for application
echo "Creating symlink..."
sudo ln -sf /home/eva_sftp/data /home/eva/eva_layout/data

# Set correct permissions
echo "Setting permissions..."
sudo chown root:root /home/eva_sftp
sudo chmod 755 /home/eva_sftp
sudo chown -R eva:eva /home/eva_sftp/data
sudo chmod 755 /home/eva_sftp/data

# Backup SSH config
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Configure SSH for chroot
echo "Configuring SSH for SFTP chroot..."
if ! grep -q "Match User eva" /etc/ssh/sshd_config; then
    sudo tee -a /etc/ssh/sshd_config > /dev/null <<'EOF'

# SFTP chroot for eva user - auto-navigate to /data
Match User eva
    ChrootDirectory /home/eva_sftp
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
EOF
    echo "SSH config updated"
else
    echo "SSH config already has eva user configuration"
fi

# Test SSH config
echo "Testing SSH configuration..."
sudo sshd -t

# Restart SSH
echo "Restarting SSH service..."
sudo systemctl restart sshd

# Show status
echo ""
echo "=== SFTP Configuration Complete ==="
echo ""
echo "Connection Details:"
echo "  Protocol: SFTP (SSH File Transfer Protocol)"
echo "  Host: $SERVER_IP"
echo "  Port: 22"
echo "  Username: eva"
echo "  Password: (your eva user password)"
echo ""
echo "FileZilla Settings:"
echo "  - Protocol: SFTP - SSH File Transfer Protocol"
echo "  - Host: $SERVER_IP"
echo "  - Port: 22"
echo "  - Logon Type: Normal"
echo "  - User: eva"
echo "  - Password: your password"
echo ""
echo "After login, you will automatically be in /data directory"
echo ""
echo "Note: First connection will ask to trust the host key - accept it"
