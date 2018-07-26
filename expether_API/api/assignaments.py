from random import choice as ranchoice
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from flask_injector import inject
from config.MySQL_config.MySQL_config import assignament_mapping as mapping
from api.cards import get_card
from utilities.messages import messenger
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table = "assignaments"
__doc_type = "assignament"
__table_keys = list(mapping.keys())
__NON_USED_HARDWARE_GROUP_NUMBER = "4093"


# Check whether the selected card can be assigned to a server
def is_feasible_to_asign_hardware(hardware, DB, EEM):
    if (get_card(hardware, DB, EEM)["group_id"] ==
            __NON_USED_HARDWARE_GROUP_NUMBER):
        return True
    else:
        return False


# Return whether or not is feasible to unasign a hardware card
# Condition 1: The hardware card is assigned only to the finished workload
def is_feasible_to_unasign_hardware(assigned_hardware, server_card, DB):
    statement = (
        "SELECT COUNT(*) "
        "FROM assignaments "
        'WHERE hardware_card = "%s" '
        "AND "
        'server_card = "%s"'
    ) % (assigned_hardware, server_card)

    result = DB.select_query(statement)
    if result and isinstance(result[0], Iterable):
        if next(iter(result[0])) == 1:  # Condition 1
            return True
    return False


# Retrieve the network card of the server the workload has to run on
def get_server_card(workload_id, DB):
    statement = (
        "SELECT id, gid "
        "FROM net_card "
        "WHERE assigned_to = ( "
            "SELECT assigned_to "
            "FROM workloads "
            "WHERE id = %s "
        ")"
    ) % workload_id
    result = DB.select_query(statement)
    if result:
        if isinstance(result[0], Iterable):
            workload_server_net_card = result[0][0]
        if isinstance(result[0], Iterable):
            gid = result[0][1]
        return (workload_server_net_card, gid)
    else:
        return (False, False)


# Return a list of the hardware boxes already assigned to a server
def get_assigned_hardware_cards(workload_id, DB):
    statement = (
        "SELECT hardware_card "
        "FROM assignaments "
        "WHERE server_card = ( "
            "SELECT id FROM net_card "
            "WHERE assigned_to = ( "
                "SELECT assigned_to "
                "FROM workloads "
                "WHERE id = %s "
        "))"
    ) % workload_id
    return DB.select_query(statement)


# Return a list of hardware boxes that are not assigned to any server
def get_available_hardware(workload_id, DB, EEM):
    # Check whether there is an available hardware card of the
    # type required by the workload
    statement = (
        "SELECT id "
        "FROM hardware_cards "
        "WHERE hardware = ( "
            "SELECT requirement "
            "FROM workloads "
            "WHERE id = %s "
            ") "
    ) % workload_id
    non_assigned_hardware = []
    available_hardware = DB.select_query(statement)
    if available_hardware:
        for hardware in available_hardware:
            if isinstance(hardware, Iterable):
                hardware = next(iter(hardware))
            if is_feasible_to_asign_hardware(hardware, DB, EEM):
                non_assigned_hardware.append(hardware)
        return non_assigned_hardware
    else:
        return False


# Return the hardware card assigned to the workload
def get_assignament_hardware(workload_id, DB):
    statement = (
        "SELECT hardware_card "
        "FROM assignaments "
        "WHERE workload = %s "
        ) % workload_id
    result = DB.select_query(statement)
    if result and isinstance(result[0], Iterable):
        return next(iter(result[0]))
    return False


# Select one hardware box out of the available pool
# For now just pick a random
def select_hardware(hardware):
    return ranchoice(hardware)


