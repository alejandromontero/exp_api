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
    if result and isinstance(result, Iterable):
        while isinstance(result, Iterable):
            result = next(iter(result))
        if result == 1:  # Condition 1
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
def get_available_hardware(hardware_type, DB, EEM):
    # Check whether there is an available hardware card of the
    # type required by the workload
    statement = (
        "SELECT id "
        "FROM hardware_cards "
        'WHERE hardware = "%s"'
    ) % hardware_type
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
    if result:
        return result
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
def create_assignament(workload, DB: MySQL, EEM: EEM):
    workload_id = next(iter(workload.values()))
    statement = ("SELECT * FROM requirements ")
    statement += ("WHERE workload_id = %s") % workload_id
    workload_requirements = DB.select_query(statement)
    if not workload_requirements:
        message = "Workload does not exist or "
        message += "does not have any requirements"
        return messenger.message404(message)

    # Retrieve server EEM net card and GID
    workload_server_net_card, gid = get_server_card(workload_id, DB)
    if not workload_server_net_card:
        return messenger.message404(
            "The workload server does not have any EEM net card attached")

    # Retrieve the hardware cards already assigned to the server card
    assigned_hardware = get_assigned_hardware_cards(workload_id, DB)
    if assigned_hardware:
        message_assignation = ""
        for box in assigned_hardware:
            box = next(iter(box))
            box_hardware_type = get_card(box, DB, EEM)["hardware"]
            for requirement in workload_requirements:
                if box_hardware_type == requirement[1]:
                    values = [box, workload_server_net_card, workload_id]
                    status, message = DB.insert_query(
                        __table,
                        __table_keys,
                        values)
                    if status:
                        message_assignation += "Card %s of type %s " % (
                            box,
                            requirement[1])
                        message_assignation += "is already assigned to the server; "
                        message_assignation += "new assignament created "
                    else:
                        message = "The assignment already exists, exiting..."
                        return messenger.message409(message)

        return messenger.message200(message_assignation)


    else:
        boxes = []
        for requirement in workload_requirements:
            available_hardware = get_available_hardware(requirement[1], DB, EEM)
            if not available_hardware:
                return messenger.message404(
                    "There is not any availble hardware of the type: %s" % (
                        requirement[1]))
            boxes.append(select_hardware(available_hardware))

        vlan_message = ""
        for box in boxes:
            values = [box, workload_server_net_card, workload_id]
            status, message = DB.insert_query(
                __table,
                __table_keys,
                values)

            if not status:
                return messenger.general_error(message)

            EEM.assign_hardware_to_server(box, gid)
            vlan_message += "New VLAN created between %s and %s " % (
                box,
                workload_server_net_card)

        return messenger.message200(vlan_message)


@inject
def erase_assignament(workload, DB: MySQL, EEM: EEM):
    workload_id = next(iter(workload.values()))
    # Retrieve server EEM net card and GID
    workload_server_net_card, gid = get_server_card(workload_id, DB)
    if not workload_server_net_card:
        message = "Workload does not exist or is not assigned to any server"
        return messenger.message404(message)
    downs_port = get_card(workload_server_net_card, DB, EEM)["downstream_port"]
    if downs_port == "All down":
        message = (
            "Cannot erase assignment as the network card %s "
            "does not have any hardware card attached"
            % workload_server_net_card)
        return messenger.message404(message)
    downs_port = downs_port["downstream_port_id"]
    assigned_cards = get_assignament_hardware(workload_id, DB)
    if not assigned_cards:
        message = (
            "Cannot erase assignment as the workload does not "
            "have any hardware card assigned"
        )
        return messenger.message404(message)

    erase_message = ""
    for assigned_hardware in assigned_cards:
        assigned_hardware = next(iter(assigned_hardware))
        values = [assigned_hardware, workload_server_net_card, workload_id]

        if is_feasible_to_unasign_hardware(
                assigned_hardware,
                workload_server_net_card,
                DB):

            EEM.disconect_hardware_from_server(assigned_hardware)

            erase_message += "VLAN erased between %s and %s" % (
                assigned_hardware,
                workload_server_net_card)

        else:
            erase_message += (
                "VLAN between %s and %s could't be erased as "
                "there are other assignaments in progress, "
                "DB assignament erased"
            ) % (assigned_hardware, workload_server_net_card)

        # Always eliminate assignment in DB even if the VLAN can't be erased
        status, message = DB.delete_query(
                __table,
                __table_keys,
                values)
        if not status:
            return messenger.general_error(message)

    return messenger.message200(erase_message)
