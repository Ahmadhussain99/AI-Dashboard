"""
SQL Security Validator
Ensures only safe, read-only SELECT queries are executed
"""

import sqlparse
from sqlparse.sql import Token, Identifier, Function
from sqlparse.tokens import Keyword, DML
from typing import Tuple, List
import re


class SQLValidator:
    """Validates SQL queries for security and read-only compliance"""
    
    # Dangerous keywords that should never appear
    FORBIDDEN_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
        'EXEC', 'EXECUTE', 'CALL', 'LOAD', 'COPY'
    }
    
    # Dangerous functions that could leak data or cause issues
    FORBIDDEN_FUNCTIONS = {
        'LOAD_FILE', 'INTO OUTFILE', 'INTO DUMPFILE',
        'SLEEP', 'BENCHMARK', 'PG_SLEEP'
    }
    
    def __init__(self):
        self.errors = []
        
    def validate(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Validate SQL query for security
        
        Args:
            sql: SQL query string to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        self.errors = []
        
        # Basic sanity checks
        if not sql or not sql.strip():
            self.errors.append("Empty query")
            return False, self.errors
        
        # Remove trailing semicolons for validation
        sql = sql.rstrip(';').strip()
        
        # Parse the SQL
        try:
            parsed = sqlparse.parse(sql)
        except Exception as e:
            self.errors.append(f"SQL parsing error: {str(e)}")
            return False, self.errors
        
        if not parsed:
            self.errors.append("Unable to parse SQL")
            return False, self.errors
        
        # Validate each statement
        for statement in parsed:
            if not self._validate_statement(statement):
                return False, self.errors
        
        return True, []
    
    def _validate_statement(self, statement) -> bool:
        """Validate a single SQL statement"""
        
        # Check if it's a SELECT statement
        if not self._is_select_statement(statement):
            self.errors.append("Only SELECT queries are allowed")
            return False
        
        # Check for forbidden keywords
        if not self._check_forbidden_keywords(statement):
            return False
        
        # Check for forbidden functions
        if not self._check_forbidden_functions(statement):
            return False
        
        # Check for suspicious patterns (SQL injection attempts)
        if not self._check_injection_patterns(str(statement)):
            return False
        
        return True
    
    def _is_select_statement(self, statement) -> bool:
        """Check if statement is a SELECT"""
        first_token = statement.token_first(skip_ws=True, skip_cm=True)
        if first_token and first_token.ttype is DML:
            return first_token.value.upper() == 'SELECT'
        return False
    
    def _check_forbidden_keywords(self, statement) -> bool:
        """Check for forbidden SQL keywords"""
        sql_upper = str(statement).upper()
        
        for keyword in self.FORBIDDEN_KEYWORDS:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                self.errors.append(f"Forbidden keyword detected: {keyword}")
                return False
        
        return True
    
    def _check_forbidden_functions(self, statement) -> bool:
        """Check for dangerous SQL functions"""
        sql_upper = str(statement).upper()
        
        for func in self.FORBIDDEN_FUNCTIONS:
            if func in sql_upper:
                self.errors.append(f"Forbidden function detected: {func}")
                return False
        
        return True
    
    def _check_injection_patterns(self, sql: str) -> bool:
        """Check for common SQL injection patterns"""
        
        # Check for comment-based injection
        if '--' in sql or '/*' in sql or '*/' in sql:
            comment_pattern = r'--.*(?:DROP|DELETE|INSERT|UPDATE|EXEC)'
            if re.search(comment_pattern, sql, re.IGNORECASE):
                self.errors.append("Suspicious comment pattern detected")
                return False
        
        # Check for stacked queries (multiple statements)
        # Remove the SQL string from semicolons first
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        if ';' in sql_no_strings:
            # Check if there's actual content after semicolon
            parts = sql_no_strings.split(';')
            if len([p.strip() for p in parts if p.strip()]) > 1:
                self.errors.append("Multiple statements not allowed")
                return False
        
        return True
    
    def sanitize_query(self, sql: str) -> str:
        """
        Sanitize a query by removing comments and normalizing whitespace
        
        Args:
            sql: Original SQL query
            
        Returns:
            Sanitized SQL query
        """
        # Remove comments
        sql = sqlparse.format(sql, strip_comments=True)
        
        # Normalize whitespace
        sql = sqlparse.format(sql, reindent=False, keyword_case='upper')
        
        # Remove trailing semicolons
        sql = sql.rstrip(';').strip()
        
        return sql


class SecureQueryExecutor:
    """Executes validated queries with additional safety measures"""
    
    def __init__(self, engine, validator: SQLValidator = None):
        """
        Initialize executor
        
        Args:
            engine: SQLAlchemy engine (should use read-only credentials)
            validator: SQLValidator instance
        """
        self.engine = engine
        self.validator = validator or SQLValidator()
        
    def execute_query(self, sql: str, max_rows: int = 10000) -> Tuple[bool, any]:
        """
        Execute a validated query with safety limits
        
        Args:
            sql: SQL query to execute
            max_rows: Maximum number of rows to return
            
        Returns:
            Tuple of (success, result_or_error)
        """
        # Validate the query
        is_valid, errors = self.validator.validate(sql)
        
        if not is_valid:
            return False, {"errors": errors}
        
        # Sanitize the query
        clean_sql = self.validator.sanitize_query(sql)
        
        # Remove any trailing semicolons
        clean_sql = clean_sql.rstrip(';').strip()
        
        # Add LIMIT clause if not present (safety measure)
        if 'LIMIT' not in clean_sql.upper():
            clean_sql = f"{clean_sql} LIMIT {max_rows}"
        
        try:
            # Execute with timeout
            with self.engine.connect() as conn:
                # Set statement timeout (PostgreSQL only)
                if self.engine.dialect.name == 'postgresql':
                    from sqlalchemy import text
                    conn.execute(text("SET statement_timeout = 30000"))  # 30 seconds
                
                # Import text for proper query execution
                from sqlalchemy import text
                
                # Execute query
                result = conn.execute(text(clean_sql))
                columns = list(result.keys())
                rows = result.fetchall()
                
                return True, {
                    'columns': columns,
                    'rows': [dict(zip(columns, row)) for row in rows],
                    'row_count': len(rows)
                }
                
        except Exception as e:
            return False, {"error": f"Query execution error: {str(e)}"}


# Example usage and testing
if __name__ == "__main__":
    validator = SQLValidator()
    
    print("Testing SQL Validator\n" + "="*50)
    
    # Test valid query
    print("\n1. Testing VALID SELECT query:")
    valid_sql = "SELECT customer_id, SUM(amount) FROM orders WHERE date > '2024-01-01' GROUP BY customer_id"
    is_valid, errors = validator.validate(valid_sql)
    print(f"Query: {valid_sql}")
    print(f"Valid: {is_valid}")
    if errors:
        print(f"Errors: {errors}")
    
    # Test query with semicolon
    print("\n2. Testing query with semicolon:")
    sql_with_semi = "SELECT * FROM users;"
    is_valid, errors = validator.validate(sql_with_semi)
    print(f"Query: {sql_with_semi}")
    print(f"Valid: {is_valid}")
    
    # Test invalid queries
    print("\n3. Testing INVALID queries:")
    invalid_queries = [
        ("SQL Injection", "SELECT * FROM users; DROP TABLE users;"),
        ("UPDATE attempt", "UPDATE users SET password = 'hacked'"),
        ("INSERT attempt", "INSERT INTO logs VALUES ('test')")
    ]
    
    for name, sql in invalid_queries:
        print(f"\n  {name}:")
        print(f"  Query: {sql[:60]}...")
        is_valid, errors = validator.validate(sql)
        print(f"  Valid: {is_valid}")
        if errors:
            print(f"  Errors: {errors}")
    
    print("\n" + "="*50)
    print("✅ SQL Validator testing complete!")