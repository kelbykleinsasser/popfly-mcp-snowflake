import os
import sys
import time
import logging
import json
from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from auth.snowflake_auth import get_snowflake_connection

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of views to replicate
STRIPE_VIEWS = [
    'ACCOUNTS',
    #'ACCOUNTS_METADATA',
    #'ACCEPTANCE_REPORTING_V3_ITEMIZED',
    #'AGGREGATE_OPTIMIZATION_DETAILS',
    #'APPLICATION_FEE_REFUNDS',
    #'APPLICATION_FEE_REFUNDS_METADATA',
    #'APPLICATION_FEES',
    #'BALANCE_TRANSACTION_FEE_DETAILS',
    'BALANCE_TRANSACTIONS',
    #'CAPTURES',
    #'CHARGE_GROUPS',
    'CHARGES',
    #'CHARGES_METADATA',
    #'CHECKOUT_CUSTOM_FIELDS',
    #'CHECKOUT_LINE_ITEMS',
    #'CHECKOUT_SESSIONS',
    'CONNECTED_ACCOUNTS',
    #'CONNECTED_ACCOUNTS_METADATA',
    #'CONNECTED_ACCOUNT_APPLICATION_FEE_REFUNDS',
    #'CONNECTED_ACCOUNT_BALANCE_TRANSACTIONS',
    #'CONNECTED_ACCOUNT_BALANCE_TRANSACTION_FEE_DETAILS',
    #'CONNECTED_ACCOUNT_CAPTURES',
    #'CONNECTED_ACCOUNT_CHARGES',
    #'CONNECTED_ACCOUNT_CHARGES_METADATA',
    #'CONNECTED_ACCOUNT_COUPONS',
    #'CONNECTED_ACCOUNT_COUPONS_CURRENCY_OPTIONS',
    #'CONNECTED_ACCOUNT_COUPONS_METADATA',
    'CONNECTED_ACCOUNT_CUSTOMERS',
    #'CONNECTED_ACCOUNT_CUSTOMERS_METADATA',
    #'CONNECTED_ACCOUNT_CUSTOMER_BALANCE_TRANSACTIONS',
    #'CONNECTED_ACCOUNT_CUSTOMER_BALANCE_TRANSACTIONS_METADATA',
    #'CONNECTED_ACCOUNT_CUSTOMER_CASH_BALANCE_TRANSACTIONS',
    #'CONNECTED_ACCOUNT_CUSTOMER_TAX_IDS',
    #'CONNECTED_ACCOUNT_CREDIT_NOTE_DISCOUNT_AMOUNTS',
    #'CONNECTED_ACCOUNT_CREDIT_NOTE_LINE_ITEMS',
    #'CONNECTED_ACCOUNT_CREDIT_NOTE_LINE_ITEM_DISCOUNT_AMOUNTS',
    #'CONNECTED_ACCOUNT_CREDIT_NOTE_LINE_ITEM_TAX_AMOUNTS',
    #'CONNECTED_ACCOUNT_CREDIT_NOTE_TAX_AMOUNTS',
    #'CONNECTED_ACCOUNT_CREDIT_NOTES',
    #'CONNECTED_ACCOUNT_CREDIT_NOTES_METADATA',
    #'CONNECTED_ACCOUNT_CRYPTO_ONRAMP_SESSIONS',
    #'CONNECTED_ACCOUNT_DISCOUNTS',
    #'CONNECTED_ACCOUNT_DISPUTES',
    #'CONNECTED_ACCOUNT_DISPUTES_ENHANCED_ELIGIBILITY',
    #'CONNECTED_ACCOUNT_DISPUTES_METADATA',
    #'CONNECTED_ACCOUNT_EARLY_FRAUD_WARNINGS',
    #'CONNECTED_ACCOUNT_EXTERNAL_ACCOUNT_BANK_ACCOUNTS',
    #'CONNECTED_ACCOUNT_EXTERNAL_ACCOUNT_CARDS',
    #'CONNECTED_ACCOUNT_FINANCING_BALANCES',
    #'CONNECTED_ACCOUNT_FINANCING_OFFERS',
    #'CONNECTED_ACCOUNT_FINANCING_TRANSACTIONS',
    #'CONNECTED_ACCOUNT_INVOICE_CUSTOMER_TAX_IDS',
    #'CONNECTED_ACCOUNT_INVOICE_CUSTOM_FIELDS',
    'CONNECTED_ACCOUNT_INVOICE_ITEMS',
    #'CONNECTED_ACCOUNT_INVOICE_ITEMS_METADATA',
    #'CONNECTED_ACCOUNT_INVOICE_LINE_ITEMS',
    #'CONNECTED_ACCOUNT_INVOICE_LINE_ITEM_DISCOUNT_AMOUNTS',
    #'CONNECTED_ACCOUNT_INVOICE_LINE_ITEM_TAX_AMOUNTS',
    'CONNECTED_ACCOUNT_INVOICE_PAYMENTS',
    #'CONNECTED_ACCOUNT_INVOICE_SHIPPING_COST_TAXES',
    'CONNECTED_ACCOUNT_INVOICES',
    'CONNECTED_ACCOUNT_INVOICES_METADATA',
    #'CONNECTED_ACCOUNT_ISSUING_AUTHORIZATIONS',
    #'CONNECTED_ACCOUNT_ISSUING_AUTHORIZATIONS_METADATA',
    #'CONNECTED_ACCOUNT_ISSUING_AUTHORIZATIONS_REQUEST_HISTORY',
    #'CONNECTED_ACCOUNT_ISSUING_CARDHOLDERS',
    #'CONNECTED_ACCOUNT_ISSUING_CARDHOLDERS_METADATA',
    #'CONNECTED_ACCOUNT_ISSUING_CARDS',
    #'CONNECTED_ACCOUNT_ISSUING_CARDS_METADATA',
    #'CONNECTED_ACCOUNT_ISSUING_DISPUTES',
    #'CONNECTED_ACCOUNT_ISSUING_FUNDING_OBLIGATIONS',
    #'CONNECTED_ACCOUNT_ISSUING_FUNDING_OBLIGATIONS_METADATA',
    #'CONNECTED_ACCOUNT_ISSUING_TRANSACTIONS',
    #'CONNECTED_ACCOUNT_ISSUING_TRANSACTIONS_METADATA',
    #'CONNECTED_ACCOUNT_ITEMIZED_FEES',
    #'CONNECTED_ACCOUNT_PAYMENT_INTENT_LINE_ITEMS',
    #'CONNECTED_ACCOUNT_PAYMENT_INTENTS',
    #'CONNECTED_ACCOUNT_PAYMENT_INTENTS_METADATA',
    #'CONNECTED_ACCOUNT_PAYMENT_METHOD_DETAILS',
    #'CONNECTED_ACCOUNT_PAYMENT_METHODS',
    #'CONNECTED_ACCOUNT_PAYMENT_METHODS_METADATA',
    #'CONNECTED_ACCOUNT_PAYMENT_REVIEWS',
    'CONNECTED_ACCOUNT_REFUNDS',
    'CUSTOMERS',
    #'CUSTOMERS_METADATA',
    'CUSTOMER_BALANCE_TRANSACTIONS',
    #'CUSTOMER_CASH_BALANCE_TRANSACTIONS',
    #'DATA_LOAD_TIMES',
    #'DISCOUNTS',
    #'DISPUTES',
    #'DISPUTES_METADATA',
    #'EARLY_FRAUD_WARNINGS',
    #'EXCHANGE_RATES_FROM_USD',
    #'EXTERNAL_ACCOUNT_BANK_ACCOUNTS',
    #'EXTERNAL_ACCOUNT_CARDS',
    #'FINANCIAL_REPORT_BALANCE_CHANGE_FROM_ACTIVITY_ITEMIZED',
    #'FINANCIAL_REPORT_CONNECT_BALANCE_CHANGE_FROM_ACTIVITY_ITEMIZED',
    #'FINANCIAL_REPORT_CONNECT_ENDING_BALANCE_RECONCILIATION_ITEMIZED',
    #'FINANCIAL_REPORT_CONNECT_PAYOUT_RECONCILIATION_ITEMIZED',
    #'FINANCIAL_REPORT_CONNECT_PAYOUTS_ITEMIZED',
    #'FINANCIAL_REPORT_ENDING_BALANCE_RECONCILIATION_ITEMIZED',
    #'FINANCIAL_REPORT_PAYOUT_RECONCILIATION_ITEMIZED',
    #'FINANCIAL_REPORT_PAYOUTS_ITEMIZED',
    #'FINANCING_BALANCES',
    #'FINANCING_OFFERS',
    #'FINANCING_TRANSACTIONS',
    #'INVOICE_CUSTOMER_TAX_IDS',
    #'INVOICE_CUSTOM_FIELDS',
    'INVOICE_ITEMS',
    #'INVOICE_ITEMS_METADATA',
    'INVOICE_LINE_ITEMS',
    #'INVOICE_LINE_ITEM_DISCOUNT_AMOUNTS',
    #'INVOICE_LINE_ITEM_TAX_AMOUNTS',
    'INVOICES',
    'INVOICES_METADATA',
    'INVOICE_PAYMENTS',
    #'INVOICE_SHIPPING_COST_TAXES',
    #'ISSUING_AUTHORIZATIONS',
    #'ISSUING_AUTHORIZATIONS_METADATA',
    #'ISSUING_AUTHORIZATIONS_REQUEST_HISTORY',
    #'ISSUING_CARDHOLDERS',
    #'ISSUING_CARDHOLDERS_METADATA',
    #'ISSUING_CARDS',
    #'ISSUING_CARDS_METADATA',
    #'ISSUING_DISPUTES',
    #'ISSUING_FUNDING_OBLIGATIONS',
    #'ISSUING_FUNDING_OBLIGATIONS_METADATA',
    #'ISSUING_TRANSACTIONS',
    #'ISSUING_TRANSACTIONS_METADATA',
    #'PAYMENT_INTENT_LINE_ITEMS',
    'PAYMENT_INTENTS',
    #'PAYMENT_INTENTS_METADATA',
    #'PAYMENT_LINKS',
    #'PAYMENT_METHOD_DETAILS',
    'PAYMENT_METHODS',
    #'PAYMENT_METHODS_METADATA',
    #'PAYMENT_REVIEWS',
    'PLANS',
    #'PLANS_METADATA',
    'PRICE_TIERS',
    'PRICES',
    #'PRICES_CURRENCY_OPTIONS',
    #'PRICES_METADATA',
    'PRODUCTS',
    #'PRODUCTS_METADATA',
    'SUBSCRIPTION_ITEMS',
    #'SUBSCRIPTION_ITEMS_METADATA',
    #'SUBSCRIPTION_ITEM_CHANGE_EVENTS',
    #'SUBSCRIPTION_SCHEDULES',
    #'SUBSCRIPTION_SCHEDULES_METADATA',
    #'SUBSCRIPTION_SCHEDULE_PHASES',
    #'SUBSCRIPTION_SCHEDULE_PHASES_METADATA',
    #'SUBSCRIPTION_SCHEDULE_PHASE_ADD_INVOICE_ITEMS',
    #'SUBSCRIPTION_SCHEDULE_PHASE_CONFIGURATION_ITEMS',
    'SUBSCRIPTIONS',
    #'SUBSCRIPTIONS_METADATA',
    'TRANSFERS',
    'TRANSFERS_METADATA',
]

