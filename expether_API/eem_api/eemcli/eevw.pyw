#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# Copyright (c) 2017 NEC Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
ExpEther(40G) Control Program
'''

from __future__ import (division,
                        absolute_import,
                        print_function,
                        unicode_literals, )
from future_builtins import *

import sys
import os
import stat
import threading
import Queue

import errno
import locale
import re

import argparse
import logging
import logging.handlers

import Tkinter as tk
import ttk
import tkMessageBox

import httplib
import urllib
import socket
import json
import base64


# constants

THREADING = True

default_config = {
    'server_ip':    '127.0.0.1',
    'server_port':  30500,
    'timeout':      30,
    'auth':         0,
    'ssl':          False,
}

commandline_options = {
    # option_str: (default, ArgumentParser.add_argument()'s args)
    'configfile': (None,  {}),
    'logfile':    (None,  {}),
    'loglevel':   (None,  {}),
    'logconsole': (False, {}, ),

    'logwin':     (False, {'help': argparse.SUPPRESS}, ),
    'debug':      (False, {'help': argparse.SUPPRESS}, ),
    'debug2':     (False, {'help': argparse.SUPPRESS}, ),

    # 'disable-initial-audit': (False, {'help': argparse.SUPPRESS}, ),
    # 'theme':      (None,  {'help': argparse.SUPPRESS}, ),
}

GID = {
    'MIN': 16,
    'MAX': 4092,
    'eeio_default': 4093,
    'eesv_default': 4094,
}


CONFIG = {
    'FORMAT': '%(base)s%(ext)s',
    'BASEs': ['eemcli', ],
    'EXTs': ['.conf', ],
}


LOG_FORMAT = {
    'CONS':   '%(levelname)-8s  %(message)s',
    'TEXT':   '%(levelname)-8s  %(message)s',
    'FILE':   '%(asctime)s  %(levelname)-8s %(message)s',
    'DIALOG': '%(message)s',
    'DATE':   '%Y-%m-%d %H:%M:%S',
}

UID_LED_On = 'UID LED On'
UID_LED_Off = 'UID LED Off'


#

class EE_Manager(object):
    '''
    ExpEther Manager interface class
    '''

    _daemon = None              # EE_Manager instance for daemon
    _thread = None              # daemon thread

    _req_q = None
    _rlock = None
    _f_term = None              # terminate thread flag (event)

    _notify_fn = None

    _device_list = {}
    _group_devs = {}
    _api_ver = 'unknown'

    def __init__(self, conf=None, notify_fn=None,
                 rlock=None, req_q=None, f_term=None):
        if conf is not None:
            EEM_REST.set_default(conf)

        self._notify_fn = notify_fn

        if rlock or req_q or f_term:  # for daemon thread
            assert notify_fn and rlock and req_q and f_term
            self._rlock = rlock
            self._req_q = req_q
            self._f_term = f_term

    #

    def _simple_command(self, api_name, **kwds):
        return self._request(api_name, **kwds)

    def _audit(self, eeid, update_device=True):
        rv, resp = self._request('Audit Device', ignore=('admin', ),
                                 eeid=eeid)

        if rv and update_device:
            return self._update_device(ignore=('admin', ), eeid=eeid)
        else:
            return rv, resp

    def _delete(self, eeid, force=False):
        if force:
            force = 'enabled'
        else:
            force = None

        return self._request('Delete Device',
                             ignore=('admin', 'monitor', 'notif', ),
                             eeid=eeid, force=force)

    def _get_led(self, eeid):
        rv, resp = self._request('Show UID LED Status', eeid=eeid)

        if rv:
            rv = self._device_list[eeid].uidled = resp.body['uid_led_status']
            return rv, resp

        else:
            return None, resp

    #

    def _get_led_cached(self, eeid):
        try:
            uidled = self._device_list[eeid].uidled
            if uidled is not None:
                return uidled, None
            else:
                return self._get_led(eeid=eeid)
        except KeyError:
            return None, None

    def _toggle_led(self, eeid):
        status, resp = self._get_led_cached(eeid)
        if status is None:
            return status, resp

        if status == 'on':
            status = 'off'
        else:
            status = 'on'

        success, resp = self._request('Update UID LED Status',
                                      eeid=eeid, uid_led_status=status)

        if not success:
            return success, resp

        return self._get_led(eeid)

    def _update_device(self, eeid, ignore=()):
        success, resp = self._request('Show Device', ignore=ignore,
                                      eeid=eeid)

        if success:
            self._device_list[eeid].refresh(resp.body['device'])
            self._refresh_group_devs()

        return success, resp

    #

    def _list_devices(self, **kwds):
        success, resp = self._request('List Devices Details')

        if success:
            self._device_list.clear()

            for data in resp.body['devices']:
                eeid = data['id']
                self._device_list[eeid] = EE_Device(data, self)

            self._refresh_group_devs()

        return success, resp

    def _get_apiver(self):
        rv, resp = self._request('Show API Version')

        if rv:
            rv = self._api_ver = resp.body['version_number']
            return rv, resp

        else:
            return None, resp

    def _audit_all(self):
        for eeid in self._device_list.keys():
            success, resp = self._audit(eeid=eeid, update_device=False)

            # ignore error here
            if not success:
                try:
                    logging.info('Initial audit %s: %s', eeid, resp.exc_str)
                except AttributeError:
                    pass

        return self._list_devices()

    _eem_command_set = {
        'del_gid':        ('Delete Group ID',         _list_devices, ),
        'del_iomac':      ('Delete EEIO MAC Address', _list_devices, ),
        'perst':          ('Reset Device (PERST)',    _update_device, ),
        'send_rst':       ('Send RESET Frame',        _update_device, ),
        'set_gid':        ('Update Group ID',         _list_devices, ),
        'set_led':        ('Update UID LED Status', ),
        'dump_stats':     ('Dump Statistics', ),

        'audit':          (_audit, ),
        'delete':         (_delete,         _list_devices, ),
        'get_led':        (_get_led, ),
        'get_led_cached': (_get_led_cached, ),
        'toggle_led':     (_toggle_led, ),

        'get_apiver':     (_get_apiver, ),

        'update_device':  (_update_device, ),  # not used
        'list_devices':   (_list_devices, ),

        '_eem_io_start':  (_get_apiver,     _list_devices, ),
        '_audit_all':     (_audit_all, ),
    }

    def _refresh_group_devs(self):
        group_devs = self._group_devs
        group_devs.clear()

        for id, ee_dev in self._device_list.items():
            group = ee_dev.group
            if group not in group_devs:
                group_devs[group] = {'eesv': [], 'eeio': []}

            group_devs[group][ee_dev.status].append(ee_dev.eeid)

    #

    def _request(self, api_name, ignore=(), **kwds):
        '''perform SINGLE EEM REST request'''

        if not self._request_ok(ignore=ignore, **kwds):
            return None, None

        rest_io = EEM_REST().request(api_name, **kwds)

        if rest_io.exc_type is not None:
            rest_io.success = False

        return rest_io.success, rest_io

    def _request_ok(self, ignore=(), **kwds):
        '''confirm target eeid can perform request'''

        if self._f_term is not None and self._f_term.is_set():
            return False

        if 'eeid' not in kwds:
            return True

        try:
            dev_sts = self._device_list[kwds['eeid']].dev_sts
        except KeyError as ex:
            return False

        for test_sts in ('admin', 'monitor', 'notif', ):
            if test_sts not in ignore and not dev_sts.get(test_sts, False):
                return False

        return True

    #

    def _request_sync(self, cmd, _Sync=True, **kwds):
        '''
        perform EEM command in logical command-set basis
        synchronous-mode; will block until receive response
        '''

        assert _Sync

        rv, resp = True, None

        for part in self._eem_command_set[cmd]:

            if isinstance(part, (str, unicode)):
                rv, resp = self._simple_command(part, **kwds)

            else:
                rv, resp = part(self, **kwds)

            if not rv:
                break

        if self._notify_fn is not None:
            self._notify_fn(cmd, rv, resp)

        return rv, resp

    request = _request_sync     # default is sync (non-threading) mode

    def _request_threading(self, cmd, _Sync=False, **kwds):
        '''
        perform EEM command in logical command-set basis
        threading-mode; send command to I/O daemon via request-queue
                        result is notified via callback
        '''

        # some command should be executed in sync-mode
        if not _Sync:
            try:
                _Sync = self._request_override_sync[cmd](self, **kwds)
            except KeyError:
                pass            # _Sync == False

        if _Sync:
            return self._request_sync(cmd, _Sync=True, **kwds)

        self._req_q.put_nowait((1, cmd, kwds))

    def _request_override_sync__get_led_cached(self, **kwds):
        try:
            # XXX
            # assume eem.device_list is shallow copy of (or identical to)
            # eem._daemon.device_list

            rv = (self._device_list[kwds['eeid']].uidled is not None)
        except KeyError:
            rv = False

        return rv

    _request_override_sync = {
        'get_led_cached': _request_override_sync__get_led_cached,
    }

    def _eem_daemon(self):
        '''EEM REST I/O daemon'''

        while True:
            if self._f_term.is_set():
                break

            pri, cmd, kwds = self._req_q.get()

            if cmd is None:     # terminate
                break

            with self._rlock:
                rv, resp = self._request_sync(cmd, _Sync=True, **kwds)

            self._req_q.task_done()

    def terminate(self):
        if self._thread is not None:
            self._f_term.set()
            self._req_q.put_nowait((0, None, None))  # terminate
            self._thread.join()  # set timeout ?
            self._thread = None

    def threading_enabler(self, handler):

        assert self._notify_fn

        rlock = self._rlock = threading.RLock()
        req_q = self._req_q = Queue.PriorityQueue()
        f_term = self._f_term = threading.Event()

        self._daemon = EE_Manager(notify_fn=handler,
                                  rlock=rlock, req_q=req_q, f_term=f_term)
        self._thread = threading.Thread(target=self._daemon._eem_daemon)
        # self._thread.daemon = True
        self._thread.start()

        self.request = self._request_threading

        return self._notify_fn

    #

    @property
    def api_ver(self):
        if self._thread:
            with self._rlock:
                self._api_ver = self._daemon._api_ver

        return self._api_ver

    @property
    def device_list(self):
        if self._thread:
            with self._rlock:
                self._device_list = self._daemon._device_list.copy()

        return self._device_list

    @property
    def group_devs(self):
        if self._thread:
            with self._rlock:
                self._group_devs = self._daemon._group_devs.copy()

        return self._group_devs


class EE_Device_Exception(Exception):
    '''something wrong in EE Device information'''


class EE_Device(object):
    '''ExpEther(40G) device information'''

    def __init__(self, data, eem):
        self.eeid = data['id']
        self.disp_id = self.eeid[2:]
        self.dev_sts = {}

        self.refresh(data)

    def refresh(self, data):
        if self.eeid != data['id']:
            raise EE_Device_Exception('unexpected eeid %s / %s'
                                      % (self.eeid, data['id']))

        self.data = data

        self.dev_sts['group'] = int(data['group_id'])
        self.dev_sts['status'] = data['status']  # eesv or eeio
        self.dev_sts['uidled'] = None
        self.dev_sts['admin'] = (data['admin_status'] == 'enabled')
        self.dev_sts['monitor'] = (data['monitoring_status'] == 'enabled')
        self.dev_sts['notif'] = (u'up' in data['notification_status0'] or
                                 u'up' in data['notification_status1'])

        if data['status'] not in ('eesv', 'eeio', ):
            raise EE_Device_Exception('unexpected ee status %(id)s: %(status)s'
                                      % data)

    def __repr__(self):
        return '%s %s' % (self.status, self.disp_id)

    @property
    def group(self):
        return self.dev_sts['group']

    @property
    def status(self):
        return self.dev_sts['status']

    @property
    def admin(self):
        return self.dev_sts['admin']

    @property
    def monitor(self):
        return self.dev_sts['monitor']

    @property
    def notif(self):
        return self.dev_sts['notif']

    @property
    def uidled(self):
        return self.dev_sts['uidled']

    @uidled.setter
    def uidled(self, status):
        self.dev_sts['uidled'] = status


# EEM REST I/O

class _EEM_REST_Exception(Exception):
    '''something wrong is happened while executing EEM Rest I/O'''

    def __init__(self, args, http_code=None):
        Exception.__init__(self, args)
        self.http_code = http_code


class EEM_REST(object):
    '''EEM REST interface client'''

    _COMMON_HEADERS = {'Accept': 'application/json', }
    _SUCCESS_CODES = (200, 204, )  # 201, 202 ?
    headers = _COMMON_HEADERS

    _re_uri_var = re.compile(r'/%\((\w+)\)s')

    def __init__(self, conf=None):
        if conf is not None:
            self._set_conf(self, conf)

        self.headers = self.headers.copy()

    def request(self, api_name, **kwds):
        '''perform EEM REST I/O'''

        self.success = False
        self.api_name = api_name

        self._build_request(api_name, **kwds)
        self._log_request()

        try:
            conn = self.connect()

            conn.request(self.method, self.uri, self.body, self.headers)
            resp = conn.getresponse()

            status = resp.status
            reason = resp.reason
            headers = dict(resp.getheaders())
            raw_data = resp.read()

            self._log_response_head(resp)

            if status not in self._SUCCESS_CODES:
                try:
                    logging.info('response body: %s', raw_data)
                    json_body = json.loads(raw_data)
                    exc_msg = '\ncode: %(code)s  %(message)s' % json_body
                    http_code = json_body['code']

                except (ValueError, KeyError):
                    http_code = None
                    exc_msg = ''

                raise _EEM_REST_Exception('HTTP status: %s (%s)%s' %
                                          (status, reason, exc_msg),
                                          http_code=http_code)

            try:
                body_length = int(headers['content-length'])

            except ValueError as ex:
                raise _EEM_REST_Exception('content-length: %s'
                                          % headers['content-length'])

            except (KeyError, TypeError) as ex:
                body_length = None

            try:
                if raw_data is not None and \
                   (body_length is None or body_length > 0):
                    json_body = json.loads(raw_data)

            except ValueError as ex:
                if body_length is None:
                    json_body = None
                else:
                    raise _EEM_REST_Exception(str(ex))

            self._log_response_body(json_body)

            if status != 204 and json_body is None:
                raise _EEM_REST_Exception('HTTP status: %s (%s) - body empty'
                                          % (status, reason))

            elif status == 204 and json_body is not None:
                # this condition will never become true
                # httplib close connection when status is 204
                raise _EEM_REST_Exception('HTTP status: %s (%s) - got data'
                                          % (status, reason))

            exp = self.eem_api.get('expect', ())

            if json_body is None:
                if exp:
                    raise _EEM_REST_Exception('response empty')

            else:
                for item in exp:
                    if item not in json_body:
                        raise _EEM_REST_Exception('missing item: %s' % item)

        except socket.error as ex:
            self.exc_type = 'socket.error'
            self.exc_str = 'Cannot communicate with EEM\n' \
                           + _os_decode(ex.strerror or str(ex))
            self.errno = ex.errno

        except httplib.HTTPException as ex:
            self.exc_type = 'HTTPException'
            self.exc_str = 'Cannot communicate with EEM\n' \
                           + type(ex).__name__

            try:
                self.args = ex.args
            except AttributeError:
                pass

        except _EEM_REST_Exception as ex:
            self.exc_type = 'EEM_REST_Exception'
            self.exc_str = 'Unexpected EEM response\n' + str(ex)
            self.http_code = ex.http_code

        else:
            self.success = True
            self.status = status
            self.reason = reason
            self.headers = headers
            self.data = raw_data
            self.body = json_body
            self.exc_type = None

        finally:
            conn.close()

        return self

    def _build_request(self, api_name, **kwds):
        '''Build EEM REST request'''

        try:
            eem_api = self.eem_api = self.EEM_API[api_name]
            method = self.method = eem_api['method']
        except KeyError as ex:
            if api_name == ex.args[0]:
                raise KeyError('Internal: Unknown API: %s' % ex.args[0])
            else:
                raise KeyError('Internal: API Table ?: %s (%s)'
                               % (ex.args[0], api_name))

        try:
            for uri_var in self._re_uri_var.finditer(eem_api['uri']):
                item = uri_var.group(1)
                if kwds[item] is None:
                    raise ValueError(item)  # None -> ValueError

            uri = '/eem' + eem_api['uri'] % (kwds)

            queries = {}
            for item in eem_api.get('query', ()):
                if item in kwds and kwds[item] is not None:
                    queries[item] = kwds[item]

            if len(queries) > 0:
                uri = uri + '?' + urllib.urlencode(queries)

            self.uri = uri

            body = None
            if method == 'PUT':
                self.headers['Content-Type'] = 'application/json'

                body_json = {}

                for item in eem_api.get('request', ()):
                    body_json[item] = kwds[item]

                for item in eem_api.get('option', ()):
                    val = kwds.get(item)
                    if val is not None:
                        body_json[item] = val

                if len(body_json) > 0:
                    body = json.dumps(body_json)

            self.body = body

        except KeyError as ex:
            raise KeyError('Internal: missing REST argument: %s (%s)'
                           % (ex.args[0], api_name))

        except ValueError as ex:
            raise ValueError('Internal: REST argument is None: %s (%s)'
                             % (ex.args[0], api_name))

    def _log_request(self):
        logging.info('request: %s %s %s', self.method, self._host, self.uri)
        logging.debug('headers: %s', str(self.headers))
        if (self.body is not None):
            logging.debug('request body: %s', str(self.body))

    def _log_response_head(self, resp):
        logging.info('http status: %s (%s)', resp.status, resp.reason)
        logging.debug('response headers:\n%s', str(resp.msg).rstrip())

    def _log_response_body(self, body):
        logging.debug2('json body:\n%s',
                       str(json.dumps(body, sort_keys=True, indent=4)))

    EEM_API = {
        # 'List Devices': {       # not tested
        #     'method': 'GET',
        #     'uri': '/devices',
        #     'query': ('status', 'group_id', 'update_time', ),
        #     'expect': ('devices', 'timestamp', ),
        # },
        'List Devices Details': {
            'method': 'GET',
            'uri': '/devices/detail',
            'query': ('status', 'group_id', 'update_time', ),  # not tested
            'expect': ('devices', 'timestamp', ),
        },
        'Show Device': {
            'method': 'GET',
            'uri': '/devices/%(eeid)s',
            'expect': ('device', 'timestamp', ),
        },
        'Delete Device': {
            'method': 'DELETE',
            'uri': '/devices/%(eeid)s',
            'query': ('force', ),
        },
        'Audit Device': {
            'method': 'PUT',
            'uri': '/devices/%(eeid)s/audit',
            'expect': ('update_time', ),
        },
        'Reset Device (PERST)': {
            'method': 'PUT',
            'uri': '/devices/%(eeid)s/perst',
        },
        'Send RESET Frame': {
            'method': 'PUT',
            'uri': '/devices/%(eeid)s/send_reset_frame',
        },
        'Show UID LED Status': {
            'method': 'GET',
            'uri': '/devices/%(eeid)s/uid_led_status',
            'expect': ('uid_led_status', ),
        },
        'Update UID LED Status': {
            'method': 'PUT',
            'uri': '/devices/%(eeid)s/uid_led_status',
            'request': ('uid_led_status', ),
        },
        'Update Group ID': {
            'method': 'PUT',
            'uri': '/devices/%(eeid)s/group_id',
            'option': ('group_id', 'update_time', ),
            'expect': ('group_id', 'update_time', ),
        },
        'Delete Group ID': {
            'method': 'DELETE',
            'uri': '/devices/%(eeid)s/group_id',
            'query': ('update_time', ),
            'expect': ('update_time', ),
        },
        'Delete EEIO MAC Address': {
            'method': 'DELETE',
            'uri': '/devices/%(eeid)s/ports/%(port)s/eeio_mac_address',
        },
        # 'List Groups': {        # not tested
        #     'method': 'GET',
        #     'uri': '/groups',
        #     'expect': ('groups', ),
        # },
        'Show API Version': {
            'method': 'GET',
            'uri': '/api_version',
            'expect': ('version_number', ),
        },
        # 'Dump Statistics': {    # not tested
        #     'method': 'PUT',
        #     'uri': '/dump_statistics',
        #     'query': ('verbose', ),
        # },
    }

    @classmethod
    def set_default(cls, conf):
        cls._set_conf(cls, conf, class_default=True)

    @staticmethod
    def _set_conf(this, conf, class_default=False):
        conf['_host'] = '%s:%s' % (conf['server_ip'], conf['server_port'])
        this._host = conf['_host']

        if conf['auth'] == 1:
            this.headers['Authorization'] = 'Basic ' + conf['encoded_id']
        elif conf['auth'] == 2:
            userpass = conf['user'] + ':' + conf['password']
            this.headers['Authorization'] = 'Basic ' + \
                                            base64.b64encode(userpass)

        logging.info('Host: %s', this._host)

        if conf['ssl']:
            _host = conf['_host']
            _cert = conf['cert']
            _timeout = conf['timeout']

            def __connect():
                return httplib.HTTPSConnection(_host,
                                               cert_file=_cert,
                                               timeout=_timeout)

        else:
            _host = conf['_host']
            _timeout = conf['timeout']

            def __connect():
                return httplib.HTTPConnection(_host, timeout=_timeout)

        if class_default:
            this.connect = staticmethod(__connect)
        else:
            this.connect = __connect


# function

# PCI Class code


def pci_class_code(code):
    '''get PCI Class Code meaning'''

    try:
        n = int(code, 16)
    except TypeError:
        n = code

    code = '0x%06x' % n

    class_code_str = {
        '0x01':      'Mass storage controller',
        '0x0100':    'SCSI storage controller',
        '0x0101':    'IDE interface',
        '0x0102':    'Floppy disk controller',
        '0x0103':    'IPI bus controller',
        '0x0104':    'RAID bus controller',
        '0x0105':    'ATA controller',
        '0x010520':  'ADMA single stepping',
        '0x010530':  'ADMA continuous operation',
        '0x0106':    'SATA controller',
        '0x010600':  'Vendor specific',
        '0x010601':  'AHCI 1.0',
        '0x010602':  'Serial Storage Bus',
        '0x0107':    'Serial Attached SCSI controller',
        '0x010701':  'Serial Storage Bus',
        '0x0108':    'Non-Volatile memory controller',
        '0x010801':  'NVMHCI',
        '0x010802':  'NVM Express',
        '0x0180':    'Mass storage controller',
        '0x02':      'Network controller',
        '0x0200':    'Ethernet controller',
        '0x0201':    'Token ring network controller',
        '0x0202':    'FDDI network controller',
        '0x0203':    'ATM network controller',
        '0x0204':    'ISDN controller',
        '0x0205':    'WorldFip controller',
        '0x0206':    'PICMG controller',
        '0x0207':    'Infiniband controller',
        '0x0208':    'Fabric controller',
        '0x0280':    'Network controller',
        '0x03':      'Display controller',
        '0x0300':    'VGA compatible controller',
        '0x030000':  'VGA controller',
        '0x030001':  '8514 controller',
        '0x0301':    'XGA compatible controller',
        '0x0302':    '3D controller',
        '0x0380':    'Display controller',
        '0x04':      'Multimedia controller',
        '0x0400':    'Multimedia video controller',
        '0x0401':    'Multimedia audio controller',
        '0x0402':    'Computer telephony device',
        '0x0403':    'Audio device',
        '0x0480':    'Multimedia controller',
        '0x05':      'Memory controller',
        '0x0500':    'RAM memory',
        '0x0501':    'FLASH memory',
        '0x0580':    'Memory controller',
        '0x06':      'Bridge',
        '0x0600':    'Host bridge',
        '0x0601':    'ISA bridge',
        '0x0602':    'EISA bridge',
        '0x0603':    'MicroChannel bridge',
        '0x0604':    'PCI bridge',
        '0x060400':  'Normal decode',
        '0x060401':  'Subtractive decode',
        '0x0605':    'PCMCIA bridge',
        '0x0606':    'NuBus bridge',
        '0x0607':    'CardBus bridge',
        '0x0608':    'RACEway bridge',
        '0x060800':  'Transparent mode',
        '0x060801':  'Endpoint mode',
        '0x0609':    'Semi-transparent PCI-to-PCI bridge',
        '0x060940':  'Primary bus towards host CPU',
        '0x060980':  'Secondary bus towards host CPU',
        '0x060a':    'InfiniBand to PCI host bridge',
        '0x0680':    'Bridge',
        '0x07':      'Communication controller',
        '0x0700':    'Serial controller',
        '0x070000':  '8250',
        '0x070001':  '16450',
        '0x070002':  '16550',
        '0x070003':  '16650',
        '0x070004':  '16750',
        '0x070005':  '16850',
        '0x070006':  '16950',
        '0x0701':    'Parallel controller',
        '0x070100':  'SPP',
        '0x070101':  'BiDir',
        '0x070102':  'ECP',
        '0x070103':  'IEEE1284',
        '0x0701fe':  'IEEE1284 Target',
        '0x0702':    'Multiport serial controller',
        '0x0703':    'Modem',
        '0x070300':  'Generic',
        '0x070301':  'Hayes/16450',
        '0x070302':  'Hayes/16550',
        '0x070303':  'Hayes/16650',
        '0x070304':  'Hayes/16750',
        '0x0704':    'GPIB controller',
        '0x0705':    'Smard Card controller',
        '0x0780':    'Communication controller',
        '0x08':      'Generic system peripheral',
        '0x0800':    'PIC',
        '0x080000':  '8259',
        '0x080001':  'ISA PIC',
        '0x080002':  'EISA PIC',
        '0x080010':  'IO-APIC',
        '0x080020':  'IO(X)-APIC',
        '0x0801':    'DMA controller',
        '0x080100':  '8237',
        '0x080101':  'ISA DMA',
        '0x080102':  'EISA DMA',
        '0x0802':    'Timer',
        '0x080200':  '8254',
        '0x080201':  'ISA Timer',
        '0x080202':  'EISA Timers',
        '0x080203':  'HPET',
        '0x0803':    'RTC',
        '0x080300':  'Generic',
        '0x080301':  'ISA RTC',
        '0x0804':    'PCI Hot-plug controller',
        '0x0805':    'SD Host controller',
        '0x0806':    'IOMMU',
        '0x0880':    'System peripheral',
        '0x09':      'Input device controller',
        '0x0900':    'Keyboard controller',
        '0x0901':    'Digitizer Pen',
        '0x0902':    'Mouse controller',
        '0x0903':    'Scanner controller',
        '0x0904':    'Gameport controller',
        '0x090400':  'Generic',
        '0x090410':  'Extended',
        '0x0980':    'Input device controller',
        '0x0a':      'Docking station',
        '0x0a00':    'Generic Docking Station',
        '0x0a80':    'Docking Station',
        '0x0b':      'Processor',
        '0x0b00':    '386',
        '0x0b01':    '486',
        '0x0b02':    'Pentium',
        '0x0b10':    'Alpha',
        '0x0b20':    'Power PC',
        '0x0b30':    'MIPS',
        '0x0b40':    'Co-processor',
        '0x0c':      'Serial bus controller',
        '0x0c00':    'FireWire (IEEE 1394)',
        '0x0c0000':  'Generic',
        '0x0c0010':  'OHCI',
        '0x0c01':    'ACCESS Bus',
        '0x0c02':    'SSA',
        '0x0c03':    'USB controller',
        '0x0c0300':  'UHCI',
        '0x0c0310':  'OHCI',
        '0x0c0320':  'EHCI',
        '0x0c0330':  'XHCI',
        '0x0c0380':  'Unspecified',
        '0x0c03fe':  'USB Device',
        '0x0c04':    'Fibre Channel',
        '0x0c05':    'SMBus',
        '0x0c06':    'InfiniBand',
        '0x0c07':    'IPMI SMIC interface',
        '0x0c08':    'SERCOS interface',
        '0x0c09':    'CANBUS',
        '0x0d':      'Wireless controller',
        '0x0d00':    'IRDA controller',
        '0x0d01':    'Consumer IR controller',
        '0x0d10':    'RF controller',
        '0x0d11':    'Bluetooth',
        '0x0d12':    'Broadband',
        '0x0d20':    '802.1a controller',
        '0x0d21':    '802.1b controller',
        '0x0d80':    'Wireless controller',
        '0x0e':      'Intelligent controller',
        '0x0e00':    'I2O',
        '0x0f':      'Satellite communications controller',
        '0x0f01':    'Satellite TV controller',
        '0x0f02':    'Satellite audio communication controller',
        '0x0f03':    'Satellite voice communication controller',
        '0x0f04':    'Satellite data communication controller',
        '0x10':      'Encryption controller',
        '0x1000':    'Network and computing encryption device',
        '0x1010':    'Entertainment encryption device',
        '0x1080':    'Encryption controller',
        '0x11':      'Signal processing controller',
        '0x1100':    'DPIO module',
        '0x1101':    'Performance counters',
        '0x1110':    'Communication synchronizer',
        '0x1120':    'Signal processing management',
        '0x1180':    'Signal processing controller',
        '0x12':      'Processing accelerators',
        '0x1200':    'Processing accelerators',
        '0x13':      'Non-Essential Instrumentation',
        '0x40':      'Coprocessor',
    }

    return class_code_str.get(code) \
        or class_code_str.get(code[:-2]) \
        or class_code_str.get(code[:-4]) \
        or 'Unknown'


def isrealfile(file):
    '''test if file is on the os filesystem'''

    if file is None:
        return False

    try:
        tmpfd = os.dup(file.fileno())
    except:
        return False
    else:
        os.close(tmpfd)
        return True


_os_encoding = None


def _os_decode(str):
    global _os_encoding

    if _os_encoding is None:
        _os_encoding = locale.getpreferredencoding()

    try:
        return str.decode(_os_encoding, 'ignore')
    except AttributeError:
        if str is None:
            return str
        else:
            raise


# Log

# register loglevel NOTICE and DEBUG2, define log function
# use ROOT logger

logging.NOTICE = ((logging.WARNING + logging.INFO) // 2)
logging.DEBUG2 = (logging.DEBUG - 2)

logging.addLevelName(logging.NOTICE, 'NOTICE')
logging.addLevelName(logging.DEBUG2, 'DEBUG2')

# register loglevel FATAL in logging._levelNames[]
# logging.FATAL is defined but logging._levelNames['FATAL'] is not
logging._levelNames['FATAL'] = logging.CRITICAL


def __log__notice(msg, *args, **kwargs):
    logging.root.log(logging.NOTICE, msg, *args, **kwargs)


def __log__debug2(msg, *args, **kwargs):
    logging.root.log(logging.DEBUG2, msg, *args, **kwargs)


logging.notice = __log__notice
logging.debug2 = __log__debug2


# LogHandler


class LogDialogHandler(logging.handlers.BufferingHandler):
    '''Log handler show Tk message box'''

    _handler = None

    def __init__(self, gui_main, level=logging.WARNING):
        super(LogDialogHandler, self).__init__(1)
        self.gui_main = gui_main

        self.setLevel(level)

    def emit(self, record):
        msg = self.format(record)
        fatal = False

        if record.levelno >= logging.ERROR:
            # CRITICAL, ERROR
            icon = 'error'
        elif record.levelno >= logging.WARNING:
            # WARNING
            icon = 'warning'
        else:
            # NOTICE, INFO, DEBUG
            icon = 'info'

        if self._handler is not None:
            self._handler(icon=icon, message=msg, fatal=fatal)

        else:
            self.gui_main.message_dialog(icon=icon, message=msg, fatal=fatal)

    def shouldFlush(self, record):
        return True

    def setLevel(self, level):
        if level < logging.WARNING:
            super(LogDialogHandler, self).setLevel(level)

    def threading_enabler(self, handler):
        self._handler = handler
        return self.gui_main.message_dialog


class LogTkTextHandler(logging.Handler):
    '''Log handler logs to Tk Text widget'''

    _handler = None
    _text = None

    def __init__(self, text=None):
        super(LogTkTextHandler, self).__init__()
        self._text = text

    def emit(self, record):
        msg = self.format(record)

        if self._handler is not None:
            self._handler(msg)

        else:
            self.print_msg(msg)

    def print_msg(self, msg):
        if self._text is None:
            return

        eot = float(self._text.index(tk.END))
        if eot > 10000:
            eot -= 9900.0
            self._text.delete('1.0', '%d.end' % int(eot))

        self._text.mark_set(tk.INSERT, tk.END)
        self._text.insert(tk.END, msg + '\n')
        self._text.see(tk.END)

    def threading_enabler(self, handler):
        self._handler = handler
        return self.print_msg


class XArgumentParser(argparse.ArgumentParser):
    '''
    ArgumentParser that raise specified exception when invalid command-line
    optiton/argument is given
    '''

    def __init__(self, raise_on_error=None, *args, **kwds):
        super(XArgumentParser, self).__init__(*args, **kwds)
        self._raise_on_error = raise_on_error

    def error(self, message):
        if self._raise_on_error is not None:
            raise self._raise_on_error(message)
        else:
            super(XArgumentParser, self).error(message)


# GUI stuff

class TtkDialog(tk.Toplevel):
    '''dialog with ttk buttons at bottom'''

    _frame_background = None

    def __init__(self, master=None, buttons=None, **kw):
        '''create dialog(toplevel) and hide it'''

        if TtkDialog._frame_background is None:
            TtkDialog._frame_background \
                = ttk.Style().lookup('TFrame', 'background')

        kw['background'] = self._frame_background
        kw['class'] = 'Dialog'

        tk.Toplevel.__init__(self, master, **kw)

        self.wm_withdraw()

        if master.winfo_toplevel().winfo_viewable():
            self.wm_transient()

        if self._windowingsystem == 'x11':
            self.wm_attributes('-type', 'dialog')

        if buttons is not None:
            self.buttons = buttons
        else:
            self.buttons = ('OK', )

        self._priv = tk.StringVar(self, '::tk::Priv(button)')

    def show(self, focus_to=None):
        '''add buttons to dialog, move to appropriate position, unhide'''

        (col, row) = self.grid_size()

        # add buttons
        bs = self.buttons
        self.buttons = {}
        bf = ttk.Frame(self)
        for n, button in enumerate(bs):
            b = ttk.Button(bf, text=button,
                           command=lambda self=self, button=button:
                           self.dialog_end(button))
            b.grid(column=n, row=0, in_=bf)
            self.buttons[button] = b

        bf.grid(column=0, row=row, columnspan=col, padx=1, pady=1, sticky=tk.E)

        self.protocol('WM_DELETE_WINDOW', self.dialog_end)

        # calc position
        self.update_idletasks()
        self.wm_resizable(False, False)

        master = self.master

        if master.winfo_ismapped():
            m_w = master.winfo_width()
            m_h = master.winfo_height()
            m_x = master.winfo_rootx()
            m_y = master.winfo_rooty()
        else:
            m_w = master.winfo_screenwidth()
            m_h = master.winfo_screenheight()
            m_x = m_y = 0

        d_w = self.winfo_width()
        d_h = self.winfo_height()

        d_x = (m_w - d_w) * 0.5 + m_x
        d_y = (m_h - d_h) * 0.5 + m_y

        v_l = master.winfo_vrootx()
        v_r = master.winfo_vrootwidth() + v_l
        v_t = master.winfo_vrooty()
        v_b = master.winfo_vrootheight() + v_t

        if d_x < v_l:
            d_x = v_l
        elif d_x + d_w > v_r:
            d_x = v_r - d_w

        if d_y < v_t:
            d_y = v_t
        elif d_y + d_h > v_b:
            d_y = v_b - d_h

        # move to calc'ed position and unhide
        self.wm_geometry("+%d+%d" % (d_x, d_y))

        self.wm_deiconify()
        self.wait_visibility()

        self.prev_focus = self.focus_get()
        if focus_to is not None:
            focus_to.focus_set()
        else:
            self.focus_set()

        self.grab_set()

    def wait(self):
        '''wait dialog_end()'''

        self.wait_variable(self._priv)

        self.grab_release()

        if self.prev_focus is not None:
            self.prev_focus.focus_set()

        return self._priv.get()

    def dialog_end(self, reason=None):
        '''invoke waiting process'''

        self._priv.set(reason)

    def destroy(self):
        del self._priv
        tk.Toplevel.destroy(self)


class TtkAutoScrollbar(ttk.Scrollbar):
    '''auto-hide scrollbar'''

    _visible = True

    def set(self, lo, hi):
        if float(lo) <= 0.0 and 1.0 <= float(hi):
            if self._visible:
                self.grid_remove()
                self._visible = False

        else:
            if not self._visible:
                self.grid()
                self._visible = True

        ttk.Scrollbar.set(self, lo, hi)

    def pack(self, **kw):
        raise tk.TclError('cannot use pack')

    def place(self, **kw):
        raise tk.TclError('cannot use place')


class TtkScrollableFrame(ttk.Frame):
    '''Frame with scrollbar and an optional Label'''

    _frame_background = None    # also indicate initialized
    _wheel_seq_normal = ['<MouseWheel>']
    _wheel_seq_shift = ['<Shift-MouseWheel>']

    def __init__(self, master=None, option_label=None, **kw):
        if TtkScrollableFrame._frame_background is None:
            TtkScrollableFrame._frame_background \
                = ttk.Style().lookup('TFrame', 'background')

            if master._windowingsystem == 'x11':
                TtkScrollableFrame._wheel_seq_normal += ['<Button-4>',
                                                         '<Button-5>']
                TtkScrollableFrame._wheel_seq_shift += ['<Shift-Button-4>',
                                                        '<Shift-Button-5>']

        self.uf = ttk.Frame(master)

        row = 0
        if option_label is not None:
            self.lt = ttk.Label(self.uf, text=option_label)
            self.lt.grid(column=0, row=row, in_=self.uf, sticky=tk.NW)
            row += 1

        self.cv = tk.Canvas(self.uf,
                            width=1, height=1,
                            background=self._frame_background,
                            highlightthickness=0)
        self.hs = TtkAutoScrollbar(self.uf,
                                   orient=tk.HORIZONTAL,
                                   command=self.cv.xview)
        self.vs = TtkAutoScrollbar(self.uf,
                                   orient=tk.VERTICAL,
                                   command=self.cv.yview)
        self.cv.configure(xscrollcommand=self.hs.set,
                          yscrollcommand=self.vs.set)

        self.cv.grid(column=0, row=row, in_=self.uf, sticky=tk.NSEW)
        self.vs.grid(column=1, row=row, in_=self.uf, sticky=tk.NS)
        row += 1
        self.hs.grid(column=0, row=row, in_=self.uf, sticky=tk.EW)

        self.uf.grid_columnconfigure(self.cv, weight=1)
        self.uf.grid_rowconfigure(self.cv, weight=1)

        ttk.Frame.__init__(self, master=self.cv, **kw)
        self.cv.create_window((0, 0), window=self._w, anchor=tk.NW)

        self.bind('<Configure>', self._onConfigure)

        self.cv.bind('<Button>', self._onButton)
        self.cv.bind('<FocusIn>', self._onFocusIn)
        self.cv.bind('<FocusOut>', self._onFocusOut)

        self.uf.bind('<Button>', self._onButton)
        if option_label is not None:
            self.lt.bind('<Button>', self._onButton)

        for meth in (dir + 'view' + form
                     for dir in ('x', 'y', )
                     for form in ('', '_moveto', '_scroll', )):
            setattr(self, meth, getattr(self.cv, meth))

        for meth in ('__str__', 'grid', ):
            setattr(self, meth, getattr(self.uf, meth))

    def _onConfigure(self, ev):
        fw = self.winfo_reqwidth()
        fh = self.winfo_reqheight()
        self.cv.configure(scrollregion=(0, 0, fw, fh))

    def _onButton(self, ev):
        self.after_idle(self.focus_set)

    def _onFocusIn(self, ev):
        for seq in self._wheel_seq_normal:
            self.cv.bind_all(seq, self._onMouseWheelV)
        for seq in self._wheel_seq_shift:
            self.cv.bind_all(seq, self._onMouseWheelH)

    def _onFocusOut(self, ev):
        for seq in self._wheel_seq_normal:
            self.cv.unbind_all(seq)
        for seq in self._wheel_seq_shift:
            self.cv.unbind_all(seq)

    def _onMouseWheelV(self, ev):
        if self.winfo_reqheight() > self.uf.winfo_height():
            self.cv.yview_scroll(self.__Delta(ev), tk.UNITS)

    def _onMouseWheelH(self, ev):
        if self.winfo_reqwidth() > self.uf.winfo_width():
            self.cv.xview_scroll(self.__Delta(ev), tk.UNITS)

    def pack(self, **kw):       # might work but not tested
        raise tk.TclError('cannot use pack')

    def place(self, **kw):      # might work but not tested
        raise tk.TclError('cannot use place')

    @staticmethod
    def __Delta(ev):
        if ev.delta < 0 or ev.num == 5:
            return 2
        else:
            return -2


class ReadOnlyText(tk.Text):
    '''read-only Text widget with supplement <Shift-MouseWheel> bindings'''

    _class_initialized = False

    def __init__(self, master=None, cnf={}, **kw):
        kw['undo'] = False      # useless
        tk.Text.__init__(self, master, cnf, **kw)
        self.line = 0

        if not ReadOnlyText._class_initialized:
            ReadOnlyText._class_initialized = True
            if tk.TkVersion < 8.6:
                self._supplement_bindings()

        self._wo = self._w + '_o'
        self.tk.eval('''
