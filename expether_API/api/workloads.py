from services.elasticsearch.elasticsearch import ElasticSearchIndex
from services.mysql.mysqlDB import MySQL
from flask_injector import inject
from config.MySQL_config.MySQL_config import workload_mapping
from config.MySQL_config.MySQL_config import requirement_mapping
from utilities.messages import messenger
from copy import deepcopy
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table_workloads = "workloads"
__table_requirements = "requirements"
__workload_keys = list(workload_mapping.keys())
__requirement_keys = list(requirement_mapping.keys())


def get_workload_requirements(DB, id):
    statement = (
        "SELECT * FROM %s "
        "WHERE workload_id = %s") % (
            __table_requirements,
            id)
    result = DB.select_query(statement)
    return result


def process_workload(DB, workload):
    requirement_mapping = deepcopy(__requirement_keys)
    requirement_mapping.remove("workload_id")
    res_workload = {}
    for x in range(0, len(__workload_keys)):
        res_workload[__workload_keys[x]] = workload[x]

    requirements = get_workload_requirements(DB, workload[0])
    res_workload["requirements"] = []
    for requirement in requirements:
        processed_req = {}
        for x in range(0, len(requirement_mapping)):
            processed_req[requirement_mapping[x]] = requirement[x+1]
        res_workload["requirements"].append(processed_req)
    return res_workload


@inject
def get_all_workloads(DB: MySQL):
    statement = ("SELECT * FROM ") + __table_workloads
    workloads = DB.select_query(statement)
    res_workloads = []
    if workloads:
        for workload in workloads:
            res_workloads.append(process_workload(DB, workload))
        return res_workloads

    else:
        error = "The requested ID does not exist on the server"
        return messenger.message404(error)


@inject
def get_workload(id, DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table_workloads
    statement += ("WHERE ID = %s") % id
    workload = DB.select_query(statement)
    if workload and isinstance(workload, Iterable):
        return process_workload(DB, next(iter(workload)))

    else:
        error = "The requested ID does not exist on the server"
        return messenger.message404(error)


@inject
def create_workload(workload, DB: MySQL):
    mapping = deepcopy(__workload_keys)
    mapping_requirement = deepcopy(__requirement_keys)
    mapping.remove("id")
    mapping_requirement.remove("workload_id")
    if len(workload.keys()) - 1 != len(mapping):
        message = "Inserted workload data is incorrect"
        return messenger.message404(message)

    values = []
    for x in range(0, len(mapping)):
        values.append(workload[mapping[x]])

    status, message = DB.insert_query(
        __table_workloads,
        mapping,
        values)

    if not status:
        return messenger.message404(message)

    # Get the assigned ID of the workload
    statement = ("SELECT LAST_INSERT_ID()")
    id = DB.select_query(statement)
    while (isinstance(id, Iterable)):
        id = next(iter(id))

    # Time to create the requirements of the workload, one entry each
    requirements = workload["requirements"]
    for requirement in requirements:
        values = [id]
        for x in range(0, len(mapping_requirement)):
            if mapping_requirement[x] in requirement.keys():
                values.append(requirement[mapping_requirement[x]])
            else:
                values.append(None)

        status, message = DB.insert_query(
            __table_requirements,
            __requirement_keys,
            values)
        if not status:
            return messenger.message404(message)

    return messenger.messageWorkload(id)


@inject
def erase_workload(id, DB: MySQL):
    status, message = DB.delete_query_simple(
        __table_requirements,
        "workload_id",
        id)

    if not status:
        return messenger.message404(message)

    mapping = ["id"]
    values = [id]
    status, message = DB.delete_query(
        __table_workloads,
        mapping,
        values)

    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)
