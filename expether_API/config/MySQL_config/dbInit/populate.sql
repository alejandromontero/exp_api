INSERT INTO servers(name,number)
VALUES
("bscdc12", "12"),
("bscdc13", "13"),
("bscdc14", "14"),
("bscdc15", "15"),
("bscdc16", "16"),
("brain1", "01"),
("brain2", "02");

INSERT INTO workloads(name,requirement,assigned_to)
VALUES
("test1", "FPGA", "bscdc12"), 
("test2", "GPU", "bscdc13"), 
("test3", "NMVE", "bscdc14"); 

INSERT INTO net_card(id,gid,assigned_to)
VALUES
("0x743a65046d30", "1012", "bscdc12"),
("0x743a65044350", "1013", "bscdc13"),
("0x743a65046d32", "1014", "bscdc14"),
("0x743a65046d2e", "1015", "bscdc15"),
("0x743a65046d34", "1016", "bscdc16"),
("0x743a6504489a", "2001", "brain1"),
("0x743a650441b2", "2002", "brain2");

INSERT INTO hardware_cards(id,hardware,model,pcie_vendor_id,pcie_device_id)
VALUES
("0x8cdf9d9122b6", "FPGA", "Nallatech 510t", "10b5", "8732"),
("0x8cdf9d9122b0", "FPGA", "Bittware A10PL4", "10b5", "8718"),
("0x8cdf9d9122b2", "OPTANE", "Device 2701","8086","2701"),
("0x8cdf9dd32010", "FPGA", "PAC10", "8086", "09c4"),
("0x8cdf9dd32012", "GPU", "Tesla K40", "10de", "1024");

INSERT INTO assignaments
VALUES
("0x8cdf9d9122b0", "0x743a65046d30", 1);
