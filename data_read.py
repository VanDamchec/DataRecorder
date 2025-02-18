import psycopg2

class DataRead():
    def __init__(self):
        # Объекты базы данных
        self.bd_connect = None
        self.bd_cursor = None
        # Проверка сколько добавилось новых данных в таблицу
        self.old_count = 0
        self.new_count = 0

        # Параметры подключения к базе данных
        db_config = {
            "dbname": "postgres",
            "user": "postgres",
            "password": "rekb,zrf",
            "host": "localhost",
            "port": "5432"
        }

        try:
            # Подключение к базе данных
            print("Попытка подключения к базе данных...")
            self.bd_connect = psycopg2.connect(**db_config)
            print("Подключение успешно!")

        except Exception as error:
            print(f"Ошибка: {error}")


    def bd_read(self, table_name, conditions):
        try:
            cursor = self.bd_connect.cursor()

            # Базовый запрос для выборки данных
            query = f"SELECT * FROM {table_name}"
            params = []

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Выполняем запрос
            cursor.execute(query, params)

            # Получаем результаты
            records = cursor.fetchall()
            print("Данные успешно считаны.")
            return records

        except Exception as error:
            print(f"Ошибка при чтении данных из таблицы: {error}")
            return []

        finally:
            cursor.close()


    def bd_read_last(self, table_name, count, new=False):
        """
        Функция для чтения последних записей из таблицы базы данных.
        :param table_name: Имя таблицы, из которой нужно считать данные.
        :param count: Количество последних записей для извлечения.
        :return: Список кортежей с данными последних записей или пустой список, если записей нет.
        """
        try:
            cursor = self.bd_connect.cursor()
            # Параметризованный запрос для выборки последних записей
            query = f"""
                SELECT * 
                FROM {table_name}
                ORDER BY id DESC
                LIMIT {count};
            """
            # Выполняем запрос с параметрами
            cursor.execute(query)
            # Получаем результат
            records = cursor.fetchall()  # Берем все записи
            self.bd_connect.commit()  # Фиксируем изменения
            if records:
                print(f"Успешно считано {len(records)} записей.")
            else:
                print("Записей в таблице нет.")

            # Если нужны только новые данные
            if new:
                # Берем последнее отчетов из таблицы
                if len(records[0]) > 2:
                    self.new_count = records[0][2]
                    delta = self.new_count - self.old_count
                    self.old_count = self.new_count
                    print(f"Новых {delta} записей.")
                    records = records[:delta]

            return records
        except Exception as error:
            print(f"Ошибка при чтении записей из таблицы: {error}")
            return []
        finally:
            cursor.close()


    def bd_close(self):
        cursor = self.bd_connect
        # Закрываем соединение
        if cursor:
           cursor.close()
        if self.bd_connect:
            self.bd_connect.close()
            print("\nСоединение закрыто.")


    def bd_clear(self, table_name):
        try:
            cursor = self.bd_connect.cursor()
            # Используем TRUNCATE для быстрой очистки таблицы
            cursor.execute(f"TRUNCATE TABLE {table_name};")
            print(f"Таблица '{table_name}' успешно очищена с помощью TRUNCATE.")
            # Фиксируем изменения
            self.bd_connect.commit()
        except Exception as error:
            # В случае ошибки откатываем изменения
            self.bd_connect.rollback()
            print(f"Ошибка при очистке таблицы: {error}")
        finally:
            cursor.close()


def main():

    BD = DataRead()

    for i in range(10):
        print(BD.bd_read_last("mean_records", 10, True))

    BD.bd_close()

if __name__ == "__main__":
    main()