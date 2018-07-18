from services.elasticsearch.elasticsearch import ElasticSearchIndex
from services.mysql.mysqlDB import MySQL
from flask_injector import inject
#from ES_config.ES_config import workload_mapping as mapping
from config.MySQL_config.MySQL_config import workload_mapping as mapping
from utilities.messages import messenger
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table = "assignaments"
__doc_type = "assignament"
__table_keys = list(mapping.keys())


@inject
def get_all_assignaments(DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table
    assignaments = DB.exec_query(statement)
    res_assignaments = []
    if assignaments:
        for assignament in assignaments:
            res_assignament = {}
            for x in range(0, len(__table_keys)):
                res_assignament[__table_keys[x]] = assignament[x]
            res_assignaments.append(res_assignament)
        return res_assignaments

    else:
        return messenger.message404("No assignaments found", "404")


@inject
def get_assignament(id, DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table
    statement += ("WHERE ID = ") + id
    assignaments = DB.exec_query(statement)
    assignament = {}
    if assignaments:
        for x in range(0, len(__table_keys)):
            assignament[__table_keys[x]] = assignaments[0][x]
        return assignament

    else:
        return messenger.message404(
                "The requested ID does not exist on the server", "404")


@inject
def create_assignament(workload, DB: MySQL):
    values = {}
    statement = ("INSERT INTO %s ") % __table
    statement += "("
    for x in range(0, len(__table_keys) - 1):
        statement += __table_keys[x] + ","
        values[__table_keys[x]] = assignament[__table_keys[x]]
    statement += __table_keys[len(__table_keys) - 1] + ") "
    statement += ("VALUES (")
    last_val = __table_keys[len(__table_keys) - 1]
    values[__table_keys[len(__table_keys) - 1]] = assignament[last_val]
    for x in range(0, len(__table_keys) - 1):
        statement += "%(" + __table_keys[x] + ")s,"
    statement += "%(" + __table_keys[len(__table_keys) - 1] + ")s)"
    DB.exec_query(statement, values)

@inject
def erase_assignament(id, DB: MySQL):
    statement = ("DELETE FROM workloads "
            "WHERE ID = " ) + id
    DB.exec_query(statement)
    #if res:
    #    return 200
    #else:
    #    error = {}
    #    error["detail"] = "The requested ID does not exist"
    #    error["status"] = "404"
    #    error["title"] = "Not Found"
    #    return error
