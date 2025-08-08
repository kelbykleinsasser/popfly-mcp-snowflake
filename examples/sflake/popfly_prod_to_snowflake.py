import os
import sys
import pyodbc
import time
import logging
from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd
# Import JSON parsing function with fallback for different execution contexts
try:
    from sflake.parse_socialmediaaccounts_json import run_socialmediaaccounts_json_parsing
except ImportError:
    from parse_socialmediaaccounts_json import run_socialmediaaccounts_json_parsing

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from auth.snowflake_auth import get_snowflake_connection

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#from db_connect_popfly import get_postgres_connection, get_postgres_cursor, close_postgres_connection

# Load environment variables
load_dotenv()

# SQL Server connection details
SQL_SERVER = os.getenv('SQL_SERVER')
SQL_DATABASE = os.getenv('SQL_DATABASE')
SQL_USER = os.getenv('SQL_USER')
SQL_PASSWORD = os.getenv('SQL_PASSWORD')

# Snowflake connection details (now handled by snowflake_auth module)
SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE')
SNOWFLAKE_SCHEMA = os.getenv('SNOWFLAKE_SCHEMA')

# Flag to control output - set to False to show only errors
VERBOSE = os.getenv('VERBOSE', 'false').lower() == 'true'

# Logging verbosity settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'ERROR').upper()  # Default to ERROR if not set
ENABLE_INFO_LOGS = os.getenv('ENABLE_INFO_LOGS', 'false').lower() == 'true'
ENABLE_DEBUG_LOGS = os.getenv('ENABLE_DEBUG_LOGS', 'false').lower() == 'true'

def log(message, is_error=False, always_show=False):
    """Output messages based on verbosity settings or if marked as always_show"""
    if is_error:
        print(f"ERROR: {message}")
    elif always_show or VERBOSE:
        print(f"INFO: {message}")

# Configure logging based on settings
if LOG_LEVEL == 'DEBUG' and ENABLE_DEBUG_LOGS:
    log("Debug logging enabled", always_show=True)
elif LOG_LEVEL == 'INFO' and ENABLE_INFO_LOGS:
    log("Info logging enabled", always_show=True)
else:
    log("Error logging enabled", always_show=True)

# List of tables to exclude from replication
EXCLUDED_TABLES = [
    'AspNetRoles',
    'AspNetUserTokens', 
    'AspNetUserClaims',
    'AspNetUserRoles',
    'AspNetUserLogins',
    'AspNetRoleClaims',
    'BrandReferences',
    'CompanyUseFeatureCounts',
    'CustomTags',
    'ExternalFolders',
    'GuestUsers',
    'InventorySystems',
    '__EFMigrationsHistory',
    #'CompanyCreatorNotes',
    'CompanyReviews',
    'InviteCompanyMembers',
    'PhylloQueueStatus',
    #'PhylloUsers',
    'PhylloWorkPlatforms',
    'TermsAndConditions'
]

# List of tables to include (if non-empty, only these tables will be processed)
INCLUDE_TABLES = []  # Example: ['Table1', 'Table2']

# Dictionary to store timing information
table_timings = {}

