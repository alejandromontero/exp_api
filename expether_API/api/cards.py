import os
import re
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from utilities.eemParser import eemParser
from flask_injector import inject
from config.MySQL_config.MySQL_config import hardware_card_mapping as mapping_hardware
from config.MySQL_config.MySQL_config import net_card_mapping as mapping_net
from utilities.messages import messenger
from collections import Iterable
from flask import (
        make_response,
        abort
)

__table_hardware = "hardware_cards"
__table_net = "net_card"
__table_keys_hardware = list(mapping_hardware.keys())
__table_keys_net = list(mapping_net.keys())


def insert_card(card, table, mapping, DB, EEM):
    #return (True, len(mapping))
    if len(card.keys()) != len(mapping):
        message = "Inserted card data is incorrect"
        return (False, message)

    cards = get_all_cards(DB, EEM)
    if card["id"] not in cards:
        message = "Card ID does not exist in EEM"
        return (False, message)

    values = []
    for x in range(0, len(mapping)):
        values.append(card[mapping[x]])

    return DB.insert_query(
        table,
        mapping,
        values)


def modify_card(card, table, mapping, DB, EEM):
    if len(card.keys()) != len(mapping):
        message = "Inserted card data is incorrect"
        return (False, message)
    out = get_card(card["id"], DB, EEM)
    if out["status"] == "404":
        message = "The card to modify has no entry in the DB"
        return (False, message)

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


def get_DB_info_cards(mapping, card_type, DB, EEM):
    out = []
    cards = get_all_cards(DB, EEM)
    for card in cards:
        card = get_card(card, DB, EEM)
        if card["status"] == card_type:
            card_out = {}
            for param in range(0, len(mapping)):
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
        mapping = __table_keys_hardware
    else:
        table = __table_net
        mapping = __table_keys_net
    statement = (
        "SELECT * FROM %s "
        'WHERE id = \"%s\"') % (table, id)
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
    return out


@inject
def get_all_hardware_cards(DB: MySQL, EEM: EEM):
    return get_DB_info_cards(
        __table_keys_hardware,
        "eeio",
        DB,
        EEM
    )


@inject
def get_all_network_cards(DB: MySQL, EEM: EEM):
    return get_DB_info_cards(
        __table_keys_net,
        "eesv",
        DB,
        EEM
    )


@inject
def create_hardware_tag(card, DB: MySQL, EEM: EEM):
    status, message = insert_card(
        card,
        __table_hardware,
        __table_keys_hardware,
        DB,
        EEM)

    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)


@inject
def create_net_tag(card, DB: MySQL, EEM: EEM):
    status, message = insert_card(
        card,
        __table_net,
        __table_keys_net,
        DB,
        EEM)

    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)


@inject
def modify_hardware_tag(card, DB: MySQL, EEM: EEM):
    status, message = modify_card(
        card,
        __table_hardware,
        __table_keys_hardware,
        DB,
        EEM)

    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)


@inject
def modify_net_tag(card, DB: MySQL, EEM: EEM):
    status, message = modify_card(
        card,
        __table_net,
        __table_keys_net,
        DB,
        EEM)

    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)


# TODO: Add does not exists card control
@inject
def erase_card(id, DB: MySQL, EEM: EEM):
    if get_card(id, DB, EEM)["status"] == "eeio":
        table = __table_hardware
    else:
        table = __table_net

    status, message = DB.delete_query_simple(
        table,
        "id",
        id
    )
    if status:
        return messenger.message200(message)
    else:
        return messenger.message404(message)
