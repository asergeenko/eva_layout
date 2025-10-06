# FTP Troubleshooting Guide

## Быстрая проверка и исправление

### 1. Проверить статус vsftpd
```bash
sudo systemctl status vsftpd
```

Если не запущен:
```bash
sudo systemctl start vsftpd
sudo systemctl enable vsftpd
```

### 2. Проверить что порт 21 слушается
```bash
sudo netstat -tlnp | grep :21
# или
sudo ss -tlnp | grep :21
```

### 3. Проверить firewall
```bash
sudo ufw status
```

Должны быть открыты:
- 21/tcp (FTP control)
- 40000:50000/tcp (FTP passive data)

Если нет, открыть:
```bash
sudo ufw allow 21/tcp
sudo ufw allow 40000:50000/tcp
```

### 4. Проверить конфигурацию vsftpd
```bash
sudo cat /etc/vsftpd.conf | grep -v "^#" | grep -v "^$"
```

**ВАЖНО**: Замените `YOUR_SERVER_PUBLIC_IP` на реальный IP сервера:
```bash
sudo sed -i 's/YOUR_SERVER_PUBLIC_IP/actual.ip.address.here/g' /etc/vsftpd.conf
sudo systemctl restart vsftpd
```

### 5. Проверить что пользователь eva существует и имеет пароль
```bash
id eva
```

Установить/изменить пароль:
```bash
sudo passwd eva
```

### 6. Проверить что директория data существует
```bash
ls -la /home/eva/eva_layout/data
```

Если нет, создать:
```bash
sudo mkdir -p /home/eva/eva_layout/data
sudo chown eva:eva /home/eva/eva_layout/data
sudo chmod 755 /home/eva/eva_layout/data
```

### 7. Проверить логи vsftpd
```bash
sudo tail -f /var/log/vsftpd.log
```

### 8. Тестовое подключение с сервера
```bash
# Установить ftp клиент если нужно
sudo apt install ftp

# Тест подключения
ftp localhost
# Введите: eva
# Введите пароль: eva2025 (или тот что установили)
```

## Настройки FTP клиента

При подключении из FileZilla или другого клиента:

1. **Host**: IP адрес сервера
2. **Port**: 21
3. **Protocol**: FTP (не SFTP!)
4. **Encryption**: Use plain FTP
5. **Logon Type**: Normal
6. **User**: eva
7. **Password**: eva2025 (или измененный)
8. **Transfer mode**: Passive

## Распространенные проблемы

### Проблема: "530 Login incorrect"
**Решение**:
```bash
# Проверить что пользователь в /etc/vsftpd.userlist
cat /etc/vsftpd.userlist

# Добавить если нет
echo "eva" | sudo tee -a /etc/vsftpd.userlist

# Установить пароль
sudo passwd eva

# Перезапустить
sudo systemctl restart vsftpd
```

### Проблема: "500 OOPS: vsftpd: refusing to run with writable root inside chroot()"
**Решение**: В /etc/vsftpd.conf должно быть `allow_writeable_chroot=YES`

### Проблема: Подключается но не показывает файлы (пассивный режим)
**Решение**:
1. Убедиться что `pasv_address` установлен в ПУБЛИЧНЫЙ IP сервера
2. Убедиться что порты 40000-50000 открыты в firewall
3. В FTP клиенте включить пассивный режим

### Проблема: Подключается но сразу переходит в /home/eva вместо /data
**Решение**: Проверить `local_root=/home/eva/eva_layout/data` в /etc/vsftpd.conf

## Полная переустановка vsftpd

```bash
# Остановить и удалить
sudo systemctl stop vsftpd
sudo apt remove --purge vsftpd
sudo rm -rf /etc/vsftpd.conf

# Переустановить
sudo apt update
sudo apt install vsftpd

# Скопировать конфиг из cloud-init.yaml
# ... (вставить содержимое /etc/vsftpd.conf)

# Запустить
sudo systemctl start vsftpd
sudo systemctl enable vsftpd
```

## Автоматический скрипт исправления

Запустите ftp_debug.sh для диагностики:
```bash
chmod +x ftp_debug.sh
./ftp_debug.sh
```
