import subprocess
import snowflake.connector
import yaml
import os
import datetime

profile_file = open("../profiles.yml", "r")
test_profile = yaml.safe_load(profile_file)['my-snowflake-db']['outputs']['TEST']
con = snowflake.connector.connect(
    user=test_profile['user'],
    password=test_profile['password'],
    account=test_profile['account'],
    warehouse=test_profile['warehouse']
)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
print(ROOT_DIR)

def init_db_and_dbt():
    con.cursor().execute("CREATE OR REPLACE DATABASE {}".format(test_profile['database']))
    con.cursor().execute("USE DATABASE {}".format(test_profile['database']))
    con.cursor().execute("CREATE OR REPLACE SCHEMA {}_STG".format(test_profile['schema']))
    con.cursor().execute("USE SCHEMA {}_STG".format(test_profile['schema']))
    con.cursor().execute("CREATE OR REPLACE TABLE {}.{}_STG.ADD_CLIENTS (\
                        ID NUMBER(38,0),\
	                    FIRST_NAME STRING,\
	                    LAST_NAME STRING, \
	                    BIRTHDATE DATE, \
                        LOADED_AT TIMESTAMP_NTZ(9))".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("CREATE OR REPLACE TABLE PERSO.ARO_STG.SOURCE_CLIENTS (\
                        ID NUMBER(38,0),\
	                    FIRST_NAME STRING,\
	                    LAST_NAME STRING, \
	                    BIRTHDATE DATE, \
                        LOADED_AT TIMESTAMP_NTZ(9))")
    os.chdir(os.path.join(ROOT_DIR, '..'))
    subprocess.run(["dbt", "deps"])

def test_initialization_without_data():
    init_db_and_dbt()
    # 1. When relation does not exist incremental stream must do a full-refresh and then include the following line 
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout 

def test_initialization_with_data():
    init_db_and_dbt()
    # 1. When relation does not exist incremental stream must do a full-refresh and then include the following line 
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout 

def test_full_refresh_without_relation():
    init_db_and_dbt()
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    # 1. Test Full Refresh
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", '--full-refresh', "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout

def test_full_refresh_with_relation():
    init_db_and_dbt()
    # 1. First Data Merge
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    # 2. Test Full Refresh
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", '--full-refresh', "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout

def test_merge_ref():
    init_db_and_dbt()

    # 1. Test first Data Merge
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)

    # 3. Test Merge on the same key
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1988-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout 

def test_incremental_messages_source():
    init_db_and_dbt()
    result = subprocess.run(["dbt", "run", "--select", "dwh_source", "--target", "TEST"], capture_output=True, text=True)
    assert "Completed successfully" in result.stdout
    con.cursor().execute("INSERT INTO PERSO.ARO_STG.SOURCE_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', CURRENT_TIMESTAMP)")
    result = subprocess.run(["dbt", "run", "--select", "dwh_source", "--target", "TEST"], capture_output=True, text=True)
    assert "Completed successfully" in result.stdout 
    con.cursor().execute("INSERT INTO PERSO.ARO_STG.SOURCE_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', CURRENT_TIMESTAMP)")
    result = subprocess.run(["dbt", "run", "--select", "dwh_source", "--target", "TEST"], capture_output=True, text=True)
    assert "Completed successfully" in result.stdout 

def test_merge_update():
    init_db_and_dbt()
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    con.cursor().execute("UPDATE {}.{}_STG.ADD_CLIENTS SET BIRTHDATE='1981-01-10', \
                         LOADED_AT=CURRENT_TIMESTAMP WHERE ID=1".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout

def test_merge_delete():
    init_db_and_dbt()
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    con.cursor().execute("DELETE FROM {}.{}_STG.ADD_CLIENTS WHERE ID=1".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_ref", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    assert con.cursor().execute("SELECT COUNT(*) FROM \
                                {}.{}_DWH.CONSO_CLIENT".format(test_profile['database'],
                                                               test_profile['schema'])).fetchone()[0] == 1
    
def test_insert_without_key():
    init_db_and_dbt()
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-15', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    subprocess.run(["dbt", "run", "--select", "dwh_insert", "--target", "TEST"], capture_output=True, text=True)
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_insert", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    result = subprocess.run(["dbt", "test", "--select", "conso_client_insert", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout

def test_update_without_key():
    init_db_and_dbt()
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    subprocess.run(["dbt", "run", "--select", "dwh_insert", "--target", "TEST"], capture_output=True, text=True)
    con.cursor().execute("UPDATE {}.{}_STG.ADD_CLIENTS SET BIRTHDATE='1981-01-10', \
                         LOADED_AT=CURRENT_TIMESTAMP WHERE ID=1".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_insert", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    assert con.cursor().execute("SELECT BIRTHDATE FROM \
                                {}.{}_DWH.CONSO_CLIENT_INSERT WHERE ID=1".format(test_profile['database'],
                                                               test_profile['schema'])).fetchone()[0] == datetime.date(1981, 1, 10)

def test_delete_without_key():
    init_db_and_dbt()
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (0, 'JAMES', 'SMITH', '1988-03-16', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    con.cursor().execute("INSERT INTO {}.{}_STG.ADD_CLIENTS VALUES (1, 'ANNIE', 'SMITH', '1984-06-12', \
                         CURRENT_TIMESTAMP)".format(test_profile['database'],test_profile['schema']))
    subprocess.run(["dbt", "run", "--select", "dwh_insert", "--target", "TEST"], capture_output=True, text=True)
    con.cursor().execute("DELETE FROM {}.{}_STG.ADD_CLIENTS WHERE ID=1".format(test_profile['database'],test_profile['schema']))
    result = subprocess.run(["dbt", "run", "--select", "dwh_insert", "--target", "TEST"], capture_output=True, text=True)
    print(result.stdout)
    assert "Completed successfully" in result.stdout
    assert con.cursor().execute("SELECT COUNT(*) FROM \
                                {}.{}_DWH.CONSO_CLIENT_INSERT".format(test_profile['database'],
                                                               test_profile['schema'])).fetchone()[0] == 1