# Prefixes to exclude from replication
EXCLUDED_FIELD_PREFIXES = [
    'CAPABILITIES',
    'FUTURE_REQUIREMENTS',
    'CONTROLLER',
    'LEGAL_ENTITY',
    'REQUIREMENTS',
    'VERIFICATION',
    'PAYMENT_SETTINGS_PAYMENT_METHOD_OPTIONS',
]

# List of currency-related substrings to identify currency fields
CURRENCY_FIELD_KEYWORDS = [
    'AMOUNT',
    'BALANCE',
    'FEE',
    'NET',
    'TAX',
    'TOTAL',
    'SUBTOTAL',
]

def log(message, is_error=False, always_show=False):
    """Output messages based on verbosity settings or if marked as always_show"""
    if is_error:
        print(f"ERROR: {message}")
    elif always_show:
        print(f"INFO: {message}")

def connect_to_snowflake():
    """Establish connection to Snowflake using RSA key authentication."""
    try:
        conn = get_snowflake_connection()
        return conn
    except Exception as e:
        log(f"Error connecting to Snowflake: {str(e)}", is_error=True)
        return None

def get_target_table_name(view_name):
    """Generate target table name based on naming rules"""
    if view_name.startswith('CONNECTED_'):
        return f"S_CA_{view_name[10:]}"  # Remove 'CONNECTED_' prefix
    return f"S_{view_name}"