def map_sql_server_type_to_snowflake(sql_type, max_length=None, precision=None, scale=None):
    """Map SQL Server data types to Snowflake data types"""
    sql_type = sql_type.lower()
    
    if sql_type in ('bit'):
        return 'BOOLEAN'
    elif sql_type in ('tinyint', 'smallint'):
        return 'SMALLINT'
    elif sql_type in ('int', 'integer'):
        return 'INTEGER'
    elif sql_type in ('bigint'):
        return 'BIGINT'
    elif sql_type in ('decimal', 'numeric'):
        if precision is not None and scale is not None:
            return f'NUMBER({precision},{scale})'
        return 'NUMBER'
    elif sql_type in ('float', 'real'):
        return 'FLOAT'
    elif sql_type in ('money', 'smallmoney'):
        return 'NUMBER(19,4)'
    elif sql_type in ('date'):
        return 'DATE'
    elif sql_type in ('time'):
        return 'TIME'
    elif sql_type in ('datetime', 'datetime2', 'smalldatetime'):
        return 'TIMESTAMP'
    elif sql_type in ('char', 'nchar'):
        if max_length is not None:
            return f'CHAR({max_length})'
        return 'CHAR'
    elif sql_type in ('varchar', 'nvarchar', 'text', 'ntext'):
        if max_length is not None and max_length > 0:
            return f'VARCHAR({max_length})'
        return 'TEXT'
    elif sql_type in ('binary', 'varbinary', 'image'):
        return 'BINARY'
    elif sql_type in ('uniqueidentifier'):
        return 'VARCHAR(36)'
    elif sql_type in ('xml'):
        return 'VARIANT'
    elif sql_type in ('json'):
        return 'VARIANT'
    else:
        # Default to VARCHAR for unsupported types
        return 'VARCHAR'

def connect_to_snowflake():
    """Establish connection to Snowflake using centralized auth."""
    try:
        conn = get_snowflake_connection()
        
        # Set database and schema after connection if not already set
        if SNOWFLAKE_DATABASE:
            conn.cursor().execute(f"USE DATABASE {SNOWFLAKE_DATABASE}")
        if SNOWFLAKE_SCHEMA:
            conn.cursor().execute(f"USE SCHEMA {SNOWFLAKE_SCHEMA}")
            
        return conn
    except Exception as e:
        log(f"Error connecting to Snowflake: {str(e)}", is_error=True)
        return None

