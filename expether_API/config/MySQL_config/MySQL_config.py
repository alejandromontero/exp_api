workload_mapping = {
        "id": "int",
        "name": "varchar(255)",
        "requirement": "varchar(255)",
        "assigned_to": "varchar(255)",
        "active": "tinyint(1)"
        }

hardware_card_mapping = {
        "id": "varchar(255)",
        "hardware": "varchar(255)",
        "model": "varchar(255)",
        "pcie_vendor_id": "varchar(255)",
        "pcie_device_id": "varchar(255)",
        "assigned_to":  "varchar(255)"
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
