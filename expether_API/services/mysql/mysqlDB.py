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
        self.db_instance = None
        self.transaction_mode = False
        self.transaction = []

    def connection(self) -> MySQLConnection:
        if not self.db_instance:
            self.db_instance = self.MySQL_factory.create()
            self.db_instance.autocommit = False

    def close_connection(self, cursor):
        cursor.close()

    def get_cursor(self):
        return self.db_instance.cursor()

    def start_transaction(self):
        self.transaction_mode = True

    def commit_transaction(self):
        self.transaction_mode = False
        cursor = self.get_cursor()
        result = []
        try:
            for query in self.transaction:
                if "values" in query:
                    cursor.execute(query["statement"], query["values"])
                else:
                    cursor.execute(query["statement"])
                values = []
                for entry in cursor:
                    values.append(entry)
                result.append(values)
            self.db_instance.commit()
        except (Error, Warning) as err:
            self.close_connection(cursor)
            return self.rollback("DB error: {}".format(err))

        self.close_connection(cursor)
        # For simple SELECT queries, return the result directly
        if len(self.transaction) == 1:
            self.transaction = []
            return (True, result[0])
        else:
            self.transaction = []
            return (True, result)

    # Used only to commit SELECT transactions that do not modify the DB
    def commit_nontransaction_select(self, query):
        cursor = self.get_cursor()
        result = []
        try:
            cursor.execute(query)
            for entry in cursor:
                result.append(entry)
            self.db_instance.commit()
            self.close_connection(cursor)
        except (Error, Warning) as err:
            self.close_connection(cursor)
            return None

        return result

    def rollback(self, error):
        self.transaction = []
        self.db_instance.rollback()
        return (False, error)

    def select_query(self, statement):
        self.connection()
        result = self.commit_nontransaction_select(statement)
        return result

    def insert_query(self, table, mapping, data):
        if len(mapping) != len(data):
            message = "Value length does not correspond "
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
            if data[x] is not None:
                values[mapping[x]] = '%s' % (data[x])
            else:
                values[mapping[x]] = None

        statement += "%(" + mapping[-1] + ")s)"
        if data[-1] is not None:
            values[mapping[-1]] = '%s' % (data[-1])
        else:
            values[mapping[-1]] = None

        self.connection()
        self.transaction.append({"statement": statement, "values": values})
        if not self.transaction_mode:
            result = self.commit_transaction()

        return (True, "OK")

    def modify_query(self, table, mapping, data, modID, modValue):
        if len(mapping) != len(data):
            message = "Value length does not correspond"
            message += "To the size of the table mapping"
            return (False, message)

        statement = (
                'UPDATE %s '
                "SET "
                ) % table
        for x in range(0, len(mapping) - 1):
            statement += '%s = "%s", ' % (mapping[x], data[x])

        statement += '%s = "%s" ' % (mapping[-1], data[-1])
        statement += 'WHERE %s = "%s"' % (modID, modValue)

        self.connection()
        self.transaction.append({"statement": statement})
        if not self.transaction_mode:
            result = self.commit_transaction()
            self.close_connection()

        return (True, "OK")

    def modify_query_complex(self, table, mapping, data, modIDs, modValues):
        if len(mapping) != len(data):
            message = "Value length does not correspond"
            message += "To the size of the table mapping"
            return (False, message)

        statement = (
                'UPDATE %s '
                "SET "
                ) % table
        for x in range(0, len(mapping) - 1):
            statement += '%s = "%s", ' % (mapping[x], data[x])

        statement += '%s = "%s" ' % (mapping[-1], data[-1])
        statement += "WHERE "
        for x in range(0, len(modIDs) - 1):
            statement += '%s = "%s" AND ' % (modIDs[x], modValues[x])
        statement += '%s = "%s"' % (modIDs[-1], modValues[-1])

        self.connection()
        self.transaction.append({"statement": statement})
        if not self.transaction_mode:
            result = self.commit_transaction()

        return (True, "OK")

    def delete_query(self, table, mapping, data):
        if len(mapping) != len(data):
            message = "Value length does not correspond"
            message += "To the size of the table mapping"
            return (False, message)

        statement = ("DELETE FROM %s ") % table
        statement += "WHERE "
        for x in range(0, len(mapping) - 1):
            statement += '%s = "%s" AND ' % (mapping[x], data[x])
        statement += '%s = "%s"' % (mapping[-1], data[-1])

        self.connection()
        self.transaction.append({"statement": statement})
        if not self.transaction_mode:
            result = self.commit_transaction()

        return (True, "OK")

    def delete_query_simple(self, table, field, value):
        statement = (
            "DELETE FROM %s "
            'WHERE %s = "%s"'
            ) % (table, field, value)


        self.connection()
        self.transaction.append({"statement": statement})
        if not self.transaction_mode:
            result = self.commit_transaction()

        return (True, "OK")
