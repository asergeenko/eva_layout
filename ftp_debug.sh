#!/bin/bash
# Script to debug and fix FTP connection issues

echo "=== Checking FTP Service Status ==="
sudo systemctl status vsftpd

echo ""
echo "=== Checking if vsftpd is listening on port 21 ==="
sudo netstat -tlnp | grep :21 || sudo ss -tlnp | grep :21

echo ""
echo "=== Checking firewall rules ==="
sudo ufw status

echo ""
echo "=== Testing FTP port connectivity ==="
nc -zv localhost 21

echo ""
echo "=== Checking vsftpd configuration ==="
cat /etc/vsftpd.conf | grep -v "^#" | grep -v "^$"

echo ""
echo "=== Checking vsftpd logs ==="
sudo tail -n 50 /var/log/vsftpd.log

echo ""
echo "=== Checking if data directory exists and has correct permissions ==="
ls -la /home/eva/eva_layout/data

echo ""
echo "=== To fix common issues, run these commands: ==="
echo "1. Install vsftpd if missing:"
echo "   sudo apt install vsftpd"
echo ""
echo "2. Restart vsftpd:"
echo "   sudo systemctl restart vsftpd"
echo ""
echo "3. Set password for eva user:"
echo "   sudo passwd eva"
echo ""
echo "4. Check if PAM is configured correctly:"
echo "   sudo cat /etc/pam.d/vsftpd"
