"""
AI-Powered Dashboard System - Main Application
With File Upload Support for CSV, Excel, and SQLite databases

Usage:
streamlit run app.py
"""

import streamlit as st
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
import pandas as pd
import sqlite3
import tempfile
from pathlib import Path
import re

# Import our custom modules
from schema_inspector import SchemaInspector
from sql_validator import SQLValidator, SecureQueryExecutor
from llm_query_generator import TextToSQLGenerator, QueryRefiner
from visualization_generator import VisualizationGenerator

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="AI Dashboard Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


class DatabaseHandler:
    """Handles file uploads and database conversion"""
    
    @staticmethod
    def convert_csv_to_sqlite(uploaded_files, db_name="uploaded_database.sqlite"):
        """Convert uploaded CSV files to SQLite"""
        
        conn = sqlite3.connect(db_name)
        imported_tables = []
        
        for uploaded_file in uploaded_files:
            try:
                # Read CSV
                df = pd.read_csv(uploaded_file)
                
                # Create table name from filename
                table_name = Path(uploaded_file.name).stem.lower()
                table_name = table_name.replace('-', '_').replace(' ', '_').replace('.', '_')
                
                # Clean column names
                df.columns = [
    re.sub(r'[^a-z0-9_]', '_', str(col).strip().lower())
    for col in df.columns
]
                
                # Import to SQLite
                df.to_sql(table_name, conn, if_exists='replace', index=False)
                
                imported_tables.append({
                    'file': uploaded_file.name,
                    'table': table_name,
                    'rows': len(df),
                    'columns': len(df.columns)
                })
                
            except Exception as e:
                st.error(f"Error importing {uploaded_file.name}: {str(e)}")
        
        conn.close()
        return db_name, imported_tables
    
    @staticmethod
    def convert_excel_to_sqlite(uploaded_file, db_name="uploaded_database.sqlite"):
        """Convert uploaded Excel file to SQLite"""
        
        conn = sqlite3.connect(db_name)
        imported_tables = []
        
        try:
            # Read all sheets from Excel
            excel_file = pd.ExcelFile(uploaded_file)
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                
                # Create table name from sheet name
                table_name = sheet_name.lower().replace(' ', '_').replace('-', '_')
                
                # Clean column names
                df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').replace('-', '_')
                
                # Import to SQLite
                df.to_sql(table_name, conn, if_exists='replace', index=False)
                
                imported_tables.append({
                    'sheet': sheet_name,
                    'table': table_name,
                    'rows': len(df),
                    'columns': len(df.columns)
                })
            
        except Exception as e:
            st.error(f"Error importing Excel file: {str(e)}")
        
        conn.close()
        return db_name, imported_tables
    
    @staticmethod
    def save_uploaded_sqlite(uploaded_file, db_name="uploaded_database.sqlite"):
        """Save uploaded SQLite file"""
        
        try:
            # Save uploaded file
            with open(db_name, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            # Verify it's a valid SQLite database
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            return db_name, [{'table': t[0]} for t in tables]
            
        except Exception as e:
            st.error(f"Error loading SQLite file: {str(e)}")
            return None, []


class DashboardApp:
    """Main dashboard application"""
    
    def __init__(self):
        self.initialize_session_state()
        self.load_configuration()
        
    def initialize_session_state(self):
        """Initialize Streamlit session state"""
        if 'history' not in st.session_state:
            st.session_state.history = []
        if 'schema_loaded' not in st.session_state:
            st.session_state.schema_loaded = False
        if 'schema_description' not in st.session_state:
            st.session_state.schema_description = None
        if 'db_connected' not in st.session_state:
            st.session_state.db_connected = False
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = 'gemini'
        if 'llm_configured' not in st.session_state:
            st.session_state.llm_configured = False
        if 'uploaded_db_name' not in st.session_state:
            st.session_state.uploaded_db_name = None
    
    def load_configuration(self):
        """Load database and API configuration"""
        
        # Sidebar for configuration
        with st.sidebar:
            st.title("⚙️ Configuration")
            
            # ===========================================
            # LLM PROVIDER SELECTION
            # ===========================================
            st.subheader("🤖 AI Model Selection")
            
            provider = st.selectbox(
                "Choose LLM Provider",
                ["Gemini (Google)", "Claude (Anthropic)", "OpenAI"],
                help="Select which AI model to use for generating SQL queries"
            )
            
            # Map display names to internal names
            provider_map = {
                "Gemini (Google)": "gemini",
                "Claude (Anthropic)": "claude",
                "OpenAI": "openai"
            }
            selected_provider = provider_map[provider]
            
            # API Key input based on provider
            if selected_provider == "gemini":
                st.info("💡 **Gemini** offers a generous free tier!")
                api_key = st.text_input(
                    "Gemini API Key",
                    type="password",
                    value=os.getenv("GOOGLE_API_KEY", ""),
                    help="Get your free key from https://makersuite.google.com/app/apikey"
                )
                if api_key:
                    os.environ["GOOGLE_API_KEY"] = api_key
                    st.session_state.llm_provider = "gemini"
                    st.session_state.llm_configured = True
                
                with st.expander("📖 How to get Gemini API Key"):
                    st.markdown("""
                    1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
                    2. Click **"Get API Key"**
                    3. Create or select a project
                    4. Click **"Create API Key"**
                    5. Copy and paste here
                    
                    **Free Tier:** 60 requests/minute
                    """)
                    
            elif selected_provider == "claude":
                st.info("💡 **Claude** offers best SQL accuracy!")
                api_key = st.text_input(
                    "Anthropic API Key",
                    type="password",
                    value=os.getenv("ANTHROPIC_API_KEY", ""),
                    help="Get your key from https://console.anthropic.com"
                )
                if api_key:
                    os.environ["ANTHROPIC_API_KEY"] = api_key
                    st.session_state.llm_provider = "claude"
                    st.session_state.llm_configured = True
                    
            elif selected_provider == "openai":
                st.info("💡 **OpenAI** GPT-4 is reliable!")
                api_key = st.text_input(
                    "OpenAI API Key",
                    type="password",
                    value=os.getenv("OPENAI_API_KEY", ""),
                    help="Get your key from https://platform.openai.com"
                )
                if api_key:
                    os.environ["OPENAI_API_KEY"] = api_key
                    st.session_state.llm_provider = "openai"
                    st.session_state.llm_configured = True
            
            st.divider()
            
            # ===========================================
            # DATABASE UPLOAD/CONNECTION
            # ===========================================
            st.subheader("💾 Database Setup")
            
            # Tabs for different input methods
            db_tab1, db_tab2 = st.tabs(["📤 Upload File", "🔌 Connect"])
            
            with db_tab1:
                st.markdown("**Upload your data file:**")
                
                file_type = st.selectbox(
                    "File Type",
                    ["CSV Files", "Excel File (.xlsx)", "SQLite Database"],
                    help="Select the type of file you want to upload"
                )
                
                if file_type == "CSV Files":
                    st.info("💡 You can upload multiple CSV files - each will become a table")
                    uploaded_files = st.file_uploader(
                        "Choose CSV file(s)",
                        type=['csv'],
                        accept_multiple_files=True,
                        help="Each CSV file will be converted to a table in SQLite"
                    )
                    
                    if uploaded_files:
                        if st.button("📥 Import CSV Files", use_container_width=True):
                            with st.spinner("Converting CSV to SQLite..."):
                                db_name, tables = DatabaseHandler.convert_csv_to_sqlite(uploaded_files)
                                
                                if tables:
                                    st.success(f"✅ Imported {len(tables)} table(s)!")
                                    
                                    # Show imported tables
                                    for table_info in tables:
                                        st.write(f"📋 **{table_info['table']}**")
                                        st.write(f"   - Source: {table_info['file']}")
                                        st.write(f"   - Rows: {table_info['rows']:,}")
                                        st.write(f"   - Columns: {table_info['columns']}")
                                    
                                    # Connect to the database
                                    conn_str = f"sqlite:///{db_name}"
                                    st.session_state.uploaded_db_name = db_name
                                    self.connect_database(conn_str)
                
                elif file_type == "Excel File (.xlsx)":
                    st.info("💡 Each sheet will become a separate table")
                    uploaded_file = st.file_uploader(
                        "Choose Excel file",
                        type=['xlsx', 'xls'],
                        help="All sheets will be imported as separate tables"
                    )
                    
                    if uploaded_file:
                        if st.button("📥 Import Excel File", use_container_width=True):
                            with st.spinner("Converting Excel to SQLite..."):
                                db_name, tables = DatabaseHandler.convert_excel_to_sqlite(uploaded_file)
                                
                                if tables:
                                    st.success(f"✅ Imported {len(tables)} sheet(s)!")
                                    
                                    for table_info in tables:
                                        st.write(f"📋 **{table_info['table']}**")
                                        st.write(f"   - Sheet: {table_info['sheet']}")
                                        st.write(f"   - Rows: {table_info['rows']:,}")
                                        st.write(f"   - Columns: {table_info['columns']}")
                                    
                                    conn_str = f"sqlite:///{db_name}"
                                    st.session_state.uploaded_db_name = db_name
                                    self.connect_database(conn_str)
                
                elif file_type == "SQLite Database":
                    st.info("💡 Upload an existing SQLite .db or .sqlite file")
                    uploaded_file = st.file_uploader(
                        "Choose SQLite file",
                        type=['db', 'sqlite', 'sqlite3'],
                        help="Upload a SQLite database file"
                    )
                    
                    if uploaded_file:
                        if st.button("📥 Load SQLite Database", use_container_width=True):
                            with st.spinner("Loading SQLite database..."):
                                db_name, tables = DatabaseHandler.save_uploaded_sqlite(uploaded_file)
                                
                                if db_name and tables:
                                    st.success(f"✅ Loaded {len(tables)} table(s)!")
                                    
                                    for table_info in tables:
                                        st.write(f"📋 {table_info['table']}")
                                    
                                    conn_str = f"sqlite:///{db_name}"
                                    st.session_state.uploaded_db_name = db_name
                                    self.connect_database(conn_str)
            
            with db_tab2:
                st.markdown("**Connect to existing database:**")
                
                db_type = st.selectbox(
                    "Database Type",
                    ["SQLite (Local File)", "PostgreSQL", "MySQL"],
                    help="Select your database type"
                )
                
                if db_type == "SQLite (Local File)":
                    db_path = st.text_input(
                        "SQLite File Path",
                        value="chinook.sqlite",
                        help="Path to your .sqlite file"
                    )
                    
                    if st.button("🔌 Connect", use_container_width=True):
                        if db_path and os.path.exists(db_path):
                            conn_str = f"sqlite:///{db_path}"
                            self.connect_database(conn_str)
                        elif db_path:
                            st.error(f"File not found: {db_path}")
                        else:
                            st.error("Please enter a file path")
                
                elif db_type in ["PostgreSQL", "MySQL"]:
                    host = st.text_input("Host", value="localhost")
                    port = st.text_input("Port", value="5432" if db_type == "PostgreSQL" else "3306")
                    database = st.text_input("Database Name", value="")
                    username = st.text_input("Username", value="")
                    password = st.text_input("Password", type="password", value="")
                    
                    if st.button("🔌 Connect", use_container_width=True):
                        if all([host, port, database, username, password]):
                            conn_str = self._build_connection_string(
                                db_type, host, port, database, username, password
                            )
                            self.connect_database(conn_str)
                        else:
                            st.error("Please fill in all fields")
            
            st.divider()
            
            # ===========================================
            # STATUS INDICATORS
            # ===========================================
            st.subheader("📊 System Status")
            
            # Database status
            if st.session_state.db_connected:
                st.success("✅ Database Connected")
                if st.session_state.uploaded_db_name:
                    st.caption(f"📁 {st.session_state.uploaded_db_name}")
            else:
                st.error("❌ Database Not Connected")
            
            # Schema status
            if st.session_state.schema_loaded:
                st.success("✅ Schema Loaded")
            else:
                st.warning("⚠️ Schema Not Loaded")
            
            # LLM status
            if st.session_state.llm_configured:
                st.success(f"✅ {selected_provider.title()} Configured")
            else:
                st.error("❌ LLM Not Configured")
            
            # Download database option
            if st.session_state.db_connected and st.session_state.uploaded_db_name:
                st.divider()
                st.subheader("💾 Download Database")
                
                if os.path.exists(st.session_state.uploaded_db_name):
                    with open(st.session_state.uploaded_db_name, 'rb') as f:
                        st.download_button(
                            label="⬇️ Download SQLite Database",
                            data=f,
                            file_name=st.session_state.uploaded_db_name,
                            mime="application/x-sqlite3",
                            use_container_width=True
                        )
    
    def _build_connection_string(
        self, db_type: str, host: str, port: str, 
        database: str, username: str, password: str
    ) -> str:
        """Build SQLAlchemy connection string"""
        if db_type == "PostgreSQL":
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        elif db_type == "MySQL":
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        return ""
    
    def connect_database(self, connection_string: str):
        """Connect to database and load schema"""
        try:
            with st.spinner("🔌 Connecting to database..."):
                # Test connection
                engine = create_engine(connection_string)
                connection = engine.connect()
                connection.close()
                
                # Store in session state
                st.session_state.connection_string = connection_string
                st.session_state.db_connected = True
                
                # Load schema
                self.load_schema(connection_string)
                
                st.success("✅ Connected successfully!")
                st.balloons()
                
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")
            st.session_state.db_connected = False
    
    def load_schema(self, connection_string: str):
        """Load and cache database schema"""
        try:
            with st.spinner("📚 Loading database schema..."):
                inspector = SchemaInspector(connection_string)
                schema_description = inspector.get_schema_for_llm()
                
                st.session_state.schema_description = schema_description
                st.session_state.inspector = inspector
                st.session_state.schema_loaded = True
                
                # Show schema summary
                schema_data = inspector.get_schema_summary()
                num_tables = len(schema_data.get('tables', {}))
                st.sidebar.info(f"📋 Found {num_tables} table(s)")
                
        except Exception as e:
            st.error(f"❌ Schema loading failed: {str(e)}")
            st.session_state.schema_loaded = False
    
    def run(self):
        """Main application loop"""
        
        # Header
        st.title("📊 AI-Powered Dashboard Generator")
        st.markdown("""
        **Upload your data** (CSV, Excel, or SQLite) and ask questions in **plain English** to get instant visualizations.
        
        💡 *No SQL knowledge required!*
        """)
        
        # Check prerequisites
        if not st.session_state.db_connected:
            st.warning("⚠️ **Please upload or connect to a database** using the sidebar →")
            
            # Quick start guide
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info("""
                **📤 Upload CSV Files**
                1. Go to sidebar
                2. Select "Upload File" tab
                3. Choose "CSV Files"
                4. Upload your CSV file(s)
                5. Click "Import CSV Files"
                """)
            
            with col2:
                st.info("""
                **📊 Upload Excel**
                1. Go to sidebar
                2. Select "Upload File" tab
                3. Choose "Excel File"
                4. Upload your .xlsx file
                5. Click "Import Excel File"
                """)
            
            with col3:
                st.info("""
                **💾 Use Sample Database**
                1. Go to sidebar
                2. Select "Connect" tab
                3. Choose "SQLite (Local File)"
                4. Enter: chinook.sqlite
                5. Click "Connect"
                """)
            
            return
        
        if not st.session_state.llm_configured:
            st.warning("⚠️ **Please configure an LLM API key** using the sidebar →")
            st.info("""
            **Recommended:**
            - **Gemini (Free)**: Best for testing, generous free tier
            - Get your key at: https://makersuite.google.com/app/apikey
            """)
            return
        
        # Main query interface
        self.query_interface()
        
        # Show history
        if st.session_state.history:
            st.divider()
            self.show_history()
    
    def query_interface(self):
        """Main query input and results interface"""
        
        # Show current provider and database
        col1, col2 = st.columns(2)
        with col1:
            provider_name = st.session_state.llm_provider.title()
            st.info(f"🤖 Using **{provider_name}** for SQL generation")
        with col2:
            if st.session_state.uploaded_db_name:
                st.info(f"💾 Database: **{st.session_state.uploaded_db_name}**")
        
        # Show database schema
        with st.expander("📋 View Database Schema"):
            if st.session_state.schema_description:
                st.text(st.session_state.schema_description)
        
        # Example questions
        with st.expander("💡 Example Questions", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **Basic Queries:**
                - Show all records from [table_name]
                - How many rows are in [table_name]?
                - What columns are in [table_name]?
                - Show first 10 rows
                """)
            
            with col2:
                st.markdown("""
                **Analysis Queries:**
                - Show top 10 [items] by [metric]
                - Display [metric] trends over time
                - Compare [metric] across [categories]
                - What's the average [value] by [group]?
                """)
        
        # Query input
        question = st.text_area(
            "❓ Ask a question about your data:",
            height=100,
            placeholder="e.g., Show the top 10 customers by total purchases",
            key="question_input"
        )
        
        col1, col2, col3 = st.columns([2, 2, 6])
        with col1:
            submit = st.button("🚀 Generate Dashboard", type="primary", use_container_width=True)
        with col2:
            clear = st.button("🗑️ Clear History", use_container_width=True)
            if clear:
                st.session_state.history = []
                st.success("History cleared!")
                st.rerun()
        
        if submit and question:
            self.process_question(question)
    
    def process_question(self, question: str):
        """Process user question and generate dashboard"""
        
        with st.spinner("🤖 Generating SQL query..."):
            try:
                # Initialize components
                provider = st.session_state.llm_provider
                generator = TextToSQLGenerator(provider=provider)
                validator = SQLValidator()
                engine = create_engine(st.session_state.connection_string)
                executor = SecureQueryExecutor(engine, validator)
                viz_generator = VisualizationGenerator()
                
                # Generate SQL
                result = generator.generate_sql(
                    question,
                    st.session_state.schema_description
                )
                
                if not result.get("success"):
                    st.error(f"❌ Failed to generate query: {result.get('error')}")
                    if 'raw_response' in result:
                        with st.expander("🔍 Debug Info"):
                            st.text(result['raw_response'])
                    return
                
                sql_query = result["sql"]
                explanation = result.get("explanation", "")
                viz_hint = result.get("visualization_hint", "auto")
                
                # Display SQL
                with st.expander("📝 Generated SQL Query", expanded=True):
                    st.code(sql_query, language="sql")
                    if explanation:
                        st.info(f"**Explanation:** {explanation}")
                
                # Execute query
                with st.spinner("⚡ Executing query..."):
                    success, query_result = executor.execute_query(sql_query)
                
                if not success:
                    st.error(f"❌ Query execution failed: {query_result.get('error', 'Unknown error')}")
                    return
                
                if query_result['row_count'] == 0:
                    st.warning("⚠️ Query executed but returned no results")
                    return
                
                # Generate visualization
                with st.spinner("📊 Creating visualization..."):
                    viz_result = viz_generator.generate(
                        query_result['rows'],
                        chart_type=viz_hint,
                        title=question,
                        question=question
                    )
                
                if viz_result.get('success'):
                    # Display visualization
                    st.plotly_chart(
                        viz_result['figure'],
                        use_container_width=True,
                        key=f"chart_{len(st.session_state.history)}"
                    )
                    
                    # Data summary
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Rows", query_result['row_count'])
                    with col2:
                        st.metric("📋 Columns", len(query_result['columns']))
                    with col3:
                        st.metric("📈 Chart", viz_result['chart_type'].title())
                    
                    # Raw data
                    with st.expander("📋 View Raw Data"):
                        df = pd.DataFrame(query_result['rows'])
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "⬇️ Download CSV",
                            csv,
                            f"results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            "text/csv"
                        )
                    
                    # Add to history
                    st.session_state.history.append({
                        'question': question,
                        'sql': sql_query,
                        'result': query_result,
                        'visualization': viz_result,
                        'timestamp': pd.Timestamp.now(),
                        'provider': provider
                    })
                    
                    st.success("✅ Dashboard generated!")
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                with st.expander("🔍 Details"):
                    st.exception(e)
    
    def show_history(self):
        """Display query history"""
        st.subheader("📜 Query History")
        
        for idx, entry in enumerate(reversed(st.session_state.history)):
            with st.expander(f"Q{len(st.session_state.history)-idx}: {entry['question'][:80]}..."):
                st.code(entry['sql'], language="sql")
                st.plotly_chart(entry['visualization']['figure'], use_container_width=True)


def main():
    """Application entry point"""
    
    # Custom CSS
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    app = DashboardApp()
    app.run()


if __name__ == "__main__":
    main()
