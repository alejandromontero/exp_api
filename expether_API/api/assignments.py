from random import choice as ranchoice
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from flask_injector import inject
from config.MySQL_config.MySQL_config import assignment_keys
from config.MySQL_config.MySQL_config import assigned_capacity_keys
from api.cards import get_card
from utilities.messages import messenger
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table = "assignments"
__table_assigned_capacities = "assigned_capacity"
__doc_type = "assignment"
__NON_USED_HARDWARE_GROUP_NUMBER = "4093"


# Check whether the selected card can be assigned to a server
# 1: If card is not assigned to any server: OK
# 2: If card is already assigned to the requested server: OK
# Otherwise, NO
def is_feasible_to_asign_hardware(hardware, server_card, DB, EEM):
    if (get_card(hardware, DB, EEM)["group_id"] ==
            __NON_USED_HARDWARE_GROUP_NUMBER):
        return True
    else:
        statement = (
            "SELECT COUNT(*) "
            "FROM assignments "
            'WHERE hardware_card = "%s" '
            'AND server_card = "%s"'
        ) % (hardware, server_card)
        result = DB.select_query(statement)
        if result and isinstance(result, Iterable):
            while isinstance(result, Iterable):
                result = next(iter(result))
            if result >= 1:
                return True
        return False


# Return whether or not is feasible to unasign a hardware card
# Condition 1: The hardware card is assigned only to the finished workload
def is_feasible_to_unasign_hardware(assigned_hardware, server_card, DB):
    statement = (
        "SELECT COUNT(*) "
        "FROM assignments "
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


# Returns the value of the specified capacity
# That is already assigned to other workloads
def get_assigned_capacity(hardware_card, capacity_req, DB):
    statement = (
        "SELECT COUNT(hardware_card) "
        "FROM assignments "
        'WHERE hardware_card = "%s"'
        ) % (hardware_card)
    card_has_assignaments = DB.select_query(statement)
    while isinstance(card_has_assignaments, Iterable):
        card_has_assignaments = next(iter(card_has_assignaments))
    if card_has_assignaments > 0:
        statement = (
            "SELECT value "
            "FROM assigned_capacity "
            'WHERE hardware_card = "%s" '
            'AND capacity_name = "%s"'
            ) % (hardware_card, capacity_req)
        values = DB.select_query(statement)
        if values:
            total_value = 0
            for value in values:
                while isinstance(value, Iterable):
                    value = next(iter(value))
                total_value += value
            return total_value
        else:
            return 0
    else:
        return 0


# Return a list of hardware boxes that can be assigned
# And comply with the requirements of the workload
# Conditions:
# 1: There has to be at least one card of the specified type
# 2: If "model" specified by the user, there has to be at least one card that
#    satisfies the name
# 3: If there is any previous assignment of the card, the capacity of the card
#    cannot be exceeded
def get_available_hardware(requirement, server_card, DB, EEM):
    # Check whether there is an available hardware card of the
    # type required by the workload
    statement = (
        "SELECT id "
        "FROM hardware_cards "
        'WHERE hardware = "%s" '
        'AND model LIKE "%%%s%%"'
    ) % (requirement[2], requirement[3])
    non_assigned_hardware = []
    available_hardware = DB.select_query(statement)

    if available_hardware:
        # In case there is available hardware,
        # check if the cards meet the requirements
        statement = (
            "SELECT requirement_name "
            "FROM capacity_requirements "
            'WHERE requirement_id = "%s" '
            'AND workload_id = "%s"'
            ) % (requirement[0], requirement[1])
        capacity_reqs = DB.select_query(statement)

        statement = (
            "SELECT value "
            "FROM capacity_requirements "
            'WHERE requirement_id = "%s" '
            'AND workload_id = "%s"'
            ) % (requirement[0], requirement[1])
        values = DB.select_query(statement)

        for hardware in available_hardware:
            if isinstance(hardware, Iterable):
                hardware = next(iter(hardware))
            if not capacity_reqs:
                non_assigned_hardware.append(hardware)
            else:
                hardware_can_be_assigned = is_feasible_to_asign_hardware(
                    hardware, server_card, DB, EEM)
                # Hardware can only be assigned if ALL requirements are met
                for x in range(0, len(capacity_reqs)):
                    if isinstance(capacity_reqs[x], Iterable):
                        capacity_reqs[x] = next(iter(capacity_reqs[x]))

                    if isinstance(values[x], Iterable):
                        values[x] = next(iter(values[x]))

                    assigned_capacity = get_assigned_capacity(
                        hardware,
                        capacity_reqs[x],
                        DB)

                    final_value = values[x] + assigned_capacity

                    # If assigned capacity + requested capacity
                    # < total capacity, then assignment is feasible
                    statement = (
                        "SELECT COUNT(hardware_id) "
                        "FROM hardware_capacity "
                        'WHERE hardware_id = "%s" '
                        'AND capacity_name = "%s" '
                        'AND value >= "%s" '
                        ) % (
                            hardware,
                            capacity_reqs[x],
                            final_value)

                    matches_capacity = DB.select_query(statement)

                    while isinstance(matches_capacity, Iterable):
                        matches_capacity = next(iter(matches_capacity))
                    if not matches_capacity >= 1:
                        hardware_can_be_assigned = False
                if hardware_can_be_assigned:
                    non_assigned_hardware.append(hardware)

        return non_assigned_hardware

    else:
        return False


# Return the hardware card assigned to the workload
def get_assignment_hardware(workload_id, DB):
    statement = (
        "SELECT hardware_card "
        "FROM assignments "
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


# Create entries in the DB for each capacity assigned
def assign_capacities(
        hardware_card, network_card,
        workload_id, requirement_id, DB):

    statement = (
        "SELECT requirement_name "
        "FROM capacity_requirements "
        'WHERE workload_id = "%s" '
        'AND requirement_id = "%s"'
        ) % (workload_id, requirement_id)
    requirements = DB.select_query(statement)

    statement = (
        "SELECT value "
        "FROM capacity_requirements "
        'WHERE workload_id = "%s" '
        'AND requirement_id = "%s"'
        ) % (workload_id, requirement_id)
    values = DB.select_query(statement)

    statement = (
        "SELECT unit "
        "FROM capacity_requirements "
        'WHERE workload_id = "%s" '
        'AND requirement_id = "%s"'
        ) % (workload_id, requirement_id)
    units = DB.select_query(statement)

    for x in range(0, len(requirements)):
        while isinstance(requirements[x], Iterable) and not \
                isinstance(requirements[x], str):
            requirements[x] = next(iter(requirements[x]))
        while isinstance(units[x], Iterable) and not \
                isinstance(units[x], str):
            units[x] = next(iter(units[x]))
        while isinstance(values[x], Iterable) and not \
                isinstance(values[x], str):
            values[x] = next(iter(values[x]))

        insert_values = [
            hardware_card,
            network_card,
            workload_id,
            requirements[x],
            units[x],
            values[x]]

        status, message = DB.insert_query(
            __table_assigned_capacities,
            assigned_capacity_keys,
            insert_values)

        if not status:
            return (status, message)

    return (True, "OK")


# Checks correctness and executes the commit if so
def finish_assignment(success, message, DB):
    if success:
        status, commit_message = DB.commit_transaction()
        if status:
            return messenger.message200(message)

        # Implicit rollback
        else:
            return messenger.message409(commit_message)
    else:
        status, error = DB.rollback(message)
        return messenger.message409(error)


@inject
def get_all_assignments(DB: MySQL):
    statement = ("SELECT * FROM %s ") % __table
    assignments = DB.select_query(statement)
    res_assignments = []
    if assignments:
        for assignment in assignments:
            res_assignment = {}
            for x in range(0, len(assignment_keys)):
                res_assignment[assignment_keys[x]] = assignment[x]
            res_assignments.append(res_assignment)
        return res_assignments

    else:
        return messenger.message404("No assignments found")


@inject
def create_assignment(workload, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    workload_id = next(iter(workload.values()))
    statement = ("SELECT * FROM hardware_requirements ")
    statement += ("WHERE workload_id = %s") % workload_id
    workload_requirements_hardware = DB.select_query(statement)
    if not workload_requirements_hardware:
        message = "Workload does not exist or "
        message += "does not have any hardware requirements"
        return finish_assignment(False, message, DB)

    # Retrieve server EEM net card and GID
    workload_server_net_card, gid = get_server_card(workload_id, DB)
    if not workload_server_net_card:
        return finish_assignment(
            False,
            "The workload server does not have any EEM net card attached",
            DB)

    boxes = set()
    for requirement in workload_requirements_hardware:
        available_hardware = get_available_hardware(
            requirement,
            workload_server_net_card,
            DB, EEM)
        if not available_hardware:
            return finish_assignment(
                False,
                "There is not any availble hardware of the type: %s" % (
                    requirement[2]),
                DB)
        hardware_choice = select_hardware(available_hardware)
        status, message = assign_capacities(
            hardware_choice,
            workload_server_net_card,
            workload_id,
            requirement[0],
            DB)
        if not status:
            return finish_assignment(
                False,
                message,
                DB)

        boxes.add(hardware_choice)

    vlan_message = ""
    for box in boxes:
        values = [box, workload_server_net_card, workload_id]
        status, message = DB.insert_query(
            __table,
            assignment_keys,
            values)

        if not status:
            return finish_assignment(
                False,
                message,
                DB)

        EEM.assign_hardware_to_server(box, gid)
        vlan_message += "New VLAN created between %s and %s " % (
            box,
            workload_server_net_card)

    return finish_assignment(
        True,
        vlan_message,
        DB)


@inject
def erase_assignment(workload, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    workload_id = next(iter(workload.values()))
    # Retrieve server EEM net card and GID
    workload_server_net_card, gid = get_server_card(workload_id, DB)
    if not workload_server_net_card:
        return finish_assignment(
            False,
            "Workload does not exist or is not assigned to any server",
            DB)

    downs_port = get_card(workload_server_net_card, DB, EEM)["downstream_port"]
    if downs_port == "All down":
        message = (
            "Cannot erase assignment as the network card %s "
            "does not have any hardware card attached"
            % workload_server_net_card)
        return finish_assignment(
            False,
            message,
            DB)

    downs_port = downs_port["downstream_port_id"]
    assigned_cards = get_assignment_hardware(workload_id, DB)
    if not assigned_cards:
        message = (
            "Cannot erase assignment as the workload does not "
            "have any hardware card assigned"
        )
        return finish_assignment(
            False,
            message,
            DB)

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
                "there are other assignments in progress, "
                "DB assignment erased"
            ) % (assigned_hardware, workload_server_net_card)

        # Always eliminate assignment in DB even if the VLAN can't be erased
        status1, message1 = DB.delete_query(
            __table,
            assignment_keys,
            values)

        status2, message2 = DB.delete_query_simple(
            __table_assigned_capacities,
            "workload",
            workload_id)

        if not status1:
            status = False
            message = message1
        elif not status2:
            status = False
            message = message2
        else:
            status = True

        if not status:
            return finish_assignment(
                False,
                message,
                DB)

    return finish_assignment(
        True,
        erase_message,
        DB)