rename ::%(_w)s ::%(_wo)s
proc ::%(_w)s { args } {
  switch -exact -- [lindex $args 0] {
    insert -
    delete {}
    default {
        return [::%(_wo)s {*}$args]
    }
  }
}
''' % {'_w': self._w, '_wo': self._wo})

    def destroy(self):
        self.tk.eval('''
rename ::%(_w)s {}
rename ::%(_wo)s ::%(_w)s
''' % {'_w': self._w, '_wo': self._wo})
        tk.Text.destroy(self)

    def delete(self, index1, index2=None):
        self.tk.call(self._wo, 'delete', index1, index2)

    def insert(self, index, chars, *args):
        self.tk.call((self._wo, 'insert', index, chars) + args)

    def clear(self):
        self.tk.call(self._wo, 'delete', '0.0', tk.END)
        self.edit_reset()
        self.line = 0

    def pr(self, data, tag=None):
        if tag is None:
            if self.line % 2 == 0:
                tag = 't_even'
            else:
                tag = 't_odd'

        self.insert(tk.END, data + '\n', tag)
        self.line += 1

    def _supplement_bindings(self):
        '''<Shift-MouseWheel> bindings'''

        self.tk.eval('''
# XXX affets ALL Text widgets
catch {
  bind Text <Shift-MouseWheel> {
    if {%D >= 0} {
      %W xview scroll [expr {-%D/3}] pixels
    } else {
      %W xview scroll [expr {(2-%D)/3}] pixels
    }
  }
  if {"x11" eq [tk windowingsystem]} {
    bind Text <Shift-4> {
      if {!$tk_strictMotif} {
        %W xview scroll -50 pixels
      }
    }
    bind Text <Shift-5> {
      if {!$tk_strictMotif} {
        %W xview scroll 50 pixels
      }
    }
  }
  if {"win32" eq [tk windowingsystem]} {
    bind Text <Control-a> {
      %W tag add sel 1.0 end
    }
  }
}

