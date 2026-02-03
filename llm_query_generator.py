"""
LLM-Powered Text-to-SQL Generator
Supports multiple LLM providers: Claude, Gemini, OpenAI
Updated to use new Google GenAI SDK
"""

import os
import json
from typing import Dict, Any, Optional
from enum import Enum


class LLMProvider(Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENAI = "openai"


class TextToSQLGenerator:
    """Generates SQL queries from natural language using various LLMs"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        provider: str = "gemini"
    ):
        """
        Initialize the generator
        
        Args:
            api_key: API key for the LLM provider
            provider: LLM provider ('claude', 'gemini', or 'openai')
        """
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key_from_env()
        
        if not self.api_key:
            raise ValueError(f"No API key found for provider: {self.provider}")
        
        # Initialize the appropriate client
        if self.provider == "claude":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
            self.model = "claude-sonnet-4-20250514"
            
        elif self.provider == "gemini":
            # Use Google GenAI SDK
            from google import genai
            from google.genai import types
            
            self.client = genai.Client(api_key=self.api_key)
            self.types = types
            self.model = "gemini-2.5-flash"
            
        elif self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            self.model = "gpt-4"
            
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _get_api_key_from_env(self) -> str:
        """Get API key from environment variables"""
        if self.provider == "claude":
            return os.getenv('ANTHROPIC_API_KEY', '')
        elif self.provider == "gemini":
            # Try both old and new env var names
            return os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY', '')
        elif self.provider == "openai":
            return os.getenv('OPENAI_API_KEY', '')
        return ''
        
    def generate_sql(
        self,
        question: str,
        schema_description: str,
        sample_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language question
        
        Args:
            question: User's natural language question
            schema_description: Database schema formatted for LLM
            sample_data: Optional sample data for context
            
        Returns:
            Dictionary containing SQL query and metadata
        """
        
        prompt = self._build_prompt(question, schema_description, sample_data)
        
        try:
            if self.provider == "claude":
                response = self._call_claude(prompt)
            elif self.provider == "gemini":
                response = self._call_gemini(prompt)
            elif self.provider == "openai":
                response = self._call_openai(prompt)
            
            # Parse the response
            result = self._parse_response(response)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"LLM error: {str(e)}"
            }
    
    def _call_claude(self, prompt: str) -> str:
        """Call Claude API"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0,
            system=self._get_system_prompt(),
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        return response.content[0].text
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self.types.GenerateContentConfig(
                system_instruction=self._get_system_prompt(),
                temperature=0,
                max_output_tokens=2000,
            ),
        )
        return response.text
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=2000
        )
        return response.choices[0].message.content
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for SQL generation"""
        return """You are an expert SQL query generator. Your task is to convert natural language questions into valid SQL queries.

CRITICAL RULES:
1. Generate ONLY SELECT queries - no INSERT, UPDATE, DELETE, or DDL
2. Use proper SQL syntax for the database type specified
3. Include appropriate JOINs when multiple tables are needed
4. Use aggregation functions (COUNT, SUM, AVG, etc.) when appropriate
5. Add WHERE clauses for filtering based on the question
6. Use GROUP BY when aggregating data
7. Add ORDER BY to sort results logically
8. Use LIMIT to prevent excessive results (default: 100 unless specified)
9. Handle date/time comparisons correctly
10. Use DISTINCT when needed to avoid duplicates

OUTPUT FORMAT:
Return a JSON object with this structure:
{
  "sql": "the SQL query",
  "explanation": "brief explanation of what the query does",
  "tables_used": ["list", "of", "tables"],
  "visualization_hint": "suggested chart type: bar|line|pie|table|scatter|area"
}

Choose visualization_hint based on the data:
- bar: comparisons across categories, rankings
- line: trends over time
- pie: part-to-whole relationships (use sparingly)
- table: detailed data, many columns
- scatter: relationships between two numeric variables
- area: cumulative values over time"""

    def _build_prompt(
        self,
        question: str,
        schema_description: str,
        sample_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the complete prompt for the LLM"""
        
        prompt = f"""Generate a SQL query to answer this question:

QUESTION: {question}

DATABASE SCHEMA:
{schema_description}
"""
        
        if sample_data:
            prompt += f"""
SAMPLE DATA (for context):
{json.dumps(sample_data, indent=2, default=str)}
"""
        
        prompt += """
Generate the SQL query following the rules in your system prompt. Return only valid JSON."""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM response"""
        
        try:
            # Try to extract JSON from the response
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            else:
                json_str = response_text.strip()
            
            result = json.loads(json_str)
            result["success"] = True
            return result
            
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse JSON response: {str(e)}",
                "raw_response": response_text
            }


