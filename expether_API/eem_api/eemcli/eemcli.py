#!/usr/bin/env python
# -*- coding: utf-8 -*-

#       Copyright (c) 2015 NEC Corporation
#       NEC CONFIDENTIAL AND PROPRIETARY
#       All rights reserved by NEC Corporation.
#       This program must be used solely for the purpose for
#       which it was furnished by NEC Corporation. No part
#       of this program may be reproduced or disclosed to
#       others, in any form, without the prior written
#       permission of NEC Corporation. Use of copyright
#       notice does not evidence publication of the program.

"""
EEM command-line interface
"""

import os
import sys
import time
import string
import argparse
import logging
import httplib
import urllib
import json
import base64
import ConfigParser

DEFAULT_CONF_FILE='eemcli.conf'
DEFAULT_SERVER_IP='127.0.0.1'
DEFAULT_SERVER_PORT=8080
DEFAULT_TIMEOUT=30
DEFAULT_AUTH=0
DEFAULT_SSL=False
DEFAULT_PRINT_JSON=False
DEFAULT_VALIDATION=True
DEFAULT_DEBUGHTTPLIB=False
MIN_PORT=0
MAX_PORT=65535
MIN_IP=0
MAX_IP=255
MIN_GID=1
MAX_GID=4094
MIN_IO=0
MAX_IO=16
MIN_TIME=0
MAX_TIME=9223372036854775807 # java.lang.Long.MAX_VALUE
MIN_ID='0x0'
MAX_ID='0xffffffffffff'
TIME_LENGTH=23   # len('2014-11-27T13:01:59,274')
DATA_LENGTH_2=6  # len('0xDEAD')
DATA_LENGTH_3=8  # len('0xDEADBE')
DATA_LENGTH_4=10 # len('0xDEADBEEF')
MAX_HOSTINFO=32
HEX_BASE=16
EETYPE_LIST=['eeio', 'eesv']
STATE_TYPE1=['on', 'off']
STATE_TYPE2=['enabled', 'disabled']
COMPATI_LIST=['10g', '40g']
SUCCESS_CODES=[200, 201, 202, 204]
EXIT_SUCCESS=0
EXIT_FAILURE=1
TIME_FMT='%Y-%m-%dT%H:%M:%S'
LOG_FMT='%(message)s'
COMMON_HEADERS={'Accept': 'application/json'}
CONTEXT_PATH='/eem'

def _validate_ip(ip):
    ret = True
    ip_list = ip.split('.')

    if (len(ip_list) is not 4):
        ret = False
    else:
        try:
            for i in range(4):
                if (int(ip_list[i]) not in range(MIN_IP, MAX_IP + 1)):
                    ret = False
        except Exception as e:
            logging.error(e)
            ret = False

    if (ret is not True):
        logging.error('invalid ip address: ' + str(ip))
    return ret

def _validate_port(port):
    if (port in range(MIN_PORT, MAX_PORT + 1)):
        return True
    else:
        logging.error('invalid port number: ' + str(port))
        return False

def _validate_gid(gid):
    if (gid in range(MIN_GID, MAX_GID + 1)):
        return True
    else:
        logging.error('invalid group id: ' + str(gid))
        return False

def _validate_type(eetype):
    if (eetype in EETYPE_LIST):
        return True
    else:
        logging.error('invalid EE card status: ' + eetype)
        logging.error('card status must be one of ' + str(EETYPE_LIST))
        return False

def _validate_time(t):
    ret = True
    try:
        msec_since_epoch = long(t)
        if ((msec_since_epoch < MIN_TIME) or
            (msec_since_epoch > MAX_TIME + 1)):
            ret = False
    except ValueError:
        if len(t) is not TIME_LENGTH:
            ret = False
        else:
            try:
                t_list = t.split(',')
                time.strptime(t_list[0], TIME_FMT)
                if (int(t_list[1]) not in range(0, 999)):
                    ret = False
            except Exception as e:
                logging.error(e)
                ret = False

    if (ret is not True):
        logging.error('invalid time: ' + str(t))
        logging.error('time must be msec since UNIX epoch '
                      'or JST represented by 2014-12-12T08:30:00,000 format.')
    return ret

def _validate_address(address):
    ret = True
    try:
        if string.find(address.lower(), '0x') is not 0:
            ret = False
        elif (int(address, HEX_BASE) % 4 is not 0):
            ret = False
    except ValueError:
        ret = False

    if (ret is not True):
        logging.error('invalid address: ' + str(address))
        logging.error('address must start with \'0x\', and must be '
                      '4 byte-aligned hexadecimal number.')
    return ret

def _validate_length(length):
    if ((length % 4 is not 0) or (length <= 0)):
        logging.error('invalid length: ' + str(length))
        logging.error('length must be decimal and multiple of 4.')
        return False
    else:
        return True

def _validate_hexstring(size, name, data):
    if (size is 2):
        length = DATA_LENGTH_2
        max_val = '0xffff'
    elif (size is 3):
        length = DATA_LENGTH_3
        max_val = '0xffffff'
    elif (size is 4):
        length = DATA_LENGTH_4
        max_val = '0xffffffff'
    else:
        logging.error('invalid size given in _validate_data().')
        return False

    ret = True
    if (len(data) > length):
        ret = False
    elif string.find(data.lower(), '0x') is not 0:
        ret = False
    else:
        try:
            int(data, HEX_BASE)
        except ValueError:
            ret = False

    if (ret is not True):
        logging.error('invalid ' + str(name) + ': ' + data)
        logging.error(str(name) + ' must be hexadecimal, and '
                      'less than ' + max_val + '.')
    return ret

def _validate_id(eeid):
    ret = True
    if string.find(eeid.lower(), '0x') is not 0:
        ret = False
    elif len(eeid) > len(MAX_ID):
        ret = False
    else:
        try:
            int_eeid = int(eeid, HEX_BASE)
            if ((int_eeid < string.atoi(MIN_ID, HEX_BASE)) 
                or (int_eeid > string.atoi(MAX_ID, HEX_BASE))):
                ret = False
        except ValueError:
            ret = False

    if (ret is not True):
        logging.error('invalid id: ' + eeid)
        logging.error('id must start with \'0x\', and must be hexadecimal '
                      'in range of ' + str(MIN_ID) + ' - ' + str(MAX_ID) + '.')

    return ret

"""
Validate whether given "state" is correct or not.
If 'type1' is specified to "arg_type", "state" must be 'on' or 'off'.
If 'type2' is specified to "arg_type", "state" must be 'enabled' or 'disabled'.
"arg_name" is used only for error message.
"""
def _validate_state(arg_type, arg_name, state):
    ret = True
    if (arg_type is 'type1'):
        choices = STATE_TYPE1
    elif (arg_type is 'type2'):
        choices = STATE_TYPE2
    else:
        logging.error('invalid arg_type given in _validate_state().')
        return False

    if (state not in choices):
        ret = False

    if (ret is False):
        logging.error(str(arg_name) + ' must be one of ' + str(choices))
    return ret

