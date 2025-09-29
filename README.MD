# Secured Mail

Учебный проект: клиент-серверная система обмена письмами с элементами шифрования.

## Возможности
- Отправка и получение сообщений
- Хранение данных в SQLite
- Использование простых криптографических примитивов (RSA и др.)

## Стек
- Python 3.11+
- SQLite
- pytest (тесты)
- GitHub Actions (CI)

## Установка и запуск
```bash
git clone https://github.com/Obn4zh/Secured_mail.git
cd Secured_mail

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

python app/server.py   # запуск сервера
python app/client.py   # запуск клиента
