import pdfplumber
import logging

class PdfParser:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract_text(self) -> str:
        ''''
            Extract text from a PDF file.
        '''
        try:
            text = ""
            with pdfplumber.open(self.file_path) as pdf:
                
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None
    
    def parse(self) -> dict:
        '''
            Parse the PDF file and return its content in a structured format.
        '''
        logging.info(f"Parsing PDF file: {self.file_path}")
        text = self.extract_text()
        if not text:
            logging.warning(f"No text extracted from PDF file: {self.file_path}")
        if text:
            return text
        else:
            return ""