def _validate_hostinfo(name, hostinfo):
    if (MAX_HOSTINFO < len(hostinfo)):
        logging.error(str(name) + ' must be less than 32 characters.')
        return False
    else:
        return True

def _validate_encrypt(encrypt):
    ret = True
    if (len(encrypt) not in range(MIN_IO, MAX_IO + 1)):
        ret = False
    else:
        for element in encrypt:
            if (_validate_state('type2', 'encrypt', element) is not True):
                ret = False
                break
    return ret

def _validate_compati(compati):
    for element in compati:
        if (element not in COMPATI_LIST):
            logging.error('compati must be one of ' + str(COMPATI_LIST))
            return False 
    return True

def _conv_time(t):
    try:
        msec_since_epoch = long(t)
    except ValueError:
        t_list = t.split(',')
        # convert TIME_FMT string to struct_time object
        struct_t = time.strptime(t_list[0], TIME_FMT)
        # convert struct_time in JST, to msec since epoch in UTC
        msec_since_epoch = long(time.mktime(struct_t)) * 1000 + long(t_list[1])

    return (str(msec_since_epoch).split('.'))[0]

def _body_exist(resp, body):
    if resp.status not in SUCCESS_CODES:
        logging.warn('http status : ' + str(resp.status) + ' (' + \
                     str(resp.reason) + ')')
    else:
        logging.debug('http status : ' + str(resp.status) + ' (' + \
                      str(resp.reason) + ')')
    logging.debug(str(resp.msg))

    if resp.status not in SUCCESS_CODES:
        logging.warn('code        : ' + str(body['code']))
        logging.warn('message     : ' + body['message'])
        return False
    else:
        return False if (body is None) else True

def _print_json(body):
    logging.info(str(json.dumps(body, sort_keys=True, indent=4)))

def _print_devinfo(elem):
    logging.info('id                    : ' + elem['id'])
    logging.info('status                : ' + elem['status'])
    logging.info('update_time           : ' + elem['update_time'])
    logging.info('admin_status          : ' + elem['admin_status'])
    logging.info('monitoring_status     : ' + elem['monitoring_status'])
    logging.info('notification_status0  : ' + str(elem['notification_status0']))
    logging.info('notification_status1  : ' + str(elem['notification_status1']))
    logging.info('mac_address           : ' + elem['mac_address'])
    logging.info('group_id              : ' + elem['group_id'])
    if elem['type'] != '10g':
        logging.info('vlan_tagging          : ' + elem['vlan_tagging'])
    if elem['type'] == '40g':
        logging.info('multi_mac_addresses   : ' + elem['multi_mac_addresses'])
        logging.info('encryption            : ' + str(elem['encryption']))
    logging.info('type                  : ' + elem['type'])
    logging.info('uid_switch_status     : ' + elem['uid_switch_status'])
    logging.info('power_status          : ' + elem['power_status'])
    logging.info('pcie_link_width       : ' + elem['pcie_link_width'])
    logging.info('interrupt_vector      : ' + elem['interrupt_vector'])
    logging.info('ee_version            : ' + elem['ee_version'])
    logging.info('device_id             : ' + elem['device_id'])
    logging.info('revision              : ' + elem['revision'])
    logging.info('fpga_version          : ' + elem['fpga_version'])
    logging.info('eeprom_data_version   : ' + elem['eeprom_data_version'])
    logging.info('serial_number         : ' + elem['serial_number'])
    logging.info('model                 : ' + elem['model'])
    logging.info('link_status0          : ' + elem['link_status0'])
    logging.info('link_status1          : ' + elem['link_status1'])
    if elem['status'] == 'eesv':
        logging.info('max_eeio_count        : ' + elem['max_eeio_count'])
        logging.info('eesv_type             : ' + elem['eesv_type'])
        if elem['type'] == '40g':
            logging.info('compatibility         : ' + str(elem['compatibility']))
        if elem['type'] != '40g':
            logging.info('power_off_inhibition_status: ' 
                         + elem['power_off_inhibition_status'])
        logging.info('host_serial_number    : ' + elem['host_serial_number'])
        logging.info('host_model            : ' + elem['host_model'])
        logging.info('downstream_ports      : ')
        dsp = elem['downstream_ports']
        for i in dsp:
            logging.info('  downstream_port_id      : ' + i['downstream_port_id'])
            logging.info('    eeio_connection_status: ' + i['eeio_connection_status'])
            logging.info('    eeio_mac_address      : ' + i['eeio_mac_address'])
    if elem['status'] == 'eeio':
        logging.info('path_status0          : ' + elem['path_status0'])
        logging.info('path_status1          : ' + elem['path_status1'])
        logging.info('eesv_connection_status: ' + elem['eesv_connection_status'])
        logging.info('eesv_mac_address      : ' + elem['eesv_mac_address'])
        logging.info('pcie_connection_status: ' + elem['pcie_connection_status'])
        logging.info('pcie_vendor_id        : ' + elem['pcie_vendor_id'])
        logging.info('pcie_device_id        : ' + elem['pcie_device_id'])
        logging.info('pcie_class_code       : ' + elem['pcie_class_code'])
        if elem['ee_version'] != 'v1.0':
            logging.info('resource_id           : ' + elem['resource_id'])
        if elem['type'] != '40g':
            logging.info('power_interlock_status: ' + elem['power_interlock_status'])

