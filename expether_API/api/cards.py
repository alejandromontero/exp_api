import os
import re
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from utilities.eemParser import eemParser
from flask_injector import inject
from config.MySQL_config.MySQL_config import hardware_card_keys
from config.MySQL_config.MySQL_config import hardware_capacity_keys
from config.MySQL_config.MySQL_config import net_card_keys
from utilities.messages import messenger
from copy import deepcopy
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table_hardware = "hardware_cards"
__table_hardware_capacity = "hardware_capacity"
__table_net = "net_card"

hardware_card_extended_keys = deepcopy(hardware_card_keys)
hardware_card_extended_keys.append("capacity")


def insert_card(card, table, mapping, DB, EEM):
    if len(card.keys()) - 1 != len(mapping):
        message = "Inserted card data is incorrect"
        return (False, message)

    cards = get_all_cards(DB, EEM)
    if card["id"] not in cards:
        message = "Card ID does not exist in EEM"
        return (False, message)

    values = []
    for x in range(0, len(mapping)):
        if mapping[x] not in card:
            message = "%s not introduced in request" % (mapping[x])
            return (False, message)
        values.append(card[mapping[x]])

    return DB.insert_query(
        table,
        mapping,
        values)


def insert_card_capacity(card, table, mapping, DB, EEM):
    if "capacity" not in card:
        message = "Inserted card data is incorrect, capacity values missing"
        return (False, message)
    for capacity in card["capacity"]:
        capacity["hardware_id"] = card["id"]
        values = []
        for x in range(0, len(mapping)):
            if mapping[x] not in capacity:
                message = "%s not introduced in the request" % (mapping[x])
                return (False, message)
            values.append(capacity[mapping[x]])

        status, message = DB.insert_query(
            table,
            mapping,
            values)

        if not status:
            return (False, message)

    return (True, "OK")


def modify_card(card, table, mapping, DB, EEM):
    if len(card.keys()) - 1 != len(mapping):
        essage = "Inserted card data is incorrect"
        return (False, message)
    out = get_card(card["id"], DB, EEM)
    if out["status"] == "404":
        message = "The card to modify has no entry in the DB"
        return (False, message)
    mapping = deepcopy(mapping)
    mapping.remove("id")
    values = []
    for x in range(0, len(mapping)):
        values.append(card[mapping[x]])

    return DB.modify_query(
        table,
        mapping,
        values,
        "id",
        card["id"])


def modify_capacities(card, table, mapping, DB, EEM):
    if "capacity" not in card:
        return (True, "No capacities to update")
    statement = (
        "SELECT * FROM %s "
        'WHERE hardware_id = "%s"'
        ) % (table, card["id"])

    current_capacities = DB.select_query(statement)
    capacities = card["capacity"]
    for capacity in capacities:
        if "capacity_name" not in capacity:
            message = "capacity_name not introduced in the request"
            return (False, message)

        found = False
        capacity["hardware_id"] = card["id"]
        for current_capacity in current_capacities:
            if capacity["hardware_id"] in current_capacity and capacity["capacity_name"] in current_capacity:
                # We need to change the capacity values,
                # Table primary key is complex, we need a bit of work
                found = True
                values = []
                for x in range(0, len(mapping)):
                    if mapping[x] not in capacity:
                        message = "%s not introduced in the request" % (
                            mapping[x])
                        return (False, message)
                    values.append(capacity[mapping[x]])

                status, message = DB.modify_query_complex(
                    table,
                    mapping,
                    values,
                    ["hardware_id", "capacity_name"],
                    [capacity["hardware_id"], capacity["capacity_name"]]
                )

                if not status:
                    return (status, message)
        if not found:
            # A new capacity has been introduced, we require a new insert
            values = []
            for x in range(0, len(mapping)):
                if mapping[x] not in capacity:
                    message = "%s not introduced in the request" % (mapping[x])
                    return (False, message)
                values.append(capacity[mapping[x]])
            status, message = DB.insert_query(
                table,
                mapping,
                values)

            if not status:
                return (False, message)

    return (True, "OK")


