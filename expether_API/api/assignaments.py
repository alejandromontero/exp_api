from services.elasticsearch.elasticsearch import ElasticSearchIndex
from flask_injector import inject
from ES_config.ES_config import assignament_mapping as mapping
from flask import (
        make_response,
        abort
)

__index = "assignaments"
__doc_type = "assignament"


@inject
def get_all_assignaments(indexer: ElasticSearchIndex):
    return indexer.get_all_docs(__index, __doc_type, mapping)


@inject
def get_assignament(id, indexer: ElasticSearchIndex):
    hits = indexer.get_doc(id, __index, __doc_type, mapping)
    hits = hits["hits"]["hits"]
    if hits:
        return hits
    else:
        error = {}
        error["detail"] = "The requested ID does not exist"
        error["status"] = "404"
        error["title"] = "Not Found"
        return error


@inject
def assign(assignament, indexer: ElasticSearchIndex):
    res = indexer.add_doc(
            assignament, __index, __doc_type, mapping)
    if res:
        return 200
    else:
        error = {}
        error["detail"] = "The requested ID already exists on the server"
        error["status"] = "304"
        error["title"] = "Not Found"
        return error


@inject
def eliminate_assignament(id, indexer: ElasticSearchIndex):
    res = indexer.eliminate_doc(id, __index, __doc_type, mapping)
    if res:
        return 200
    else:
        error = {}
        error["detail"] = "The requested ID does not exist"
        error["status"] = "404"
        error["title"] = "Not Found"
        return error