class EemParser(object):
    def create_parser(self):
        parser = argparse.ArgumentParser(
            epilog = 'See "eemcli.py <subcommand> --help" '
            'for help on a specific subcommand.',
            add_help = True)

        # Parser for common options
        parser.add_argument('-v', '--verbose', action='store_true',
                            dest='verbose', default=False,
                            help='print debug messages')
        parser.add_argument('-c', '--config', action='store', type=str,
                            dest='config', default=None,
                            help='specify config file path')

        cmnds = EemCommands()
        subpsr = parser.add_subparsers(metavar='<subcommand>')

        # Subcommand parser for dumpreg
        psr_dumpreg = subpsr.add_parser('dumpreg',
                                        help='dump register.')
        psr_dumpreg.add_argument('--id', '-i', type=str, required=True,
                                 help='device id of target EE card.')
        psr_dumpreg.add_argument('--address', '-a', type=str,
                                 help='start address to dump.')
        psr_dumpreg.add_argument('--length', '-l', type=int,
                                 help='length to dump.')
        psr_dumpreg.set_defaults(func=cmnds.dumpreg)

        # Subcommand parser for readreg
        psr_readreg = subpsr.add_parser('readreg',
                                        help='read register.')
        psr_readreg.add_argument('--id', '-i', type=str, required=True,
                                 help='device id of target EE card.')
        psr_readreg.add_argument('--address', '-a', type=str,
                                 required=True, help='address to read.')
        psr_readreg.set_defaults(func=cmnds.readreg)

        # Subcommand parser for writereg
        psr_writereg = subpsr.add_parser('writereg',
                                        help='write register.')
        psr_writereg.add_argument('--id', '-i', type=str, required=True,
                                 help='device id of target EE card.')
        psr_writereg.add_argument('--address', '-a', type=str,
                                 required=True, help='address to write.')
        psr_writereg.add_argument('--data', '-d', type=str, required=True,
                                 help='data to write.')
        psr_writereg.add_argument('--verify', '-V', type=str,
                                  help='verify whether updated data is correct.')
        psr_writereg.set_defaults(func=cmnds.writereg)

        # Subcommand parser for dumprom
        psr_dumprom = subpsr.add_parser('dumprom',
                                        help='dump eeprom.')
        psr_dumprom.add_argument('--id', '-i', type=str, required=True,
                                 help='device id of target EE card.')
        psr_dumprom.add_argument('--address', '-a', type=str,
                                 help='start address to dump.')
        psr_dumprom.add_argument('--length', '-l', type=int,
                                 help='length to dump.')
        psr_dumprom.set_defaults(func=cmnds.dumprom)

        # Subcommand parser for readrom
        psr_readrom = subpsr.add_parser('readrom',
                                        help='read eeprom.')
        psr_readrom.add_argument('--id', '-i', type=str, required=True,
                                 help='device id of target EE card.')
        psr_readrom.add_argument('--address', '-a', type=str,
                                 required=True, help='address to read.')
        psr_readrom.set_defaults(func=cmnds.readrom)

        # Subcommand parser for writerom
        psr_writerom = subpsr.add_parser('writerom',
                                         help='write eeprom.')
        psr_writerom.add_argument('--id', '-i', type=str, required=True,
                                  help='device id of target EE card.')
        psr_writerom.add_argument('--address', '-a', type=str,
                                  required=True, help='address to write.')
        psr_writerom.add_argument('--data', '-d', type=str, required=True,
                                  help='data to write.')
        psr_writerom.add_argument('--verify', '-V', type=str,
                                  help='verify whether updated data is correct.')
        psr_writerom.set_defaults(func=cmnds.writerom)

        # Subcommand parser for get
        psr_get = subpsr.add_parser('get', help='get information of '
                                    'EE card(s).')

        mutexgrp_get = psr_get.add_mutually_exclusive_group(required=True)
        mutexgrp_get.add_argument('--id', '-i', type=str,
                                  help='get detailed information of single EE card.')
        mutexgrp_get.add_argument('--list', '-l', action='store_true',
                                  dest='list', default=False,
                                  help='get IDs of all EE cards.')
        mutexgrp_get.add_argument('--all', '-a', action='store_true',
                                  dest='all', default=False,
                                  help='get detailed information of all EE cards.')

        psr_get.add_argument('--status', '-s', type=str,
                             help='narrow output by EE card status (eesv or eeio).')
        psr_get.add_argument('--time', '-t', type=str,
                             help='narrow output by last updated time.')
        psr_get.add_argument('--gid', '-g', type=int,
                             help='narrow output by group id.')
        psr_get.set_defaults(func=cmnds.get)

        # Subcommand parser for delete
        psr_del = subpsr.add_parser('delete', help='delete information of '
                                    'EE card.')
        psr_del.add_argument('--id', '-i', type=str, required=True,
                             help='device id of target EE card.')
        psr_del.add_argument('--force', '-f', type=str,
                                 help='delete without checking status.')
        psr_del.set_defaults(func=cmnds.delete)

        # Subcommand parser for audit
        psr_adt = subpsr.add_parser('audit', help='audit EE card info.')
        psr_adt.add_argument('--id', '-i', type=str, required=True,
                             help='device id of target EE card.')
        psr_adt.set_defaults(func=cmnds.audit)

        # Subcommand parser for init
        psr_init = subpsr.add_parser('init', help='initialize eeprom.')
        psr_init.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_init.set_defaults(func=cmnds.init)

        # Subcommand parser for replace
        psr_rplc = subpsr.add_parser('replace', help='replace EE card.')
        psr_rplc.add_argument('--id', '-i', type=str, required=True,
                              help='device id of EE card which will take over.')
        psr_rplc.add_argument('--oldid', '-o', type=str, required=True,
                              help='device id of EE card which will be removed.')
        psr_rplc.set_defaults(func=cmnds.replace)

        # Subcommand parser for perst
        psr_perst = subpsr.add_parser('perst', help='reset (PERST) EE card.')
        psr_perst.add_argument('--id', '-i', type=str, required=True,
                               help='device id of target EE card.')
        psr_perst.set_defaults(func=cmnds.perst)

        # Subcommand parser for sysrst
        psr_sysrst = subpsr.add_parser('sysrst', help='reset (SYSRST) EE card.')
        psr_sysrst.add_argument('--id', '-i', type=str, required=True,
                                help='device id of target EE card.')
        psr_sysrst.set_defaults(func=cmnds.sysrst)

        # Subcommand parser for send_reset
        psr_sendrst = subpsr.add_parser('send_rst', help='broadcast RESET frame.')
        psr_sendrst.add_argument('--id', '-i', type=str, required=True,
                                help='device id of target EE card.')
        psr_sendrst.set_defaults(func=cmnds.send_rst)

        # Subcommand parser for set_powstat
        psr_spowst = subpsr.add_parser('set_powstat',
                                       help='toggle power status.')
        psr_spowst.add_argument('--id', '-i', type=str, required=True,
                                help='device id of target EE card.')
        psr_spowst.set_defaults(func=cmnds.set_powstat)

        # Subcommand parser for get_led
        psr_gled = subpsr.add_parser('get_led',
                                     help='get UID LED status.')
        psr_gled.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_gled.set_defaults(func=cmnds.get_led)

        # Subcommand parser for set_led
        psr_sled = subpsr.add_parser('set_led',
                                     help='set UID LED status.')
        psr_sled.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_sled.add_argument('--state', '-s', type=str, required=True,
                              help='target UID LED status.')
        psr_sled.set_defaults(func=cmnds.set_led)

        # Subcommand parser for get_rotary
        psr_rot = subpsr.add_parser('get_rotary',
                                    help='get rotary switch status.')
        psr_rot.add_argument('--id', '-i', type=str, required=True,
                             help='device id of target EE card.')
        psr_rot.set_defaults(func=cmnds.get_rotary)

        # Subcommand parser for set_manage
        psr_smng = subpsr.add_parser('set_manage',
                                     help='set management status.')
        psr_smng.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_smng.add_argument('--admin', '-a', type=str, 
                              help='target administrative status.')
        psr_smng.add_argument('--monitor', '-m', type=str,
                              help='target monitoring status.')
        psr_smng.add_argument('--time', '-t', type=str,
                              help='do consistency check.')
        psr_smng.set_defaults(func=cmnds.set_manage)

        # Subcommand parser for set_gid
        psr_sgid = subpsr.add_parser('set_gid',
                                     help='set group id.')
        psr_sgid.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_sgid.add_argument('--gid', '-g', type=int,
                              help='group id to set.')
        psr_sgid.add_argument('--time', '-t', type=str,
                              help='do consistency check.')
        psr_sgid.set_defaults(func=cmnds.set_gid)

        # Subcommand parser for del_gid
        psr_dgid = subpsr.add_parser('del_gid',
                                     help='delete group id.')
        psr_dgid.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_dgid.add_argument('--time', '-t', type=str,
                              help='do consistency check.')
        psr_dgid.set_defaults(func=cmnds.del_gid)

        # Subcommand parser for set_vlantagging
        psr_svlan = subpsr.add_parser('set_vlantagging',
                                      help='set vlan tagging mode.')
        psr_svlan.add_argument('--id', '-i', type=str, required=True,
                               help='device id of target EE card.')
        psr_svlan.add_argument('--state', '-s', type=str, required=True,
                               help='target vlan tagging mode.')
        psr_svlan.add_argument('--time', '-t', type=str,
                               help='do consistency check.')
        psr_svlan.set_defaults(func=cmnds.set_vlantagging)

        # Subcommand parser for set_multimac
        psr_smac = subpsr.add_parser('set_multimac',
                                     help='set multi mac address mode.')
        psr_smac.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_smac.add_argument('--state', '-s', type=str, required=True,
                              help='target multi mac address mode.')
        psr_smac.add_argument('--time', '-t', type=str,
                              help='do consistency check')
        psr_smac.set_defaults(func=cmnds.set_multimac)

        # Subcommand parser for set_encrypt
        psr_scrypt = subpsr.add_parser('set_encrypt',
                                       help='set encryption mode.')
        psr_scrypt.add_argument('--id', '-i', type=str, required=True,
                                help='device id of target EE card.')
        psr_scrypt.add_argument('--encrypt', '-e', type=str, nargs='+',
                                required=True,
                                help='target encryption mode.')
        psr_scrypt.add_argument('--time', '-t', type=str,
                                help='do consistency check.')
        psr_scrypt.set_defaults(func=cmnds.set_encrypt)

        # Subcommand parser for set_compati
        psr_scpt = subpsr.add_parser('set_compati',
                                     help='set compatibility mode.')
        psr_scpt.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_scpt.add_argument('--compati', '-c', type=str, nargs='+',
                              required=True,
                              help='target compatibility mode.')
        psr_scpt.add_argument('--time', '-t', type=str,
                              help='do consistency check.')
        psr_scpt.set_defaults(func=cmnds.set_compati)

        # Subcommand parser for del_compati
        psr_dcpt = subpsr.add_parser('del_compati',
                                     help='delete compatibility mode.')
        psr_dcpt.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_dcpt.add_argument('--time', '-t', type=str,
                              help='do consistency check')
        psr_dcpt.set_defaults(func=cmnds.del_compati)

        # Subcommand parser for set_powinh
        psr_spinh = subpsr.add_parser('set_powinh',
                                      help='set power-off inhibition status.')
        psr_spinh.add_argument('--id', '-i', type=str, required=True,
                               help='device id of target EE card.')
        psr_spinh.add_argument('--state', '-s', type=str, required=True,
                               help='target power-off inhibition status.')
        psr_spinh.add_argument('--time', '-t', type=str,
                               help='do consistency check.')
        psr_spinh.set_defaults(func=cmnds.set_powinh)

        # Subcommand parser for set_hostinfo
        psr_hinfo = subpsr.add_parser('set_hostinfo',
                                      help='set host information.')
        psr_hinfo.add_argument('--id', '-i', type=str, required=True,
                               help='device id of target EE card.')
        psr_hinfo.add_argument('--serial', '-s', type=str, required=True,
                               help='product serial number.')
        psr_hinfo.add_argument('--model', '-m', type=str, required=True,
                               help='product model name.')
        psr_hinfo.add_argument('--time', '-t', type=str,
                               help='do consistency check.')
        psr_hinfo.set_defaults(func=cmnds.set_hostinfo)

        # Subcommand parser for set_maxio
        psr_maxio = subpsr.add_parser('set_maxio',
                                      help='set max EEIO count.')
        psr_maxio.add_argument('--id', '-i', type=str, required=True,
                               help='device id of target EE card.')
        psr_maxio.add_argument('--count', '-c', type=int, required=True,
                               help='max EEIO count.')
        psr_maxio.add_argument('--time', '-t', type=str,
                               help='do consistency check.')
        psr_maxio.set_defaults(func=cmnds.set_maxio)

        # Subcommand parser for set_pcieinfo
        psr_pcie = subpsr.add_parser('set_pcieinfo',
                                     help='set PCIe device information.')
        psr_pcie.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_pcie.add_argument('--vendor', '-v', type=str, required=True,
                              help='vendor id.')
        psr_pcie.add_argument('--device', '-d', type=str, required=True,
                              help='device id.')
        psr_pcie.add_argument('--classcode', '-c', type=str, required=True,
                              help='class code.')
        psr_pcie.add_argument('--time', '-t', type=str,
                              help='do consistency check.')
        psr_pcie.set_defaults(func=cmnds.set_pcieinfo)

        # Subcommand parser for set_powlink
        psr_splnk = subpsr.add_parser('set_powlink',
                                      help='set power interlock status.')
        psr_splnk.add_argument('--id', '-i', type=str, required=True,
                               help='device id of target EE card.')
        psr_splnk.add_argument('--state', '-s', type=str, required=True,
                               help='target power interlock status.')
        psr_splnk.add_argument('--time', '-t', type=str,
                               help='do consistency check.')
        psr_splnk.set_defaults(func=cmnds.set_powlink)

        # Subcommand parser for del_iomac
        psr_dcpt = subpsr.add_parser('del_iomac',
                                     help='delete EEIO mac address.')
        psr_dcpt.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_dcpt.add_argument('--port', '-p', type=int, required=True,
                              help='port id to unfix EEIO.')
        psr_dcpt.set_defaults(func=cmnds.del_iomac)
 
        # Subcommand parser for get_group
        psr_getgrp = subpsr.add_parser('get_groups', help='get groups.')
        psr_getgrp.set_defaults(func=cmnds.get_groups)

        # Subcommand parser for get_apiver
        psr_getaver = subpsr.add_parser('get_apiver', help='get api version.')
        psr_getaver.set_defaults(func=cmnds.get_apiver)

        # Subcommand parser for dump_stats
        psr_dump_stats = subpsr.add_parser('dump_stats',
            help='dump statistics to eem_lfi_stats.log.')
        psr_dump_stats.add_argument('-L', '--level', default=0,
            type=int, help='verbose level, 0 or more (default: 0)')
        psr_dump_stats.set_defaults(func=cmnds.dump_stats)

        # Subcommand parser for unlock_eeprom
        psr_unlock_eeprom = subpsr.add_parser('unlock_eeprom',
            help='unlock EEPROM access forcibly.')
        psr_unlock_eeprom.add_argument('--id', '-i', type=str, required=True,
                              help='device id of target EE card.')
        psr_unlock_eeprom.set_defaults(func=cmnds.unlock_eeprom)

        return parser

