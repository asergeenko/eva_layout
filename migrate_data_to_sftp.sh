#!/bin/bash
# Migrate existing data to SFTP directory

echo "=== Migrating data to SFTP directory ==="

# Check if old data directory exists
if [ -L /home/eva/eva_layout/data ]; then
    echo "Data is already a symlink, removing it..."
    sudo rm /home/eva/eva_layout/data
fi

# Find where the actual data is
if [ -d /home/eva/eva_layout/data.backup ]; then
    echo "Found backup data directory"
    DATA_SOURCE="/home/eva/eva_layout/data.backup"
elif [ -d /home/eva/eva_layout/data ]; then
    echo "Found original data directory"
    DATA_SOURCE="/home/eva/eva_layout/data"
else
    echo "No existing data found"
    DATA_SOURCE=""
fi

# Copy data if found
if [ -n "$DATA_SOURCE" ] && [ -d "$DATA_SOURCE" ]; then
    echo "Copying data from $DATA_SOURCE to /home/eva_sftp/data/"
    sudo rsync -av "$DATA_SOURCE/" /home/eva_sftp/data/

    # Backup old directory
    if [ "$DATA_SOURCE" = "/home/eva/eva_layout/data" ]; then
        echo "Backing up old data directory..."
        sudo mv /home/eva/eva_layout/data /home/eva/eva_layout/data.old
    fi
fi

# Ensure SFTP directory exists and has correct permissions
echo "Setting up SFTP directory..."
sudo mkdir -p /home/eva_sftp/data
sudo chown root:root /home/eva_sftp
sudo chmod 755 /home/eva_sftp
sudo chown -R eva:eva /home/eva_sftp/data
sudo chmod -R 755 /home/eva_sftp/data

# Create symlink
echo "Creating symlink..."
sudo ln -sf /home/eva_sftp/data /home/eva/eva_layout/data

# Show results
echo ""
echo "=== Migration complete ==="
echo "SFTP directory: /home/eva_sftp/data"
echo "Application symlink: /home/eva/eva_layout/data -> /home/eva_sftp/data"
echo ""
echo "Contents:"
sudo ls -la /home/eva_sftp/data/
echo ""
echo "Now reconnect via SFTP - you should see all files in /data"