def get_DB_info_cards(mapping, card_type, DB, EEM):
    out = []
    cards = get_all_cards(DB, EEM)
    for card in cards:
        card = get_card(card, DB, EEM)
        if card["status"] == card_type:
            card_out = {}
            for param in range(0, len(mapping)):
                if mapping[param] in card:
                    card_out[mapping[param]] = card[mapping[param]]
            out.append(card_out)
    return out


@inject
def get_all_cards(DB: MySQL, EEM: EEM):
    out = EEM.get_list()
    ids = re.findall('0x[\w]*', out)

    if ids:
        return ids

    else:
        return messenger.message404("There is not card info avilable")


@inject
def get_card(id, DB: MySQL, EEM: EEM):
    ids = get_all_cards(DB, EEM)
    if id not in ids:
        return messenger.message404(
            "The requested card ID does not exist on the server")

    out = eemParser.parse(EEM.get_box_info(id))
    if out["status"] == "eeio":
        table = __table_hardware
        mapping = hardware_card_keys
        statement = (
            "SELECT * FROM %s "
            'WHERE hardware_id = "%s"') % (
                __table_hardware_capacity,
                id)
        capacities = DB.select_query(statement)
    else:
        table = __table_net
        mapping = net_card_keys
        capacities = None
    statement = (
        "SELECT * FROM %s "
        'WHERE id = "%s"') % (table, id)
    card = DB.select_query(statement)
    if card:
        if(isinstance(card, Iterable) and not isinstance(card, str)):
            card = next(iter(card))
        for param in range(0, len(mapping)):
            out[mapping[param]] = card[param]
    else:
        for param in range(0, len(mapping)):
            if mapping[param] != "id":
                out[mapping[param]] = "UNKNOWN"
    if capacities:
        insert_capactities = []
        for capacity in capacities:
            insert_capacity = {}
            for param in range(0, len(hardware_capacity_keys)):
                if hardware_capacity_keys[param] != "hardware_id":
                    insert_capacity[hardware_capacity_keys[param]] \
                        = capacity[param]
            insert_capactities.append(insert_capacity)
        out["capacity"] = insert_capactities
    else:
        out["capacity"] = "UNKNOWN"

    return out


@inject
def get_all_hardware_cards(DB: MySQL, EEM: EEM):
    cards = get_DB_info_cards(
        hardware_card_extended_keys,
        "eeio",
        DB,
        EEM
    )
    return cards


@inject
def get_all_network_cards(DB: MySQL, EEM: EEM):
    return get_DB_info_cards(
        net_card_keys,
        "eesv",
        DB,
        EEM
    )


@inject
def create_hardware_tag(card, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    status, message = insert_card(
        card,
        __table_hardware,
        hardware_card_keys,
        DB,
        EEM)

    status, message = insert_card_capacity(
        card,
        __table_hardware_capacity,
        hardware_capacity_keys,
        DB,
        EEM)

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
        status, error = DB.rollback(message)
        return messenger.message404(error)


@inject
def create_net_tag(card, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    status, message = insert_card(
        card,
        __table_net,
        net_card_keys,
        DB,
        EEM)

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
        status, error = DB.rollback(message)
        return messenger.message404(error)


@inject
def modify_hardware_tag(card, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    status, message = modify_card(
        card,
        __table_hardware,
        hardware_card_keys,
        DB,
        EEM)

    status, message = modify_capacities(
        card,
        __table_hardware_capacity,
        hardware_capacity_keys,
        DB,
        EEM)

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
        status, error = DB.rollback(message)
        return messenger.message404(error)


@inject
def modify_net_tag(card, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    status, message = modify_card(
        card,
        __table_net,
        net_card_keys,
        DB,
        EEM)

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
        status, error = DB.rollback(message)
        return messenger.message404(error)


# TODO: Add does not exists card control
@inject
def erase_card(id, DB: MySQL, EEM: EEM):
    DB.start_transaction()

    if get_card(id, DB, EEM)["status"] == "eeio":
        DB.start_transaction()

        status, message = DB.delete_query_simple(
            __table_hardware,
            "id",
            id)

    else:
        status, message = DB.delete_query_simple(
            __table_net,
            "id",
            id)

    # First status code checks:
    # 1: Syntaxis
    # 2: Completeness
    if status:
        status, result = DB.commit_transaction()
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