class EemConfig(object):
    def set_defaults(self):
        self.ip = DEFAULT_SERVER_IP
        self.port = DEFAULT_SERVER_PORT
        self.timeout = DEFAULT_TIMEOUT
        self.auth = DEFAULT_AUTH
        self.ssl = DEFAULT_SSL
        self.debughttplib = DEFAULT_DEBUGHTTPLIB
        self.validation = DEFAULT_VALIDATION
        self.print_json = DEFAULT_PRINT_JSON
        return True

    def load(self, confpath):
        logging.debug('loading config file: ' + confpath)
        config = ConfigParser.RawConfigParser()

        try:
            config.read(confpath)
        except Exception:
            logging.error('invalid config file')
            return False

        if (config.has_section('eemcli') is not True):
            logging.error('[eemcli] section not found.')
            return False

        try:
            self.ip = config.get('eemcli', 'server_ip')
            if (_validate_ip(self.ip) is not True):
                return False
        except ConfigParser.NoOptionError:
            logging.debug('server_ip is not set in config. set default.')
            self.ip = DEFAULT_SERVER_IP
        except:
            logging.error('invalid configuration (server_ip).')
            return False

        try:
            self.port = config.getint('eemcli', 'server_port')
            if (_validate_port(self.port) is not True):
                return False
        except ConfigParser.NoOptionError:
            logging.debug('server_port is not set in config. set default.')
            self.port = DEFAULT_SERVER_PORT
        except:
            logging.error('invalid configuration (server_port).')
            return False

        try:
            self.timeout = config.getint('eemcli', 'timeout')
            if (self.timeout <= 0):
                logging.error('timeout must be positive integer.')
                return False
        except ConfigParser.NoOptionError:
            logging.debug('timeout is not set in config. set default.')
            self.timeout = DEFAULT_TIMEOUT
        except:
            logging.error('invalid configuration (timeout).')
            return False

        try:
            self.auth = config.getint('eemcli', 'auth')
        except ConfigParser.NoOptionError:
            logging.debug('auth is not set in config. set default.')
            self.auth = DEFAULT_AUTH
        except:
            logging.error('invalid configuration (auth).')
            return False

        if self.auth is 0:
            pass
        elif self.auth is 1:
            try:
                self.encoded_id = config.get('eemcli', 'encoded_id')
            except:
                logging.error('invalid configuration (encoded_id).')
                return False
        elif self.auth is 2:
            try:
                self.user = config.get('eemcli', 'user')
            except:
                logging.error('invalid configuration (user).')
                return False
            try:
                self.password = config.get('eemcli', 'password')
            except:
                logging.error('invalid configuration (password).')
                return False
        else:
            logging.error('invalid configuration (auth).')
            return False

        try:
            self.ssl = config.getboolean('eemcli', 'ssl')
        except ConfigParser.NoOptionError:
            logging.debug('ssl is not set in config. set default.')
            self.ssl = DEFAULT_SSL
        except:
            logging.error('invalid configuration (ssl).')
            return False

        if self.ssl:
            try:
                self.cert = config.get('eemcli', 'cert')
                if (os.path.exists(self.cert) is not True):
                    logging.error('specified cert file not found.')
                    return False
            except:
                self.cert = None

        try:
            self.print_json = config.getboolean('eemcli', 'print_json')
        except ConfigParser.NoOptionError:
            logging.debug('print_json is not set in config. set default.')
            self.print_json = DEFAULT_PRINT_JSON
        except:
            logging.error('invalid configuration (print_json).')
            return False

        try:
            self.validation = config.getboolean('eemcli', 'validation')
        except ConfigParser.NoOptionError:
            logging.debug('validation is not set in config. set default.')
            self.validation = DEFAULT_VALIDATION
        except:
            logging.error('invalid configuration (validation).')
            return False

        try:
            self.debughttplib = config.getboolean('eemcli', 'debughttplib')
        except :
            self.debughttplib = DEFAULT_DEBUGHTTPLIB

        return True

    def print_debug(self):
        logging.debug('config: server_ip = ' + self.ip)
        logging.debug('config: server_port = ' + str(self.port))
        logging.debug('config: timeout = ' + str(self.timeout))
        logging.debug('config: auth = ' + str(self.auth))
        if self.auth is 1:
            logging.debug('config: encoded_id = ' + str(self.encoded_id))
        elif self.auth is 2:
            logging.debug('config: user = ' + str(self.user))
            logging.debug('config: password = ' + str(self.password))
        logging.debug('config: ssl = ' + str(self.ssl))
        if self.ssl:
            logging.debug('config: cert = ' + str(self.cert))
        logging.debug('config: validation = ' + str(self.validation))
        logging.debug('config: print_json = ' + str(self.print_json))

