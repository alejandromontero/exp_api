CREATE DATABASE IF NOT EXISTS expether;

use expether;

CREATE TABLE IF NOT EXISTS servers (
	name varchar(255) NOT NULL,
	number int,
	PRIMARY KEY (name)
	);

CREATE TABLE IF NOT EXISTS workloads (
	id int NOT NULL AUTO_INCREMENT,
	name varchar(255) NOT NULL,
	user varchar(255) NOT NULL,
	description varchar(255),
	assigned_to varchar(255),
	PRIMARY KEY (id),
	FOREIGN KEY (assigned_to) REFERENCES servers(name)
	);

CREATE TABLE IF NOT EXISTS hardware_requirements (
	workload_id int NOT NULL,
	hardware_type varchar(255) NOT NULL,
	model varchar(255),
	PRIMARY KEY (workload_id,hardware_type),
	FOREIGN KEY (workload_id) REFERENCES workloads(id)
	);

CREATE TABLE IF NOT EXISTS capacity_requirements (
	workload_id int NOT NULL,
	requirement_name varchar(255) NOT NULL,
	unit varchar(255),
	value int NOT NULL,
	PRIMARY KEY(workload_id,requirement_name),
	FOREIGN KEY (workload_id) REFERENCES workloads(id)
	);

CREATE TABLE IF NOT EXISTS net_card (
	id varchar(255) NOT NULL,
	gid int NOT NULL,
	assigned_to varchar(255) NULL,
	PRIMARY KEY(id),
	FOREIGN KEY(assigned_to) REFERENCES servers(name)
	);


CREATE TABLE IF NOT EXISTS hardware_cards (
	id varchar(255) NOT NULL,
	hardware varchar(255),
	model varchar(255),
	pcie_vendor_id varchar(255),
	pcie_device_id varchar(255),
	PRIMARY KEY (id)
	);

CREATE TABLE IF NOT EXISTS hardware_capacity (
	hardware_id varchar(255) NOT NULL,
	capacity_name varchar(255) NOT NULL,
	unit varchar(255),
	value int NOT NULL,
	PRIMARY KEY(hardware_id,capacity_name),
	FOREIGN KEY(hardware_id) REFERENCES hardware_cards(id)
	);

CREATE TABLE IF NOT EXISTS assignments (
	hardware_card varchar(255) NOT NULL,
	server_card varchar (255) NOT NULL,
	workload int NOT NULL,
	PRIMARY KEY (hardware_card,server_card,workload),
	FOREIGN KEY (hardware_card) REFERENCES hardware_cards(id),
	FOREIGN KEY (server_card) REFERENCES net_card(id),
	FOREIGN KEY (workload) REFERENCES workloads(id)
	);

CREATE TABLE IF NOT EXISTS assigned_capacity (
	hardware_card varchar(255) NOT NULL,
	server_card varchar (255) NOT NULL,
	workload int NOT NULL,
	capacity_name varchar(255) NOT NULL,
	unit varchar(255) NOT NULL,
	value int,
	PRIMARY KEY (hardware_card,server_card,workload,capacity_name),
	FOREIGN KEY (hardware_card) REFERENCES hardware_cards(id),
	FOREIGN KEY (server_card) REFERENCES net_card(id),
	FOREIGN KEY (workload) REFERENCES workloads(id)
	);
