import configparser

class Settings:
    def __init__(self):
        self.settings = dict()
        self.config = configparser.ConfigParser()

    def __setitem__(self, key, value):
        self.settings[key] = value

    def __getitem__(self, key):
        return self.settings[key]

    def load(self):
        try:
            self.settings.clear()
            self.config.read("./MailClient-master/settings.ini")
            self.settings["imap_server"] = self.config.get("MAILSERVER", "imap_server")
            self.settings["smtp_server"] = self.config.get("MAILSERVER", "smtp_server")
            self.settings["imap_port"] = self.config.getint("MAILSERVER", "imap_port")
            self.settings["smtp_port"] = self.config.getint("MAILSERVER", "smtp_port")
            self.settings["ssl"] = True if self.config.get("MAILSERVER", "ssl").lower() == "yes" else False
            self.settings["mail"] = self.config.get("MAILSERVER", "mail")
            self.settings["ca_server"] = self.config.get("MAILSERVER", "ca_server", fallback="")
            self.settings["key_server"] = self.config.get("MAILSERVER", "key_server", fallback="")


            
            # Проверяем наличие smtp_user, если его нет - не вызываем ошибку
            if self.config.has_option("MAILSERVER", "smtp_user"):
                self.settings["smtp_user"] = self.config.get("MAILSERVER", "smtp_user")
            else:
                self.settings["smtp_user"] = ""  # Или оставляем пустым, чтобы позже задать

            if self.config.has_option("MAILSERVER", "smtp_password"):
                self.settings["smtp_password"] = self.config.get("MAILSERVER", "smtp_password")
            else:
                self.settings["smtp_password"] = ""

        except configparser.NoOptionError as e:
            print(f"Ошибка в файле настроек: {e}")
        except Exception as e:
            print(f"Произошла общая ошибка при загрузке настроек: {e}")

    def save(self):
        with open("./MailClient-master/settings.ini", "w") as configfile:
            self.config.write(configfile)

    def set(self, key, value):
        # Добавляем секцию, если она отсутствует
        if not self.config.has_section('MAILSERVER'):
            self.config.add_section('MAILSERVER')

        # Устанавливаем значение и сохраняем
        self.config.set('MAILSERVER', key, value)
        self.save()  #

