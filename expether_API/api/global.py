import os
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from flask_injector import inject
from api.cards import get_card
from utilities.messages import messenger
from api.assignments import get_all_assignments
from api.workloads import get_all_workloads
from api.cards import get_all_hardware_cards
from api.cards import get_all_network_cards
from utilities.html import html
from copy import deepcopy
from utilities.eemParser import eemParser
from collections import Iterable
from flask import (
    make_response,
    abort,
    render_template
)
from config.MySQL_config.MySQL_config import (
    workload_keys,
    hardware_card_keys,
    hardware_capacity_keys,
    net_card_keys,
    servers_keys,
    assignment_keys
)


__NON_USED_HARDWARE_GROUP_NUMBER = "4093"
__state_html_filename = "global_state.html"
__html_dumb_folder = os.path.join(
    os.path.dirname(__file__),
    "..", "www"
    )
assignment_keys_extended = [
        "hardware_card",
        "server_card",
        "workload",
        "hardware_type",
        "hardware_model",
        "server_name",
        "user",
        "description"]

workload_keys_extended = deepcopy(workload_keys)
hardware_card_extended_keys = deepcopy(hardware_card_keys)
workload_keys_extended.append("requirements")
hardware_card_extended_keys.append("capacity")


# Return whether an assignment was performed by the API
# For now we are limited to test whether there is a row in the DB
# That assigns a hardware card to a net card, even if there are other
# Assignaments performed manually by the user
def is_ghost_assignment(hard_card, net_card, DB):
    statement = (
        "SELECT COUNT(*) "
        "FROM assignments "
        'WHERE hardware_card = "%s" '
        "AND "
        'server_card = "%s"'
    ) % (hard_card, net_card)

    count = DB.select_query(statement)
    while (isinstance(count, Iterable)):
        count = next(iter(count))

    if count == 0:
        return True
    else:
        return False


def get_next_id(DB):
    statement = (
        "SELECT MIN(id) "
        "FROM workloads"
    )
    id = DB.select_query(statement)
    while (isinstance(id, Iterable)):
        id = next(iter(id))

    if not id:
        return -1
    elif id >= 0:
        return -1
    else:
        return id - 1


def get_from_DB_simple(attribute, table, condition, condition_value, DB):
    statement = (
        "SELECT %s "
        "FROM %s "
        'WHERE %s = "%s"'
    ) % (attribute, table, condition, condition_value)
    value = DB.select_query(statement)
    while (isinstance(value, Iterable) and not isinstance(value, str)):
        value = next(iter(value))
    return value


def dumb_html_file(html):
    dumb_file = os.path.join(
        __html_dumb_folder,
        __state_html_filename
    )
    with open(dumb_file, 'w') as file:
        file.write(html)


def read_html_file():
    dumb_file = os.path.join(
        __html_dumb_folder,
        __state_html_filename
    )
    if os.path.exists(dumb_file):
        with open(dumb_file, 'r') as file:
            return file.read()
    else:
        return False


def update_assigned_cards(cards, DB):
    assigned_cards = []
    for card in cards:
        parsed_card = eemParser.parse(card)
        if (
            parsed_card["status"] == "eeio" and
            parsed_card["group_id"] != __NON_USED_HARDWARE_GROUP_NUMBER
        ):
            assigned_cards.append(
                {
                    "id": parsed_card["id"],
                    "group_id": parsed_card["group_id"],
                }
            )

    # Get API assignments that have a hardware card assigned to a
    # Net card with the corresponding GID
    for card in assigned_cards:
        net_card = get_from_DB_simple(
            "id",
            "net_card",
            "gid",
            card["group_id"],
            DB)
        if is_ghost_assignment(card["id"], net_card, DB):
            # First, generate a new workload with unknown data
            id = get_next_id(DB)
            server = get_from_DB_simple(
                "assigned_to",
                "net_card",
                "gid",
                card["group_id"],
                DB)
            values = [id, "UNKNOWN", "UNKNOWN", "UNKNOWN", server]
            status, message = DB.insert_query(
                "workloads",
                workload_keys,
                values)
            if not status:
                return (status, message)

            # Second, generate a new ghost assignment
            values = [card["id"], net_card, id]
            status, message = DB.insert_query(
                "assignments",
                assignment_keys,
                values)

            if not status:
                return (status, values)
                return (status, message)
    return (True, 'OK')


