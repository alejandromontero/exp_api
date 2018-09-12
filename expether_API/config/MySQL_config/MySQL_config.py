workload_mapping = {
        "id": "int",
        "name": "varchar(255)",
        "user": "varchar(255)",
        "description": "varchar(255)",
        "assigned_to": "varchar(255)"
        }

workload_mapping_extended = {
        "id": "int",
        "name": "varchar(255)",
        "user": "varchar(255)",
        "description": "varchar(255)",
        "assigned_to": "varchar(255)",
        "requirements": "List"
        }

requirement_mapping = {
        "workload_id": "int",
        "hardware_type": "varchar(255)",
        "model": "varchar(255)",
        "capacity": "int"
        }

hardware_card_mapping = {
        "id": "varchar(255)",
        "hardware": "varchar(255)",
        "model": "varchar(255)",
        "pcie_vendor_id": "varchar(255)",
        "pcie_device_id": "varchar(255)"
        }

net_card_mapping = {
        "id": "varchar(255)",
        "gid": "int",
        "assigned_to": "varchar(255)"
        }

servers_mapping = {
        "id": "varchar(255)",
        "name": "varchar(255)",
        "number": "int"
        }

assignment_mapping = {
        "hardware_card": "varchar(255)",
        "server_card": "varchar(255)",
        "workload": "int"
        }
