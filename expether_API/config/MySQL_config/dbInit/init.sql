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
	requirement varchar(255),
	assigned_to varchar(255),
	active bool DEFAULT 0,
	PRIMARY KEY (id),
	FOREIGN KEY (assigned_to) REFERENCES servers(name)
	);

CREATE TABLE IF NOT EXISTS net_card (
	id varchar(255) NOT NULL,
	gid int NOT NULL,
	assigned_to varchar(255),
	PRIMARY KEY(id),
	FOREIGN KEY(assigned_to) REFERENCES servers(name)
	);


CREATE TABLE IF NOT EXISTS box_tags (
	id varchar(255) NOT NULL,
	hardware varchar(255),
	model varchar(255),
	pcie_vendor_id varchar(255),
	pcie_device_id varchar(255),
	assigned_to varchar(255),
	PRIMARY KEY (id),
	FOREIGN KEY(assigned_to) REFERENCES net_card(id)
	);

CREATE TABLE IF NOT EXISTS assignaments (
	hardware_box varchar(255) NOT NULL,
	server_card varchar (255) NOT NULL,
	workload int NOT NULL,
	PRIMARY KEY (hardware_box,server_card,workload),
	FOREIGN KEY (hardware_box) REFERENCES box_tags(id),
	FOREIGN KEY (server_card) REFERENCES net_card(id),
	FOREIGN KEY (workload) REFERENCES workloads(id)
	);