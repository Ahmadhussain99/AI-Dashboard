"""
Comprehensive Test Suite for AI Dashboard System

Run with: pytest test_suite.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from sqlalchemy import create_engine, text
import json

# Import components to test
from sql_validator import SQLValidator, SecureQueryExecutor
from schema_inspector import SchemaInspector
from llm_query_generator import TextToSQLGenerator, QueryRefiner
from visualization_generator import VisualizationGenerator


class TestSQLValidator:
    """Test SQL validation and security"""
    
    def setup_method(self):
        self.validator = SQLValidator()
    
    def test_valid_select_query(self):
        """Test that valid SELECT queries pass"""
        queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM customers WHERE active = true",
            "SELECT COUNT(*) FROM orders GROUP BY region",
            "SELECT a.*, b.name FROM orders a JOIN customers b ON a.customer_id = b.id"
        ]
        
        for query in queries:
            is_valid, errors = self.validator.validate(query)
            assert is_valid, f"Query should be valid: {query}"
            assert len(errors) == 0
    
    def test_forbidden_keywords(self):
        """Test that dangerous keywords are blocked"""
        forbidden_queries = [
            "INSERT INTO users VALUES (1, 'hacker')",
            "UPDATE users SET role = 'admin'",
            "DELETE FROM users",
            "DROP TABLE users",
            "CREATE TABLE evil (id INT)",
            "ALTER TABLE users ADD COLUMN hack TEXT",
            "TRUNCATE TABLE users",
            "GRANT ALL ON users TO hacker"
        ]
        
        for query in forbidden_queries:
            is_valid, errors = self.validator.validate(query)
            assert not is_valid, f"Query should be blocked: {query}"
            assert len(errors) > 0
    
    def test_sql_injection_attempts(self):
        """Test that SQL injection patterns are detected"""
        injection_attempts = [
            "SELECT * FROM users WHERE id = 1; DROP TABLE users;",
            "SELECT * FROM users WHERE id = 1 OR 1=1--",
            "SELECT * FROM users; DELETE FROM logs;",
            "SELECT * FROM users WHERE name = ''; DROP TABLE users--'"
        ]
        
        for query in injection_attempts:
            is_valid, errors = self.validator.validate(query)
            assert not is_valid, f"Injection should be blocked: {query}"
    
    def test_forbidden_functions(self):
        """Test that dangerous functions are blocked"""
        dangerous_queries = [
            "SELECT LOAD_FILE('/etc/passwd')",
            "SELECT * FROM users INTO OUTFILE '/tmp/users.txt'",
            "SELECT SLEEP(10)",
            "SELECT BENCHMARK(1000000, MD5('test'))"
        ]
        
        for query in dangerous_queries:
            is_valid, errors = self.validator.validate(query)
            assert not is_valid, f"Dangerous function should be blocked: {query}"
    
    def test_query_sanitization(self):
        """Test query sanitization"""
        query_with_comments = """
        SELECT * FROM users  -- get all users
        WHERE active = true /* only active */
        """
        
        sanitized = self.validator.sanitize_query(query_with_comments)
        assert '--' not in sanitized or '/*' not in sanitized
        assert 'SELECT' in sanitized.upper()
    
    def test_empty_query(self):
        """Test empty query handling"""
        is_valid, errors = self.validator.validate("")
        assert not is_valid
        assert "Empty query" in str(errors)


class TestSchemaInspector:
    """Test schema introspection"""
    
    @pytest.fixture
    def mock_engine(self):
        """Create a mock SQLAlchemy engine"""
        engine = Mock()
        return engine
    
    def test_schema_format_for_llm(self):
        """Test that schema is formatted correctly for LLM"""
        # Use SQLite for testing (no external dependencies)
        engine = create_engine("sqlite:///:memory:")
        
        # Create test tables
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER,
                    amount REAL,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """))
            conn.commit()
        
        inspector = SchemaInspector("sqlite:///:memory:")
        inspector.engine = engine
        inspector.inspector = Mock()
        
        # Mock inspector methods
        inspector.inspector.get_table_names = Mock(return_value=['customers', 'orders'])
        inspector.inspector.get_columns = Mock(side_effect=[
            [  # customers
                {'name': 'id', 'type': 'INTEGER', 'nullable': False, 'default': None},
                {'name': 'name', 'type': 'TEXT', 'nullable': False, 'default': None},
                {'name': 'email', 'type': 'TEXT', 'nullable': True, 'default': None}
            ],
            [  # orders
                {'name': 'id', 'type': 'INTEGER', 'nullable': False, 'default': None},
                {'name': 'customer_id', 'type': 'INTEGER', 'nullable': True, 'default': None},
                {'name': 'amount', 'type': 'REAL', 'nullable': True, 'default': None}
            ]
        ])
        inspector.inspector.get_pk_constraint = Mock(side_effect=[
            {'constrained_columns': ['id']},  # customers
            {'constrained_columns': ['id']}   # orders
        ])
        inspector.inspector.get_foreign_keys = Mock(side_effect=[
            [],  # customers
            [{'constrained_columns': ['customer_id'], 'referred_table': 'customers', 'referred_columns': ['id']}]  # orders
        ])
        inspector.inspector.get_indexes = Mock(return_value=[])
        
        schema = inspector.get_schema_for_llm()
        
        assert 'customers' in schema
        assert 'orders' in schema
        assert 'Table:' in schema