# TODO: Is there a way to discover the server by using the GID???
def update_net_card(card, DB):
    values = []
    for field in net_card_keys:
        if field in card:
            values.append(card[field])
        else:
            if field == "gid":
                values.append(card["group_id"])
            else:
                values.append(None)

    return DB.insert_query(
        "net_card",
        net_card_keys,
        values)


def update_hardware_card(card, DB):
    values = []
    for field in hardware_card_keys:
        if field in card and field != "model":
            values.append(card[field])
        else:
            values.append("UNKNOWN")

    return DB.insert_query(
        "hardware_cards",
        hardware_card_keys,
        values)


def update_cards(cards, DB):
    DB_cards = []
    statement = (
        "SELECT id "
        "FROM hardware_cards"
    )
    statement2 = (
        "SELECT id "
        "FROM net_card"
    )
    for DB_card in DB.select_query(statement):
        while (isinstance(DB_card, Iterable) and not isinstance(DB_card, str)):
            DB_card = next(iter(DB_card))
        DB_cards.append(DB_card)
    for DB_card in DB.select_query(statement2):
        while (isinstance(DB_card, Iterable) and not isinstance(DB_card, str)):
            DB_card = next(iter(DB_card))
        DB_cards.append(DB_card)
    for card in cards:
        status = True
        card = eemParser.parse(card)
        if card["id"] not in DB_cards:
            if card["status"] == "eeio":
                status, message = update_hardware_card(card, DB)
            else:
                status, message = update_net_card(card, DB)

            if not status:
                return messenger.general_error(message)

    return messenger.message200('OK')


def create_state_html(DB, EEM):
    docs = []
    assignments = get_all_assignments(DB)
    if "status" not in assignments:
        assignments_extended = []
        for assignment in assignments:
            assignment_extended = assignment

            assignment_extended["hardware_type"] = get_from_DB_simple(
                "hardware",
                "hardware_cards",
                "id",
                assignment["hardware_card"],
                DB)

            assignment_extended["hardware_model"] = get_from_DB_simple(
                "model",
                "hardware_cards",
                "id",
                assignment["hardware_card"],
                DB)

            assignment_extended["server_name"] = get_from_DB_simple(
                "assigned_to",
                "net_card",
                "id",
                assignment["server_card"],
                DB)

            assignment_extended["user"] = get_from_DB_simple(
                "user",
                "workloads",
                "id",
                assignment["workload"],
                DB)

            assignment_extended["description"] = get_from_DB_simple(
                "description",
                "workloads",
                "id",
                assignment["workload"],
                DB)

            assignments_extended.append(assignment_extended)

        docs.append(
            {
                "name": "assignments",
                "mapping": assignment_keys_extended,
                "values": assignments_extended
            }
        )
    workloads = get_all_workloads(DB)
    if "status" not in workloads:
        docs.append(
            {
                "name": "workloads",
                "mapping": workload_keys_extended,
                "values": workloads
            }
        )
    hardw_cards = get_all_hardware_cards(DB, EEM)
    if "status" not in hardw_cards:
        docs.append(
            {
                "name": "hardware cards",
                "mapping": hardware_card_extended_keys,
                "values": hardw_cards
            }
        )
    net_cards = get_all_network_cards(DB, EEM)
    if "status" not in net_cards:
        docs.append(
            {
                "name": "network cards",
                "mapping": net_card_keys,
                "values": net_cards
            }
        )
    return html.generate_table_jinja(docs)


@inject
def get_state(DB: MySQL, EEM: EEM):
    n_cards = 0
    cards = []
    for line in EEM.get_all_logical_assigned().splitlines():
        if "[Errno 113]" in line:
            return messenger.message404("No route to EEM")
        if (
            line != "----------------------------------------" and
            "timestamp:" not in line
        ):
            if len(cards) <= n_cards:
                cards.append("")
            cards[n_cards] += line + '\n'
        else:
            n_cards += 1
    status, message = update_cards(cards, DB)
    status, message = update_assigned_cards(cards, DB)
    if not status:
        return messenger.general_error(message)

    return make_response(create_state_html(DB, EEM))

