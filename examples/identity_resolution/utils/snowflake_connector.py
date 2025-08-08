"""
Snowflake database connection and data extraction utilities
"""
import os
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
import json
from snowflake.connector.pandas_tools import write_pandas
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from auth.snowflake_auth import get_snowflake_connection

load_dotenv()

class SnowflakeManager:
    """
    Manages Snowflake connection, data extraction, and persistence for identity resolution.
    """
    def __init__(self):
        self.conn = get_snowflake_connection()

    def fetch_pf_companies(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.PF_COMPANIES')

    def fetch_pf_contentcreators(self):
        """
        Fetch complete creator data by joining PF_CONTENTCREATORS with PF_ASPNETUSERS.
        PF_ASPNETUSERS contains the core user information (names, emails, etc.)
        """
        query = """
        SELECT 
            cc.CONTENTCREATORID as CREATOR_ID,
            cc.USERID as ASPNET_USER_ID,
            cc.HEADLINE,
            cc.ABOUTME as BIO,
            cc.PORTFOLIOURL as BUSINESS_URL,
            cc.DATECREATED as CREATOR_CREATED_AT,
            cc.DATEUPDATED as CREATOR_UPDATED_AT,
            -- Core user data from ASPNETUSERS
            u.ID as USER_ID,
            u.USERNAME,
            u.EMAIL,
            u.EMAILCONFIRMED,
            u.PHONENUMBER,
            u.PHONENUMBERCONFIRMED,
            u.FIRSTNAME,
            u.LASTNAME,
            u.AVATAR as PROFILE_IMAGE_URL,
            u.DATECREATED as USER_CREATED_AT,
            u.DATEUPDATED as USER_UPDATED_AT,
            u.ISACTIVE as USER_IS_ACTIVE,
            -- Concatenated full name
            CONCAT(COALESCE(u.FIRSTNAME, ''), ' ', COALESCE(u.LASTNAME, '')) as FULL_NAME
        FROM PF.BI.PF_CONTENTCREATORS cc
        INNER JOIN PF.BI.PF_ASPNETUSERS u ON cc.USERID = u.ID
        WHERE u.ISACTIVE = TRUE
        """
        return self.query_to_dataframe(query)

    def fetch_pf_companyusers(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.PF_COMPANYUSERS')

    def fetch_pf_stripecustomers(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.PF_STRIPECUSTOMERS')

    def fetch_sf_account(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.SF_ACCOUNT')

    def fetch_sf_contact(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.SF_CONTACT')

    def fetch_s_customers(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.S_CUSTOMERS')

    def fetch_s_ca_accounts(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.S_CA_ACCOUNTS')
    
    def fetch_creator_payment_relationships(self):
        """
        Fetch creator-to-payment account relationships through PF_CONNECTACCOUNTS.
        This shows which creators are linked to which Stripe Connected Accounts.
        """
        query = """
        SELECT 
            ca.ID as STRIPE_ACCOUNT_ID,
            ca.USERID as CREATOR_USER_ID,
            ca.CREATED as CONNECTION_CREATED_AT,
            ca.DELETED as CONNECTION_IS_DELETED,
            ca.PAYOUTSENABLED,
            ca.CHARGESENABLED,
            ca.DETAILSSUBMITTED,
            -- Creator info
            cc.CONTENTCREATORID as CREATOR_ID,
            cc.HEADLINE as CREATOR_HEADLINE,
            cc.PORTFOLIOURL as CREATOR_BUSINESS_URL,
            -- User info from ASPNETUSERS
            u.EMAIL as CREATOR_EMAIL,
            u.FIRSTNAME as CREATOR_FIRSTNAME,
            u.LASTNAME as CREATOR_LASTNAME,
            u.USERNAME as CREATOR_USERNAME,
            CONCAT(COALESCE(u.FIRSTNAME, ''), ' ', COALESCE(u.LASTNAME, '')) as CREATOR_FULL_NAME,
            -- Stripe Connected Account info
            s.BUSINESS_NAME as STRIPE_BUSINESS_NAME,
            s.EMAIL as STRIPE_EMAIL,
            s.BUSINESS_URL as STRIPE_BUSINESS_URL,
            s.DISPLAY_NAME as STRIPE_DISPLAY_NAME
        FROM PF.BI.PF_CONNECTACCOUNTS ca
        INNER JOIN PF.BI.PF_CONTENTCREATORS cc ON ca.USERID = cc.USERID
        INNER JOIN PF.BI.PF_ASPNETUSERS u ON cc.USERID = u.ID
        LEFT JOIN PF.BI.S_CA_ACCOUNTS s ON ca.ID = s.ID
        WHERE ca.DELETED = FALSE 
        AND u.ISACTIVE = TRUE
        """
        return self.query_to_dataframe(query)

    def fetch_sf_lead(self):
        return self.query_to_dataframe('SELECT * FROM PF.BI.SF_LEAD')

    def query_to_dataframe(self, query):
        """Run a query and return a pandas DataFrame."""
        cur = self.conn.cursor()
        try:
            cur.execute(query)
            cols = [col[0] for col in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        finally:
            cur.close()

    def execute_non_query(self, statement):
        """Execute a non-query SQL statement (e.g., DDL, DML)."""
        cur = self.conn.cursor()
        try:
            cur.execute(statement)
        finally:
            cur.close()

    def test_connection(self):
        try:
            self.conn.cursor().execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self):
        self.conn.close()

    def _sql_escape(self, val):
        if val is None:
            return 'NULL'
        if isinstance(val, bool):
            return 'TRUE' if val else 'FALSE'
        if isinstance(val, (int, float)):
            return str(val)
        # For timestamps, strings, etc.
        return "'" + str(val).replace("'", "''") + "'"

    def write_master_entities(self, entities):
        """
        Write master entities to IR_MASTER_ENTITIES using batch insert via Pandas and write_pandas.
        entities: list of dicts or DataFrame with keys matching table columns.
        """
        # Convert to DataFrame if needed
        if isinstance(entities, pd.DataFrame):
            df = entities.copy()
        else:
            df = pd.DataFrame(entities)
        # Convert ADDITIONAL_DATA to JSON string
        df['ADDITIONAL_DATA_JSON'] = df['ADDITIONAL_DATA'].apply(lambda x: json.dumps(x, default=str) if pd.notnull(x) else None)
        # Ensure NOT NULL columns are never null
        df['MASTER_ENTITY_ID'] = df['MASTER_ENTITY_ID'].fillna('').astype(str)
        df['ENTITY_TYPE'] = df['ENTITY_TYPE'].fillna('').astype(str)
        df['CANONICAL_NAME'] = df['CANONICAL_NAME'].fillna('').astype(str)
        # Staging table name
        staging_table = 'STG_IR_MASTER_ENTITIES'
        # Create staging table (all columns as VARCHAR except ADDITIONAL_DATA_JSON)
        create_sql = f'''
        CREATE OR REPLACE TEMPORARY TABLE {staging_table} (
            MASTER_ENTITY_ID VARCHAR(50),
            ENTITY_TYPE VARCHAR(20),
            CANONICAL_NAME VARCHAR(500),
            CANONICAL_EMAIL VARCHAR(255),
            CANONICAL_PHONE VARCHAR(50),
            CANONICAL_ADDRESS VARCHAR(1000),
            CANONICAL_WEBSITE VARCHAR(500),
            STRIPE_CONNECTED_ACCOUNT_ID VARCHAR(100),
            PAYMENT_ENABLED VARCHAR(10),
            CONFIDENCE_SCORE VARCHAR(50),
            SOURCE_COUNT VARCHAR(50),
            ADDITIONAL_DATA_JSON STRING,
            CREATED_TIMESTAMP VARCHAR(50),
            UPDATED_TIMESTAMP VARCHAR(50),
            IS_ACTIVE VARCHAR(10)
        )'''
        cur = self.conn.cursor()
        try:
            cur.execute(create_sql)
            # Write to staging table
            write_pandas(self.conn, df[[
                'MASTER_ENTITY_ID', 'ENTITY_TYPE', 'CANONICAL_NAME', 'CANONICAL_EMAIL', 'CANONICAL_PHONE',
                'CANONICAL_ADDRESS', 'CANONICAL_WEBSITE', 'STRIPE_CONNECTED_ACCOUNT_ID', 'PAYMENT_ENABLED',
                'CONFIDENCE_SCORE', 'SOURCE_COUNT', 'ADDITIONAL_DATA_JSON', 'CREATED_TIMESTAMP',
                'UPDATED_TIMESTAMP', 'IS_ACTIVE'
            ]], staging_table, auto_create_table=False, overwrite=True)
            # Insert from staging to final table
            insert_sql = f'''
            INSERT INTO PF.BI.IR_MASTER_ENTITIES (
                MASTER_ENTITY_ID, ENTITY_TYPE, CANONICAL_NAME, CANONICAL_EMAIL, CANONICAL_PHONE, CANONICAL_ADDRESS,
                CANONICAL_WEBSITE, STRIPE_CONNECTED_ACCOUNT_ID, PAYMENT_ENABLED, CONFIDENCE_SCORE, SOURCE_COUNT,
                ADDITIONAL_DATA, CREATED_TIMESTAMP, UPDATED_TIMESTAMP, IS_ACTIVE
            )
            SELECT
                MASTER_ENTITY_ID, ENTITY_TYPE, CANONICAL_NAME, CANONICAL_EMAIL, CANONICAL_PHONE, CANONICAL_ADDRESS,
                CANONICAL_WEBSITE, STRIPE_CONNECTED_ACCOUNT_ID,
                IFF(PAYMENT_ENABLED IS NULL, FALSE, TRY_CAST(PAYMENT_ENABLED AS BOOLEAN)),
                TRY_CAST(CONFIDENCE_SCORE AS FLOAT),
                TRY_CAST(SOURCE_COUNT AS NUMBER(38,0)),
                PARSE_JSON(ADDITIONAL_DATA_JSON),
                TRY_CAST(CREATED_TIMESTAMP AS TIMESTAMP_LTZ(9)),
                TRY_CAST(UPDATED_TIMESTAMP AS TIMESTAMP_LTZ(9)),
                IFF(IS_ACTIVE IS NULL, TRUE, TRY_CAST(IS_ACTIVE AS BOOLEAN))
            FROM {staging_table}
            '''
            cur.execute(insert_sql)
            # Drop staging table (optional, since it's TEMPORARY)
            cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
        finally:
            cur.close()

    def write_entity_mappings(self, mappings):
        """
        Write entity mappings to IR_ENTITY_MAPPINGS using batch insert via Pandas and write_pandas.
        mappings: list of dicts or DataFrame with keys matching table columns.
        """
        if isinstance(mappings, pd.DataFrame):
            df = mappings.copy()
        else:
            df = pd.DataFrame(mappings)
        df['MAPPING_METADATA_JSON'] = df['MAPPING_METADATA'].apply(lambda x: json.dumps(x, default=str) if pd.notnull(x) else None)
        staging_table = 'STG_IR_ENTITY_MAPPINGS'
        create_sql = f'''
        CREATE OR REPLACE TEMPORARY TABLE {staging_table} (
            MAPPING_ID VARCHAR(100),
            MASTER_ENTITY_ID VARCHAR(50),
            SOURCE_SYSTEM VARCHAR(50),
            SOURCE_ENTITY_ID VARCHAR(100),
            SOURCE_TABLE VARCHAR(100),
            MAPPING_CONFIDENCE VARCHAR(50),
            MAPPING_METADATA_JSON STRING,
            CREATED_TIMESTAMP VARCHAR(50),
            IS_ACTIVE VARCHAR(10)
        )'''
        cur = self.conn.cursor()
        try:
            cur.execute(create_sql)
            write_pandas(self.conn, df[[
                'MAPPING_ID', 'MASTER_ENTITY_ID', 'SOURCE_SYSTEM', 'SOURCE_ENTITY_ID', 'SOURCE_TABLE',
                'MAPPING_CONFIDENCE', 'MAPPING_METADATA_JSON', 'CREATED_TIMESTAMP', 'IS_ACTIVE'
            ]], staging_table, auto_create_table=False, overwrite=True)
            insert_sql = f'''
            INSERT INTO PF.BI.IR_ENTITY_MAPPINGS (
                MAPPING_ID, MASTER_ENTITY_ID, SOURCE_SYSTEM, SOURCE_ENTITY_ID, SOURCE_TABLE, MAPPING_CONFIDENCE,
                MAPPING_METADATA, CREATED_TIMESTAMP, IS_ACTIVE
            )
            SELECT
                MAPPING_ID, MASTER_ENTITY_ID, SOURCE_SYSTEM, SOURCE_ENTITY_ID, SOURCE_TABLE,
                TRY_CAST(MAPPING_CONFIDENCE AS FLOAT),
                PARSE_JSON(MAPPING_METADATA_JSON),
                TRY_CAST(CREATED_TIMESTAMP AS TIMESTAMP_LTZ(9)),
                IFF(IS_ACTIVE IS NULL, TRUE, TRY_CAST(IS_ACTIVE AS BOOLEAN))
            FROM {staging_table}
            '''
            cur.execute(insert_sql)
            cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
        finally:
            cur.close()

    def write_match_results(self, matches):
        """
        Write match results to IR_ENTITY_MATCH_RESULTS using batch insert via Pandas and write_pandas.
        matches: list of dicts or DataFrame with keys matching table columns.
        """
        if isinstance(matches, pd.DataFrame):
            df = matches.copy()
        else:
            df = pd.DataFrame(matches)
        df['ML_SCORES_JSON'] = df['ML_SCORES'].apply(lambda x: json.dumps(x, default=str) if pd.notnull(x) else None)
        df['RECOMMENDATIONS_JSON'] = df['RECOMMENDATIONS'].apply(lambda x: json.dumps(x, default=str) if pd.notnull(x) else '[]')
        staging_table = 'STG_IR_ENTITY_MATCH_RESULTS'
        create_sql = f'''
        CREATE OR REPLACE TEMPORARY TABLE {staging_table} (
            MATCH_ID VARCHAR(100),
            ENTITY_1_ID VARCHAR(100),
            ENTITY_2_ID VARCHAR(100),
            ENTITY_TYPE VARCHAR(20),
            MATCH_PROBABILITY VARCHAR(50),
            CONFIDENCE_SCORE VARCHAR(50),
            CONFIDENCE_LEVEL VARCHAR(20),
            ML_SCORES_JSON STRING,
            EXPLANATION VARCHAR(1000),
            RECOMMENDATIONS_JSON STRING,
            BATCH_ID VARCHAR(100),
            CREATED_TIMESTAMP VARCHAR(50),
            RESOLUTION_STATUS VARCHAR(50),
            RESOLVED_BY VARCHAR(100),
            RESOLVED_TIMESTAMP VARCHAR(50),
            MASTER_ENTITY_ID VARCHAR(50)
        )'''
        cur = self.conn.cursor()
        try:
            cur.execute(create_sql)
            write_pandas(self.conn, df[[
                'MATCH_ID', 'ENTITY_1_ID', 'ENTITY_2_ID', 'ENTITY_TYPE', 'MATCH_PROBABILITY',
                'CONFIDENCE_SCORE', 'CONFIDENCE_LEVEL', 'ML_SCORES_JSON', 'EXPLANATION', 'RECOMMENDATIONS_JSON',
                'BATCH_ID', 'CREATED_TIMESTAMP', 'RESOLUTION_STATUS', 'RESOLVED_BY', 'RESOLVED_TIMESTAMP', 'MASTER_ENTITY_ID'
            ]], staging_table, auto_create_table=False, overwrite=True)
            insert_sql = f'''
            INSERT INTO PF.BI.IR_ENTITY_MATCH_RESULTS (
                MATCH_ID, ENTITY_1_ID, ENTITY_2_ID, ENTITY_TYPE, MATCH_PROBABILITY, CONFIDENCE_SCORE, CONFIDENCE_LEVEL,
                ML_SCORES, EXPLANATION, RECOMMENDATIONS, BATCH_ID, CREATED_TIMESTAMP, RESOLUTION_STATUS, RESOLVED_BY,
                RESOLVED_TIMESTAMP, MASTER_ENTITY_ID
            )
            SELECT
                MATCH_ID, ENTITY_1_ID, ENTITY_2_ID, ENTITY_TYPE,
                TRY_CAST(MATCH_PROBABILITY AS FLOAT),
                TRY_CAST(CONFIDENCE_SCORE AS FLOAT),
                CONFIDENCE_LEVEL,
                PARSE_JSON(ML_SCORES_JSON),
                EXPLANATION, 
                PARSE_JSON(RECOMMENDATIONS_JSON),
                BATCH_ID,
                TRY_CAST(CREATED_TIMESTAMP AS TIMESTAMP_LTZ(9)),
                RESOLUTION_STATUS, RESOLVED_BY,
                TRY_CAST(RESOLVED_TIMESTAMP AS TIMESTAMP_LTZ(9)),
                MASTER_ENTITY_ID
            FROM {staging_table}
            '''
            cur.execute(insert_sql)
            cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
        finally:
            cur.close()

    def get_processing_statistics(self):
        # TODO: Implement statistics extraction for reporting
        return {
            'TOTAL_MASTER_ENTITIES': 0,
            'entities_by_type': {},
            'mappings_by_source': {},
            'matches_by_confidence': {}
        }

    def truncate_output_tables(self):
        """
        Truncate the main output tables before a full pipeline run.
        """
        cur = self.conn.cursor()
        try:
            cur.execute("TRUNCATE TABLE PF.BI.IR_MASTER_ENTITIES")
            cur.execute("TRUNCATE TABLE PF.BI.IR_ENTITY_MAPPINGS")
            cur.execute("TRUNCATE TABLE PF.BI.IR_ENTITY_MATCH_RESULTS")
        finally:
            cur.close()