''')


class TtkReadOnlyEntry(ttk.Entry):
    '''read-only Entry widget; used as label'''

    def __init__(self, master=None, widget=None, **kw):

        if 'text' in kw:
            text = kw['text']
            del kw['text']
        else:
            text = None

        ttk.Entry.__init__(self, master, widget, **kw)

        self._wo = self._w + '_o'
        self.tk.eval('''
rename ::%(_w)s ::%(_wo)s
proc ::%(_w)s { args } {
  switch -exact -- [lindex $args 0] {
    insert -
    delete {}
    default {
        return [::%(_wo)s {*}$args]
    }
  }
}
''' % {'_w': self._w, '_wo': self._wo})

        if text is not None:
            self.insert('0', text)

    def delete(self, first, last=None):
        self.tk.call(self._wo, 'delete', first, last)

    def insert(self, index, string):
        self.tk.call(self._wo, 'insert', index, string)

    def destroy(self):
        self.tk.eval('''
rename ::%(_w)s {}
rename ::%(_wo)s ::%(_w)s
''' % {'_w': self._w, '_wo': self._wo})
        ttk.Entry.destroy(self)


#


class EEM_App_Error(Exception):
    '''something wrong in application (mainly during initialization).'''


class EEM_App_GUI(tk.Tk):
    '''main / GUI'''

    logger = {}
    config = {}
    option = {}

    tclvar = {}

    thread_event_q = None
    thread_handlers = {}
    poll_timer_id = None
    poll_index = -1
    poll_interval = (100, 100, 100, 100, 200, 200, 500, )

    auto_refresh_codes = {'40004': (),
                          '40400': (),
                          '40011': ('delete', ),
                          '50003': (), }

    cannot_read_config_msg = 'cannot read config-file: %s: %s'

    _mainloop = False
    busy_count = 0

    device_list = None
    group_devs = None
    curr_dev = None

    keep_tab = False

    def __init__(self):

        tk.Tk.__init__(self)

        # copy default option
        for k, v in commandline_options.items():
            self.option[k] = v[0]

        try:
            try:
                self.init_logger()
                self.parse_option()
                self.stream_logger()

            finally:
                self.init_gui()
                self.gui_logger()

            self.init_config()
            # self.stream_logger()  # for config-file

            self.eem = EE_Manager(conf=self.config,
                                  notify_fn=self.eem_request_done)
            self.prepare_threading('eem', self.eem.threading_enabler)

        except EEM_App_Error as ex:
            self.after_idle(logging.error, ex.message)
            self.tk.mainloop()  # not self.mainloop()
            self.terminate(1)

    def parse_option(self):
        '''parse command-line option'''

        parser = XArgumentParser(add_help=False,
                                 raise_on_error=EEM_App_Error)

        # make argument parser
        for k, v in commandline_options.items():
            if isinstance(v[0], bool):
                v[1]['action'] = 'store_true'

            parser.add_argument('--' + k, **v[1])

        parser.add_argument('section', nargs='?', metavar='config-section')

        # parse command-line
        # no error check here; XArgumentParser.error() raise exception on error
        opts = parser.parse_args()

        # copy to dict
        for k in commandline_options.keys():
            v = getattr(opts, k.replace('-', '_'))
            if v:
                self.option[k] = v

        self.option['section'] = opts.section

        if opts.debug or opts.debug2:
            self.option['logwin'] = True

    def init_config(self):
        '''read config-file (given by command-line option or default)'''

        import ConfigParser as cp

        config = self.config
        option = self.option

        conf = cp.RawConfigParser(dict_type=dict)

        if option['configfile'] is not None:
            configfiles = [option['configfile']]

        else:
            configfiles = self._configfiles()

        for conffile in configfiles:
            try:
                st_mode = os.stat(conffile).st_mode
                if not stat.S_ISREG(st_mode):
                    raise EEM_App_Error(self.cannot_read_config_msg
                                        % (conffile, 'not a regular-file'))
                with open(conffile, 'r') as fobj:
                    conf.readfp(fobj)
                    logging.debug('config: %s: parse done', conffile)
                    break

            except cp.Error as ex:
                raise EEM_App_Error('invalid config-file: %s: %s'
                                    % (conffile,
                                       _os_decode(str(ex))))

            except IOError as ex:
                raise EEM_App_Error(self.cannot_read_config_msg
                                    % (conffile,
                                       _os_decode(ex.strerror or str(ex))))

            except OSError as ex:  # WindowsError is subclass of OSError
                # default file may not exist
                if option['configfile'] is None and ex.errno == errno.ENOENT:
                    # default file not exist; ignore
                    logging.debug(self.cannot_read_config_msg,
                                  ex.filename,
                                  _os_decode(ex.strerror or str(ex)))
                else:
                    # config-file given as command-line option did not exist
                    # or something wrong
                    raise EEM_App_Error(self.cannot_read_config_msg
                                        % (conffile,
                                           _os_decode(ex.strerror or str(ex))))

        else:
            # default config-file not exist
            if option['section']:  # section specified
                raise EEM_App_Error('config-file not exists')

            else:
                # use hard-coded defaults
                logging.notice('config-file not exists, use default')
                for item in ('server_ip', 'server_port',
                             'timeout', 'auth', 'ssl', ):
                    config[item] = default_config[item]

            return

        if option['section']:
            # section name is given as command-line argument
            section = option['section']

        else:
            # use config-file name as section name
            section = os.path.splitext(os.path.basename(conffile))[0]

        logging.debug('config: section: %s', section)

        try:
            use_default = []

            # get config item from file or use default
            for item in ('server_ip', 'server_port',
                         'timeout', 'auth', 'ssl', ):
                try:
                    config[item] = conf.get(section, item)
                except cp.NoOptionError as ex:
                    config[item] = default_config[item]
                    use_default.append("'%s'" % item)

            # convert to number(int)
            for item in ('timeout', 'auth', ):
                v = config[item]
                if not isinstance(v, int):
                    try:
                        config[item] = int(config[item])
                    except ValueError as ex:
                        raise EEM_App_Error('config: %s'
                                            % _os_decode(str(ex)))

            # convert to boolean as ConfigParser.getboolean() does
            # XXX use ConfigParser's internal _boolean_states
            for item in ('ssl', ):
                v = config[item]

                if not isinstance(v, bool):
                    try:
                        config[item] = conf._boolean_states[v.lower()]
                    except KeyError as ex:
                        raise EEM_App_Error('config: Not a boolean: %s' % v)

            # additional item for auth and ssl
            if config['auth'] == 1:
                for item in ['encoded_id', ]:
                    config[item] = conf.get(section, item)
            elif config['auth'] == 2:
                for item in ['user', 'password', ]:
                    config[item] = conf.get(section, item)

            if config['ssl']:
                for item in ['cert', ]:
                    config[item] = conf.get(section, item)

        except (cp.NoOptionError, cp.NoSectionError) as ex:
            raise EEM_App_Error('config: %s: %s'
                                % (conffile, _os_decode(str(ex))))

        # some config-item was not defined in config-file/section
        if use_default:
            if len(use_default) > 1:
                opts_default = '%s and %s are' % \
                               (', '.join(use_default[0:-1]), use_default[-1])
            else:
                opts_default = '%s is' % use_default[0]

            logging.notice('config-option %s not defined in section [%s], '
                           'use default.' % (opts_default, section))

        # # get logfile and loglevel unless set by command-line option
        # for item in ('logfile', 'loglevel', ):
        #     if option[item] is None:
        #         try:
        #             option[item] = conf.get(section, item)
        #         except cp.NoOptionError:
        #             pass        # ignore

    @staticmethod
    def _configfiles():
        base0 = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        return [CONFIG['FORMAT'] % {'base': base, 'ext': ext}
                for base in [base0] + CONFIG['BASEs']
                for ext in CONFIG['EXTs']]

    def init_logger(self):
        '''initialize logger; set loglevel to hard-coded default'''

        log = self.logger
        log['logger'] = logging.getLogger()  # use root logger

        log['loglevel'] = log['logger_level'] = logging.NOTICE
        log['logger'].setLevel(logging.NOTICE)

    def _option_loglevel_to_num(self, default=None):
        '''convert log-level string to number'''

        level = default
        errstr = None
        if self.option['loglevel'] is not None:
            loglevel = self.option['loglevel']
            if loglevel.isdigit():
                loglevel = int(loglevel)
            else:
                loglevel = self.option['loglevel'].upper()

            try:
                # convert to number
                # XXX use logging module's internal _checkLevel()
                level = logging._checkLevel(loglevel)
                if level < logging.NOTSET:
                    raise ValueError(level)
            except (ValueError, TypeError) as ex:
                errstr = str(ex)
                self.option['loglevel'] = None
                level = default

        if level is not None and default is not None and level > default:
            level = default

        return level, errstr

    def stream_logger(self):
        '''
        open stream log handler; log-file and/or console(stderr)
        set log-level
        '''

        option = self.option
        log = self.logger
        loglevel = log['loglevel']

        # console (stderr) (if available)
        if option['logconsole'] and 'stderr' not in log and \
           isrealfile(sys.stderr):
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT['CONS']))
            stderr_handler.setLevel(loglevel)

            log['logger'].addHandler(stderr_handler)
            log['stderr'] = stderr_handler

        # logfile
        if option['logfile'] is not None and 'file' not in log:
            try:
                file_handler = logging.FileHandler(option['logfile'], 'a')
                file_handler.setFormatter(logging.Formatter(LOG_FORMAT['FILE'],
                                                            LOG_FORMAT['DATE']))
                file_handler.setLevel(loglevel)

                log['logger'].addHandler(file_handler)
                log['file'] = file_handler
            except IOError as ex:
                logging.warning('cannot open logfile: %s: %s',
                                option['logfile'], ex.strerror)

        # loglevel (affects file and console)
        level, errstr = self._option_loglevel_to_num(loglevel)
        if errstr is not None:
            logging.warning('Invalid loglevel: %s', errstr)

        if level < loglevel:
            logging.debug('change loglevel %d -> %d', loglevel, level)
            loglevel = level
            if 'stderr' in log:
                log['stderr'].setLevel(loglevel)
            if 'file' in log:
                log['file'].setLevel(loglevel)

        if loglevel < log['logger_level']:
            log['logger'].setLevel(loglevel)
            log['logger_level'] = loglevel

    def gui_logger(self):
        '''log to Tk widget; Dialog and Text (if enabled)'''

        log = self.logger
        loglevel = log['loglevel']

        # Tk dialog
        dialog_handler = LogDialogHandler(self, logging.NOTICE)
        dialog_handler.setFormatter(logging.Formatter(LOG_FORMAT['DIALOG']))
        log['logger'].addHandler(dialog_handler)
        log['dialog'] = dialog_handler

        self.prepare_threading('dialog', dialog_handler.threading_enabler)

        if not self.option['logwin']:
            return

        tktext_handler = LogTkTextHandler(text=self.Log)
        tktext_handler.setFormatter(logging.Formatter(LOG_FORMAT['TEXT']))

        self.prepare_threading('log', tktext_handler.threading_enabler)

        # not change handler's loglevel; use logger's
        log['logger'].addHandler(tktext_handler)
        log['tktext'] = tktext_handler

        # change loglevel when --debug option is given; affects TkText only
        if self.option['debug2']:
            loglevel = min(log['logger_level'], logging.DEBUG2)
        elif self.option['debug']:
            loglevel = min(log['logger_level'], logging.DEBUG)

        # change logger's loglevel if necessary
        if loglevel < log['logger_level']:
            log['logger'].setLevel(loglevel)
            log['logger_level'] = loglevel

    def init_gui(self):
        '''build GUI'''

        # declare tcl variables
        tclvar = self.tclvar

        for v in ('eeid', 'group', 'api_version', ):
            tclvar[v] = tk.StringVar(self, name=str('::eevw(%s)' % v))

        for v in ('delete_force', ):
            tclvar[v] = tk.BooleanVar(self, name=str('::eevw(%s)' % v))
            tclvar[v].set(False)

        conn = tclvar['conn'] = {}
        for port in range(16):
            for v in ('eeid', 'status', 'group', 'class', ):
                conn[(port, v)] \
                    = tk.StringVar(self, name=str('::eevw_conn(%d,%s)'
                                                  % (port, v)))

        self.refresh_api_version('unknown')

        style = ttk.Style()

        # if self.option['theme'] is not None:
        #     style.theme_use(self.option['theme'])

        self.configure(background=style.lookup('TFrame', 'background'))

        self.tk.eval(
            '''bind TButton <Key-Return> [bind TButton <Key-space>]'''
        )

        try:
            app_title = __doc__.strip().split('\n')[0]
        except AttributeError:
            app_title = os.path.splitext(os.path.basename(sys.argv[0]))[0]

        self.wm_title(app_title)

        base = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self.List = EEM_App_GUI_List(master=base, gui_main=self)
        self.Data = EEM_App_GUI_Data(master=base, gui_main=self)

        base.add(self.List)
        base.add(self.Data)

        base.grid(column=0, row=0, sticky=tk.NSEW)
        self.grid_columnconfigure(base, weight=1)
        self.grid_rowconfigure(base, weight=1)

        self.update_idletasks()
        self.wm_geometry(self.wm_geometry())  # settle window size

        self.update()           # update_idletasks() seems insufficient (?)

    #

    def mainloop(self):
        '''dive into Tkinter.mainloop and start I/O'''

        self.enable_threading()
        self.poll_event_timer(event=True)

        self.after(50, self._eem_io_start)
        self._mainloop = True

        try:
            self.tk.mainloop()
        except KeyboardInterrupt:
            pass

        self.terminate()

    def terminate(self, status=0):
        self.destroy()
        sys.exit(status)

    def destroy(self):
        try:
            self.eem.terminate()
        except AttributeError:
            pass

        try:
            tk.Tk.destroy(self)
        except tk.TclError:
            pass

    def busy_cursor(self, n):

        self.busy_count += n

        if n > 0 and self.busy_count == n:  # was == 0
            cursor = 'watch'
        elif n < 0 and self.busy_count == 0:
            cursor = ''
        elif self.busy_count < 0:
            raise EEM_App_Error('Internal: busy_count')
        else:
            cursor = None

        if cursor is not None:
            self.configure(cursor=cursor)
            self.Info.set_cursor(cursor=cursor)

    @staticmethod
    def disable_children(master):
        children = master.winfo_children()

        try:
            while True:
                child = children.pop()
                if isinstance(child, (tk.Frame, ttk.Frame, tk.Canvas)):
                    children.extend(child.winfo_children())

                    try:
                        child.configure(state=tk.DISABLED)
                    except tk.TclError:
                        pass

        except IndexError:
            pass

    # error/warning message dialog

    def message_dialog(self, icon, message, fatal=False):
        '''
        show message dialog, not block (not wait user operation)
        if fatal is True, terminate program after OK is pressed
        '''
        self.update()
        self.after_idle(self._message_dialog, icon, message, fatal)

    def _message_dialog(self, icon, message, fatal):
        tkMessageBox._show(title=icon, message=message, icon=icon,
                           type=tkMessageBox.OK)
        if fatal or (icon == 'error' and not self._mainloop):
            self.terminate(1)

    # threading

    def prepare_threading(self, tag, enabler):
        '''register threading enabler'''

        self.thread_handlers[tag] = enabler

    def enable_threading(self):

        if THREADING:
            self.thread_event_q = Queue.Queue()

            for tag in list(self.thread_handlers.keys()):
                enabler = self.thread_handlers[tag]

                def __thread_handler(self, tag):
                    def __handler(*args, **kwds):
                        self.thread_event_q.put_nowait((tag, args, kwds))

                    return __handler

                # def __thread_handler(self, tag):
                #     main_thread_id = threading.currentThread().ident

                #     def __handler(*args, **kwds):
                #         if threading.currentThread().ident != main_thread_id:
                #             self.thread_event_q.put_nowait((tag, args, kwds))
                #         else:
                #             self.thread_handlers[tag](*args, **kwds)

                #     return __handler

                self.thread_handlers[tag] \
                    = enabler(__thread_handler(self, tag))

            self.poll_event = self._poll_event
            self.poll_event_timer = self._poll_event_timer

        else:
            self.thread_handlers = None

    def _poll_event(self):
        '''event poller; called periodically'''

        self.poll_timer_id = None

        event_handled = 0
        try:
            while True:
                tag, args, kwds = self.thread_event_q.get_nowait()
                self.thread_handlers[tag](*args, **kwds)
                event_handled += 1

        except Queue.Empty:
            pass

        self.poll_event_timer(event=(event_handled > 0))

    def _poll_event_timer(self, start=False, end=False, event=False):
        '''(re) start poll timer'''

        if start:
            # I/O start
            if self.poll_timer_id is not None:
                self.after_cancel(self.poll_timer_id)
                self.poll_timer_id = None

            self.poll_index = None  # I/O active
            poll_interval = self.poll_interval[0]

        elif end:
            # I/O end
            if self.poll_timer_id is not None:
                self.after_cancel(self.poll_timer_id)
                self.poll_timer_id = None

            self.poll_index = 0  # after I/O done
            poll_interval = self.poll_interval[0]  # self.poll_index

        else:
            # restart or initial start
            if self.poll_timer_id is not None:
                # race
                return

            if self.poll_index is None:
                # I/O active
                poll_interval = self.poll_interval[0]

            elif event:
                self.poll_index = 0
                poll_interval = self.poll_interval[0]

            elif self.poll_index >= 0:
                # after I/O done
                self.poll_index += 1
                if self.poll_index >= len(self.poll_interval):
                    self.poll_index = -1

                poll_interval = self.poll_interval[self.poll_index]

            else:
                # idle
                # self.poll_index == -1
                poll_interval = self.poll_interval[-1]

        self.poll_timer_id = self.after(poll_interval, self.poll_event)

    @staticmethod
    def __nop(*args, **kwds):
        return

    poll_event = __nop
    poll_event_timer = __nop

    #

    def eem_request(self, cmd, curr_dev=None, **kwds):
        '''send 'command' to EEM with eeid of currently selected device'''

        if curr_dev is not None:
            if curr_dev.eeid not in self.device_list:
                logging.warning('unknown eeid %s %s', curr_dev.eeid, cmd)
                return

            kwds['eeid'] = curr_dev.eeid

        self.busy_cursor(+1)

        self.eem.request(cmd, **kwds)

        self.poll_event_timer(start=True)  # NOP if not threading

    def eem_request_done(self, cmd, rv, resp):

        self.poll_event_timer(end=True)  # NOP if not threading
        if rv:
            try:
                cbfn = self._eem_request_cbs[cmd]
            except KeyError:
                pass
            else:
                self.after_idle(cbfn, self, rv, resp)

        else:
            # something wrong
            logging.info('eem_request_done: %s - %s', cmd, rv)

            if resp is not None and not resp.success:
                errmsg = resp.exc_str

                try:
                    code = resp.http_code
                    auto_refresh_cmds = self.auto_refresh_codes[code]

                    if cmd in auto_refresh_cmds or auto_refresh_cmds is ():
                        self.after_idle(self.device_list_refresh)
                        errmsg += '\n\nrefresh automatically.'

                except (AttributeError, KeyError):
                    pass

                logging.error('%s', errmsg)

                try:
                    logging.info('args = %s', str(resp.args))
                except (AttributeError):
                    pass

                try:
                    logging.info('errno = %d', resp.errno)
                except (AttributeError, TypeError):
                    pass

            if cmd == '_eem_io_start':
                self.after_idle(self.refresh_disable_all)

        self.after_idle(self.busy_cursor, -1)

    #

    def _eem_io_start(self):
        self.eem_request('_eem_io_start')

    def _eem_io_start_done(self, rv, resp):
        if rv:
            self.List.b_refresh.configure(state=tk.NORMAL)
            self.refresh_api_version(self.eem.api_ver)
            self.refresh_device_list()
            self.update()

            if not self.option.get('disable-initial-audit', False):
                self.after(50, self._audit_all)

    def _audit_all(self):
        self.eem_request('_audit_all')

    def get_led_cached(self):
        self.eem_request('get_led_cached', curr_dev=self.curr_dev)

    def refresh_api_version(self, api_ver):
        self.tclvar['api_version'].set('API Version: %s' % api_ver)

    def refresh_device(self, *args):
        self.keep_tab = True
        self.Data.refresh()
        self.after_idle(self.get_led_cached)

    def refresh_device_list(self, *args):
        self.device_list = self.eem.device_list
        self.group_devs = self.eem.group_devs

        self.List.refresh(self.group_devs)

        if self.curr_dev is not None and \
           self.curr_dev.eeid in self.device_list:
            self.keep_tab = True
            self.List.select_item_eeid('eeid_' + self.curr_dev.eeid)
        else:
            self.refresh_device_gone()

    def refresh_uid_led(self, *args):
        self.Ctrl.refresh_uid_led(args[0])

    def refresh_device_gone(self):
        self.tclvar['eeid'].set('')
        self.tclvar['group'].set('')

        self.Data.refresh_device_gone()

    def refresh_disable_all(self):
        logging.info('Cannot continue')

        self.disable_children(self.List)
        self.Data.refresh_disable_all()

        # self.disable_children(self.Data)

    _eem_request_cbs = {
        'audit':          refresh_device,
        'delete':         refresh_device_list,
        'perst':          refresh_device,
        'send_rst':       refresh_device,
        'set_gid':        refresh_device_list,
        'del_gid':        refresh_device_list,
        'del_iomac':      refresh_device_list,
        'get_led_cached': refresh_uid_led,
        'toggle_led':     refresh_uid_led,

        'list_devices':   refresh_device_list,

        '_eem_io_start':  _eem_io_start_done,
        '_audit_all':     refresh_device_list,
    }

    # 'command' button handlers

    def audit(self):
        self.eem_request('audit', curr_dev=self.curr_dev)

    def delete(self):
        force = self.tclvar['delete_force'].get()
        self.eem_request('delete', curr_dev=self.curr_dev, force=force)

    def perst(self):
        if self.confirm_dialog('reset'):
            self.eem_request('perst', curr_dev=self.curr_dev)

    def send_rst(self):
        if self.confirm_dialog('reset'):
            self.eem_request('send_rst', curr_dev=self.curr_dev)

    def set_led(self):
        self.eem_request('toggle_led', curr_dev=self.curr_dev)

    def set_gid(self):
        groups = [gid for gid, sts in self.group_devs.items() if sts['eesv']]

        gid_dialog = EEM_App_GUI_GID_Dialog(self,
                                            self.curr_dev.disp_id,
                                            self.curr_dev.status,
                                            groups)

        result, group_id = gid_dialog.wait()
        gid_dialog.destroy()

        if result == 'OK' and self.confirm_dialog('change_gid'):
            if group_id.lower() == 'auto':
                group_id = None

            self.eem_request('set_gid',
                             curr_dev=self.curr_dev, group_id=group_id)

    def del_gid(self):
        if self.confirm_dialog('change_gid'):
            self.eem_request('del_gid', curr_dev=self.curr_dev)

    def del_iomac(self, port):  # at Connection frame
        self.eem_request('del_iomac', curr_dev=self.curr_dev, port=port)

    def device_list_refresh(self):  # at bottom of Device List (left pane)
        self.eem_request('list_devices')

    def device_list_select(self, eeid):
        curr_dev = self.curr_dev = self.device_list[eeid]

        self.tclvar['eeid'].set(curr_dev.disp_id)
        self.tclvar['group'].set(curr_dev.group)

        self.Data.refresh()
        self.after_idle(self.get_led_cached)

    #

    def confirm_dialog(self, what):
        confirm_dialog = {
            'reset':      ('Reset device',
                           'Resetting ExpEther device while OS is running '
                           'may affect the operation of the OS.'
                           '\n\n'
                           'Continue ?', ),
            'change_gid': ('Change group ID',
                           'Changing the group ID of ExpEther device '
                           'while OS is running '
                           'may affect the operation of the the OS.'
                           '\n\n'
                           'Continue ?', ),
        }

        title, message = confirm_dialog[what]

        result = tkMessageBox._show(icon=tkMessageBox.WARNING,
                                    type=tkMessageBox.OKCANCEL,
                                    default=tkMessageBox.CANCEL,
                                    title=title, message=message)
        return result == tkMessageBox.OK

    #


class EEM_App_GUI_List(ttk.Frame):
    '''List frame (left pane)'''

    _nc_treeview_initilaized = False

    def __init__(self, master, gui_main):
        ttk.Frame.__init__(self, master)

        self.gui_main = gui_main

        if not EEM_App_GUI_List._nc_treeview_initilaized:
            EEM_App_GUI_List._nc_treeview_initilaized = True
            self._initialize_nc_treeview()

        ttk.Label(self, text='ExpEther Device').\
            grid(column=0, row=0, sticky=tk.NW)

        self.gui_main = gui_main

        tv_list = ttk.Treeview(self, show='tree', selectmode=tk.BROWSE,
                               style='NC.Treeview')
        sv_list = TtkAutoScrollbar(self,
                                   command=tv_list.yview,
                                   orient=tk.VERTICAL)
        tv_list.configure(yscrollcommand=sv_list.set)

        tv_list.grid(column=0, row=1, sticky=tk.NSEW)
        sv_list.grid(column=1, row=1, sticky=tk.NS)

        self.grid_columnconfigure(tv_list, weight=1)
        self.grid_rowconfigure(tv_list, weight=1)

        b_refresh = ttk.Button(self, text='Refresh',
                               command=self._onRefreshButton,
                               state=tk.DISABLED)
        b_refresh.grid(column=0, row=2, columnspan=2)

        tv_list.bind('<<TreeviewSelect>>', self._onTreeviewSelect)

        tags = tv_list.bindtags()
        tv_list.bindtags((tags[0], 'NC.Treeview') + tags[1:])

        self.tv_list = tv_list
        self.b_refresh = b_refresh

    def _onRefreshButton(self):
        self.gui_main.after_idle(self.gui_main.device_list_refresh)

    def _onTreeviewSelect(self, ev):
        '''called when list item is selected'''

        cursel = self.tv_list.selection()  # or focus() ?
        type, id = cursel[0].split('_')
        if type == 'eeid':
            self.gui_main.after_idle(self.gui_main.device_list_select, id)

    def refresh(self, group_devs):
        '''refresh device list'''

        tv_list = self.tv_list
        for group_iid in tv_list.get_children(item=''):
            tv_list.delete(group_iid)

        for group in sorted(group_devs.keys()):
            group_iid = 'group_%4d' % group
            tv_list.insert('', tk.END, open=True,
                           iid=group_iid,
                           text='Group  %4d%s'
                           % (group,
                              '  (default)' if group > GID['MAX'] else ''))

            for type, type_str in (('eesv', 'Board'), ('eeio', 'I/O Unit')):
                for id in sorted(group_devs[group][type]):
                    eeid = 'eeid_' + id
                    tv_list.insert(group_iid, tk.END,
                                   iid=eeid,
                                   text='%s  %s' % (type_str, id))

        self.update_idletasks()

    def select_item_eeid(self, eeid):
        '''select item programmatically'''

        tv_list = self.tv_list
        tv_list.see(eeid)
        tv_list.selection_set(eeid)

    def _initialize_nc_treeview(self):
        '''non-collapsable treeview'''
        self.tk.eval('''
