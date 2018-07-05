import os
import connexion
from connexion.resolver import RestyResolver
from flask_injector import FlaskInjector
from services.elasticsearch.elasticsearch import (
        ElasticSearchIndex,
        ElasticSearchFactory
    )


def configure(binder):
    # workloadIndex = Key('workloadIndex')
    binder.bind(
        ElasticSearchIndex,
        to=ElasticSearchIndex(
            ElasticSearchFactory(
                os.environ['ELASTICSEARCH_HOST'],
                os.environ['ELASTICSEARCH_PORT'],
            ),
        )
    )
    return binder


if __name__ == '__main__':
    app = connexion.FlaskApp(__name__, specification_dir='appi_descriptor/')
    app.add_api('expether_api.yaml', resolver=RestyResolver('api'))
    FlaskInjector(app=app.app, modules=[configure])
    app.run(port=5555)
