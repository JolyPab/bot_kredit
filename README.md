# Бот для чистки кредитной истории

Telegram-бот для автоматизации процесса чистки кредитной истории клиентов.

## 🚀 Возможности

- **Онбординг клиентов** с привязкой к брокерам
- **Загрузка и анализ** PDF отчетов из БКИ
- **Диагностика кредитной истории** с выявлением ошибок
- **Автоматическое формирование заявлений** в БКИ
- **Отслеживание статусов** заявок
- **Личный кабинет брокера** с отчетностью
- **Защита персональных данных** с шифрованием

## 📋 Требования

- Python 3.9+
- PostgreSQL или SQLite
- Telegram Bot Token
- Google Drive API (для хранения документов)
- AmoCRM API (опционально)

## 🛠 Установка

1. **Клонирование проекта:**
```bash
git clone <repo-url>
cd bot_kredit
```

2. **Установка зависимостей:**
```bash
pip install -r requirements.txt
```

3. **Настройка переменных окружения:**
Создайте файл `.env` в корне проекта:
```env
BOT_TOKEN=your_bot_token_here
DATABASE_URL=sqlite+aiosqlite:///bot.db
ENCRYPTION_KEY=your-secure-key-32-chars-minimum
# ... другие переменные
```

4. **Создание бота в Telegram:**
- Найдите @BotFather в Telegram
- Создайте нового бота командой `/newbot`
- Скопируйте токен в переменную `BOT_TOKEN`

5. **Настройка Google Drive (опционально):**
- Создайте проект в Google Cloud Console
- Включите Google Drive API
- Создайте Service Account и скачайте credentials.json
- Укажите путь в `GOOGLE_CREDENTIALS_FILE`

## ▶️ Запуск

```bash
python main.py
```

## 📁 Структура проекта

```
bot_kredit/
├── main.py                 # Точка входа
├── config/
│   └── settings.py         # Конфигурация
├── database/
│   ├── models.py          # Модели БД
│   └── database.py        # Подключение к БД
├── services/
│   ├── user_service.py    # Работа с пользователями
│   └── encryption_service.py # Шифрование ПД
├── bot/
│   ├── handlers/          # Обработчики сообщений
│   ├── keyboards/         # Клавиатуры
│   ├── middlewares/       # Middleware
│   └── utils/            # Утилиты и сообщения
└── requirements.txt       # Зависимости
```

## 🔧 Основные сценарии

### 1. Онбординг клиента
- Переход по реферальной ссылке от брокера
- Сбор контактных данных (телефон, email)
- Получение согласий на обработку ПД
- Привязка к брокеру

### 2. Диагностика КИ
- Загрузка PDF отчетов из БКИ
- Автоматический анализ документов
- Выявление ошибок и проблем
- Формирование рекомендаций

### 3. Подача заявлений
- Генерация заявлений на исправление ошибок
- Получение согласия на представительство
- Отправка в БКИ
- Отслеживание статусов

### 4. Брокерский кабинет
- Статистика по клиентам
- Генерация реферальных ссылок
- Отчеты по заработку
- Управление клиентской базой

## 🔐 Безопасность

- Персональные данные шифруются AES-256
- Логирование всех действий пользователей
- Минимальное хранение ПД
- Соблюдение 152-ФЗ

## 🚀 Развертывание

### На VPS сервере:

1. **Обновите систему:**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Установите Python и зависимости:**
```bash
sudo apt install python3 python3-pip python3-venv git -y
```

3. **Клонируйте проект:**
```bash
git clone <repo-url>
cd bot_kredit
```

4. **Создайте виртуальное окружение:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. **Настройте переменные окружения:**
```bash
nano .env  # Заполните переменные
```

6. **Запустите в фоне:**
```bash
nohup python main.py > bot.log 2>&1 &
```

### Использование systemd:

Создайте файл `/etc/systemd/system/credit-bot.service`:
```ini
[Unit]
Description=Credit History Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/bot_kredit
Environment=PATH=/path/to/bot_kredit/venv/bin
ExecStart=/path/to/bot_kredit/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустите сервис:
```bash
sudo systemctl enable credit-bot
sudo systemctl start credit-bot
```

## 📝 Переменные окружения

| Переменная | Описание | Пример |
|------------|----------|---------|
| `BOT_TOKEN` | Токен Telegram бота | `123456:ABC-DEF...` |
| `DATABASE_URL` | URL подключения к БД | `sqlite+aiosqlite:///bot.db` |
| `ENCRYPTION_KEY` | Ключ шифрования ПД | `your-32-char-secure-key` |
| `AMOCRM_SUBDOMAIN` | Поддомен AmoCRM | `yourcompany` |
| `GOOGLE_FOLDER_ID` | ID папки Google Drive | `1ABC...` |
| `KI_SERVER_URL` | URL сервера диагностики | `http://ki-server.com` |

## ⚙️ Быстрый старт

1. **Создайте бота в Telegram и получите токен**
2. **Создайте файл .env:**
```bash
BOT_TOKEN=your_bot_token_from_botfather
DATABASE_URL=sqlite+aiosqlite:///bot.db
ENCRYPTION_KEY=my-super-secret-encryption-key-32-chars
```
3. **Установите зависимости и запустите:**
```bash
pip install -r requirements.txt
python main.py
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `tail -f bot.log`
2. Убедитесь что все переменные окружения заданы
3. Проверьте подключение к БД
4. Обратитесь к разработчику

## 📄 Лицензия

Проект разработан для внутреннего использования. 