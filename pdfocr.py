
import os
from pdf2image import convert_from_path
import pytesseract
import pandas as pd
import re
import subprocess
import time
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)

class PDFTableExtractor:
    def __init__(self, poppler_path=None, tesseract_path=None):
        self.poppler_path = poppler_path
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

    def clean_amount(self, value):
        try:
            if isinstance(value, str):
                value = value.replace('$', '').replace(',', '')
                return f"${float(value):.2f}"
            return value
        except:
            return '$0.00'

    def preprocess_resident_name(self, row_data, parts):
        # Check if parts[4] and parts[5] (assumed to be Resident name) are split
        if len(parts) > 6 and re.match(r'[A-Za-z]+', parts[4]) and re.match(r'[A-Za-z]+', parts[5]):
            row_data['Resident'] = ' '.join(parts[4:6])
            row_data['Move-In Date'] = parts[6]
            row_data['Lease Expiration Date'] = parts[7]
            # Handling the case where other fields are shifted
            row_data['Base Rent'] = self.clean_amount(parts[8])
            row_data['Pet Fee'] = self.clean_amount(parts[9])
            row_data['MTM Premium'] = self.clean_amount(parts[10])
            row_data['ST Premium'] = self.clean_amount(parts[11])
            row_data['Vacancy'] = self.clean_amount(parts[12])
            row_data['Total Charges'] = self.clean_amount(parts[13]) if len(parts) > 13 else '$0.00'
        else:
            row_data['Resident'] = ' '.join(parts[4:6])  # Fix name
            row_data['Move-In Date'] = parts[6]
            row_data['Lease Expiration Date'] = parts[7]
            row_data['Base Rent'] = self.clean_amount(parts[8])
            row_data['Pet Fee'] = self.clean_amount(parts[9])
            row_data['MTM Premium'] = self.clean_amount(parts[10])
            row_data['ST Premium'] = self.clean_amount(parts[11])
            row_data['Vacancy'] = self.clean_amount(parts[12])
            row_data['Total Charges'] = self.clean_amount(parts[13]) if len(parts) > 13 else '$0.00'
        
        return row_data

    def image_to_string_with_timeout(image, timeout=60):
        try:
            result = None
            start_time = time.time()
        # Using subprocess to set a timeout for pytesseract
            process = subprocess.Popen(
            ['tesseract', image, 'stdout', '-c', 'tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
            stdout, stderr = process.communicate(timeout=timeout)
        
            if process.returncode == 0:
                result = stdout.decode('utf-8')
            else:
                logging.error(f"Tesseract error: {stderr.decode()}")
        
            elapsed_time = time.time() - start_time
            logging.info(f"Processed in {elapsed_time:.2f} seconds")
        
            return result
    
        except subprocess.TimeoutExpired:
            logging.error("Tesseract OCR timed out.")
            return None
        except Exception as e:
            logging.error(f"Error occurred: {str(e)}")
            return None

    def extract_table(self, pdf_path):
        pages = convert_from_path(pdf_path, poppler_path=self.poppler_path)
        all_data = []
        
        for page in pages:
            text = pytesseract.image_to_string(page)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Find table start
            table_start = 0
            for i, line in enumerate(lines):
                if re.match(r'^\d+\s+\d+-\d+', line):
                    table_start = i
                    break

            data = []
            for line in lines[table_start:]:
                if re.match(r'^\d+\s+\d+-\d+', line):
                    parts = line.split()
                    try:
                        row_data = {
                            'Ctl#': parts[0],
                            'Site #': parts[1],
                            'Type': parts[2],
                            'Status': parts[3],
                        }
                        # Preprocess resident name and other fields
                        row_data = self.preprocess_resident_name(row_data, parts)
                        data.append(row_data)
                    except IndexError:
                        logging.warning(f"Skipping malformed line: {line}")
                        continue

            all_data.extend(data)

        return pd.DataFrame(all_data)
    
    def resize_image(image, max_width=1000, max_height=1000):
        width, height = image.size
        if width > max_width or height > max_height:
            new_width = min(width, max_width)
            new_height = int((new_width / width) * height)
            image = image.resize((new_width, new_height), Image.ANTIALIAS)
        return image

    def generate_html(self, df):
        html = """
        <html>
        <head>
            <style>
                table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
                th, td { border: 1px solid black; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                td[class*="amount"] { text-align: right; }
            </style>
        </head>
        <body>
        """
        html += df.to_html(index=False, classes='dataframe')
        html += "</body></html>"
        return html

def main():
    extractor = PDFTableExtractor(
        poppler_path=r'C:\Users\Naveen Raghav\Downloads\Poppler\poppler-24.08.0\Library\bin',
        tesseract_path=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    )
    
    pdf_path = r'C:\Users\Naveen Raghav\Desktop\pdf_scraper_tool\pdf_scraper_tool\Rent Roll with Lease Charges.pdf'
    output_path = 'rentroll1.html'
    
    try:
        df = extractor.extract_table(pdf_path)
        html_content = extractor.generate_html(df)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logging.info(f"HTML file generated successfully")
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")

if __name__ == '__main__':
    main()
