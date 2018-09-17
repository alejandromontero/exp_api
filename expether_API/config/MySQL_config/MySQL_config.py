workload_keys = [
        "id",
        "name",
        "user",
        "description",
        "assigned_to"
        ]


hardware_requirements_keys = [
        "requirement_id",
        "workload_id",
        "hardware_type",
        "model"
        ]

capacity_requirements_keys = [
        "workload_id",
        "requirement_id",
        "requirement_name",
        "value",
        "unit"
        ]

hardware_card_keys = [
        "id",
        "hardware",
        "model",
        "pcie_vendor_id",
        "pcie_device_id"
        ]

hardware_capacity_keys = [
        "hardware_id",
        "capacity_name",
        "unit",
        "value"
        ]

net_card_keys = [
        "id",
        "gid",
        "assigned_to"
        ] 

servers_keys = [
        "id",
        "name",
        "number"
        ]

assignment_keys = [
        "hardware_card",
        "server_card",
        "workload"
        ]

assigned_capacity = [
        "hardware_card",
        "server_card",
        "workload",
        "capacity_name",
        "unit",
        "value"
        ]
