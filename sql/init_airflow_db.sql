-- Runs on first Postgres volume creation. Creates the Airflow metadata database
-- in the same instance as the pipeline data.
CREATE DATABASE airflow OWNER dss150p_user;