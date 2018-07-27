import os
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from flask_injector import inject
from api.cards import get_card
from utilities.messages import messenger
from api.assignaments import get_all_assignaments
from api.workloads import get_all_workloads
from api.cards import get_all_hardware_cards
from api.cards import get_all_network_cards
from config.MySQL_config.MySQL_config import hardware_card_mapping
from config.MySQL_config.MySQL_config import net_card_mapping
from utilities.html import html
from utilities.eemParser import eemParser
from collections import Iterable
from flask import (
    make_response,
    abort
)
from config.MySQL_config.MySQL_config import (
    workload_mapping,
    hardware_card_mapping,
    net_card_mapping,
    servers_mapping,
    assignament_mapping
)


__NON_USED_HARDWARE_GROUP_NUMBER = "4093"
__work_mapping = list(workload_mapping.keys())
__hardw_mapping = list(hardware_card_mapping.keys())
__net_mapping = list(net_card_mapping.keys())
__serv_mapping = list(servers_mapping.keys())
__assig_mapping = list(assignament_mapping.keys())
__html_dumb_folder = os.path.join(
    os.path.dirname(__file__),
    "..", "www"
    )


# Return whether an assignament was performed by the API
# For now we are limited to test whether there is a row in the DB
# That assigns a hardware card to a net card, even if there are other
# Assignaments performed manually by the user
def is_ghost_assignament(hard_card, net_card, DB):
    statement = (
        "SELECT COUNT(*) "
        "FROM assignaments "
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


def get_network_card(gid, DB):
    statement = (
        "SELECT id "
        "FROM net_card "
        'WHERE gid = "%s"'
    ) % (gid)
    net = DB.select_query(statement)
    while (isinstance(net, Iterable) and not isinstance(net, str)):
        net = next(iter(net))
    return net


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


def get_workload_server(gid, DB):
    statement = (
        "SELECT assigned_to "
        "FROM net_card "
        'WHERE gid = "%s"'
    ) % (gid)
    server = DB.select_query(statement)
    while (isinstance(server, Iterable) and not isinstance(server, str)):
        server = next(iter(server))
    return server  # For some reason the above loop never converges


def dumb_html_file(filename, html):
    dumb_file = os.path.join(
        __html_dumb_folder,
        filename
    )
    with open(dumb_file, 'w') as file:
        file.write(html)


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

    # Get API assignaments that have a hardware card assigned to a
    # Net card with the corresponding GID
    for card in assigned_cards:
        net_card = get_network_card(card["group_id"], DB)
        if is_ghost_assignament(card["id"], net_card, DB):
            # First, generate a new workload with unknown data
            id = get_next_id(DB)
            server = get_workload_server(card["group_id"], DB)
            values = [id, "UNKNOWN", "UNKNOWN", server]
            status, message = DB.insert_query(
                "workloads",
                __work_mapping,
                values)
            if not status:
                return (status, message)

            # Second, generate a new ghost assignament
            values = [card["id"], net_card, id]
            status, message = DB.insert_query(
                "assignaments",
                __assig_mapping,
                values)

            if not status:
                return (status, values)
                return (status, message)
    return (True, 'OK')


# TODO: Is there a way to discover the server by using the GID???
def update_net_card(card, DB):
    mapping = list(net_card_mapping.keys())
    values = []
    for field in mapping:
        if field in card:
            values.append(card[field])
        else:
            if field == "gid":
                values.append(card["group_id"])
            else:
                values.append(None)

    return DB.insert_query(
        "net_card",
        mapping,
        values)


def update_hardware_card(card, DB):
    mapping = list(hardware_card_mapping.keys())
    values = []
    for field in mapping:
        if field in card and field != "model":
            values.append(card[field])
        else:
            values.append("UNKNOWN")

    return DB.insert_query(
        "hardware_cards",
        mapping,
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


@inject
def get_state(DB: MySQL, EEM: EEM):
    docs = []
    assignaments = get_all_assignaments(DB)
    if "status" not in assignaments:
        docs.append(
            {
                "name": "assignaments",
                "mapping": __assig_mapping,
                "values": assignaments
            }
        )
    workloads = get_all_workloads(DB)
    if "status" not in workloads:
        docs.append(
            {
                "name": "workloads",
                "mapping": __work_mapping,
                "values": workloads
            }
        )
    hardw_cards = get_all_hardware_cards(DB, EEM)
    if "status" not in hardw_cards:
        docs.append(
            {
                "name": "hardware cards",
                "mapping": __hardw_mapping,
                "values": hardw_cards
            }
        )
    net_cards = get_all_network_cards(DB, EEM)
    if "status" not in net_cards:
        docs.append(
            {
                "name": "network cards",
                "mapping": __net_mapping,
                "values": net_cards
            }
        )
    html_file = html.generate_table_jinja(docs)
    dumb_html_file("global_state.html", html_file)


@inject
def update_state(DB: MySQL, EEM: EEM):
    n_cards = 0
    cards = []
    for line in EEM.get_all_logical_assigned().splitlines():
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
    if status:
        return messenger.message200('OK')
    else:
        return messenger.general_error(message)