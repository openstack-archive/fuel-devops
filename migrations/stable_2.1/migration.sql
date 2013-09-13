--BEGIN;
-- devops_node
ALTER TABLE devops_node RENAME COLUMN externalmodel_ptr_id TO id ;
ALTER TABLE devops_node ADD COLUMN name character varying(255);
ALTER TABLE devops_node ADD COLUMN uuid character varying(255);
ALTER TABLE devops_node ADD COLUMN environment_id integer;

UPDATE devops_node SET name = devops_externalmodel.name, uuid = devops_externalmodel.uuid, environment_id = devops_externalmodel.environment_id
	FROM devops_externalmodel
	WHERE devops_node.id = devops_externalmodel.id;

ALTER TABLE devops_node ALTER COLUMN id SET NOT NULL;
ALTER TABLE devops_node ALTER COLUMN name SET NOT NULL;
ALTER TABLE devops_node ALTER COLUMN uuid SET NOT NULL;

-- devops_volume
ALTER TABLE devops_volume RENAME COLUMN externalmodel_ptr_id TO id ;
ALTER TABLE devops_volume ADD COLUMN name character varying(255);
ALTER TABLE devops_volume ADD COLUMN uuid character varying(255);
ALTER TABLE devops_volume ADD COLUMN environment_id integer;

UPDATE devops_volume SET name = devops_externalmodel.name, uuid = devops_externalmodel.uuid, environment_id = devops_externalmodel.environment_id
	FROM devops_externalmodel
	WHERE devops_volume.id = devops_externalmodel.id;

ALTER TABLE devops_volume ALTER COLUMN id SET NOT NULL;
ALTER TABLE devops_volume ALTER COLUMN name SET NOT NULL;
ALTER TABLE devops_volume ALTER COLUMN uuid SET NOT NULL;

-- devops_network
ALTER TABLE devops_network RENAME COLUMN externalmodel_ptr_id TO id ;
ALTER TABLE devops_network ADD COLUMN name character varying(255);
ALTER TABLE devops_network ADD COLUMN uuid character varying(255);
ALTER TABLE devops_network ADD COLUMN environment_id integer;

UPDATE devops_network SET name = devops_externalmodel.name, uuid = devops_externalmodel.uuid, environment_id = devops_externalmodel.environment_id
	FROM devops_externalmodel
	WHERE devops_network.id = devops_externalmodel.id;

ALTER TABLE devops_network ALTER COLUMN id SET NOT NULL;
ALTER TABLE devops_network ALTER COLUMN name SET NOT NULL;
ALTER TABLE devops_network ALTER COLUMN uuid SET NOT NULL;

DROP TABLE devops_externalmodel CASCADE;

CREATE SEQUENCE devops_network_id_seq
  INCREMENT 1
  MINVALUE 1
  MAXVALUE 9223372036854775807
  START 1081
  CACHE 1;
ALTER TABLE devops_network ALTER COLUMN id SET DEFAULT nextval('devops_network_id_seq'::regclass);

CREATE SEQUENCE devops_node_id_seq
  INCREMENT 1
  MINVALUE 1
  MAXVALUE 9223372036854775807
  START 1080
  CACHE 1;
ALTER TABLE devops_node ALTER COLUMN id SET DEFAULT nextval('devops_node_id_seq'::regclass);

CREATE SEQUENCE devops_volume_id_seq
  INCREMENT 1
  MINVALUE 1
  MAXVALUE 9223372036854775807
  START 1099
  CACHE 1;
ALTER TABLE devops_volume ALTER COLUMN id SET DEFAULT nextval('devops_volume_id_seq'::regclass);

--END;