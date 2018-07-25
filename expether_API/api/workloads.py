from services.elasticsearch.elasticsearch import ElasticSearchIndex
from services.mysql.mysqlDB import MySQL
from flask_injector import inject
from config.MySQL_config.MySQL_config import workload_mapping as mapping
from utilities.messages import messenger
from copy import deepcopy
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table = "workloads"
__workload_keys = list(mapping.keys())


@inject
def get_all_workloads(DB: MySQL):
    statement = ("SELECT * FROM ") + __table
    workloads = DB.select_query(statement)
    res_workloads = []
    if workloads:
        for workload in workloads:
            res_workload = {}
            for x in range(0, len(__workload_keys)):
                res_workload[__workload_keys[x]] = workload[x]
            res_workloads.append(res_workload)
        return res_workloads

    else:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "400"
        error["title"] = "Not Found"
        return error


@inject
def get_workload(id, DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table
    statement += ("WHERE ID = %s") % id
    workloads = DB.select_query(statement)
    workload = {}
    if workloads:
        for x in range(0, len(__workload_keys)):
            workload[__workload_keys[x]] = workloads[0][x]
        return workload

    else:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "400"
        error["title"] = "Not Found"
        return error


@inject
def create_workload(workload, DB: MySQL):
    mapping = deepcopy(__workload_keys)
    mapping.remove("id")
    if len(workload.keys()) != len(mapping):
        message = "Inserted workload data is incorrect"
        return messenger.message404(message)

    values = []
    for x in range(0, len(mapping)):
        values.append(workload[mapping[x]])

    status, message = DB.insert_query(
        __table,
        mapping,
        values)

    if not status:
        return messenger.message404(message)

    statement = ("SELECT LAST_INSERT_ID()")
    id = DB.select_query(statement)
    while (isinstance(id, Iterable)):
        id = next(iter(id))

    return messenger.messageWorkload(id)


@inject
def erase_workload(id, DB: MySQL):
    mapping = ["id"]
    values = [id]

    status, message = DB.delete_query(
        __table,
        mapping,
        values)

    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)
