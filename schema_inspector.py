"""
Database Schema Inspector
Extracts and formats database schema for LLM consumption
"""

from sqlalchemy import create_engine, inspect, MetaData
from typing import Dict, List, Any
import json


class SchemaInspector:
    """Inspects database schema and formats it for LLM understanding"""
    
    def __init__(self, connection_string: str):
        """
        Initialize with database connection
        
        Args:
            connection_string: SQLAlchemy connection string
                e.g., 'postgresql://user:pass@localhost/dbname'
        """
        self.engine = create_engine(connection_string)
        self.inspector = inspect(self.engine)
        
    def get_schema_summary(self) -> Dict[str, Any]:
        """
        Extract complete schema information
        
        Returns:
            Dictionary containing tables, columns, types, relationships
        """
        schema = {
            'database_type': self.engine.dialect.name,
            'tables': {}
        }
        
        for table_name in self.inspector.get_table_names():
            schema['tables'][table_name] = self._get_table_info(table_name)
            
        return schema
    
    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific table"""
        columns = self.inspector.get_columns(table_name)
        pk_constraint = self.inspector.get_pk_constraint(table_name)
        foreign_keys = self.inspector.get_foreign_keys(table_name)
        indexes = self.inspector.get_indexes(table_name)
        
        return {
            'columns': [
                {
                    'name': col['name'],
                    'type': str(col['type']),
                    'nullable': col['nullable'],
                    'default': str(col['default']) if col['default'] else None,
                    'primary_key': col['name'] in pk_constraint.get('constrained_columns', [])
                }
                for col in columns
            ],
            'primary_key': pk_constraint.get('constrained_columns', []),
            'foreign_keys': [
                {
                    'constrained_columns': fk['constrained_columns'],
                    'referred_table': fk['referred_table'],
                    'referred_columns': fk['referred_columns']
                }
                for fk in foreign_keys
            ],
            'indexes': [
                {
                    'name': idx['name'],
                    'columns': idx['column_names'],
                    'unique': idx['unique']
                }
                for idx in indexes
            ]
        }
    
    def get_schema_for_llm(self) -> str:
        """
        Format schema in a way that's optimized for LLM understanding
        
        Returns:
            Human-readable schema description
        """
        schema = self.get_schema_summary()
        
        prompt = f"Database Schema ({schema['database_type']}):\n\n"
        
        for table_name, table_info in schema['tables'].items():
            prompt += f"Table: {table_name}\n"
            prompt += "Columns:\n"
            
            for col in table_info['columns']:
                pk_marker = " [PRIMARY KEY]" if col['primary_key'] else ""
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                prompt += f"  - {col['name']}: {col['type']} {nullable}{pk_marker}\n"
            
            if table_info['foreign_keys']:
                prompt += "Foreign Keys:\n"
                for fk in table_info['foreign_keys']:
                    prompt += f"  - {', '.join(fk['constrained_columns'])} -> "
                    prompt += f"{fk['referred_table']}.{', '.join(fk['referred_columns'])}\n"
            
            prompt += "\n"
        
        return prompt
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict]:
        """
        Get sample rows from a table for context
        
        Args:
            table_name: Name of table to sample
            limit: Number of rows to retrieve
            
        Returns:
            List of dictionaries representing rows
        """
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        
        with self.engine.connect() as conn:
            result = conn.execute(query)
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]


# Example usage
if __name__ == "__main__":
    # Example connection string (update with your credentials)
    conn_str = "postgresql://readonly_user:password@localhost:5432/sales_db"
    
    inspector = SchemaInspector(conn_str)
    
    # Get formatted schema for LLM
    schema_description = inspector.get_schema_for_llm()
    print(schema_description)
    
    # Get sample data for context
    # sample = inspector.get_sample_data('orders', limit=3)
    # print(json.dumps(sample, indent=2, default=str))