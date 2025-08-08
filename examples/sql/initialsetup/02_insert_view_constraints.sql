-- File: examples/sql/initialsetup/02_insert_view_constraints.sql
-- Insert constraints for V_CREATOR_PAYMENTS_UNION
INSERT INTO AI_VIEW_CONSTRAINTS (VIEW_NAME, ALLOWED_OPERATIONS, FORBIDDEN_KEYWORDS, COLUMN_WHITELIST, COLUMN_DESCRIPTIONS)
VALUES (
    'V_CREATOR_PAYMENTS_UNION',
    ARRAY_CONSTRUCT('SELECT', 'WHERE', 'GROUP BY', 'ORDER BY', 'LIMIT', 'SUM', 'COUNT', 'AVG', 'MAX', 'MIN'),
    ARRAY_CONSTRUCT('DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 'TRUNCATE', 'MERGE'),
    ARRAY_CONSTRUCT('CREATOR_NAME', 'CAMPAIGN_NAME', 'PAYMENT_TYPE', 'COMPANY_NAME', 'PAYMENT_AMOUNT', 
                    'PAYMENT_DATE', 'PAYMENT_STATUS', 'REFERENCE_ID', 'REFERENCE_TYPE'),
    PARSE_JSON('{
        "CREATOR_NAME": "Name of the content creator receiving payment",
        "CAMPAIGN_NAME": "Marketing campaign associated with the payment",
        "PAYMENT_TYPE": "Type of payment (advance, completion, bonus, etc.)",
        "PAYMENT_AMOUNT": "Payment amount in USD",
        "PAYMENT_DATE": "Date when payment was processed",
        "PAYMENT_STATUS": "Status: completed, pending, or failed"
    }')
);
