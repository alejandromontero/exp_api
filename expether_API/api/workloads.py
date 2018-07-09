from services.elasticsearch.elasticsearch import ElasticSearchIndex
from services.mysql.mysqlDB import MySQL
from flask_injector import inject
#from ES_config.ES_config import workload_mapping as mapping
from config.MySQL_config.MySQL_config import workload_mapping as mapping
from flask import (
        make_response,
        abort
)

__table = "workloads"
__doc_type = "workloads"
__workload_keys = list(mapping.keys())


@inject
def get_all_docs(DB: MySQL):
    statement = ("SELECT * FROM ") + __table
    docs = DB.exec_query(statement)
    res_docs = []
    if docs:
        for doc in docs:
            res_doc = {}
            for x in range(0, len(__workload_keys)):
                res_doc[__workload_keys[x]] = doc[x]
            res_docs.append(res_doc)
        return res_docs

    else:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "400"
        error["title"] = "Not Found"
        return error


@inject
def get_doc(id, DB: MySQL):
    statement = ("SELECT * FROM ") + __table
    statement += ("WHERE ID = ") + id
    docs = DB.exec_query(statement)
    doc = {}
    if docs:
        for x in range(0, len(__workload_keys)):
            doc[__workload_keys[x]] = docs[0][x]
        return doc

    else:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "400"
        error["title"] = "Not Found"
        return error


@inject
def create_doc(doc, DB: MySQL):
    values = {}
    statement = ("INSERT INTO ") + __table
    statement += "("
    for x in range(0, len(__workload_keys) - 1):
        statement += __workload_keys[x] + ","
        values[__workload_keys[x]] = doc[__workload_keys[x]]
    statement += __workload_keys[len(__workload_keys) - 1] + ") "
    statement += ("VALUES (")
    last_val = __workload_keys[len(__workload_keys) - 1]
    values[__workload_keys[len(__workload_keys) - 1]] = doc[last_val]
    for x in range(0, len(__workload_keys) - 1):
        statement += "%(" + __workload_keys[x] + ")s,"
    statement += "%(" + __workload_keys[len(__workload_keys) - 1] + ")s)"
    DB.exec_query(statement, values)
    #print (statement,values)
    #else:
    #    error = {}
    #    error["detail"] = "The requested ID already exists on the server"
    #    error["status"] = "304"
    #    error["title"] = "Not Found"
    #    return error


@inject
def erase_doc(id, DB: MySQL):
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