@inject
def get_all_assignaments(DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table
    assignaments = DB.select_query(statement)
    res_assignaments = []
    if assignaments:
        for assignament in assignaments:
            res_assignament = {}
            for x in range(0, len(__table_keys)):
                res_assignament[__table_keys[x]] = assignament[x]
            res_assignaments.append(res_assignament)
        return res_assignaments

    else:
        return messenger.message404("No assignaments found")


@inject
def get_assignament(id, DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table
    statement += ("WHERE ID = ") + id
    assignaments = DB.select_query(statement)
    assignament = {}
    if assignaments:
        for x in range(0, len(__table_keys)):
            assignament[__table_keys[x]] = assignaments[0][x]
        return assignament

    else:
        return messenger.message404(
                "The requested ID does not exist on the server")


@inject
def create_assignament(workload, DB: MySQL, EEM: EEM):
    workload_id = next(iter(workload.values()))
    statement = ("SELECT requirement FROM workloads ")
    statement += ("WHERE id = %s") % workload_id
    workload_requirement = DB.select_query(statement)
    if workload_requirement:
        workload_requirement = next(iter(workload_requirement))
        if isinstance(workload_requirement, Iterable):
            workload_requirement = next(iter(workload_requirement))

    # Retrieve server EEM net card and GID
    workload_server_net_card, gid = get_server_card(workload_id, DB)
    if not workload_server_net_card:
        return messenger.message404(
            "The workload server does not have any EEM net card attached")

    # Retrieve the hardware cards already assigned to the server card
    assigned_hardware = get_assigned_hardware_cards(workload_id, DB)
    if assigned_hardware:
        for box in next(iter(assigned_hardware)):
            if get_card(box, DB, EEM)["hardware"] == workload_requirement:
                values = [box, workload_server_net_card, workload_id]
                status, message = DB.insert_query(
                        __table,
                        __table_keys,
                        values)
                if status:
                    message = "Card %s of type %s " % (
                            box,
                            workload_requirement)
                    message += "is already assigned to the server; "
                    message += "new assignament created"
                    return messenger.message200(message)
                else:
                    return messenger.general_error(message)

    # Retrieve a list of available hardware of the requested type
    available_hardware = get_available_hardware(workload_id, DB, EEM)
    if available_hardware:
        box = select_hardware(available_hardware)
        values = [box, workload_server_net_card, workload_id]
        status, message = DB.insert_query(
                __table,
                __table_keys,
                values)
        if status:
            return messenger.mesage200Debug(
                "New VLAN created between %s and %s" % (
                    box,
                    workload_server_net_card),
                EEM.assign_hardware_to_server(box, gid)
            )
        else:
            return messenger.general_error(message)
    else:
        return messenger.message404(
            "There is not any availble hardware of the type: %s" % (
                workload_requirement))


@inject
def erase_assignament(workload, DB: MySQL, EEM: EEM):
    workload_id = next(iter(workload.values()))
    # Retrieve server EEM net card and GID
    workload_server_net_card, gid = get_server_card(workload_id, DB)
    downs_port = get_card(workload_server_net_card, DB, EEM)["downstream_port"]
    if downs_port == "All down":
        message = (
            "Cannot erase assignment as the network card %s "
            "does not have any hardware card attached"
            % workload_server_net_card)
        return messenger.message404(message)
    downs_port = downs_port["downstream_port_id"]
    assigned_hardware = get_assignament_hardware(workload_id, DB)
    if not assigned_hardware:
        message = (
            "Cannot erase assignment as the workload does not "
            "have any hardware card assigned"
        )
        return messenger.message404(message)

    values = [assigned_hardware, workload_server_net_card, workload_id]
    status, message = DB.delete_query(
            __table,
            __table_keys,
            values)

    if is_feasible_to_unasign_hardware(
            assigned_hardware,
            workload_server_net_card,
            DB):
        return messenger.mesage200Debug(
            "VLAN erased between %s and %s" % (
                assigned_hardware,
                workload_server_net_card),
            EEM.disconect_hardware_from_server(gid, downs_port)
        )

    else:
        return messenger.message200(
            "VLAN between %s and %s could't be erased as "
            "there are other assignaments in progress"
        ) % (assigned_hardware, workload_server_net_card)
