import os
from subprocess import (
        Popen,
        PIPE
    )


class EEMFactory(object):
    def __init__(self, conf, clientPath):
        self.conf = conf
        self.clientBasePath = clientPath
        self.clientPath = os.path.join(
                self.clientBasePath,
                "eemcli", "eemcli.py"
                )

    def get_base_cmd(self):
        return ['python2', self.clientPath, '-c', self.conf]


class EEM(object):
    def __init__(
            self,
            EEM_factory: EEMFactory,
    ):
        self.EEM_factory = EEM_factory
        self.cmd = None

    def make_request(self, expanded_cmd):
        return Popen(
                self.get_cmd()+expanded_cmd,
                stdout=PIPE).communicate()[0].decode('ascii')

    def get_cmd(self):
        if not self.cmd:
            self.cmd = self.EEM_factory.get_base_cmd()
        return self.cmd

    def get_list(self):
        expanded_cmd = ['get', '--list']
        return self.make_request(expanded_cmd)

    def get_box_info(self, id):
        expanded_cmd = ['get', '--id', id]
        return self.make_request(expanded_cmd)