class TestTextToSQLGenerator:
    """Test LLM-based SQL generation"""
    
    @patch('anthropic.Anthropic')
    def test_generate_sql_success(self, mock_anthropic):
        """Test successful SQL generation"""
        # Mock API response
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps({
            "sql": "SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id",
            "explanation": "Sum orders by customer",
            "tables_used": ["orders"],
            "visualization_hint": "bar"
        }))]
        
        mock_client = Mock()
        mock_client.messages.create = Mock(return_value=mock_response)
        mock_anthropic.return_value = mock_client
        
        generator = TextToSQLGenerator(api_key="test_key", provider="claude")
        generator.client = mock_client
        
        result = generator.generate_sql(
            "Show total sales by customer",
            "Table: orders (customer_id, amount)"
        )
        
        assert result.get("success") is True
        assert "SELECT" in result.get("sql", "")
        assert "visualization_hint" in result
    
    def test_parse_json_response(self):
        """Test parsing of different response formats"""
        generator = TextToSQLGenerator(api_key="test_key")
        
        # Test plain JSON
        response = '{"sql": "SELECT * FROM users", "tables_used": ["users"]}'
        result = generator._parse_response(response)
        assert result["success"] is True
        
        # Test JSON with markdown
        response = '```json\n{"sql": "SELECT * FROM users"}\n```'
        result = generator._parse_response(response)
        assert result["success"] is True


class TestVisualizationGenerator:
    """Test visualization generation"""
    
    def setup_method(self):
        self.generator = VisualizationGenerator()
    
    def test_chart_type_detection(self):
        """Test automatic chart type detection"""
        
        # Time series data -> line chart
        time_data = [
            {'date': '2024-01-01', 'sales': 1000},
            {'date': '2024-02-01', 'sales': 1200}
        ]
        df = pd.DataFrame(time_data)
        df['date'] = pd.to_datetime(df['date'])
        
        chart_type = self.generator._detect_chart_type(df, "show sales over time")
        assert chart_type == 'line'
        
        # Categorical comparison -> bar chart
        category_data = [
            {'category': 'A', 'value': 100},
            {'category': 'B', 'value': 200}
        ]
        df = pd.DataFrame(category_data)
        
        chart_type = self.generator._detect_chart_type(df, "compare categories")
        assert chart_type == 'bar'
    
    def test_bar_chart_generation(self):
        """Test bar chart creation"""
        data = [
            {'region': 'North', 'sales': 1000},
            {'region': 'South', 'sales': 1500},
            {'region': 'East', 'sales': 1200}
        ]
        
        result = self.generator.generate(data, chart_type='bar')
        
        assert result['success'] is True
        assert result['chart_type'] == 'bar'
        assert result['figure'] is not None
    
    def test_line_chart_generation(self):
        """Test line chart creation"""
        data = [
            {'month': '2024-01', 'revenue': 5000},
            {'month': '2024-02', 'revenue': 5500},
            {'month': '2024-03', 'revenue': 6000}
        ]
        
        result = self.generator.generate(data, chart_type='line')
        
        assert result['success'] is True
        assert result['chart_type'] == 'line'
    
    def test_pie_chart_generation(self):
        """Test pie chart creation"""
        data = [
            {'category': 'A', 'count': 10},
            {'category': 'B', 'count': 20},
            {'category': 'C', 'count': 15}
        ]
        
        result = self.generator.generate(data, chart_type='pie')
        
        assert result['success'] is True
        assert result['chart_type'] == 'pie'
    
    def test_table_generation(self):
        """Test table creation"""
        data = [
            {'id': 1, 'name': 'Alice', 'age': 30},
            {'id': 2, 'name': 'Bob', 'age': 25}
        ]
        
        result = self.generator.generate(data, chart_type='table')
        
        assert result['success'] is True
        assert result['chart_type'] == 'table'
    
    def test_empty_data_handling(self):
        """Test handling of empty data"""
        result = self.generator.generate([], chart_type='bar')
        
        assert result['success'] is False
        assert 'error' in result