ttk::style layout NC.Treeview.Item {
  Treeitem.padding -sticky {nsew} -children {
    Treeitem.image -side left -sticky {}
    Treeitem.focus -side left -sticky {} -children {
      Treeitem.text -side left -sticky {}
    }
  }
}

proc bind_NC_Treeview {} {
  foreach { seq map } { KeyPress-Left        KeyPress-Up
                        KeyPress-Right       KeyPress-Down
                        Double-ButtonPress-1 ButtonPress-1 } {
    bind NC.Treeview "<${seq}>" "[bind Treeview <${map}>]; break"
  }
  foreach seq { Shift-ButtonPress-1 KeyPress-Return KeyPress-space } {
    bind NC.Treeview "<${seq}>" { break }
  }

  rename bind_NC_Treeview {}
}

bind_NC_Treeview
''')


class EEM_App_GUI_Data(ttk.Notebook):
    '''Data frame (right pane)'''

    def __init__(self, master, gui_main):
        ttk.Notebook.__init__(self, master)

        self.gui_main = gui_main

        self.tabs = {}
        tabs = [('Info', EEM_App_GUI_Info, ' Information ', ),
                ('Conn', EEM_App_GUI_Conn, ' Connection ', ),
                ('Ctrl', EEM_App_GUI_Ctrl, ' Control ', ), ]

        if gui_main.option['logwin']:
            tabs += [('Log', EEM_App_GUI_Log, ' Log ', )]

        for attr, tab_class, label in tabs:
            tab = tab_class(master=self, gui_main=gui_main)
            self.tabs[attr] = tab
            setattr(self, attr, tab)
            setattr(gui_main, attr, tab)
            self.add(tab, text=label, sticky=tk.NSEW)

    def refresh(self):
        '''refresh child window'''

        self.Info.refresh()
        self.Conn.refresh()
        self.Ctrl.refresh()

        curr_dev = self.gui_main.curr_dev
        if curr_dev is None:
            return

        if curr_dev.status == 'eesv':
            self.tab(self.Conn, state=tk.NORMAL)

        else:
            self.tab(self.Conn, state=tk.DISABLED)

        if not self.gui_main.keep_tab:
            self.select(self.Info)
            self.Info.focus_set()

        self.gui_main.keep_tab = False

    def refresh_device_gone(self):
        self.Info.refresh_device_gone()
        self.Conn.refresh_device_gone()
        self.Ctrl.refresh_device_gone()

    def refresh_disable_all(self):
        for tab in ('Info', 'Conn', 'Ctrl', ):
            self.gui_main.disable_children(self.tabs[tab])


class EEM_App_GUI_Info(ttk.Frame):
    '''Info frame (tab)'''

    def __init__(self, master, gui_main):
        ttk.Frame.__init__(self, master)

        self.gui_main = gui_main

        ttk.Label(self, text='ExpEther Device Details').\
            grid(column=0, row=0, sticky=tk.NW)

        t_info = ReadOnlyText(self, tabstyle='wordprocessor', wrap=tk.NONE,
                              insertofftime=0, insertontime=0)
        sv_info = TtkAutoScrollbar(self, command=t_info.yview,
                                   orient=tk.VERTICAL)
        sh_info = TtkAutoScrollbar(self, command=t_info.xview,
                                   orient=tk.HORIZONTAL)
        t_info.configure(xscrollcommand=sh_info.set,
                         yscrollcommand=sv_info.set)

        t_info.grid(column=0, row=1, sticky=tk.NSEW)
        sv_info.grid(column=1, row=1, sticky=tk.NS)
        sh_info.grid(column=0, row=2, sticky=tk.EW)

        self.grid_columnconfigure(t_info, weight=1)
        self.grid_rowconfigure(t_info, weight=1)

        self.t_info = t_info

        t_info.tag_configure(
            't_head', background='#0070c0', foreground='white')
        t_info.tag_configure(
            't_sub',  background='#00b0f0', foreground='white')
        t_info.tag_configure('t_even', background='#deebf7')
        t_info.tag_configure('t_odd',  background='white')
        t_info.tag_raise(tk.SEL)

        for meth in ('focus_set', ):
            setattr(self, meth, getattr(t_info, meth))

    def refresh(self):
        '''print EE device info'''

        self.t_info.clear()

        data = self.gui_main.curr_dev.data

        for item in ('id', 'status', 'update_time', 'admin_status',
                     'monitoring_status',
                     'notification_status0', 'notification_status1',
                     'mac_address', 'group_id', ):
            self._p1(data, item)

        if data['type'] != '10g':
            self._p1(data, 'vlan_tagging')

        if data['type'] == '40g':
            self._p1(data, 'multi_mac_addresses')
            self._p1(data, 'encryption')

        for item in ('type', 'uid_switch_status', 'power_status',
                     'pcie_link_width', 'interrupt_vector', 'ee_version',
                     'device_id', 'revision', 'fpga_version',
                     'eeprom_data_version', 'serial_number', 'model',
                     'link_status0', 'link_status1', ):
            self._p1(data, item)

        if data['status'] == 'eesv':
            self._p1(data, 'max_eeio_count')
            self._p1(data, 'eesv_type')

            if data['type'] == '40g':
                self._p1(data, 'compatibility')

            if data['type'] != '40g':
                self._p1(data, 'power_off_inhibition_status')

            self._p1(data, 'host_serial_number')
            self._p1(data, 'host_model')
            self.t_info.pr('downstream_ports      : ')

            dsp = data['downstream_ports']
            for pi in dsp:
                self._p2(pi, 'downstream_port_id', '')
                self._p2(pi, 'eeio_connection_status', '  ')
                self._p2(pi, 'eeio_mac_address', '  ')

        if data['status'] == 'eeio':
            for item in ('path_status0', 'path_status1',
                         'eesv_connection_status', 'eesv_mac_address',
                         'pcie_connection_status', 'pcie_vendor_id',
                         'pcie_device_id', 'pcie_class_code', ):
                self._p1(data, item)

            if data['ee_version'] != 'v1.0':
                self._p1(data, 'resource_id')

            if data['type'] != '40g':
                self._p1(data, 'power_interlock_status')

        self.t_info.mark_set(tk.INSERT, '1.0')

    def _p1(self, data, item):
        self.t_info.pr('%-22s: %s' % (item, data[item]))

    def _p2(self, data, item, pad):
        self.t_info.pr('  %-24s: %s' % (pad + item, data[item]))

    def refresh_device_gone(self):
        self.t_info.clear()

    def set_cursor(self, cursor):
        self.t_info.configure(cursor=cursor)


class EEM_App_GUI_Conn(TtkScrollableFrame):
    '''Connection frame (tab)'''

    _frame_option_initialized = False

    def __init__(self, master, gui_main):
        if not self._frame_option_initialized:
            EEM_App_GUI_Conn._frame_option_initialized = True
            self._initialize_conn_frame_option(master)

        TtkScrollableFrame.__init__(self, master,
                                    option_label='Connection Information',
                                    class_='ConnInfo')

        self.gui_main = gui_main

        v_conn = self.v_conn = gui_main.tclvar['conn']
        b_delio = self.b_delio = {}

        col = 0
        for label, span in (('source', 2), ('destination', 3)):
            ttk.Label(self, text='Connection ' + label).\
                grid(column=col, row=0, columnspan=span)
            col += span

        for col, label in enumerate(('Port id', 'Status', 'PCI Device',
                                     'ExpEther id', 'Group id', )):
            ttk.Label(self, text=label).grid(column=col, row=1)

        cols = self.grid_size()[0]

        for port in range(16):
            row = port + 2
            ttk.Label(self, text=port).grid(column=0, row=row)
            for col, v in enumerate(('status', 'class', 'eeid', 'group', ),
                                    start=1):
                l = ttk.Label(self, textvariable=v_conn[(port, v)])
                l.grid(column=col, row=row)

                if v == 'eeid':
                    l.bind('<Double-Button-1>',
                           lambda ev, self=self, port=port:
                           self._onDouble_eeio(port))

            b = ttk.Button(self, text='del_iomac',
                           command=lambda gui_main=gui_main, port=port:
                           gui_main.after_idle(gui_main.del_iomac, port))
            b.grid(column=5, row=row, padx=1, pady=1)
            b_delio[port] = b

        for col in range(cols):
            for w in self.grid_slaves(column=col):
                w.grid_configure(ipadx=5, sticky=tk.NSEW)

        self.grid_columnconfigure(tk.ALL, weight=1)

        self.bind('<Button>', self._onButton)
        for w in self.winfo_children():
            w.bind('<Button>', self._onButton)

    def _onButton(self, ev):
        self.focus_set()

    def _onDouble_eeio(self, port):
        eeid = self.v_conn[(port, 'eeid')].get()
        if eeid:
            id = 'eeid_0x' + eeid
            self.gui_main.List.select_item_eeid(id)

    def refresh(self):
        '''refresh EE connection info'''

        curr_dev = self.gui_main.curr_dev
        dev_list = self.gui_main.device_list

        if curr_dev.status != 'eesv':
            return

        self.xview_moveto(0)
        self.yview_moveto(0)

        v_conn = self.v_conn

        self.clear_conn_info()  # clear table and disable del_iomac button

        for pinfo in curr_dev.data['downstream_ports']:
            pid = int(pinfo['downstream_port_id'])

            eeid = '0x' + ''.join(pinfo['eeio_mac_address'].split(':'))
            if eeid == '0x000000000000' or eeid not in dev_list:
                continue

            # update info
            status = pinfo['eeio_connection_status'].capitalize()
            eeio = dev_list[eeid]
            group = eeio.group

            v_conn[(pid, 'status')].set(status)
            v_conn[(pid, 'eeid')].set(eeio.disp_id)
            v_conn[(pid, 'group')].set(group)
            v_conn[(pid, 'class')].\
                set(pci_class_code(eeio.data['pcie_class_code']))

            if not curr_dev.admin or not curr_dev.monitor:
                continue

            # enable del_iomac if eeio_connection_status is 'Down'
            # status is capitalized about 15 lines above
            if status == 'Down':
                self.b_delio[pid].configure(state=tk.NORMAL)

    def clear_conn_info(self):
        '''clear connection info table and disable del_iomac button'''
        for v in self.v_conn.values():
            v.set('')

        for p in range(16):
            self.b_delio[p].configure(state=tk.DISABLED)

    refresh_device_gone = clear_conn_info

    @staticmethod
    def _initialize_conn_frame_option(master):
        if master is None:
            master = ttk.setup_master(master)

        master.option_add('*ConnInfo.TLabel.anchor', tk.CENTER)
        master.option_add('*ConnInfo.TLabel.borderWidth', 1)  # for some theme
        master.option_add('*ConnInfo.TLabel.justify', tk.CENTER)
        master.option_add('*ConnInfo.TLabel.relief', tk.SOLID)
        master.option_add('*ConnInfo.TButton.style', 'Short.TButton')
        master.option_add('*ConnInfo.TButton.state', tk.DISABLED)
        ttk.Style().configure('Short.TButton', padding=0)


class EEM_App_GUI_Ctrl(ttk.Frame):
    '''Control frame (tab)'''

    def __init__(self, master, gui_main):
        ttk.Frame.__init__(self, master)

        self.gui_main = gui_main

        tclvar = gui_main.tclvar
        b_ctrls = self.b_ctrls = {}

        padw = []

        l = ttk.Label(self, text='ExpEther Operation')
        l.grid(column=0, row=0, columnspan=7, sticky=tk.EW)
        padh = l.winfo_reqheight() // 2

        for row, (label, var) in enumerate((('ExpEther id ', 'eeid'),
                                            ('group id', 'group'), ), start=1):
            l = ttk.Label(self, text=label)
            l.grid(column=1, row=row, columnspan=2, padx=2, sticky=tk.EW)

            padw.append(l.winfo_reqwidth() // 2)

            ttk.Label(self, textvariable=tclvar[var], width=20,
                      background='white', relief=tk.SOLID, padding=[2, 0]).\
                grid(column=3, row=row, sticky=tk.W, columnspan=5, pady=1)

        padr = self.grid_size()[1]

        for row, name in enumerate(('set_led', 'set_gid', 'del_gid',
                                    'audit', 'delete_force', 'delete',
                                    'perst', 'send_rst', ),
                                   start=padr + 1):

            if name == 'delete_force':
                b_ctrls[name] = ttk.Checkbutton(self, text='FORCE',
                                                # set other options later
                                                state=tk.DISABLED)
                continue

            command = getattr(gui_main, name)
            b = ttk.Button(self, text=name,
                           command=lambda gui_main=gui_main, command=command:
                           gui_main.after_idle(command),
                           state=tk.DISABLED)
            b.grid(column=2, row=row, columnspan=3, pady=1)

            b_ctrls[name] = b

        padw.append(b.winfo_reqwidth() // 3)
        padw = max(padw)

        for col in range(self.grid_size()[0]):
            f = ttk.Frame(self, width=padw, height=padh)
            f.grid(column=col, row=padr, sticky=tk.EW)

        # UID LED
        f_uid = ttk.Frame(self)
        l_uid_mark = ttk.Label(f_uid,
                               text='\u25cf',  # or '\N{BLACK CIRCLE}', is '●'
                               foreground='gray')
        l_uid_mark.grid(column=0, row=0, sticky=tk.W, in_=f_uid)
        l_uid_text = ttk.Label(f_uid, text=UID_LED_Off)
        l_uid_text.grid(column=1, row=0, sticky=tk.W, in_=f_uid)

        # labels also toggle LED (works as button)
        for l in [f_uid, l_uid_mark, l_uid_text]:
            l.bind('<Button-1>', self._onButton_set_led)

        _gi = b_ctrls['set_led'].grid_info()
        col = int(_gi['column']) + int(_gi['columnspan'])
        row = int(_gi['row'])
        f_uid.grid(column=col, row=row, columnspan=3, sticky=tk.W)

        self.l_uid_mark = l_uid_mark
        self.l_uid_text = l_uid_text

        # delete -FORCE checkbutton
        b = b_ctrls['delete_force']
        b.configure(command=self._onToggle_delete_force,
                    variable=tclvar['delete_force'],
                    onvalue=True, offvalue=False)

        _gi = b_ctrls['delete'].grid_info()
        col = int(_gi['column']) + int(_gi['columnspan'])
        row = int(_gi['row'])
        b.grid(column=col, row=row, columnspan=3, sticky=tk.W)

        # API Version
        row = self.grid_size()[1]
        ttk.Label(self, justify=tk.LEFT, textvariable=tclvar['api_version']).\
            grid(column=col, columnspan=3, row=(row - 1), rowspan=2,
                 padx=2, sticky=tk.SE)

        self.grid_columnconfigure(col, weight=1)
        self.grid_rowconfigure(row, weight=1)

    def _onButton_set_led(self, ev=None):
        self.b_ctrls['set_led'].invoke()

    def _onToggle_delete_force(self):
        '''callback for FORCE checkbutton toggle'''
        gui_main = self.gui_main

        if gui_main.curr_dev.notif:
            if gui_main.tclvar['delete_force'].get():
                st = tk.NORMAL
            else:
                st = tk.DISABLED

        else:
            st = tk.NORMAL

        self.b_ctrls['delete'].configure(state=st)

    def refresh(self):
        '''refresh EE control button status'''

        curr_dev = self.gui_main.curr_dev

        admin = curr_dev.admin
        notif = curr_dev.notif
        monitor = curr_dev.monitor

        button_state = {}

        if not monitor:
            button_state_default = tk.DISABLED

            # button_state['delete'] = tk.DISABLED
            button_state['delete_force'] = tk.NORMAL

        elif admin:
            if notif:
                # admin and notif
                button_state_default = tk.NORMAL

                if curr_dev.status == 'eesv':
                    # button_state['set_gid'] = tk.NORMAL

                    if curr_dev.group == GID['eesv_default']:
                        button_state['del_gid'] = tk.DISABLED
                    # else:
                    #     button_state['del_gid'] = tk.NORMAL

                elif curr_dev.status == 'eeio':
                    if curr_dev.group == GID['eeio_default']:
                        # button_state['set_gid'] = tk.NORMAL
                        button_state['del_gid'] = tk.DISABLED
                    else:
                        button_state['set_gid'] = tk.DISABLED
                        # button_state['del_gid'] = tk.NORMAL

                button_state['delete'] = tk.DISABLED

            else:
                # admin and ! notif
                button_state_default = tk.DISABLED

                button_state['delete'] = tk.NORMAL
                button_state['delete_force'] = tk.NORMAL

        else:
            if notif:
                # ! admin and notif
                button_state_default = tk.DISABLED

                button_state['audit'] = tk.NORMAL
                button_state['delete_force'] = tk.NORMAL

            else:
                # ! admin and ! notif
                button_state_default = tk.DISABLED

                button_state['delete'] = tk.NORMAL
                button_state['delete_force'] = tk.NORMAL

        for bn, b in self.b_ctrls.items():
            b.configure(state=button_state.get(bn, button_state_default))

        self.gui_main.tclvar['delete_force'].set(False)

    def refresh_device_gone(self):
        for b in self.b_ctrls.values():
            b.configure(state=tk.DISABLED)

        self.gui_main.tclvar['delete_force'].set(False)

    def refresh_uid_led(self, status):
        '''called when UID LED status is changed'''

        if self.getboolean(status):
            self.l_uid_mark.configure(foreground='blue')
            self.l_uid_text.configure(text=UID_LED_On)
        else:
            self.l_uid_mark.configure(foreground='grey')
            self.l_uid_text.configure(text=UID_LED_Off)


class EEM_App_GUI_Log(ttk.Frame):
    '''Log frame for internal message etc.'''

    def __init__(self, master, gui_main):
        ttk.Frame.__init__(self, master)

        l_log = ttk.Label(self, text='Log')
        l_log.grid(column=0, row=0, sticky=tk.NW)

        t_log = ReadOnlyText(self, tabstyle='wordprocessor', wrap=tk.NONE)
        sv_log = TtkAutoScrollbar(self, command=t_log.yview,
                                  orient=tk.VERTICAL)
        sh_log = TtkAutoScrollbar(self, command=t_log.xview,
                                  orient=tk.HORIZONTAL)
        t_log.configure(xscrollcommand=sh_log.set,
                        yscrollcommand=sv_log.set)

        t_log.grid(column=0, row=1, sticky=tk.NSEW)
        sv_log.grid(column=1, row=1, sticky=tk.NS)
        sh_log.grid(column=0, row=2, sticky=tk.EW)

        ttk.Sizegrip(self).grid(column=1, row=2, sticky=tk.SE)

        self.grid_columnconfigure(t_log, weight=1)
        self.grid_rowconfigure(t_log, weight=1)

        for meth in ('insert', 'delete', 'index', 'mark_set', 'see', ):
            setattr(self, meth, getattr(t_log, meth))


class EEM_App_GUI_GID_Dialog(TtkDialog):
    '''set_gid dialog'''

    _RE_auto = re.compile('^(?:a(?:u(?:t(?:o)?)?)?)?$', re.IGNORECASE)

    def __init__(self, master, eeid, ee_status, groups):

        TtkDialog.__init__(self, master, buttons=('OK', 'Cancel', ))

        self.wm_title('Update group ID')

        self.ee_status = ee_status
        self.groups = groups

        self._vcmd = self.register(self._validate_gid)
        self.style = ttk.Style()

        ttk.Label(self, text='Update group ID').\
            grid(column=0, row=0, sticky=tk.EW, columnspan=2)

        for row, label in enumerate(('ExpEther id', 'New group id', ),
                                    start=1):
            ttk.Label(self, text=label).\
                grid(column=0, row=row, sticky=tk.EW, padx=2)

        TtkReadOnlyEntry(self, text=eeid).grid(column=1, row=1, pady=1)

        e_group = ttk.Entry(self, style='Col.TEntry', validate='key',
                            validatecommand=(self._vcmd, '%P'))
        e_group.grid(column=1, row=2, pady=1)
        self.e_group = e_group

        if ee_status == 'eesv':
            msg = "Enter group ID in range 16 to 4092 or 'auto'."
        else:
            msg = "Enter group ID in range 16 to 4092.\n" \
                  "group ID must be set on ExpEther Board."

        ttk.Label(self, text=msg, justify=tk.LEFT).\
            grid(column=0, row=3, columnspan=2, padx=2, sticky=tk.EW)

        e_group.bind('<Key-Return>', self._onReturn)
        self.bind('<Key-Escape>', lambda ev, self=self: self.dialog_end())

        self.after_idle(self._validate_gid, '')
        self.show(focus_to=e_group)

    def destroy(self):
        del self._vcmd
        TtkDialog.destroy(self)

    def wait(self):
        result = TtkDialog.wait(self)
        newgid = self.e_group.get()

        return result, newgid

    def _onReturn(self, ev):
        if self._validate_gid(self.e_group.get(), validate_value=True):
            self.dialog_end('OK')
        else:
            return              # ignore

    def _validate_gid(self, text, validate_value=False):

        valid = None
        if text == '':
            valid = False

        if self.ee_status == 'eesv':
            if text.isdigit():
                if GID['MIN'] <= int(text) <= GID['MAX']:
                    valid = True
                else:
                    valid = False

            elif self._RE_auto.match(text):
                if text == 'auto':
                    valid = True
                else:
                    valid = False

            else:
                # valid = None
                pass

        else:                   # eeio
            if text.isdigit():
                id = int(text)
                if id in self.groups and GID['MIN'] <= id <= GID['MAX']:
                    valid = True
                else:
                    valid = False

            else:
                # valid = None
                pass

        if validate_value:
            return valid

        elif valid is None:
            self.bell()
            return False

        elif valid:
            self.style.configure('Col.TEntry', foreground='default')
            self.buttons['OK'].configure(state=tk.NORMAL)

        else:
            self.style.configure('Col.TEntry', foreground='red')
            self.buttons['OK'].configure(state=tk.DISABLED)

        return True


#


def main():
    EEM_App_GUI().mainloop()

#


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, '')
    # _os_encoding = locale.getpreferredencoding()

    main()
