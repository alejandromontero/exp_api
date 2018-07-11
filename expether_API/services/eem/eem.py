import os

__eemcly = os.path.join(
        os.path.dirname(__file__),
        '..', 'eemcli', 'eemcli.py'
        )


class EEMFactory(object):
    def __init__(self, conf):
        self.conf = conf


class EEM(object):
    def __init__(
            self,
            EEM_factory: EEMFactory,
    ):
        self.EEM_factory = EEMFactory
        self.instance = None