def delete_existing_tables(cursor):
    """Delete all tables that begin with S_ or S_CA_"""
    try:
        # Get all tables in the current schema
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        # Filter for tables starting with S_ or S_CA_
        tables_to_delete = [table[1] for table in tables if table[1].startswith(('S_', 'S_CA_'))]
        
        if tables_to_delete:
            log(f"Found {len(tables_to_delete)} existing tables to delete", always_show=True)
            for table in tables_to_delete:
                log(f"Dropping table {table}...", always_show=True)
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            log("Successfully deleted all existing tables", always_show=True)
        else:
            log("No existing tables found to delete", always_show=True)
            
    except Exception as e:
        log(f"Error deleting existing tables: {str(e)}", is_error=True)
        raise

def get_view_row_count(cursor, view_name):
    """Get the row count for a view"""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM STRIPE.STRIPE.{view_name}")
        return cursor.fetchone()[0]
    except Exception as e:
        log(f"Error getting row count for view {view_name}: {str(e)}", is_error=True)
        return 0

def get_filtered_columns(cursor, view_name):
    """Get columns for a view, excluding those with specified prefixes."""
    try:
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'STRIPE' AND TABLE_NAME = '{view_name}'")
        columns = [row[0] for row in cursor.fetchall()]
        filtered = [col for col in columns if not any(col.lower().startswith(prefix.lower()) for prefix in EXCLUDED_FIELD_PREFIXES)]
        return filtered
    except Exception as e:
        log(f"Error getting columns for view {view_name}: {str(e)}", is_error=True)
        return []