class QueryRefiner:
    """Refines queries based on execution results and errors"""
    
    def __init__(self, generator: TextToSQLGenerator):
        self.generator = generator
        
    def refine_query(
        self,
        original_question: str,
        original_sql: str,
        error_message: str,
        schema_description: str
    ) -> Dict[str, Any]:
        """
        Refine a query that resulted in an error
        """
        
        refinement_prompt = f"""The following SQL query resulted in an error. Please fix it.

ORIGINAL QUESTION: {original_question}

FAILED SQL:
{original_sql}

ERROR MESSAGE:
{error_message}

DATABASE SCHEMA:
{schema_description}

Generate a corrected SQL query as JSON."""

        try:
            if self.generator.provider == "claude":
                response = self.generator._call_claude(refinement_prompt)
            elif self.generator.provider == "gemini":
                response = self.generator._call_gemini(refinement_prompt)
            elif self.generator.provider == "openai":
                response = self.generator._call_openai(refinement_prompt)
            
            return self.generator._parse_response(response)
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Refinement error: {str(e)}"
            }


# Testing
if __name__ == "__main__":
    schema = """Database Schema (sqlite):

Table: customers
Columns:
  - customer_id: INTEGER NOT NULL [PRIMARY KEY]
  - name: TEXT NOT NULL
  - email: TEXT NULL
  - city: TEXT NULL
  - created_at: DATE NOT NULL

Table: orders
Columns:
  - order_id: INTEGER NOT NULL [PRIMARY KEY]
  - customer_id: INTEGER NOT NULL
  - product_name: TEXT NOT NULL
  - amount: REAL NOT NULL
  - order_date: DATE NOT NULL
  - status: TEXT NOT NULL
Foreign Keys:
  - customer_id -> customers.customer_id
"""
    
    print("Testing Text-to-SQL Generator (Updated)\n" + "="*50)
    
    # Check for API keys
    providers_available = []
    if os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'):
        providers_available.append('gemini')
    if os.getenv('ANTHROPIC_API_KEY'):
        providers_available.append('claude')
    if os.getenv('OPENAI_API_KEY'):
        providers_available.append('openai')
    
    if not providers_available:
        print("\n[WARN] No API keys found!")
        print("\nSet one in your .env file:")
        print("GOOGLE_API_KEY=your_key_here")
        print("or")
        print("GEMINI_API_KEY=your_key_here")
    else:
        print(f"\n[OK] Available: {', '.join(providers_available)}")
        provider = providers_available[0]
        
        try:
            generator = TextToSQLGenerator(provider=provider)
            print(f"\nUsing: {provider.upper()}")
            
            question = "Show total sales by city"
            print(f"\nQuestion: {question}")
            
            result = generator.generate_sql(question, schema)
            
            if result.get("success"):
                print("\n[OK] SQL Generated:")
                print(f"{result['sql']}")
                print(f"\n[INFO] Visualization: {result.get('visualization_hint')}")
            else:
                print(f"\n[ERROR] {result.get('error')}")
                
        except Exception as e:
            print(f"\n[ERROR] Failed: {e}")
    
    print("\n" + "="*50)
