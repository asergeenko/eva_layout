# SFTP Setup Guide (Recommended - More Secure than FTP)

## Что такое SFTP?

SFTP (SSH File Transfer Protocol) - это безопасный протокол передачи файлов через SSH.
Он уже работает на вашем сервере через порт 22 (SSH).

## Настройка автоматического перехода в /data для SFTP

### 1. На сервере создайте скрипт для ограничения доступа:

```bash
# Создать директорию для chroot
sudo mkdir -p /home/eva_sftp/data

# Переместить данные
sudo mv /home/eva/eva_layout/data/* /home/eva_sftp/data/ 2>/dev/null || true

# Создать симлинк
sudo ln -sf /home/eva_sftp/data /home/eva/eva_layout/data

# Установить правильные права
sudo chown root:root /home/eva_sftp
sudo chmod 755 /home/eva_sftp
sudo chown eva:eva /home/eva_sftp/data
sudo chmod 755 /home/eva_sftp/data
```

### 2. Настроить SSH для chroot:

Добавьте в `/etc/ssh/sshd_config`:

```bash
# Добавить в конец файла
Match User eva
    ChrootDirectory /home/eva_sftp
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
```

Применить:
```bash
sudo systemctl restart sshd
```

### 3. Настройки FileZilla для SFTP:

- **Хост**: `217.198.6.15`
- **Порт**: `22`
- **Протокол**: `SFTP - SSH File Transfer Protocol`
- **Тип входа**: `Обычный`
- **Пользователь**: `eva`
- **Пароль**: ваш пароль

После подключения вы сразу окажетесь в `/data`.

## Быстрый скрипт настройки SFTP

Запустите на сервере:

```bash
#!/bin/bash
# Quick SFTP setup with chroot to /data

# Create SFTP chroot structure
sudo mkdir -p /home/eva_sftp/data

# Copy existing data if any
if [ -d /home/eva/eva_layout/data ]; then
    sudo rsync -av /home/eva/eva_layout/data/ /home/eva_sftp/data/
fi

# Create symlink for application
sudo rm -rf /home/eva/eva_layout/data
sudo ln -sf /home/eva_sftp/data /home/eva/eva_layout/data

# Set permissions (root owns chroot dir, eva owns data inside)
sudo chown root:root /home/eva_sftp
sudo chmod 755 /home/eva_sftp
sudo chown -R eva:eva /home/eva_sftp/data
sudo chmod 755 /home/eva_sftp/data

# Configure SSH for chroot
if ! grep -q "Match User eva" /etc/ssh/sshd_config; then
    sudo tee -a /etc/ssh/sshd_config > /dev/null <<'EOF'

# SFTP chroot for eva user
Match User eva
    ChrootDirectory /home/eva_sftp
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
EOF
fi

# Restart SSH
sudo systemctl restart sshd

echo "SFTP configured successfully!"
echo "Connect with:"
echo "  Protocol: SFTP"
echo "  Host: $(curl -s ifconfig.me)"
echo "  Port: 22"
echo "  User: eva"
echo "  You will automatically be in /data directory"
```

## Преимущества SFTP над FTP:

1. ✅ **Безопасность**: Шифрование всех данных
2. ✅ **Один порт**: Использует только порт 22 (SSH)
3. ✅ **Уже настроен**: SSH обычно уже работает на сервере
4. ✅ **Firewall**: Меньше портов для открытия
5. ✅ **Простота**: Использует существующие SSH учетные данные

## Что выбрать?

**Используйте SFTP если:**
- Вам важна безопасность
- Вы подключаетесь через интернет
- У вас уже работает SSH

**Используйте FTP если:**
- Вам нужна совместимость со старыми системами
- Локальная сеть (не интернет)
- Требуется максимальная скорость (меньше overhead от шифрования)