def is_numeric_type(dtype_info):
    """Helper function to determine if a Snowflake data type is numeric"""
    if isinstance(dtype_info, str):
        return dtype_info.upper() in ("NUMBER", "FLOAT", "DECIMAL", "FIXED")
    elif isinstance(dtype_info, dict):
        return dtype_info.get("type", "").upper() in ("NUMBER", "FLOAT", "DECIMAL", "FIXED")
    return False

def run_replicate_stripe_views(snowflake_conn=None):
    debug_printed = False
    try:
        # Use provided Snowflake connection or create one
        if snowflake_conn is None:
            log("Connecting to Snowflake...", always_show=True)
            snowflake_conn = connect_to_snowflake()
            if not snowflake_conn:
                raise Exception("Failed to connect to Snowflake")
        snowflake_cur = snowflake_conn.cursor()
        
        # Filter STRIPE_VIEWS to only those that exist in STRIPE.STRIPE
        snowflake_cur.execute("SHOW VIEWS IN SCHEMA STRIPE.STRIPE")
        existing_views = set(row[1] for row in snowflake_cur.fetchall())
        filtered_stripe_views = [v for v in STRIPE_VIEWS if v in existing_views]
        if len(filtered_stripe_views) < len(STRIPE_VIEWS):
            log(f"Filtered out {len(STRIPE_VIEWS) - len(filtered_stripe_views)} non-existent views.", always_show=True)
        
        # Delete existing tables
        log("Deleting existing tables...", always_show=True)
        delete_existing_tables(snowflake_cur)
        
        # Dictionary to store timing information
        view_timings = {}
        
        succeeded = 0
        failed = 0
        total_views = len(filtered_stripe_views)
        for view_name in filtered_stripe_views:
            start_time = time.time()
            target_table = get_target_table_name(view_name)
            
            try:
                log(f"Processing view: {view_name}", always_show=True)
                
                # Check row count before proceeding
                row_count = get_view_row_count(snowflake_cur, view_name)
                if row_count == 0:
                    log(f"Skipping {view_name} as it has no rows", always_show=True)
                    continue
                
                # Get filtered columns and their types using SHOW COLUMNS
                cursor = snowflake_cur
                cursor.execute(f"SHOW COLUMNS IN TABLE STRIPE.STRIPE.{view_name}")
                column_info = [(row[2], row[3]) for row in cursor.fetchall()]  # (column_name, data_type)
                filtered_columns = [col for col, _ in column_info if not any(col.lower().startswith(prefix.lower()) for prefix in EXCLUDED_FIELD_PREFIXES)]
                filtered_column_info = [(col, dtype) for col, dtype in column_info if col in filtered_columns]
                
                if not filtered_columns:
                    log(f"No columns to replicate for {view_name} after filtering", always_show=True)
                    continue

                # Build select expressions: convert currency fields and rename if numeric
                select_exprs = []
                # Only consider email columns that are string types
                string_types = ["TEXT", "VARCHAR", "CHAR", "STRING"]
                email_columns = [col for col, dtype in filtered_column_info if 'email' in col.lower() and (isinstance(dtype, str) and any(t in dtype.upper() for t in string_types))]
                for col, dtype in filtered_column_info:
                    try:
                        dtype_info = json.loads(dtype) if isinstance(dtype, str) else dtype
                    except (json.JSONDecodeError, TypeError):
                        dtype_info = dtype
                    
                    target_col_name = col.upper()

                    if any(keyword in col.upper() for keyword in CURRENCY_FIELD_KEYWORDS) and is_numeric_type(dtype_info):
                        new_col_name = f"{target_col_name}_USD"
                        select_exprs.append(f'"{col}" * 0.01 AS {new_col_name}')
                    else:
                        select_exprs.append(f'"{col}" AS {target_col_name}')

                # Add domain columns for email fields (string type only)
                for email_col in email_columns:
                    domain_col_name = f'{email_col.upper()}_DOMAIN'
                    select_exprs.append(f'SPLIT_PART("{email_col}", \'@\', 2) AS {domain_col_name}')
                columns_str = ', '.join(select_exprs)
                
                # Create and execute the query
                if view_name == 'INVOICES':
                    # Special case: Add metadata columns for S_INVOICES
                    # Build select expressions with table alias for INVOICES
                    invoice_select_exprs = []
                    for col, dtype in filtered_column_info:
                        try:
                            dtype_info = json.loads(dtype) if isinstance(dtype, str) else dtype
                        except (json.JSONDecodeError, TypeError):
                            dtype_info = dtype
                        
                        target_col_name = col.upper()

                        if any(keyword in col.upper() for keyword in CURRENCY_FIELD_KEYWORDS) and is_numeric_type(dtype_info):
                            new_col_name = f"{target_col_name}_USD"
                            invoice_select_exprs.append(f'i."{col}" * 0.01 AS {new_col_name}')
                        else:
                            invoice_select_exprs.append(f'i."{col}" AS {target_col_name}')

                    # Add domain columns for email fields in INVOICES
                    string_types = ["TEXT", "VARCHAR", "CHAR", "STRING"]
                    email_columns = [col for col, dtype in filtered_column_info if 'email' in col.lower() and (isinstance(dtype, str) and any(t in dtype.upper() for t in string_types))]
                    for email_col in email_columns:
                        domain_col_name = f'{email_col.upper()}_DOMAIN'
                        invoice_select_exprs.append(f'SPLIT_PART(i."{email_col}", \'@\', 2) AS {domain_col_name}')
                    
                    invoice_columns_str = ', '.join(invoice_select_exprs)
                    group_by_cols = ', '.join([f'i."{col}"' for col, _ in filtered_column_info])
                    
                    create_query = f"""
                        CREATE TABLE {target_table} AS 
                        SELECT 
                            {invoice_columns_str},
                            MAX(CASE WHEN im.KEY ILIKE 'creatorid' THEN im.VALUE END)::INTEGER as CREATOR_ID,
                            MAX(CASE WHEN im.KEY ILIKE 'campaignid' THEN im.VALUE END)::INTEGER as CAMPAIGN_ID,
                            MAX(CASE WHEN im.KEY ILIKE 'companyid' THEN im.VALUE END)::INTEGER as COMPANY_ID
                        FROM STRIPE.STRIPE.{view_name} i
                        LEFT JOIN STRIPE.STRIPE.INVOICES_METADATA im ON i.ID = im.INVOICE_ID
                        GROUP BY {group_by_cols}
                    """
                elif view_name == 'TRANSFERS':
                    # Special case: Add metadata columns for S_TRANSFERS
                    # Build select expressions with table alias for TRANSFERS
                    transfer_select_exprs = []
                    for col, dtype in filtered_column_info:
                        try:
                            dtype_info = json.loads(dtype) if isinstance(dtype, str) else dtype
                        except (json.JSONDecodeError, TypeError):
                            dtype_info = dtype
                        
                        target_col_name = col.upper()

                        if any(keyword in col.upper() for keyword in CURRENCY_FIELD_KEYWORDS) and is_numeric_type(dtype_info):
                            new_col_name = f"{target_col_name}_USD"
                            transfer_select_exprs.append(f't."{col}" * 0.01 AS {new_col_name}')
                        else:
                            transfer_select_exprs.append(f't."{col}" AS {target_col_name}')

                    # Add domain columns for email fields in TRANSFERS
                    string_types = ["TEXT", "VARCHAR", "CHAR", "STRING"]
                    email_columns = [col for col, dtype in filtered_column_info if 'email' in col.lower() and (isinstance(dtype, str) and any(t in dtype.upper() for t in string_types))]
                    for email_col in email_columns:
                        domain_col_name = f'{email_col.upper()}_DOMAIN'
                        transfer_select_exprs.append(f'SPLIT_PART(t."{email_col}", \'@\', 2) AS {domain_col_name}')
                    
                    transfer_columns_str = ', '.join(transfer_select_exprs)
                    group_by_cols = ', '.join([f't."{col}"' for col, _ in filtered_column_info])
                    
                    create_query = f"""
                        CREATE TABLE {target_table} AS 
                        SELECT 
                            {transfer_columns_str},
                            MAX(CASE WHEN tm.KEY ILIKE 'campaignid' THEN tm.VALUE END)::INTEGER as CAMPAIGNID_METADATA,
                            MAX(CASE WHEN tm.KEY ILIKE 'companyid' THEN tm.VALUE END)::INTEGER as COMPANYID_METADATA,
                            MAX(CASE WHEN tm.KEY ILIKE 'invoiceid' THEN tm.VALUE END) as INVOICEID_METADATA
                        FROM STRIPE.STRIPE.{view_name} t
                        LEFT JOIN STRIPE.STRIPE.TRANSFERS_METADATA tm ON t.ID = tm.TRANSFER_ID
                        GROUP BY {group_by_cols}
                    """
                else:
                    create_query = f"""
                        CREATE TABLE {target_table} AS 
                        SELECT {columns_str} FROM STRIPE.STRIPE.{view_name}
                    """
                snowflake_cur.execute(create_query)
                
                log(f"Successfully replicated {view_name} to {target_table} ({row_count} rows)", always_show=True)
                succeeded += 1
                
            except Exception as e:
                log(f"Error processing view {view_name}: {str(e)}", is_error=True)
                failed += 1
                continue
            
            # Record timing
            end_time = time.time()
            elapsed_time = end_time - start_time
            view_timings[view_name] = elapsed_time
        
        # Print timing summary
        log("\nView Replication Timing Summary (sorted by duration):", always_show=True)
        log("-" * 60, always_show=True)
        log(f"{'View Name':<40} {'Duration (seconds)':<20}", always_show=True)
        log("-" * 60, always_show=True)
        
        # Sort views by duration (descending)
        sorted_views = sorted(view_timings.items(), key=lambda x: x[1], reverse=True)
        
        for view_name, duration in sorted_views:
            log(f"{view_name:<40} {duration:<20.2f}", always_show=True)
        
        log("-" * 60, always_show=True)
        total_time = sum(view_timings.values())
        log(f"Total replication time: {total_time:.2f} seconds", always_show=True)
        
        # Automatically run audit sync if TRANSFERS_METADATA was processed
        if 'TRANSFERS_METADATA' in filtered_stripe_views:
            sync_transfers_metadata_audit(snowflake_conn)
        
        # Run post-processing SQL after all view replication is complete
        run_stripe_post_processing(snowflake_conn)
        
        if succeeded + failed == 0:
            return 'failed'
        elif failed == 0:
            return 'success'
        elif succeeded > 0:
            return 'partial'
        else:
            return 'failed'
    except Exception as e:
        log(f"Error: {str(e)}", is_error=True)
        import traceback
        traceback.print_exc()
        return 'failed'

