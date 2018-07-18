import os
import re
from services.mysql.mysqlDB import MySQL
from services.eem.eem import EEM
from utilities.eemParser import eemParser
from flask_injector import inject
from config.MySQL_config.MySQL_config import hardware_card_mapping as mapping
from flask import (
        make_response,
        abort
)

__table = "hardware_cards"
__table_keys = list(mapping.keys())
__eemcly = os.path.join(
        os.path.dirname(__file__),
        '..', 'eemcli', 'eemcli.py'
        )


#def surround_by_quotes(string):


@inject
def get_all_docs(DB: MySQL, EEM: EEM):
    out = EEM.get_list()
    ids = re.findall('0x[\w]*', out)

    if ids:
        return ids

    else:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "400"
        error["title"] = "Not Found"
        return error


@inject
def get_doc(id, DB: MySQL, EEM: EEM):
    ids = get_all_docs(DB, EEM)
    if id not in ids:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "400"
        error["title"] = "Not Found"
        return error

    out = eemParser.parse(EEM.get_box_info(id))
    if re.match("^0x8", id) is not None:
        statement = ("SELECT * FROM ") + __table
        statement += (" WHERE id = \"%s\"") % id
        doc = DB.exec_query(statement)
        if not doc:
            error = {}
            error["detail"] = "The requested ID doesn't have any TAG available"
            error["status"] = "400"
            error["title"] = "Not Found"
            return error
        doc = doc[0]  # There should be only one doc as answer from the query
        for param in range(0, len(__table_keys)):
            out[__table_keys[param]] = doc[param]
    return out


# TODO: Add already existing doc control
@inject
def create_doc(doc, DB: MySQL):
    values = {}
    statement = ("INSERT INTO ") + __table
    statement += "("
    for x in range(0, len(__table_keys) - 1):
        statement += __table_keys[x] + ","
        values[__table_keys[x]] = doc[__table_keys[x]]
    statement += __table_keys[len(__table_keys) - 1] + ") "
    statement += ("VALUES (")
    last_val = __table_keys[len(__table_keys) - 1]
    values[__table_keys[len(__table_keys) - 1]] = doc[last_val]
    for x in range(0, len(__table_keys) - 1):
        statement += "%(" + __table_keys[x] + ")s,"
    statement += "%(" + __table_keys[len(__table_keys) - 1] + ")s)"
    DB.exec_query(statement, values)
    #print (statement,values)
    #else:
    #    error = {}
    #    error["detail"] = "The requested ID already exists on the server"
    #    error["status"] = "304"
    #    error["title"] = "Not Found"
    #    return error


# TODO: Add does not exists doc control
@inject
def erase_doc(id, DB: MySQL):
    statement = ("DELETE FROM ") + __table
    statement += ("WHERE ID = ") + id
    DB.exec_query(statement)
    #if res:
    #    return 200
    #else:
    #    error = {}
    #    error["detail"] = "The requested ID does not exist"
    #    error["status"] = "404"
    #    error["title"] = "Not Found"
    #    return error