def run_popfly_prod_to_snowflake(snowflake_conn=None):
    sql_conn = None
    try:
        # Connect to SQL Server using pyodbc with Microsoft's ODBC driver
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={SQL_SERVER},1433;"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USER};"
            f"PWD={SQL_PASSWORD};"
            f"TrustServerCertificate=Yes;"
        )
        log(f"Connecting to SQL Server: {SQL_SERVER}", always_show=True)
        sql_conn = pyodbc.connect(connection_string)
        sql_cur = sql_conn.cursor()
        log("SQL Server connection successful", always_show=True)
        
        # Use provided Snowflake connection or create one
        if snowflake_conn is None:
            log("Connecting to Snowflake", always_show=True)
            snowflake_conn = connect_to_snowflake()
            if not snowflake_conn:
                raise Exception("Failed to connect to Snowflake")
        snowflake_cur = snowflake_conn.cursor()
        log("Snowflake connection successful", always_show=True)

        # Get all non-system tables from SQL Server
        log("Fetching table list from SQL Server", always_show=True)
        sql_cur.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE' 
            AND TABLE_NAME NOT LIKE 'sys%'
            AND TABLE_NAME NOT LIKE 'INFORMATION_SCHEMA%'
        """)
        tables = sql_cur.fetchall()
        log(f"Found {len(tables)} tables to sync", always_show=True)

        succeeded = 0
        failed = 0
        total_tables = len(tables)
        for table in tables:
            table_name = table[0]
            prefixed_table_name = f"PF_{table_name}"
            
            # If INCLUDE_TABLES is non-empty, only process those tables
            if INCLUDE_TABLES:
                if table_name not in INCLUDE_TABLES:
                    continue
                is_excluded = False  # Ignore exclude list if include list is used
            else:
                # Otherwise, use the exclude list
                is_excluded = table_name.lower() in [t.lower() for t in EXCLUDED_TABLES]
                
            log(f"Starting to process table: {table_name}", always_show=True)
            
            # Always attempt to drop the table in Snowflake, even if it's excluded
            try:
                log(f"Dropping table {prefixed_table_name} if it exists", always_show=True)
                snowflake_cur.execute(f"DROP TABLE IF EXISTS {prefixed_table_name}")
                if is_excluded:
                    log(f"Dropped excluded table: {prefixed_table_name}", always_show=True)
                    log(f"Completed table: {table_name} (excluded)", always_show=True)
                    continue
            except Exception as drop_error:
                log(f"Error dropping table {prefixed_table_name}: {str(drop_error)}", is_error=True)
                if is_excluded:
                    log(f"Completed table: {table_name} (excluded with error)", always_show=True)
                    continue

            # Start timing for this table
            start_time = time.time()
            
            try:
                # Get column information
                sql_cur.execute(f"""
                    SELECT 
                        COLUMN_NAME, 
                        DATA_TYPE,
                        CHARACTER_MAXIMUM_LENGTH,
                        NUMERIC_PRECISION,
                        NUMERIC_SCALE,
                        ORDINAL_POSITION
                    FROM 
                        INFORMATION_SCHEMA.COLUMNS 
                    WHERE 
                        TABLE_NAME = '{table_name}'
                    ORDER BY 
                        ORDINAL_POSITION
                """)
                column_info = sql_cur.fetchall()
                
                # Process columns
                supported_columns = []
                column_types = {}
                date_columns = []
                
                for col_name, data_type, max_length, precision, scale, ordinal_position in column_info:
                    # Ignore any column named 'Domain' (case-insensitive)
                    if data_type.lower() not in ('geography', 'geometry', 'hierarchyid', 'xml', 'image', 'sql_variant'):
                        supported_columns.append(col_name)
                        
                        # Special handling for known problematic columns
                        if col_name.upper() in ['GIFTINGTOKENEXPIRATIONDATE', 'DELIVEREDDATE']:
                            column_types[col_name] = 'TIMESTAMP_NTZ(9)'
                            date_columns.append(col_name)
                        else:
                            sf_type = map_sql_server_type_to_snowflake(data_type, max_length, precision, scale)
                            column_types[col_name] = sf_type
                            if sf_type in ['DATE', 'TIMESTAMP']:
                                date_columns.append(col_name)
                
                # If no supported columns remain, skip the table
                if not supported_columns:
                    log(f"Error: {table_name} - No supported columns", logging.ERROR, True)
                    continue
                
                # Build SELECT query
                column_parts = []
                for col in supported_columns:
                    # Add explicit CAST for known problematic date columns
                    if col.upper() in ['GIFTINGTOKENEXPIRATIONDATE', 'DELIVEREDDATE']:
                        column_parts.append(f"CAST(COALESCE(TRY_CONVERT(DATETIME2, [{col}]), '1970-01-01 00:00:00.000') AS DATETIME2) as [{col}]")
                    # Special handling for AspNetUsers table
                    elif table_name == 'AspNetUsers' and col.upper() == 'LOCKOUTEND':
                        column_parts.append(f"CAST(COALESCE(TRY_CONVERT(DATETIME2, [{col}]), '1970-01-01 00:00:00.000') AS DATETIME2) as [{col}]")
                    else:
                        column_parts.append(f"[{col}]")
                
                select_query = f"SELECT {', '.join(column_parts)} FROM [{table_name}]"
                
                # Create table in Snowflake with "PF_" prefix
                create_table_query = f"CREATE TABLE {prefixed_table_name} ({', '.join([f'{col} {column_types[col]}' for col in supported_columns])})"
                log(f"Creating table {prefixed_table_name}", always_show=True)
                snowflake_cur.execute(create_table_query)
                
                # Fetch data from SQL Server and load into Snowflake
                log(f"Fetching data from {table_name}", always_show=True)
                sql_cur.execute(select_query)
                
                # Process data in chunks using pandas
                chunk_size = 10000
                row_count = 0
                # Only consider email columns that are string types
                string_types = ["TEXT", "VARCHAR", "CHAR", "STRING"]
                email_columns = [col for col in supported_columns if 'email' in col.lower() and any(t in column_types[col].upper() for t in string_types)]
                while True:
                    rows = sql_cur.fetchmany(chunk_size)
                    if not rows:
                        break
                        
                    # Convert to pandas DataFrame
                    df = pd.DataFrame.from_records(rows, columns=supported_columns)
                    
                     # Handle date columns
                    for col in df.columns:
                        # Only apply date/time conversion to columns that are DATE or TIMESTAMP, or the special cases
                        if column_types.get(col) in ['DATE', 'TIMESTAMP'] or col.upper() in ['GIFTINGTOKENEXPIRATIONDATE', 'DELIVEREDDATE']:
                            # First convert to datetime, handling potential NaT values
                            df[col] = pd.to_datetime(df[col], errors='coerce')
                            # Convert to UTC timezone if it's not already
                            if df[col].dt.tz is None:
                                df[col] = df[col].dt.tz_localize('UTC')
                            else:
                                df[col] = df[col].dt.tz_convert('UTC')
                            # Convert to string format that Snowflake expects
                            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                    
                    # Write to Snowflake
                    success, nchunks, nrows, _ = write_pandas(
                        snowflake_conn,
                        df,
                        prefixed_table_name,
                        database=SNOWFLAKE_DATABASE,
                        schema=SNOWFLAKE_SCHEMA,
                        quote_identifiers=False,
                        auto_create_table=False,
                        overwrite=True,
                        chunk_size=1000
                    )
                    
                    row_count += nrows
                    log(f"Processed {row_count} rows for {table_name}", always_show=True)
                
                log(f"Completed table: {table_name} ({row_count} rows replicated)", always_show=True)
                succeeded += 1
            
            except Exception as e:
                error_msg = str(e)
                log(f"Error processing table {table_name}: {error_msg}", is_error=True)
                log(f"Completed table: {table_name} (failed)", always_show=True)
                failed += 1
                continue
            
            # Record the time taken for this table
            end_time = time.time()
            elapsed_time = end_time - start_time
            table_timings[table_name] = elapsed_time
            
        # Post-processing: Add JSON-parsed columns to PF_SOCIALMEDIAACCOUNTS
        log("Running post-processing for PF_SOCIALMEDIAACCOUNTS...", always_show=True)
        try:
            json_parse_result = run_socialmediaaccounts_json_parsing(snowflake_conn)
            if json_parse_result == 'success':
                log("PF_SOCIALMEDIAACCOUNTS JSON parsing completed successfully", always_show=True)
            else:
                log("PF_SOCIALMEDIAACCOUNTS JSON parsing failed, but continuing...", always_show=True)
        except Exception as e:
            log(f"Error in PF_SOCIALMEDIAACCOUNTS post-processing: {e}", always_show=True)
            
        if succeeded + failed == 0:
            return 'failed'
        elif failed == 0:
            return 'success'
        elif succeeded > 0:
            return 'partial'
        else:
            return 'failed'

    except Exception as e:
        log(f"Error: Database connection failed: {str(e)}", is_error=True)
        import traceback
        log(traceback.format_exc(), is_error=True)
        return 'failed'
    finally:
        if 'sql_cur' in locals():
            sql_cur.close()
        if sql_conn:
            sql_conn.close()
        # Do not close snowflake_conn if it was passed in
        
        # Print timing summary
        log("\nTable Replication Timing Summary (sorted by duration):", always_show=True)
        log("-" * 60, always_show=True)
        log(f"{'Table Name':<40} {'Duration (seconds)':<20}", always_show=True)
        log("-" * 60, always_show=True)
        
        # Sort tables by duration (descending)
        sorted_tables = sorted(table_timings.items(), key=lambda x: x[1], reverse=True)
        
        for table_name, duration in sorted_tables:
            log(f"{table_name:<40} {duration:<20.2f}", always_show=True)
        
        log("-" * 60, always_show=True)
        total_time = sum(table_timings.values())
        log(f"Total replication time: {total_time:.2f} seconds", always_show=True)

if __name__ == "__main__":
    run_popfly_prod_to_snowflake() 