class EemCommands(object):
    def _dump(self, target, args, conf):
        if ((target is not 'registers') and (target is not 'eeproms')):
            logging.error('invalid target given in _dump().')
            return EXIT_FAILURE

        # Validate arguments
        if conf.validation:
            if (_validate_id(args.id) is not True):
                sys.exit(EXIT_FAILURE)
            if (args.address is not None):
                if (_validate_address(args.address) is not True):
                    sys.exit(EXIT_FAILURE)
            if (args.length is not None):
                if (_validate_length(args.length) is not True):
                    sys.exit(EXIT_FAILURE)

        # Create query string
        query = {}
        if (args.address is not None):
            query['start_address'] = args.address
        if (args.length is not None):
            query['length'] = args.length

        logging.debug('args: id = ' + args.id)
        logging.debug('args: address = ' + str(args.address))
        logging.debug('args: length = ' + str(args.length))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + target
        if len(query) > 0:
            path += '?' + urllib.urlencode(query)

        # Call REST API
        client = EemClient(conf)
        return client.get(path)

    def _read(self, target, args, conf):
        if ((target is not 'registers') and (target is not 'eeproms')):
            logging.error('invalid target given in _read().')
            sys.exit(EXIT_FAILURE)

        if conf.validation:
            if (_validate_id(args.id) is not True):
                sys.exit(EXIT_FAILURE)
            if (_validate_address(args.address) is not True):
                sys.exit(EXIT_FAILURE)

        logging.debug('args: id = ' + args.id)
        logging.debug('args: address = ' + str(args.address))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + target + \
               '/' + args.address
        client = EemClient(conf)
        return client.get(path)

    def _write(self, target, args, conf):
        if ((target is not 'registers') and (target is not 'eeproms')):
            logging.error('invalid target given in _write().')
            sys.exit(EXIT_FAILURE)

        if conf.validation:
            if (_validate_id(args.id) is not True):
                sys.exit(EXIT_FAILURE)
            if (_validate_hexstring(4, 'data', args.data) is not True):
                sys.exit(EXIT_FAILURE)
            if (_validate_address(args.address) is not True):
                sys.exit(EXIT_FAILURE)
            if (args.verify is not None):
                if (_validate_state('type2', 'verify', args.verify) is not True):
                    sys.exit(EXIT_FAILURE)

        logging.debug('args: id = ' + args.id)
        logging.debug('args: address = ' + str(args.address))
        logging.debug('args: data = ' + args.data)
        logging.debug('args: verify = ' + str(args.verify))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + target + \
               '/' + args.address
        if args.verify is not None:
            query = {}
            query['verify'] = args.verify
            path += '?' + urllib.urlencode(query)

        body = {'data' : args.data}
        client = EemClient(conf)
        return client.put(path, json.dumps(body))

    def dumpreg(self, args, conf):
        logging.debug('subcommand: dumpreg')
        resp, body = self._dump('registers', args, conf)

        if _body_exist(resp, body):
            if conf.print_json is True:
                _print_json(body)
            else:
                registers = body['registers']
                for elem in registers:
                    logging.info('0x%04x: 0x%08x', int(elem['address'], HEX_BASE), 
                                 int(elem['data'], HEX_BASE))

        return EXIT_SUCCESS

    def dumprom(self, args, conf):
        logging.debug('subcommand: dumprom')
        resp, body = self._dump('eeproms', args, conf)

        if _body_exist(resp, body):
            if conf.print_json is True:
                _print_json(body)
            else:
                eeproms = body['eeproms']
                for elem in eeproms:
                    logging.info('0x%03x: 0x%08x', int(elem['address'], HEX_BASE),
                                 int(elem['data'], HEX_BASE))

        return EXIT_SUCCESS

    def readreg(self, args, conf):
        logging.debug('subcommand: readreg')
        resp, body = self._read('registers', args, conf)

        if _body_exist(resp, body):
            if conf.print_json is True:
                _print_json(body)
            else:
                logging.info('0x%04x: 0x%08x', int(body['address'], HEX_BASE),
                             int(body['data'], HEX_BASE))

        return EXIT_SUCCESS

    def readrom(self, args, conf):
        logging.debug('subcommand: readrom')
        resp, body = self._read('eeproms', args, conf)

        if _body_exist(resp, body):
            if conf.print_json is True:
                _print_json(body)
            else:
                logging.info('0x%03x: 0x%08x', int(body['address'], HEX_BASE),
                             int(body['data'], HEX_BASE))

        return EXIT_SUCCESS

    def writereg(self, args, conf):
        logging.debug('subcommand: writereg')
        resp, body = self._write('registers', args, conf)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def writerom(self, args, conf):
        logging.debug('subcommand: writerom')
        resp, body = self._write('eeproms', args, conf)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def get(self, args, conf):
        logging.debug('subcommand: get')

        def _get_multiple_devices(mode, args, conf):
            if mode == 'all':
                logging.debug('mode: --all')
                path = CONTEXT_PATH + '/devices' + '/detail'
            elif mode == 'list':
                logging.debug('mode: --list')
                path = CONTEXT_PATH + '/devices'
            else:
                logging.error('invalid mode given in _get().')
                return EXIT_FAILURE

            if conf.validation:
                if (args.status is not None):
                    if (_validate_type(args.status) is not True):
                        return EXIT_FAILURE
                if (args.time is not None):
                    if (_validate_time(args.time) is not True):
                        return EXIT_FAILURE
                if (args.gid is not None):
                    if (_validate_gid(args.gid) is not True):
                        return EXIT_FAILURE

            query = {}
            if (args.status is not None):
                query['status'] = args.status
            if (args.time is not None):
                query['update_time'] = _conv_time(args.time)
            if (args.gid is not None):
                query['group_id'] = str(args.gid)

            logging.debug('args: status = ' + str(args.status))
            logging.debug('args: time = ' + str(args.time))
            logging.debug('args: gid = ' + str(args.gid))

            if len(query) > 0:
                path += '?' + urllib.urlencode(query)

            client = EemClient(conf)
            resp, body = client.get(path)

            if _body_exist(resp, body):
                if conf.print_json is True:
                    _print_json(body)
                elif mode == 'list':
                    devidlist = body['devices']
                    for elem in devidlist:
                        logging.info(elem['id'])
                    logging.info('(timestamp: ' + body['timestamp'] + ')')
                elif mode == 'all':
                    devinfolist = body['devices']
                    for elem in devinfolist:
                        _print_devinfo(elem)
                        logging.info('----------------------------------------')
                    logging.info('(timestamp: ' + body['timestamp'] + ')')

            return EXIT_SUCCESS

        def _get_single_device(args, conf):
            logging.debug('mode: --id')

            if conf.validation:
                if (_validate_id(args.id) is not True):
                    return EXIT_FAILURE

            if (args.status is not None):
                logging.warning('--status option is ignored.')
            if (args.time is not None):
                logging.warning('--time option is ignored.')
            if (args.gid is not None):
                logging.warning('--gid option is ignored.')

            logging.debug('args: id = ' + str(args.id))

            path = CONTEXT_PATH + '/devices' + '/' + args.id.lower()
            client= EemClient(conf)
            resp, body = client.get(path)

            if _body_exist(resp, body):
                if conf.print_json is True:
                    _print_json(body)
                else:
                    _print_devinfo(body['device'])
                    logging.info('(timestamp: ' + body['timestamp'] + ')')

            return EXIT_SUCCESS

        if (args.id is not None):
            return _get_single_device(args, conf)
        if (args.all is True):
            return _get_multiple_devices('all', args, conf)
        if (args.list is True):
            return _get_multiple_devices('list', args, conf)

    def delete(self, args, conf):
        logging.debug('subcommand: delete')
        
        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.force is not None):
                if (_validate_state('type2', 'force', args.force) is not True):
                    return EXIT_FAILURE
        
        # Create query string
        query = {}
        if (args.force is not None):
            query['force'] = args.force

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: force = ' + str(args.force))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower()
        if len(query) > 0:
            path += '?' + urllib.urlencode(query)

        client = EemClient(conf)
        resp, body = client.delete(path)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def audit(self, args, conf):
        logging.debug('subcommand: audit')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/audit'
        client = EemClient(conf)
        resp, body = client.put(path, None)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def init(self, args, conf):
        logging.debug('subcommand: init')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/initialize'
        client = EemClient(conf)
        resp, body = client.put(path, None)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def replace(self, args, conf):
        logging.debug('subcommand: replace')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (_validate_id(args.oldid) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: oldid = ' + str(args.oldid))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/replace'
        body = { 'old_device_id' : args.oldid }
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def perst(self, args, conf):
        logging.debug('subcommand: perst')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/perst'
        client = EemClient(conf)
        resp, body = client.put(path, None)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def sysrst(self, args, conf):
        logging.debug('subcommand: sysrst')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/sysrst'
        client = EemClient(conf)
        resp, body = client.put(path, None)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def send_rst(self, args, conf):
        logging.debug('subcommand: send_rst')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/send_reset_frame'
        client = EemClient(conf)
        resp, body = client.put(path, None)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def _set_resource(self, resource, args, conf):
        if (resource in ['uid_led_status']):
            arg_type = 'type1' # on or off
            check_time = False
        elif (resource in ['vlan_tagging', 'power_off_inhibition_status', \
                           'power_interlock_status', 'multi_mac_addresses']):
            arg_type = 'type2' # enabled or disabled
            check_time = True
        else:
            logging.error('invalid resource given in _set().')
            sys.exit(EXIT_FAILURE)

        if conf.validation:
            if (_validate_id(args.id) is not True):
                sys.exit(EXIT_FAILURE)
            if (_validate_state(arg_type, 'state', args.state) is not True):
                sys.exit(EXIT_FAILURE)
            if (check_time and (args.time is not None)):
                if (_validate_time(args.time) is not True):
                    sys.exit(EXIT_FAILURE)

        body = {}
        body[resource] = args.state
        if (check_time and (args.time is not None)):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: state = ' + str(args.state))
        if check_time:
            logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + resource
        client = EemClient(conf)
        return client.put(path, json.dumps(body))

    def set_powstat(self, args, conf):
        logging.debug('subcommand: set_powstat')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/power_status'
        client = EemClient(conf)
        resp, body = client.put(path, None)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def get_led(self, args, conf):
        logging.debug('subcommand: get_led')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/uid_led_status'
        client = EemClient(conf)
        resp, body = client.get(path)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('uid_led_status: ' + body['uid_led_status'])

        return EXIT_SUCCESS

    def set_led(self, args, conf):
        logging.debug('subcommand: set_led')
        resp, body = self._set_resource('uid_led_status', args, conf)

        _body_exist(resp, body)
        return EXIT_SUCCESS

    def get_rotary(self, args, conf):
        logging.debug('subcommand: get_rotary')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices' + '/' \
               + args.id.lower() + '/rotary_switch_status'
        client = EemClient(conf)
        resp, body = client.get(path)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('rotary_switch_status: ' + body['rotary_switch_status'])

        return EXIT_SUCCESS

    def set_manage(self, args, conf):
        logging.debug('subcommand: set_manage')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.admin is not None):
                if (_validate_state('type2', 'admin', args.admin) is not True):
                    return EXIT_FAILURE
            if (args.monitor is not None):
                if (_validate_state('type2', 'monitor', args.monitor) is not True):
                    return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        if (args.admin is not None):
            body['admin_status'] = args.admin
        if (args.monitor is not None):
            body['monitoring_status'] = args.monitor
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: admin = ' + str(args.admin))
        logging.debug('args: monitor = ' + str(args.monitor))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/management'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_gid(self, args, conf):
        logging.debug('subcommand: set_gid')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.gid is not None):
                if (_validate_gid(args.gid) is not True):
                    return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        if (args.gid is not None):
            body['group_id'] = str(args.gid)
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: gid = ' + str(args.gid))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/group_id'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('group_id   : ' + body['group_id'])
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def del_gid(self, args, conf):
        logging.debug('subcommand: del_gid')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/group_id'
        if (args.time is not None):
            query = {}
            query['update_time'] = _conv_time(args.time)
            path += '?' + urllib.urlencode(query)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: time = ' + str(args.time))

        client = EemClient(conf)
        resp, body = client.delete(path)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_vlantagging(self, args, conf):
        logging.debug('subcommand: set_vlantagging')
        resp, body = self._set_resource('vlan_tagging', args, conf)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_multimac(self, args, conf):
        logging.debug('subcommand: set_multimac')
        resp, body = self._set_resource('multi_mac_addresses', args, conf)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_encrypt(self, args, conf):
        logging.debug('subcommand: set_encrypt')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (_validate_encrypt(args.encrypt) is not True):
                return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        body['encryption'] = args.encrypt
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: encrypt = ' + str(args.encrypt))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/encryption'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_compati(self, args, conf):
        logging.debug('subcommand: set_compati')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (_validate_compati(args.compati) is not True):
                return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        body['compatibility'] = args.compati
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: compati = ' + str(args.compati))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + \
               '/' + 'compatibility'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def del_compati(self, args, conf):
        logging.debug('subcommand: del_compati')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + \
               '/' + 'compatibility'

        if args.time is not None:
            query = {}
            query['update_time'] = args.time
            path += '?' + urllib.urlencode(query)

        client = EemClient(conf)
        resp, body = client.delete(path)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_powinh(self, args, conf):
        logging.debug('subcommand: set_powinh')
        resp, body = self._set_resource('power_off_inhibition_status', args, conf)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_hostinfo(self, args, conf):
        logging.debug('subcommand: set_hostinfo')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.serial is not None):
                if (_validate_hostinfo('serial', args.serial) is not True):
                    return EXIT_FAILURE
            if (args.model is not None):
                if (_validate_hostinfo('model', args.model) is not True):
                    return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        if (args.serial is not None):
            body['host_serial_number'] = args.serial
        if (args.model is not None):
            body['host_model'] = args.model
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: serial = ' + str(args.serial))
        logging.debug('args: model = ' + str(args.model))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + 'host'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_maxio(self, args, conf):
        logging.debug('subcommand: set_maxio')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.count not in range(MIN_IO, MAX_IO + 1)):
                logging.error('count must be in range of 0 - 16.')
                return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        body['max_eeio_count'] = str(args.count)
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: count = ' + str(args.count))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + \
               'max_eeio_count'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_pcieinfo(self, args, conf):
        logging.debug('subcommand: set_pcieinfo')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.vendor is not None):
                if (_validate_hexstring(2, 'vendor', args.vendor) is not True):
                    return EXIT_FAILURE
            if (args.device is not None):
                if (_validate_hexstring(2, 'device', args.device) is not True):
                    return EXIT_FAILURE
            if (args.classcode is not None):
                if (_validate_hexstring(3, 'classcode', args.classcode) is not True):
                    return EXIT_FAILURE
            if (args.time is not None):
                if (_validate_time(args.time) is not True):
                    return EXIT_FAILURE

        body = {}
        if (args.vendor is not None):
            body['pcie_vendor_id'] = args.vendor
        if (args.device is not None):
            body['pcie_device_id'] = args.device
        if (args.classcode is not None):
            body['pcie_class_code'] = args.classcode
        if (args.time is not None):
            body['update_time'] = _conv_time(args.time)

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: vendor = ' + str(args.vendor))
        logging.debug('args: device = ' + str(args.device))
        logging.debug('args: classcode = ' + str(args.classcode))
        logging.debug('args: time = ' + str(args.time))

        path = CONTEXT_PATH + '/devices' + '/' + args.id.lower() + '/' + 'pcie_device'
        client = EemClient(conf)
        resp, body = client.put(path, json.dumps(body))

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def set_powlink(self, args, conf):
        logging.debug('subcommand: set_powlink')
        resp, body = self._set_resource('power_interlock_status', args, conf)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('update_time: ' + body['update_time'])

        return EXIT_SUCCESS

    def del_iomac(self, args, conf):
        logging.debug('subcommand: del_iomac')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE
            if (args.port not in range(MIN_IO, MAX_IO)):
                logging.error('port id must be in range of 0 - 15.')
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))
        logging.debug('args: port = ' + str(args.port))

        path = CONTEXT_PATH + '/devices/' + args.id.lower() + \
               '/ports/' + str(args.port) + '/eeio_mac_address'

        client = EemClient(conf)
        resp, body = client.delete(path)

        _body_exist(resp, body)

        return EXIT_SUCCESS

    def get_groups(self, args, conf):
        logging.debug('subcommand: get_groups')

        path = CONTEXT_PATH + '/groups'
        client = EemClient(conf)
        resp, body = client.get(path)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                group_list = body['groups']
                for elm in group_list:
                    logging.info(elm['id'])

        return EXIT_SUCCESS

    def get_apiver(self, args, conf):
        logging.debug('subcommand: get_apiver')

        path = CONTEXT_PATH + '/api_version'
        client = EemClient(conf)
        resp, body = client.get(path)

        if _body_exist(resp, body):
            if conf.print_json:
                _print_json(body)
            else:
                logging.info('version_number: ' + body['version_number'])

        return EXIT_SUCCESS

    def dump_stats(self, args, conf):
        logging.debug('subcommand: dump_stats')

        path = CONTEXT_PATH + '/dump_statistics'

        if args.level is not None:
            query = {}
            query['verbose'] = args.level
            path += '?' + urllib.urlencode(query)

        client = EemClient(conf)
        resp, body = client.put(path, None)

        _body_exist(resp, body)

        return EXIT_SUCCESS

    def unlock_eeprom(self, args, conf):
        logging.debug('subcommand: unlock_eeprom')

        if conf.validation:
            if (_validate_id(args.id) is not True):
                return EXIT_FAILURE

        logging.debug('args: id = ' + str(args.id))

        path = CONTEXT_PATH + '/devices/' + args.id.lower() + \
               '/registers/0x5204'

        query = {}
        query['verify'] = 'disabled'
        path += '?' + urllib.urlencode(query)

        body = {'data' : '0x0000ffff'}

        client = EemClient(conf)

        resp, body = client.put(path, json.dumps(body))

        _body_exist(resp, body)

        return EXIT_SUCCESS

