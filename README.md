# Cipher

Автоматический торговый бот для Binance Futures. Принимает сигналы через вебхуки (TradingView и т.д.) и торгует автономно по стратегии на основе индикатора Nadaraya-Watson.

## Возможности

- **Webhook-режим** — приём сигналов через `POST /webhook` (TradingView alerts)
- **Strategy Engine** — автономная торговля по индикатору Nadaraya-Watson (kernel regression)
- Лимитные и рыночные ордера на Binance Futures
- Stop-Loss / Take-Profit
- Отслеживание позиций и история сделок (CSV-экспорт)
- REST API для мониторинга и управления
- Деплой на удалённый сервер через `deploy.sh`

## Стек

- Python 3.12+
- FastAPI + Uvicorn
- python-binance
- pandas / numpy (индикаторы)
- UV (пакетный менеджер)

## Структура проекта

```
├── main.py                 # Точка входа (uvicorn)
├── __main__.py             # Альтернативный запуск (python -m)
├── app.py                  # Создание FastAPI приложения
├── backtest.py             # Бэктест стратегии на истории
├── deploy.sh               # Деплой на сервер (tar + scp)
├── pyproject.toml          # Зависимости (uv)
├── uv.lock                 # Lock-файл зависимостей
│
├── config/
│   └── settings.py         # Настройки из .env
│
├── core/
│   └── logging.py          # Конфигурация логирования
│
├── api/
│   ├── router.py           # Агрегация роутеров
│   ├── schemas.py          # Pydantic-модели
│   └── routers/
│       ├── health.py       # GET / и /status
│       ├── webhook.py      # POST /webhook
│       ├── positions.py    # Управление позициями
│       ├── trading.py      # История и аналитика
│       ├── signals.py      # Трекинг сигналов
│       └── strategy.py     # Статус стратегии
│
├── models/
│   └── order.py            # Модель OrderRequest
│
├── services/
│   ├── binance_gateway.py  # Обёртка над Binance API
│   ├── order_manager.py    # Размещение ордеров
│   ├── signal_manager.py   # Обработка отложенных сигналов
│   ├── signal_tracker.py   # Трекинг истории сигналов
│   ├── strategy_engine.py  # Движок стратегии (NW)
│   ├── position_store.py   # Хранилище позиций (JSON)
│   ├── position_history.py # История сделок (CSV)
│   ├── background_tasks.py # Фоновые задачи
│   ├── indicators.py       # Индикатор Nadaraya-Watson
│   ├── calculations.py     # Расчёты цен и P&L
│   └── storage.py          # JSON-хранилище
│
└── tests/                  # Тесты
```

## Установка

### Требования

