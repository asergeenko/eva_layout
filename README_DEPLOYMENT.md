# Deployment Guide - Eva Layout Optimizer

## Автоматическое развертывание на Ubuntu 24.04

### Предварительные требования

1. **GitHub репозиторий**: Код приложения должен быть загружен в GitHub
2. **Cloud provider**: Любой провайдер поддерживающий cloud-init (AWS, DigitalOcean, Hetzner, etc.)
3. **Ubuntu 24.04 LTS** - чистая установка

### Шаги развертывания

#### 1. Подготовка cloud-init скрипта

Отредактируйте `cloud-init.yaml`:

```yaml
# Замените YOUR_USERNAME на ваш GitHub username
- sudo -u eva git clone https://github.com/YOUR_USERNAME/eva_layout.git /home/eva/eva_layout
```

Опционально настройте домен в nginx конфиге:
```yaml
server_name your-domain.com;  # вместо _
```

#### 2. Создание сервера

**На DigitalOcean:**
```bash
doctl compute droplet create eva-layout \
  --region fra1 \
  --size s-2vcpu-4gb \
  --image ubuntu-24-04-x64 \
  --user-data-file cloud-init.yaml \
  --ssh-keys YOUR_SSH_KEY_ID
```

**На AWS EC2:**
1. Launch new instance → Ubuntu 24.04
2. В разделе "Advanced details" → "User data" вставьте содержимое `cloud-init.yaml`
3. Security group: открыть порты 22, 80, 443

**На Hetzner Cloud:**
```bash
hcloud server create --name eva-layout \
  --type cx21 \
  --image ubuntu-24.04 \
  --user-data-from-file cloud-init.yaml
```

#### 3. Проверка установки

После запуска сервера (обычно 2-5 минут):

```bash
# Подключитесь к серверу
ssh eva@YOUR_SERVER_IP

# Проверьте статус сервиса
sudo systemctl status eva-layout

# Просмотрите логи
sudo journalctl -u eva-layout -f
```

#### 4. Доступ к приложению

Откройте в браузере: `http://YOUR_SERVER_IP`

### Управление приложением

#### Перезапуск сервиса
```bash
sudo systemctl restart eva-layout
```

#### Просмотр логов
```bash
# Все логи
sudo journalctl -u eva-layout

# Последние логи в реальном времени
sudo journalctl -u eva-layout -f

# Логи за последний час
sudo journalctl -u eva-layout --since "1 hour ago"
```

#### Обновление кода из GitHub
```bash
sudo -u eva git -C /home/eva/eva_layout pull
sudo systemctl restart eva-layout
```

#### Остановка/запуск сервиса
```bash
sudo systemctl stop eva-layout
sudo systemctl start eva-layout
```

### Настройка HTTPS (опционально)

После развертывания можно настроить SSL с помощью Let's Encrypt:

```bash
# Установка certbot
sudo apt install certbot python3-certbot-nginx

# Получение SSL сертификата
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление
sudo systemctl enable certbot.timer
```

### Структура приложения на сервере

```
/home/eva/eva_layout/
├── venv/                    # Python виртуальное окружение
├── streamlit_demo.py        # Главный файл приложения
├── layout_optimizer.py      # Алгоритм оптимизации
├── dxf_utils.py            # Работа с DXF
├── data/                    # DXF файлы заказов
├── tmp_test/               # Временные файлы
└── logs/                    # Логи приложения
```

### Мониторинг ресурсов

```bash
# Использование CPU/RAM
htop

# Дисковое пространство
df -h

# Сетевая активность
sudo iftop
```

### Troubleshooting

#### Приложение не запускается
```bash
# Проверьте логи
sudo journalctl -u eva-layout -n 50

# Проверьте права доступа
ls -la /home/eva/eva_layout/

# Переустановите зависимости
sudo -u eva /home/eva/eva_layout/venv/bin/pip install -r /home/eva/eva_layout/requirements.txt --force-reinstall
```

#### Nginx не работает
```bash
# Проверьте конфигурацию
sudo nginx -t

# Перезапустите nginx
sudo systemctl restart nginx

# Проверьте статус
sudo systemctl status nginx
```

#### Firewall блокирует доступ
```bash
# Проверьте правила UFW
sudo ufw status

# Откройте необходимые порты
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Бэкапы

Рекомендуется настроить регулярные бэкапы:

```bash
# Создать скрипт бэкапа
cat > /home/eva/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /home/eva/backup_${DATE}.tar.gz /home/eva/eva_layout/data
# Опционально: загрузить на S3/другое хранилище
EOF

chmod +x /home/eva/backup.sh

# Добавить в cron (ежедневно в 2:00)
echo "0 2 * * * /home/eva/backup.sh" | sudo crontab -u eva -
```

### Масштабирование

Для обработки большего количества пользователей:

1. **Увеличить ресурсы сервера** (больше CPU/RAM)
2. **Настроить несколько инстансов** с load balancer
3. **Использовать Redis** для кэширования расчетов
4. **Настроить CDN** для статических файлов

### Безопасность

1. **Регулярные обновления**:
```bash
sudo apt update && sudo apt upgrade -y
sudo systemctl restart eva-layout
```

2. **Ограничение SSH доступа**:
```bash
# Разрешить только ключи SSH
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

3. **Fail2ban** для защиты от брутфорса:
```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

### Поддержка

- GitHub Issues: https://github.com/YOUR_USERNAME/eva_layout/issues
- Документация Streamlit: https://docs.streamlit.io
- Cloud-init docs: https://cloudinit.readthedocs.io