def sync_transfers_metadata_audit(snowflake_conn):
    """
    Syncs STRIPE.STRIPE.TRANSFERS_METADATA to PF.BI.BI_CP_METADATA_AUDIT.
    Ensures no duplicate audit records are created.
    """
    print("Special case: populating TRANSFERS_METADATA audit table")
    cur = snowflake_conn.cursor()
    try:
        # 1. Insert any new metadata records not already in the audit table (initial load or new values)
        insert_sql = """
        INSERT INTO PF.BI.BI_CP_METADATA_AUDIT (
            REFERENCE_ID,
            REFERENCE_TYPE,
            REFERENCE_DATE,
            METADATA_KEY_NEW,
            METADATA_VALUE_OLD,
            METADATA_VALUE_NEW
        )
        SELECT
            tm.TRANSFER_ID,
            'TRANSFER',
            CAST(tm.BATCH_TIMESTAMP AS DATE),
            tm.KEY,
            NULL,
            tm.VALUE
        FROM STRIPE.STRIPE.TRANSFERS_METADATA tm
        WHERE NOT EXISTS (
            SELECT 1 FROM PF.BI.BI_CP_METADATA_AUDIT a
            WHERE a.REFERENCE_ID = tm.TRANSFER_ID
              AND a.REFERENCE_TYPE = 'TRANSFER'
              AND a.REFERENCE_DATE = CAST(tm.BATCH_TIMESTAMP AS DATE)
              AND a.METADATA_KEY_NEW = tm.KEY
              AND a.METADATA_VALUE_NEW = tm.VALUE
        );
        """
        cur.execute(insert_sql)

        # 2. For any changed value (same id/key/date, different value), insert a new audit record with old value
        # (This is a safety net for updates, but with your PK, only new values will be inserted)
        update_sql = """
        INSERT INTO PF.BI.BI_CP_METADATA_AUDIT (
            REFERENCE_ID,
            REFERENCE_TYPE,
            REFERENCE_DATE,
            METADATA_KEY_NEW,
            METADATA_VALUE_OLD,
            METADATA_VALUE_NEW
        )
        SELECT
            tm.TRANSFER_ID,
            'TRANSFER',
            CAST(tm.BATCH_TIMESTAMP AS DATE),
            tm.KEY,
            a.METADATA_VALUE_NEW,
            tm.VALUE
        FROM STRIPE.STRIPE.TRANSFERS_METADATA tm
        JOIN PF.BI.BI_CP_METADATA_AUDIT a
          ON a.REFERENCE_ID = tm.TRANSFER_ID
         AND a.REFERENCE_TYPE = 'TRANSFER'
         AND a.METADATA_KEY_NEW = tm.KEY
        WHERE a.REFERENCE_DATE < CAST(tm.BATCH_TIMESTAMP AS DATE)
          AND a.METADATA_VALUE_NEW <> tm.VALUE
          AND NOT EXISTS (
              SELECT 1 FROM PF.BI.BI_CP_METADATA_AUDIT a2
              WHERE a2.REFERENCE_ID = tm.TRANSFER_ID
                AND a2.REFERENCE_TYPE = 'TRANSFER'
                AND a2.REFERENCE_DATE = CAST(tm.BATCH_TIMESTAMP AS DATE)
                AND a2.METADATA_KEY_NEW = tm.KEY
                AND a2.METADATA_VALUE_NEW = tm.VALUE
          );
        """
        cur.execute(update_sql)

        print("Audit sync for TRANSFERS_METADATA completed successfully.")
    finally:
        cur.close()

def run_stripe_post_processing(snowflake_conn):
    """
    Runs the Stripe post-processing SQL to add database comments.
    """
    log("Running Stripe post-processing SQL...", always_show=True)
    cur = snowflake_conn.cursor()
    try:
        # Read the SQL file
        sql_file_path = os.path.join(os.path.dirname(__file__), 'sql', 'stripe_post_processing.sql')
        with open(sql_file_path, 'r') as f:
            sql_content = f.read()
        
        # Split on SQL statement boundaries and execute each statement
        statements = sql_content.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    cur.execute(statement)
                except Exception as e:
                    log(f"Warning: Failed to execute statement: {statement[:50]}... Error: {str(e)}", is_error=True)
        
        log("Stripe post-processing SQL completed successfully.", always_show=True)
    except Exception as e:
        log(f"Error running Stripe post-processing SQL: {str(e)}", is_error=True)
    finally:
        cur.close()

if __name__ == "__main__":
    run_replicate_stripe_views() 