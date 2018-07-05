from elasticsearch import Elasticsearch


class ElasticSearchFactory(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def create(self):
        return Elasticsearch(
            [{'host': self.host, 'port': self.port}]
        )


class ElasticSearchIndex(object):
    def __init__(
            self,
            elastic_factory: ElasticSearchFactory,
    ):
        self.elastic_factory = elastic_factory
        self.instance = None

    def connection(self, index, mapper) -> Elasticsearch:
        if not self.instance:
            self.instance = self.elastic_factory.create()
            if not self.instance.indices.exists(index):
                self.instance.indices.create(
                    index=index,
                    body=mapper
                )

        return self.instance

    def get_doc(self, id_doc, index, doc_type, mapper):
        return self.connection(index, mapper).search(
            index=index,
            doc_type=doc_type,
            scroll='1m',
            body={
                "query": {
                    "match": {
                        "id": id_doc,
                    }
                }
            }
        )

    def get_all_docs(self, index, doc_type, mapper):
        docs_queried = self.connection(index, mapper).search(
            index=index,
            doc_type=doc_type,
            scroll='1m',
            body={
                "query": {
                    "match_all": {}
                }
            }
        )
        return docs_queried

    def add_doc(self, assignament, index, doc_type, mapper):
        hits = self.get_doc(assignament["id"], index, doc_type, mapper)
        if not hits["hits"]["hits"]:
            self.connection(index, mapper).create(
                index=index,
                doc_type=doc_type,
                id=assignament["id"],
                body=assignament)
            return True
        else:
            return False

    def eliminate_doc(self, id_doc, index, doc_type, mapper):
        hits = self.get_doc(id_doc, index, doc_type, mapper)
        if hits["hits"]["hits"]:
            self.connection(index, mapper).delete(
                index=index,
                doc_type=doc_type,
                id=id_doc
            )
            return True
        else:
            return False

class ElasticAssignaments(object):
    def __init__(
            self,
            index: ElasticSearchIndex
    ):
        self.index = index

    def get_all_docs(self):
        return self.index.get_all_docs()

    def get_doc(self, id_doc):
        return self.index.get_doc(id_doc)

    def add_doc(self, assignament):
        return self.index.add_doc(assignament)

    def eliminate_doc(self, id_doc):
        return self.index.eliminate_doc(id_doc)


class ElasticWorkloads(object):
    def __init__(
            self,
            index: ElasticSearchIndex
    ):
        self.index = index

    def get_all_docs(self):
        return self.index.get_all_docs()

    def get_doc(self, id_doc):
        return self.index.get_doc(id_doc)

    def add_doc(self, assignament):
        return self.index.add_doc(assignament)

    def eliminate_doc(self, id_doc):
        return self.index.eliminate_doc(id_doc)


class ElasticBlocks(object):
    def __init__(
            self,
            index: ElasticSearchIndex
    ):
        self.index = index

    def get_all_docs(self):
        return self.index.get_all_docs()

    def get_doc(self, id_doc):
        return self.index.get_doc(id_doc)

    def add_doc(self, assignament):
        return self.index.add_doc(assignament)

    def eliminate_doc(self, id_doc):
        return self.index.eliminate_doc(id_doc)

