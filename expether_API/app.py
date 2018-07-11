import os
import connexion
from connexion.resolver import RestyResolver
from utilities.DATParser import DATParser
from flask_injector import FlaskInjector
from services.mysql.mysqlDB import (
        MySQLFactory,
        MySQL
    )
from services.eem.eem import (
        EEMFactory,
        EEM
    )

__eemConfigFile = ""
__eemBasePath = ""


def configure(binder):
    binder.bind(
        MySQL,
        to=MySQL(MySQLFactory(
                os.environ['MYSQL_HOST'],
                os.environ['MYSQL_USER'],
                os.environ['MYSQL_PASSWORD'],
                os.environ['MYSQL_DATABASE'],
            ),
        )
    )
    binder.bind(
        EEM,
        to=EEM(EEMFactory(
            __eemConfigFile,
            __eemBasePath,
            ),
        )
    )
    return binder


if __name__ == '__main__':
    # Load configuration
    __eemConfigFile = os.path.join(
        os.path.dirname(__file__),
        "config", "EEM", "eemcli.conf"
        )
    __eemBasePath = os.path.join(
        "/", "opt", "eemCli"
        )

    app = connexion.FlaskApp(__name__, specification_dir='appi_descriptor/')
    app.add_api('expether_api.yaml', resolver=RestyResolver('api'))
    FlaskInjector(app=app.app, modules=[configure])
    app.run(port=5555)
