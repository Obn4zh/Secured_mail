# Secured Mail

Учебный проект: клиент–сервер для обмена письмами с простым шифрованием.

> **Важно:** проект учебный. Не используйте текущую криптографическую реализацию в продакшене.

## Возможности
- Отправка и приём сообщений
- Простая БД (SQLite)
- Логи работы клиента/сервера

## Технологии
- Python 3.11+
- SQLite (stdlib: `sqlite3`)
- Логи (stdlib: `logging`)

## Быстрый старт
```bash
git clone https://github.com/Obn4zh/Secured_mail.git
cd Secured_mail

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Примеры (уточни пути/модули под свой код):
python server.py          # Запуск сервера
# отдельной вкладкой
python MailClient-master/main.py  # или python app/client.py
```

## Тестирование
```bash
pytest -q
```

## Планы (TODO)
- [ ] Разнести код на `app/server.py` и `app/client.py`
- [ ] Убрать артефакты из git (`*.db`, `*.log`) и генерировать их при старте
- [ ] Минимальные тесты (pytest)
- [ ] CI (GitHub Actions)

## Лицензия
MIT — см. `LICENSE`.
