from mysql.connector import (
        MySQLConnection,
        errorcode
        )


class MySQLFactory(object):
    def __init__(self, host, user, password, db):
        self.host = host
        self.user = user
        self.password = password
        self.db = db

    def create(self):
        return (MySQLConnection(
            user=self.user, password=self.password,
            host=self.host,
            database=self.db)
        )


class MySQL(object):
    def __init__(
            self,
            MySQL_factory: MySQLFactory,
    ):
        self.MySQL_factory = MySQL_factory
        self.instance = None

    def connection(self) -> MySQLConnection:
        if not self.instance:
            self.instance = self.MySQL_factory.create()

        return self.instance

    def exec_query(self, statement, values=None):
        cnx = self.connection()
        cursor = cnx.cursor()
        if values is None:
            cursor.execute(statement)
        else:
            cursor.execute(statement, values)
        values = []
        for entry in cursor:
            values.append(entry)
        cursor.close()
        cnx.commit()
        cursor.close()

        return values
