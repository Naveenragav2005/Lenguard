import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from jinja2 import Template
import fitz  # PyMuPDF

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))

class RentRollPipeline:
    def __init__(self):
        self.html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid black; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            {{ table_html }}
        </body>
        </html>
        """

    def read_file(self, file_path):
        """Read CSV, XLSX, or PDF file into a pandas DataFrame"""
        file_ext = Path(file_path).suffix.lower()
        try:
            if file_ext == '.csv':
                return pd.read_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return pd.read_excel(file_path)
            elif file_ext == '.pdf':
                return self.extract_pdf_data(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
        except Exception as e:
            raise Exception(f"Error reading file: {str(e)}")

    def extract_pdf_data(self, pdf_path):
        """Extract structured data from a PDF file."""
        doc = fitz.open(pdf_path)
        all_data = []
        headers = []
        current_row = []

        for page in doc:
            text = page.get_text("text").split('\n')
        
        # Process each line
        for line in text:
            if "Unit" in line or "Occupancy" in line or "Vacant" in line:
                # Detect header
                headers = line.split()
                continue
            
            # Attempt to parse row data
            row_data = line.split()
            
            # Handle continuation of row data
            if len(row_data) < len(headers):
                current_row.extend(row_data)
            else:
                if current_row:
                    all_data.append(dict(zip(headers, current_row)))
                current_row = row_data

    # Append final row if any
        if current_row:
            all_data.append(dict(zip(headers, current_row)))
        
        return pd.DataFrame(all_data) if all_data else pd.DataFrame()


    def convert_to_html(self, df):
        """Convert DataFrame to HTML"""
        table_html = df.to_html(classes='data-table', index=False)
        template = Template(self.html_template)
        return template.render(table_html=table_html)

    def analyze_with_ai(self, html_content):
        """Send HTML to AI model for analysis"""
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # Change model from gpt-4 to gpt-3.5-turbo
                messages=[ 
                    {"role": "system", "content": "You are an expert at analyzing rent roll data. Extract and structure the key information from the provided rent roll table."},
                    {"role": "user", "content": f"Analyze this rent roll data and provide a structured summary: {html_content}"}
                ]
            )
            return response.choices[0].message['content']
        except Exception as e:
            raise Exception(f"Error in AI analysis: {str(e)}")


    def process_file(self, input_file):
        """Main pipeline process"""
        print(f"Processing file: {input_file}")
        
        # Read the file
        df = self.read_file(input_file)
        
        if df.empty:
            raise Exception(f"No data found in {input_file}")
        
        # Convert to HTML
        html_content = self.convert_to_html(df)
        
        # Save HTML for reference
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_output = f"processed_rent_roll_{timestamp}.html"
        with open(html_output, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Analyze with AI
        analysis = self.analyze_with_ai(html_content)
        
        return {
            'original_data': df,
            'html_output': html_output,
            'ai_analysis': analysis
        }

def main():
    # Example usage
    pipeline = RentRollPipeline()
    
    # Get input file from user
    input_file = input("Enter the path to your rent roll file (CSV, XLSX, or PDF): ")
    
    try:
        results = pipeline.process_file(input_file)
        
        print("\nProcessing complete!")
        print(f"HTML output saved to: {results['html_output']}")
        print("\nAI Analysis:")
        print(results['ai_analysis'])
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()