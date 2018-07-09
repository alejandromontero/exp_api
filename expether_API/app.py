import os
import connexion
from connexion.resolver import RestyResolver
from flask_injector import FlaskInjector
from services.mysql.mysqlDB import (
        MySQLFactory,
        MySQL
    )


def configure(binder):
    # workloadIndex = Key('workloadIndex')
    binder.bind(
        MySQL,
        to=MySQL(MySQLFactory(
                os.environ['HOST'],
                os.environ['MYSQL_USER'],
                os.environ['MYSQL_PASSWORD'],
                os.environ['MYSQL_DATABASE'],
            ),
        )
    )
    return binder


if __name__ == '__main__':
    app = connexion.FlaskApp(__name__, specification_dir='appi_descriptor/')
    app.add_api('expether_api.yaml', resolver=RestyResolver('api'))
    FlaskInjector(app=app.app, modules=[configure])
    app.run(port=5555)
