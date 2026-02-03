"""
Dashboard Visualization Generator
Converts query results into appropriate visualizations
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List, Optional
import numpy as np


class VisualizationGenerator:
    """Generates appropriate visualizations based on query results"""
    
    def __init__(self):
        self.chart_types = {
            'bar': self._create_bar_chart,
            'line': self._create_line_chart,
            'pie': self._create_pie_chart,
            'scatter': self._create_scatter_chart,
            'area': self._create_area_chart,
            'table': self._create_table
        }
    
    def generate(
        self,
        data: List[Dict[str, Any]],
        chart_type: str = 'auto',
        title: str = None,
        question: str = None
    ) -> Dict[str, Any]:
        """
        Generate visualization from query results
        
        Args:
            data: List of dictionaries (query results)
            chart_type: Type of chart ('bar', 'line', 'pie', 'auto')
            title: Chart title
            question: Original question (for auto-detection)
            
        Returns:
            Dictionary with figure and metadata
        """
        
        if not data:
            return {
                'success': False,
                'error': 'No data to visualize'
            }
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(data)
        
        # Auto-detect chart type if needed
        if chart_type == 'auto':
            chart_type = self._detect_chart_type(df, question)
        
        # Generate the visualization
        if chart_type in self.chart_types:
            try:
                fig = self.chart_types[chart_type](df, title)
                return {
                    'success': True,
                    'figure': fig,
                    'chart_type': chart_type,
                    'data_shape': df.shape
                }
            except Exception as e:
                # Fallback to table on error
                return {
                    'success': True,
                    'figure': self._create_table(df, title),
                    'chart_type': 'table',
                    'warning': f'Could not create {chart_type} chart: {str(e)}'
                }
        else:
            return {
                'success': False,
                'error': f'Unknown chart type: {chart_type}'
            }
    
    def _detect_chart_type(self, df: pd.DataFrame, question: str = None) -> str:
        """
        Automatically detect the best chart type
        
        Args:
            df: DataFrame with query results
            question: User's original question
            
        Returns:
            Suggested chart type
        """
        
        # Check column types
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        date_cols = df.select_dtypes(include=['datetime64']).columns
        categorical_cols = df.select_dtypes(include=['object']).columns
        
        n_rows = len(df)
        n_cols = len(df.columns)
        
        # If question mentions trends or time
        if question:
            q_lower = question.lower()
            if any(word in q_lower for word in ['trend', 'over time', 'timeline', 'history']):
                return 'line'
            if any(word in q_lower for word in ['compare', 'comparison', 'versus', 'vs']):
                return 'bar'
            if any(word in q_lower for word in ['breakdown', 'distribution', 'composition']):
                if n_rows <= 10:
                    return 'pie'
                else:
                    return 'bar'
        
        # Time series data
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            return 'line'
        
        # Two numeric columns -> scatter
        if len(numeric_cols) >= 2 and n_rows > 5:
            return 'scatter'
        
        # One categorical, one numeric -> bar
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            if n_rows <= 15:
                return 'bar'
        
        # Small categorical breakdown -> pie
        if len(categorical_cols) > 0 and len(numeric_cols) > 0 and n_rows <= 8:
            return 'pie'
        
        # Default to table for complex data
        if n_cols > 5 or n_rows > 100:
            return 'table'
        
        return 'bar'  # Safe default
    
    def _create_bar_chart(self, df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create a bar chart"""
        
        # Find x (categorical) and y (numeric) columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns
        
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            x_col = categorical_cols[0]
            y_col = numeric_cols[0]
            
            # Sort by value for better visualization
            df_sorted = df.sort_values(by=y_col, ascending=False)
            
            fig = px.bar(
                df_sorted,
                x=x_col,
                y=y_col,
                title=title or f'{y_col} by {x_col}',
                labels={x_col: x_col.replace('_', ' ').title(),
                       y_col: y_col.replace('_', ' ').title()}
            )
            
            fig.update_layout(
                xaxis_tickangle=-45,
                height=500,
                showlegend=False
            )
            
            return fig
        else:
            raise ValueError("Need categorical and numeric columns for bar chart")
    
    def _create_line_chart(self, df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create a line chart (typically for time series)"""
        
        # Find date/time column and numeric columns
        date_cols = df.select_dtypes(include=['datetime64']).columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        # If no datetime column, try to convert first column
        if len(date_cols) == 0:
            first_col = df.columns[0]
            try:
                df[first_col] = pd.to_datetime(df[first_col])
                date_cols = [first_col]
            except:
                pass
        
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            x_col = date_cols[0]
            y_col = numeric_cols[0]
            
            # Sort by date
            df_sorted = df.sort_values(by=x_col)
            
            fig = px.line(
                df_sorted,
                x=x_col,
                y=y_col,
                title=title or f'{y_col} over time',
                markers=True
            )
            
            fig.update_layout(height=500)
            
            return fig
        else:
            # Fallback: use first two columns
            fig = px.line(
                df,
                x=df.columns[0],
                y=df.columns[1],
                title=title or 'Trend',
                markers=True
            )
            fig.update_layout(height=500)
            return fig
    
    def _create_pie_chart(self, df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create a pie chart"""
        
        # Find categorical and numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns
        
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            labels_col = categorical_cols[0]
            values_col = numeric_cols[0]
            
            # Limit to top N slices for readability
            if len(df) > 10:
                df = df.nlargest(10, values_col)
            
            fig = px.pie(
                df,
                names=labels_col,
                values=values_col,
                title=title or f'{values_col} by {labels_col}'
            )
            
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=500)
            
            return fig
        else:
            raise ValueError("Need categorical and numeric columns for pie chart")
    
    def _create_scatter_chart(self, df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create a scatter plot"""
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) >= 2:
            x_col = numeric_cols[0]
            y_col = numeric_cols[1]
            
            # Check for a categorical column to use for color
            categorical_cols = df.select_dtypes(exclude=[np.number]).columns
            color_col = categorical_cols[0] if len(categorical_cols) > 0 else None
            
            fig = px.scatter(
                df,
                x=x_col,
                y=y_col,
                color=color_col,
                title=title or f'{y_col} vs {x_col}',
                labels={x_col: x_col.replace('_', ' ').title(),
                       y_col: y_col.replace('_', ' ').title()}
            )
            
            fig.update_layout(height=500)
            
            return fig
        else:
            raise ValueError("Need at least two numeric columns for scatter plot")
    
    def _create_area_chart(self, df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create an area chart"""
        
        # Similar to line chart but with filled area
        date_cols = df.select_dtypes(include=['datetime64']).columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(date_cols) == 0:
            first_col = df.columns[0]
            try:
                df[first_col] = pd.to_datetime(df[first_col])
                date_cols = [first_col]
            except:
                pass
        
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            x_col = date_cols[0]
            y_col = numeric_cols[0]
            
            df_sorted = df.sort_values(by=x_col)
            
            fig = px.area(
                df_sorted,
                x=x_col,
                y=y_col,
                title=title or f'{y_col} over time'
            )
            
            fig.update_layout(height=500)
            
            return fig
        else:
            fig = px.area(
                df,
                x=df.columns[0],
                y=df.columns[1],
                title=title or 'Area Chart'
            )
            fig.update_layout(height=500)
            return fig
    
    def _create_table(self, df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create a table visualization"""
        
        # Format numeric columns
        df_display = df.copy()
        for col in df_display.select_dtypes(include=[np.number]).columns:
            if df_display[col].dtype == 'float64':
                df_display[col] = df_display[col].round(2)
        
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[f'<b>{col}</b>' for col in df_display.columns],
                fill_color='paleturquoise',
                align='left',
                font=dict(size=12)
            ),
            cells=dict(
                values=[df_display[col] for col in df_display.columns],
                fill_color='lavender',
                align='left',
                font=dict(size=11)
            )
        )])
        
        fig.update_layout(
            title=title or 'Results Table',
            height=min(500, 50 + len(df) * 30)
        )
        
        return fig


# Example usage
if __name__ == "__main__":
    # Sample data
    sample_data = [
        {'month': '2024-01', 'sales': 45000, 'orders': 120},
        {'month': '2024-02', 'sales': 52000, 'orders': 145},
        {'month': '2024-03', 'sales': 48000, 'orders': 135},
        {'month': '2024-04', 'sales': 61000, 'orders': 170},
        {'month': '2024-05', 'sales': 58000, 'orders': 165}
    ]
    
    generator = VisualizationGenerator()
    
    # Generate line chart
    result = generator.generate(
        sample_data,
        chart_type='line',
        title='Monthly Sales Trend',
        question='Show sales over time'
    )
    
    if result['success']:
        # In a real app, you'd render this in Streamlit:
        # st.plotly_chart(result['figure'])
        print(f"Generated {result['chart_type']} chart")
        print(f"Data shape: {result['data_shape']}")