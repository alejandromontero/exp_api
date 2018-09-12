workload_keys = [
        "id",
        "name",
        "user",
        "description",
        "assigned_to"
        ]

workload_keys_extended = [
        "id",
        "name",
        "user",
        "description",
        "assigned_to",
        "requirements"
        ]

hardware_requirements_keys = [
        "workload_id",
        "hardware_type",
        "model"
        ]

capacity_requirements_keys = [
        "workload_id",
        "requirement_name",
        "unit",
        "value"
        ]

hardware_card_keys = [
        "id",
        "hardware",
        "model",
        "pcie_vendor_id",
        "pcie_device_id"
        ]

hardware_capacity = [
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
