use expether;

CREATE TABLE IF NOT EXISTS workloads (
	id int NOT NULL AUTO_INCREMENT,
	name varchar(255) NOT NULL,
	requirements varchar(255),
	active bool,
	PRIMARY KEY (id));

CREATE TABLE IF NOT EXISTS box_tags (
	id varchar(255) NOT NULL,
	hardware varchar(255),
	PRIMARY KEY (id));

