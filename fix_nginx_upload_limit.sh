#!/bin/bash
# Fix nginx 413 error - increase upload file size limit

echo "=== Fixing nginx upload size limit ==="

# Backup current config
sudo cp /etc/nginx/sites-available/eva-layout /etc/nginx/sites-available/eva-layout.backup

# Update nginx config to allow 100MB uploads
sudo tee /etc/nginx/sites-available/eva-layout > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    # Увеличиваем лимит размера загружаемых файлов до 100MB
    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF

# Test nginx config
echo "Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "Config is valid, reloading nginx..."
    sudo systemctl reload nginx
    echo ""
    echo "=== Fix applied successfully ==="
    echo "Max upload size is now 100MB"
    echo "Try uploading your Excel file again"
else
    echo ""
    echo "=== ERROR: nginx config test failed ==="
    echo "Restoring backup..."
    sudo cp /etc/nginx/sites-available/eva-layout.backup /etc/nginx/sites-available/eva-layout
    exit 1
fi
