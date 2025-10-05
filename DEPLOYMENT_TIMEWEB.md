# Развертывание на Timeweb.Cloud с приватным GitHub репозиторием

## Вариант 1: SSH Deploy Key (Рекомендуется)

### Шаг 1: Создайте SSH ключ для деплоя

На вашем локальном компьютере:

```bash
# Создайте новый SSH ключ специально для деплоя
ssh-keygen -t ed25519 -C "deploy@eva-layout" -f ~/.ssh/eva_deploy_key -N ""

# Скопируйте публичный ключ
cat ~/.ssh/eva_deploy_key.pub
```

### Шаг 2: Добавьте Deploy Key в GitHub

1. Перейдите в репозиторий: https://github.com/asergeenko/eva_layout
2. Settings → Deploy keys → Add deploy key
3. Title: `Timeweb Production Server`
4. Key: вставьте содержимое `eva_deploy_key.pub`
5. ✅ Allow write access (только если нужен push с сервера)
6. Нажмите "Add key"

### Шаг 3: Подготовьте cloud-init с SSH ключом

Создайте файл `cloud-init-private.yaml`:

```yaml
#cloud-config

package_update: true
package_upgrade: true

packages:
  - python3.12
  - python3.12-venv
  - python3-pip
  - git
  - nginx
  - ufw
  - curl

users:
  - name: eva
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']

write_files:
  - path: /home/eva/.ssh/deploy_key
    owner: eva:eva
    permissions: '0600'
    content: |
      -----BEGIN OPENSSH PRIVATE KEY-----
      ВСТАВЬТЕ_СЮДА_СОДЕРЖИМОЕ_eva_deploy_key
      -----END OPENSSH PRIVATE KEY-----

  - path: /home/eva/.ssh/config
    owner: eva:eva
    permissions: '0600'
    content: |
      Host github.com
        HostName github.com
        User git
        IdentityFile ~/.ssh/deploy_key
        StrictHostKeyChecking no

  - path: /etc/systemd/system/eva-layout.service
    content: |
      [Unit]
      Description=Eva Layout Optimizer - Streamlit Application
      After=network.target

      [Service]
      Type=simple
      User=eva
      WorkingDirectory=/home/eva/eva_layout
      Environment="PATH=/home/eva/eva_layout/venv/bin"
      ExecStart=/home/eva/eva_layout/venv/bin/streamlit run streamlit_demo.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
      Restart=always
      RestartSec=10

      [Install]
      WantedBy=multi-user.target

  - path: /etc/nginx/sites-available/eva-layout
    content: |
      server {
          listen 80;
          server_name _;

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

runcmd:
  # Setup SSH directory
  - sudo -u eva mkdir -p /home/eva/.ssh
  - sudo -u eva chmod 700 /home/eva/.ssh

  # Clone private repository using deploy key
  - sudo -u eva git clone git@github.com:asergeenko/eva_layout.git /home/eva/eva_layout

  # Create Python virtual environment
  - sudo -u eva python3.12 -m venv /home/eva/eva_layout/venv

  # Install Python dependencies
  - sudo -u eva /home/eva/eva_layout/venv/bin/pip install --upgrade pip
  - sudo -u eva /home/eva/eva_layout/venv/bin/pip install -r /home/eva/eva_layout/requirements.txt

  # Create necessary directories
  - sudo -u eva mkdir -p /home/eva/eva_layout/data
  - sudo -u eva mkdir -p /home/eva/eva_layout/tmp_test
  - sudo -u eva mkdir -p /home/eva/eva_layout/logs

  # Configure nginx
  - rm -f /etc/nginx/sites-enabled/default
  - ln -s /etc/nginx/sites-available/eva-layout /etc/nginx/sites-enabled/
  - nginx -t
  - systemctl restart nginx

  # Configure firewall
  - ufw allow 22/tcp
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw --force enable

  # Enable and start the application
  - systemctl daemon-reload
  - systemctl enable eva-layout.service
  - systemctl start eva-layout.service

  # Set correct permissions
  - chown -R eva:eva /home/eva/eva_layout

final_message: |
  Eva Layout Optimizer deployed successfully!
  Access: http://YOUR_SERVER_IP
```

**ВАЖНО**: Замените `ВСТАВЬТЕ_СЮДА_СОДЕРЖИМОЕ_eva_deploy_key` на содержимое приватного ключа:

```bash
cat ~/.ssh/eva_deploy_key
```

### Шаг 4: Создание сервера на Timeweb.Cloud

1. **Через веб-интерфейс Timeweb.Cloud:**
   - Перейдите в раздел "Серверы" → "Создать сервер"
   - Выберите Ubuntu 24.04
   - Тариф: минимум 2 CPU / 4GB RAM
   - В разделе "Дополнительно" → "Cloud-init" вставьте содержимое `cloud-init-private.yaml`
   - Создайте сервер

2. **Через Timeweb API:**

```bash
# Установите twc CLI
pip install twc

# Авторизуйтесь
twc config set-token YOUR_API_TOKEN

# Создайте сервер с cloud-init
twc server create \
  --name eva-layout \
  --os-id ubuntu-24.04 \
  --preset-id s-2-4-80 \
  --cloud-init cloud-init-private.yaml
```

### Шаг 5: Проверка

Через 3-5 минут после создания:

