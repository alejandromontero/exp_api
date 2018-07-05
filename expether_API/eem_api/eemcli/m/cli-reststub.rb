#class Module
#  def singleton_method_added(name)
#    puts "singleton_method #{name} was added"
#  end
#  def method_added(name)
#    puts "method #{name} was added"
#  end
#end

module RestC

  #
  # override(redefine) stub
  #
  def self.get_gids(ds)
    s = <<'E'
{
    "groups": [
        {
            "id": "17"
        },
        {
            "id": "4000"
        }
    ]
}
E
    s
  end

  #
  #
  def self.get_ids(ds)
    s = <<'E'
{
    "devices": [
        {
            "id": "0x001122334455"
        },
        {
            "id": "0x021122334400"
        },
        {
            "id": "0x0011dd33cc00"
        }
    ],
    "timestamp": "1429979349749"
}
E
    s
  end

  #
  # @return JSON string or raise error.
  #
  def self.get_ids_detail(ds, gid=nil)
    # 3.3.7 List Devices
    #       List Devices Details
    # 3.3.8 Show Device
    # See sample ticket:68#comment:21
    #            ticket:74#comment:4
    s = <<'E'
{
    "devices": [
    ],
    "timestamp": "1429979349749"
}
E
    s = <<'E'
{
    "devices": [
        {
            "id": "0x0011dd33cc00",
            "status": "eeio",
            "type": "1g", 
            "update_time": "1428979450777",
            "notification_status0": [
                "down", "down"
            ],
            "notification_status1": [
                "down", "down"
            ],
            "group_id": "17",
            "uid_switch_status": "off",
            "link_status0": "down",
            "link_status1": "down",
            "path_status0": "down",
            "path_status1": "down",
            "eesv_connection_status": "down"
        },
        {
            "id": "0x001122334455",
            "status": "eesv",
            "type": "10g", 
            "update_time": 1428979349749,
            "notification_status0": [
                "up", "up"
            ],
            "notification_status1": [
                "down", "down"
            ],
            "downstream_ports": [
                {
                    "downstream_port_id": "0", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "1", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "2", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "3", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "4", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "5", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "6", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "7", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }
            ], 
            "group_id": "17",
            "uid_switch_status": "on",
            "link_status0": "up",
            "link_status1": "down"
        },
        {
            "id": "0x021122334400",
            "status": "eeio",
            "type": "10g", 
            "update_time": 1428979350749,
            "notification_status0": [
                "up", "up"
            ],
            "notification_status1": [
                "up", "up"
            ],
            "group_id": "17",
            "uid_switch_status": "off",
            "link_status0": "up",
            "link_status1": "up"
        },
        {
            "admin_status": "enabled", 
            "compatibility": [
                "default"
            ], 
            "device_id": "0x1d", 
            "downstream_ports": [
                {
                    "downstream_port_id": "0", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:11:22:33:ae:18"
                }, 
                {
                    "downstream_port_id": "1", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "2", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "3", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "4", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "5", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "6", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "7", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "8", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "9", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "10", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "11", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "12", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "13", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "14", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }, 
                {
                    "downstream_port_id": "15", 
                    "eeio_connection_status": "down", 
                    "eeio_mac_address": "00:00:00:00:00:00"
                }
            ], 
            "ee_version": "v1.0", 
            "eeprom_data_version": "0x0", 
            "eesv_type": "na", 
            "encryption": [
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled", 
                "disabled"
            ], 
            "fpga_version": "0x1", 
            "group_id": "17", 
            "host_model": "", 
            "host_serial_number": "", 
            "id": "0x001122338654", 
            "interrupt_vector": "0x10", 
            "link_status0": "up", 
            "link_status1": "up", 
            "mac_address": "00:11:22:33:86:54", 
            "max_eeio_count": "16", 
            "model": "", 
            "monitoring_status": "enabled", 
            "multi_mac_addresses": "disabled", 
            "notification_status0": [
                "up", 
                "up"
            ], 
            "notification_status1": [
                "down", 
                "down"
            ], 
            "pcie_link_width": "x8", 
            "power_status": "on", 
            "revision": "0x0", 
            "serial_number": "", 
            "status": "eesv", 
            "type": "40g", 
            "uid_switch_status": "off", 
            "update_time": "1448961731001", 
            "vlan_tagging": "disabled"
        }
    ],
    "timestamp": "1429979349749"
}
E
    s
  end

  #
  #
  def self.get_uid_jsonstr(id, ds)
    led = (Random.rand(1000000) % 5 == 0 ? "on" : "off")
    s = <<"E"
{
    "uid_led_status": "#{led}"
}
E
    s
  end

  #
  #
  def self.get_rotary_jsonstr(id, ds)
    s = <<'E'
{
    "rotary_switch_status": "14"
}
E
    s
  end

end