class EemClient(object):
    def __init__(self, conf):
        self.host = conf.ip + ':' + str(conf.port)
        self.ssl = conf.ssl
        self.headers = COMMON_HEADERS
        self.headers['Host'] = conf.ip + ':' + str(conf.port)
        self.timeout = conf.timeout
        if conf.auth is 1:
            self.headers['Authorization'] = 'Basic ' + conf.encoded_id
        elif conf.auth is 2:
            self.headers['Authorization'] = 'Basic ' + \
                                            base64.b64encode(conf.user + ':' + \
                                                             conf.password)
        self.cert = conf.cert if conf.ssl else None
        self.debughttplib = conf.debughttplib

    def _logging_request(self, method, path, param):
        logging.debug('request: ' + method + ' ' + path)
        logging.debug('request header: ' + str(self.headers))
        if (param is not None):
            logging.debug('request body: ' + str(param))
        curl_command = 'curl -v -X ' + method
        for k, v in self.headers.items():
            curl_command += ' -H \'' + str(k) + ': ' + str(v) + '\''
        curl_command += ' --data \'' + str(param) + '\'' if (param is not None) else ''
        curl_command += ' https://' if self.ssl else ' http://' 
        curl_command += self.host + path
        logging.debug('equivalent curl command: ' + '\n' + curl_command)

    def get(self, path):
        return self.do_request('GET', path)

    def put(self, path, param):
        self.headers['Content-Type'] = 'application/json'
        self.headers['Content-Length'] = 0 if (param is None) else len(param)
        return self.do_request('PUT', path, param)

    def delete(self, path):
        return self.do_request('DELETE', path)

    def do_request(self, method, path, param=None):
        if self.ssl:
            conn = httplib.HTTPSConnection(self.host,
                                           cert_file=self.cert,
                                           timeout=self.timeout)
        else:
            conn = httplib.HTTPConnection(self.host,
                                          timeout=self.timeout)

        if self.debughttplib:
            conn.set_debuglevel(10)

        self._logging_request(method, path, param)

        try:
            conn.request(method, path, param, self.headers)
            resp = conn.getresponse()
        except Exception as e:
            logging.error(e)
            conn.close()
            sys.exit(EXIT_FAILURE)

        msg_dict = dict(resp.msg)
        if msg_dict.has_key('Content-Length'):
            body_length = int(msg_dict['Content-Length'])
        else: 
            body_length = None

        # In case 'content-length' is not set, we can not judge 
        # whether response body exists or not. So, try to read it.
        if ((body_length is None) or (body_length > 0)):
            try:
                body =  json.load(resp)
            except Exception as e:
                body = None
        else:
            body = None

        conn.close()
        return resp, body

def main(argv):
    # Parse common options
    parser = EemParser().create_parser()
    (options, args) = parser.parse_known_args(argv)

    # Setup logging
    loglevel = logging.DEBUG if options.verbose else logging.INFO
    logging.basicConfig(level=loglevel, format=LOG_FMT, stream=sys.stdout)

    # Load config
    conf = EemConfig()
    if (options.config is None):
        conf_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 DEFAULT_CONF_FILE))
        if (os.path.exists(conf_path) is not True):
            logging.warning('config file not found. applying default values.')
            ret = conf.set_defaults()
        else:
            ret = conf.load(conf_path)
    else:
        if (os.path.exists(options.config) is not True):
            logging.error('specified path not found.')
            return EXIT_FAILURE
        else:
            ret = conf.load(options.config)

    if (ret is not True):
        logging.error('failed to load config file.')
        return EXIT_FAILURE

    if options.verbose:
        conf.print_debug()

    # Parse arguments for subcommand.
    subcmnd_args = parser.parse_args()

    # Execute subcommand.
    return subcmnd_args.func(subcmnd_args, conf)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
