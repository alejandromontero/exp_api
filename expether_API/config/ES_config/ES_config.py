assignament_mapping = {
		"settings": {
			"number_of_shards": 1,
			"number_of_replicas": 1
		},
        "assignament": {
		"properties": {
			"id": {"type": "integer"},
                        "workloadID": {"type": "integer"},
                        "blockID": {"type": "integer"},
		}
	}
}
workload_mapping = {
		"settings": {
			"number_of_shards": 1,
			"number_of_replicas": 1
		},
        "workload": {
		"properties": {
			"id": {"type": "integer"},
			"requirements": {"type": "array"},
                        "status": {"type": "string"}
		}
	}
}
block_mapping = {
		"settings": {
			"number_of_shards": 1,
			"number_of_replicas": 1
		},
        "assignament": {
		"properties": {
			"id": {"type": "string"},
			"hardware": {"type": "string"}
		}
	}
}
