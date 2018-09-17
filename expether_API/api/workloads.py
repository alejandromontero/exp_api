from services.elasticsearch.elasticsearch import ElasticSearchIndex
from services.mysql.mysqlDB import MySQL
from flask_injector import inject
from config.MySQL_config.MySQL_config import workload_keys
from config.MySQL_config.MySQL_config import hardware_requirements_keys
from config.MySQL_config.MySQL_config import capacity_requirements_keys
from utilities.messages import messenger
from copy import deepcopy
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table_workloads = "workloads"
__table_hardware_requirements = "hardware_requirements"
__table_capacity_requirements = "capacity_requirements"


def get_workload_requirements(DB, id):
    statement = (
        "SELECT * FROM %s "
        "WHERE workload_id = %s") % (
            __table_hardware_requirements,
            id)
    result = DB.select_query(statement)
    return result

def get_workload_capacities(DB, id):
    statement = (
        "SELECT * FROM %s "
        "WHERE workload_id = %s") % (
            __table_capacity_requirements,
            id)
    result = DB.select_query(statement)
    return result

def process_workload(DB, workload):
    hardware_requirement_key_simplified = deepcopy(hardware_requirements_keys)
    capacity_requirement_key_simplified = deepcopy(capacity_requirements_keys)
    hardware_requirement_key_simplified.remove("workload_id")
    hardware_requirement_key_simplified.remove("requirement_id")
    capacity_requirement_key_simplified.remove("workload_id")
    capacity_requirement_key_simplified.remove("requirement_id")
    res_workload = {}
    for x in range(0, len(workload_keys)):
        res_workload[workload_keys[x]] = workload[x]

    requirements = get_workload_requirements(DB, workload[0])
    res_workload["requirements"] = []
    for requirement in requirements:
        processed_req = {}
        for x in range(0, len(hardware_requirement_key_simplified)):
            processed_req[
                hardware_requirement_key_simplified[x]] = requirement[x+2]
        capacities = get_workload_capacities(DB, workload[0])
        processed_req["hardware_capacity_requirements"] = []
        for capacity in capacities:
            processed_cap = {}
            for y in range(0, len(capacity_requirement_key_simplified)):
                processed_cap[
                    capacity_requirement_key_simplified[y]] = capacity[y+2]
            processed_req[
                "hardware_capacity_requirements"].append(processed_cap)
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
    DB.start_transaction()

    mapping = deepcopy(workload_keys)
    mapping_requirement = deepcopy(hardware_requirements_keys)
    mapping_requirement_insert = deepcopy(hardware_requirements_keys)
    mapping_capacity = deepcopy(capacity_requirements_keys)
    mapping.remove("id")  # As it is assigned by the API
    mapping_requirement.remove("workload_id")  # Not present in the petition
    mapping_requirement.remove("requirement_id")  # Not present in the petition
    mapping_requirement_insert.remove("requirement_id")  # Not present in the petition
    mapping_capacity.remove("workload_id")  # Not present in the petition
    mapping_capacity.remove("requirement_id")  # Not present in the petition

    if len(workload.keys()) - 1 != len(mapping):
        message = "Inserted workload data is incorrect"
        return messenger.message404(message)

    values = []
    for x in range(0, len(mapping)):
        if mapping[x] in workload:
            values.append(workload[mapping[x]])
        else:
            message = "%s not introduced in the request" % (
                mapping[x])
            return messenger.message404(message)

    status1, message1 = DB.insert_query(
        __table_workloads,
        mapping,
        values)

    # Get the assigned ID of the workload
    statement = ("SELECT MAX(id) FROM workloads")
    workload_id = DB.select_query(statement)
    while (isinstance(workload_id, Iterable)):
        workload_id = next(iter(workload_id))
    if not workload_id or workload_id < 0:
        workload_id = 1
    else:
        workload_id += 1

    # Time to create the requirements of the workload, one entry each
    requirements = workload["requirements"]
    for requirement in requirements:
        values = [workload_id]
        for x in range(0, len(mapping_requirement)):
            if mapping_requirement[x] in requirement:
                values.append(requirement[mapping_requirement[x]])
            else:
                message = "%s not introduced in the request" % (
                    mapping_requirement[x])
                return messenger.message404(message)

        status2, message2 = DB.insert_query(
            __table_hardware_requirements,
            mapping_requirement_insert,
            values)

        statement = ("SELECT MAX(requirement_id) FROM hardware_requirements")
        req_id = DB.select_query(statement)
        while (isinstance(req_id, Iterable)):
            req_id = next(iter(req_id))
        if not req_id:
            req_id = 1
        else:
            req_id += 1

        capacity_req = requirement["hardware_capacity_requirements"]
        for capacity in capacity_req:
            values = [workload_id, req_id]
            for x in range(0, len(mapping_capacity)):
                if mapping_capacity[x] in capacity:
                    values.append(capacity[mapping_capacity[x]])
                else:
                    message = "%s not introduced in the request" % (
                        mapping_capacity[x])
                    return messenger.message404(message)

            status3, message3 = DB.insert_query(
                __table_capacity_requirements,
                capacity_requirements_keys,
                values)

    if not status1:
        status = False
        message = message1
    elif not status2:
        status = False
        message = message2
    elif not status3:
        status = False
        message = message3
    else:
        status = True
        message = "OK"

    # First status code checks:
    # 1: Syntaxis
    # 2: Completeness
    if status:
        status, message = DB.commit_transaction()
        # Second status checks:
        # 1: Data integrity
        if status:
            return messenger.messageWorkload(workload_id)

        # Implicit rollback
        else:
            return messenger.message404(message)
    else:
        status, error = DB.rollback(messsage)
        return messenger.message404(error)



@inject
def erase_workload(id, DB: MySQL):
    DB.start_transaction()

    mapping = ["id"]
    values = [id]

    status1, message1 = DB.delete_query_simple(
        __table_capacity_requirements,
        "workload_id",
        id)

    status2, message2 = DB.delete_query_simple(
        __table_hardware_requirements,
        "workload_id",
        id)

    status3, message3 = DB.delete_query_simple(
        __table_workloads,
        "id",
        id)

    if not status1:
        status = False
        message = message1
    elif not status2:
        status = False
        message = message2
    elif not status3:
        status = False
        message = message3
    else:
        status = True
        message = "OK"

    # First status code checks:
    # 1: Syntaxis
    # 2: Completeness
    if status:
        status, message = DB.commit_transaction()
        # Second status checks:
        # 1: Data integrity
        if status:
            return messenger.message200("OK")

        # Implicit rollback
        else:
            return messenger.message404(message)
    else:
        status, error = DB.rollback(messsage)
        return messenger.message404(error)
