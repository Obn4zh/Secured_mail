import sqlite3

# Подключение к базе данных (или создание новой, если она не существует)
conn = sqlite3.connect('pubKey_storage.db')
cursor = conn.cursor()

# Создание таблицы
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    pub_key TEXT NOT NULL
)
''')

# Добавление данных
cursor.execute('''
INSERT INTO users (email, pub_key) VALUES (?, ?)
''', ('example@example.com', 'your_public_key_here'))

# Сохранение изменений и закрытие соединения
conn.commit()
conn.close()