import os
from subprocess import (
        Popen,
        PIPE
        )
from services.elasticsearch.elasticsearch import ElasticSearchIndex
from flask_injector import inject
from config.ES_config.ES_config import block_mapping as mapping
from flask import (
        make_response,
        abort
)

__index = "assignments"
__doc_type = "assignment"
__eemcly = os.path.join(
            os.path.dirname(__file__),
            '..', 'eem_api', 'eemcli', 'eemcli.py'
          )


@inject
def get_all_boxes(indexer: ElasticSearchIndex):
    cmd = ['python2', __eemcly, 'get', '--list', '--status', 'eeio']
    out = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf-8').split()
    ids = []
    for id in out:
        ids.append(id)
    return ids


@inject
def get_box_info(id, indexer: ElasticSearchIndex):
    ids = get_all_boxes(indexer)
    if ids:
        cmd = ['python2', __eemcly, 'get', '--id', id]
        out = Popen(cmd, stdout=PIPE).communicate()[0].decode('utf-8').split()
        out_info = []
        for line in out:
            out_info.append(line)
        return out_info
    else:
        error = {}
        error["detail"] = "The requested ID does not exist on the server"
        error["status"] = "304"
        error["title"] = "Not Found"
        return error

    

@inject
def create_tag(assignment, indexer: ElasticSearchIndex):
    res = indexer.add_doc(
            assignment, __index, __doc_type, mapping)
    if res:
        return 200
    else:
        error = {}
        error["detail"] = "The requested ID already exists on the server"
        error["status"] = "304"
        error["title"] = "Not Found"
        return error


@inject
def eliminate_tag(id, indexer: ElasticSearchIndex):
    res = indexer.eliminate_doc(id, __index, __doc_type, mapping)
    if res:
        return 200
    else:
        error = {}
        error["detail"] = "The requested ID does not exist"
        error["status"] = "404"
        error["title"] = "Not Found"
        return error