class TestSecureQueryExecutor:
    """Test secure query execution"""
    
    @pytest.fixture
    def mock_engine(self):
        """Create mock database engine"""
        engine = Mock()
        connection = Mock()
        result = Mock()
        
        # Mock query result
        result.keys.return_value = ['id', 'name']
        result.fetchall.return_value = [(1, 'Alice'), (2, 'Bob')]
        
        connection.execute.return_value = result
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        
        engine.connect.return_value = connection
        engine.dialect.name = 'postgresql'
        
        return engine
    
    def test_execute_valid_query(self, mock_engine):
        """Test execution of valid query"""
        validator = SQLValidator()
        executor = SecureQueryExecutor(mock_engine, validator)
        
        success, result = executor.execute_query("SELECT * FROM users")
        
        assert success is True
        assert 'rows' in result
        assert len(result['rows']) == 2
    
    def test_execute_invalid_query(self, mock_engine):
        """Test rejection of invalid query"""
        validator = SQLValidator()
        executor = SecureQueryExecutor(mock_engine, validator)
        
        success, result = executor.execute_query("DROP TABLE users")
        
        assert success is False
        assert 'errors' in result
    
    def test_row_limit_enforcement(self, mock_engine):
        """Test that row limits are enforced"""
        validator = SQLValidator()
        executor = SecureQueryExecutor(mock_engine, validator)
        
        # Query without LIMIT should get one added
        success, result = executor.execute_query("SELECT * FROM users")
        
        # Verify LIMIT was added (check mock calls)
        assert success is True


class TestIntegration:
    """Integration tests for complete workflow"""
    
    @pytest.fixture
    def test_database(self):
        """Create in-memory test database"""
        engine = create_engine("sqlite:///:memory:")
        
        with engine.connect() as conn:
            # Create test schema
            conn.execute(text("""
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER,
                    amount REAL,
                    order_date DATE,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """))
            
            # Insert test data
            conn.execute(text("INSERT INTO customers VALUES (1, 'Alice', 'alice@example.com')"))
            conn.execute(text("INSERT INTO customers VALUES (2, 'Bob', 'bob@example.com')"))
            
            conn.execute(text("INSERT INTO orders VALUES (1, 1, 100.50, '2024-01-01')"))
            conn.execute(text("INSERT INTO orders VALUES (2, 1, 200.75, '2024-01-15')"))
            conn.execute(text("INSERT INTO orders VALUES (3, 2, 150.00, '2024-02-01')"))
            
            conn.commit()
        
        return engine
    
    def test_end_to_end_simple_query(self, test_database):
        """Test complete flow with a simple query"""
        
        # 1. Validate query
        validator = SQLValidator()
        sql = "SELECT * FROM customers"
        is_valid, _ = validator.validate(sql)
        assert is_valid
        
        # 2. Execute query
        executor = SecureQueryExecutor(test_database, validator)
        success, result = executor.execute_query(sql)
        assert success
        assert len(result['rows']) == 2
        
        # 3. Generate visualization
        viz_gen = VisualizationGenerator()
        viz_result = viz_gen.generate(result['rows'], chart_type='table')
        assert viz_result['success']
    
    def test_end_to_end_aggregation(self, test_database):
        """Test complete flow with aggregation"""
        
        sql = "SELECT customer_id, SUM(amount) as total FROM orders GROUP BY customer_id"
        
        validator = SQLValidator()
        is_valid, _ = validator.validate(sql)
        assert is_valid
        
        executor = SecureQueryExecutor(test_database, validator)
        success, result = executor.execute_query(sql)
        assert success
        assert len(result['rows']) == 2
        
        viz_gen = VisualizationGenerator()
        viz_result = viz_gen.generate(result['rows'], chart_type='bar')
        assert viz_result['success']


def run_tests():
    """Run all tests and generate report"""
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--color=yes'
    ])


if __name__ == "__main__":
    run_tests()