- Python 3.12+
- [UV](https://docs.astral.sh/uv/) — пакетный менеджер
- Binance-аккаунт с Futures API ключами

### Шаги

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-username/cipher.git
cd cipher

# 2. Установить uv (если ещё нет)
pip install uv

# 3. Установить зависимости
uv sync

# 4. Создать .env файл из примера
cp .env.example .env

# 5. Заполнить .env — вписать API ключи Binance и настроить параметры
```

## Настройка .env

| Переменная | Описание | По умолчанию |
|---|---|---|
| `BINANCE_API_KEY` | API ключ Binance Futures | — |
| `BINANCE_API_SECRET` | API секрет Binance Futures | — |
| `STRATEGY_ENABLED` | Включить автономную стратегию | `true` |
| `STRATEGY_SYMBOLS` | Торговые пары через запятую | `BTCUSDT,ETHUSDT,...` |
| `STRATEGY_TIMEFRAME` | Таймфрейм свечей | `1h` |
| `STRATEGY_LEVERAGE` | Плечо для стратегии (1-50) | `20` |
| `STRATEGY_USE_FIXED_AMOUNT` | Фиксированная сумма на сделку | `true` |
| `STRATEGY_FIXED_AMOUNT` | Сумма в USD на сделку | `5` |
| `MAX_CONCURRENT_POSITIONS` | Макс. открытых позиций | `4` |
| `NW_BANDWIDTH` | Ширина окна Nadaraya-Watson | `8` |
| `NW_MULT` | Множитель полос NW | `3` |
| `NW_LOOKBACK` | Lookback окно NW | `500` |
| `STRATEGY_TP_PERCENT` | Take Profit, % | `20` |
| `STRATEGY_SL_PERCENT` | Stop Loss, % | `10` |
| `HOST` | Хост сервера | `0.0.0.0` |
| `PORT` | Порт сервера | `8000` |

## Запуск

```bash
# Основной запуск
uv run python main.py

# Или как модуль
uv run python -m cipher

# Или напрямую через uvicorn
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Фоновый запуск (nohup)

```bash
nohup uv run python main.py > cipher.log 2>&1 &

# Логи
tail -f cipher.log

# Остановить
ps aux | grep main.py
kill <PID>
```

### Systemd (рекомендуется для сервера)

```bash
sudo nano /etc/systemd/system/cipher.service
```

```ini
[Unit]
Description=Cipher Trading Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/cipher
ExecStart=/home/your-user/.local/bin/uv run python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cipher
sudo systemctl start cipher

# Логи
journalctl -u cipher -f
```

После запуска API доступно по адресу `http://localhost:8000`.

## API Endpoints

### Health
| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | Корневой эндпоинт |
| GET | `/status` | Статус системы и статистика |

### Webhook
| Метод | Путь | Описание |
|---|---|---|
| POST | `/webhook` | Приём торгового сигнала |

Пример тела запроса:
```json
{
  "ticker": "BTCUSDT",
  "action": "long",
  "time": "2025-01-01T12:00:00",
  "price": 50000.0,
  "market_order": false
}
```

### Позиции
| Метод | Путь | Описание |
|---|---|---|
| GET | `/positions` | Сводка по позициям |
| GET | `/positions/all` | Все позиции (локальные + API) |
| GET | `/positions/check/{symbol}` | Проверить позицию по символу |
| POST | `/positions/manual/add` | Добавить позицию вручную |
| POST | `/positions/manual/close` | Закрыть позицию вручную |

### История торговли
| Метод | Путь | Описание |
|---|---|---|
| GET | `/trading/statistics` | Торговая статистика |
| GET | `/trading/history` | Последние закрытые позиции |
| GET | `/trading/history/{symbol}` | История по символу |
| GET | `/trading/download` | Скачать CSV с историей |

### Сигналы
| Метод | Путь | Описание |
|---|---|---|
| GET | `/signals/statistics` | Статистика обработки сигналов |
| GET | `/signals/recent` | Сигналы за 24ч |
| POST | `/signals/cleanup` | Очистка старых сигналов |

### Стратегия
| Метод | Путь | Описание |
|---|---|---|
| GET | `/strategy/status` | Статус движка стратегии |

## Бэктест

```bash
uv run python backtest.py
```

## Тесты

```bash
uv run pytest
```

## Деплой на сервер

```bash
bash deploy.sh user@server:/opt/cipher
```

## Git — начало работы

```bash
git init
git add .
git commit -m "Initial commit"

git remote add origin https://github.com/your-username/cipher.git
git branch -M main
git push -u origin main
```

## Перенос на другую машину

### Через Git

```bash
git clone https://github.com/your-username/cipher.git
cd cipher
pip install uv
uv sync
cp .env.example .env
# Заполнить .env
uv run python main.py
```

### Через deploy.sh

```bash
bash deploy.sh user@server:/opt/cipher
```

### Ручной перенос

```bash
# Упаковать (без секретов и кэша)
tar czf cipher.tar.gz \
  --exclude='__pycache__' \
  --exclude='.venv' \
  --exclude='.env' \
  --exclude='.git' \
  --exclude='*.pyc' \
  --exclude='positions.json' \
  --exclude='processed_signals.json' \
  --exclude='signal_history.json' \
  --exclude='closed_positions.csv' \
  .

scp cipher.tar.gz user@server:/opt/
ssh user@server "mkdir -p /opt/cipher && tar xzf /opt/cipher.tar.gz -C /opt/cipher"
```

## Лицензия

Private / All rights reserved.