```bash
# Подключитесь к серверу
ssh eva@YOUR_SERVER_IP

# Проверьте статус
sudo systemctl status eva-layout

# Проверьте логи
sudo journalctl -u eva-layout -f
```

---

## Вариант 2: Personal Access Token (PAT)

Если не хотите использовать SSH ключи:

### Шаг 1: Создайте GitHub Personal Access Token

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Название: `Timeweb Eva Layout Deploy`
4. Права: `repo` (для приватного репозитория)
5. Скопируйте токен (сохраните, он показывается только один раз!)

### Шаг 2: Используйте токен в cloud-init

```yaml
runcmd:
  # Clone private repository using PAT
  - sudo -u eva git clone https://YOUR_TOKEN@github.com/asergeenko/eva_layout.git /home/eva/eva_layout
```

Замените `YOUR_TOKEN` на ваш токен.

**⚠️ Недостаток**: токен будет виден в истории команд и логах cloud-init.

---

## Вариант 3: Ручная настройка после создания сервера

Самый безопасный вариант:

### Шаг 1: Создайте сервер с базовым cloud-init

Используйте упрощенный `cloud-init.yaml` без клонирования репозитория:

```yaml
#cloud-config

package_update: true
package_upgrade: true

packages:
  - python3.12
  - python3.12-venv
  - python3-pip
  - git
  - nginx
  - ufw

users:
  - name: eva
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - ВСТАВЬТЕ_ВАШ_ПУБЛИЧНЫЙ_SSH_КЛЮЧ

runcmd:
  - ufw allow 22/tcp
  - ufw allow 80/tcp
  - ufw --force enable
```

### Шаг 2: Подключитесь и клонируйте вручную

```bash
# Подключитесь к серверу
ssh eva@YOUR_SERVER_IP

# Настройте git credentials для приватного репозитория
git config --global credential.helper store

# Клонируйте репозиторий (введете username и токен при запросе)
git clone https://github.com/asergeenko/eva_layout.git /home/eva/eva_layout

# Или используйте SSH ключ
ssh-keygen -t ed25519 -C "eva@timeweb" -f ~/.ssh/github
cat ~/.ssh/github.pub  # Добавьте в GitHub Settings → SSH keys

git clone git@github.com:asergeenko/eva_layout.git /home/eva/eva_layout
```

### Шаг 3: Запустите установочный скрипт

Создайте и выполните скрипт установки:

```bash
cat > /home/eva/install.sh << 'EOF'
#!/bin/bash
set -e

cd /home/eva/eva_layout

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p data tmp_test logs

# Setup systemd service
sudo tee /etc/systemd/system/eva-layout.service > /dev/null << 'SERVICE'
[Unit]
Description=Eva Layout Optimizer
After=network.target

[Service]
Type=simple
User=eva
WorkingDirectory=/home/eva/eva_layout
Environment="PATH=/home/eva/eva_layout/venv/bin"
ExecStart=/home/eva/eva_layout/venv/bin/streamlit run streamlit_demo.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

# Setup nginx
sudo tee /etc/nginx/sites-available/eva-layout > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
NGINX

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/eva-layout /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Start service
sudo systemctl daemon-reload
sudo systemctl enable eva-layout
sudo systemctl start eva-layout

echo "✅ Installation complete!"
echo "Access: http://$(curl -s ifconfig.me)"
EOF

chmod +x /home/eva/install.sh
./install.sh
```

---

## Обновление приложения

После настройки, обновления делайте так:

```bash
ssh eva@YOUR_SERVER_IP

cd /home/eva/eva_layout
git pull
sudo systemctl restart eva-layout
```

Или автоматически через webhook (опционально):

```bash
# Создайте скрипт обновления
cat > /home/eva/update.sh << 'EOF'
#!/bin/bash
cd /home/eva/eva_layout
git pull
sudo systemctl restart eva-layout
EOF

chmod +x /home/eva/update.sh

# Настройте GitHub webhook на URL: http://YOUR_SERVER_IP/update
# Используйте webhook сервис типа webhook.site или настройте простой HTTP сервер
```

---

## Рекомендации по безопасности

1. **Используйте Deploy Keys** (Вариант 1) - самый безопасный
2. **Никогда не коммитьте токены** в репозиторий
3. **Ограничьте права токенов** до минимума
4. **Регулярно меняйте токены** и ключи
5. **Используйте firewall** (UFW настроен автоматически)

## Проверка работы

```bash
# Статус сервиса
sudo systemctl status eva-layout

# Логи
sudo journalctl -u eva-layout -f

# Проверка портов
sudo netstat -tlnp | grep -E ':(80|8501)'

# Тест приложения
curl http://localhost:8501
```

## Troubleshooting Timeweb.Cloud

1. **Cloud-init не выполнился:**
   ```bash
   # Проверьте логи cloud-init
   sudo cat /var/log/cloud-init-output.log
   ```

2. **Репозиторий не клонировался:**
   ```bash
   # Проверьте SSH ключ
   sudo -u eva ssh -T git@github.com

   # Клонируйте вручную
   sudo -u eva git clone git@github.com:asergeenko/eva_layout.git /home/eva/eva_layout
   ```

3. **Нет доступа к приложению:**
   ```bash
   # Проверьте firewall Timeweb в панели управления
   # Убедитесь что порт 80 открыт
   ```
