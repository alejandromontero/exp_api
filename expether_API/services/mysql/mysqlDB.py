from mysql.connector import (
        MySQLConnection,
        errorcode,
        Error,
        Warning
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

    def select_query(self, statement):
        cnx = self.connection()
        cursor = cnx.cursor()
        try:
            cursor.execute(statement)
        except (Error, Warning) as err:
            print (err)

        values = []
        for entry in cursor:
            values.append(entry)
        cursor.close()
        cnx.commit()
        cursor.close()

        return values

    def insert_query(self, table, mapping, data):
        if len(mapping) != len(data):
            message = "Value length does not correspond"
            message += "To the size of the table mapping"
            return (False, message)

        statement = ("INSERT INTO %s") % table
        statement += "("
        values = {}
        for x in range(0, len(mapping) - 1):
            statement += mapping[x] + ","

        statement += mapping[-1] + ")"
        statement += "VALUES ("
        for x in range(0, len(mapping) - 1):
            statement += "%(" + mapping[x] + ")s, "
            values[mapping[x]] = data[x]
        statement += "%(" + mapping[-1] + ")s)"
        values[mapping[-1]] = data[-1]

        cnx = self.connection()
        cursor = cnx.cursor()

        try:
            cursor.execute(statement, values)
        except (Error, Warning) as err:
            print(err)

        cursor.close()
        cnx.commit()
        cursor.close()
        return (True, "OK")

    def delete_query(self, table, mapping, data):
        if len(mapping) != len(data):
            message = "Value length does not correspond"
            message += "To the size of the table mapping"
            return (False, message)

        statement = ("DELETE FROM %s ") % table
        statement += "WHERE "
        for x in range(0, len(mapping) - 1):
            statement += mapping[x] + " = " + data[x] + " AND "
        statement += mapping[-1] + " = " + str(data[-1])

        cnx = self.connection()
        cursor = cnx.cursor()

        try:
            cursor.execute(statement)
        except (Error, Warning) as err:
            print(err)

        cursor.close()
        cnx.commit()
        cursor.close()
        return (True, "OK")
