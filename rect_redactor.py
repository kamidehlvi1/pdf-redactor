
import sys
import json
import base64
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import DictionaryObject, NumberObject, FloatObject, NameObject, ArrayObject
from secure_redact import encrypt_data

import uuid
import os

def redact_regions(input_pdf, output_pdf, page_num, zones):
    """
    Redacts multiple rectangular regions on a specific page.
    zones: List of dicts, each having:
           {'rect': (x, y, w, h), 'password': '...'}
    """
    
    output = PdfFileWriter()
    
    with open(input_pdf, "rb") as f_in:
        input1 = PdfFileReader(f_in)
        
        if page_num < 0 or page_num >= input1.getNumPages():
            raise ValueError("Invalid page number")
    
        extracted_text = ""
        new_entries = []
    
        for i in range(input1.getNumPages()):
            page = input1.getPage(i)
            
            if i == page_num:
                # 1. Extract text ONCE for the page (limit of PyPDF2)
                try:
                    extracted_text = page.extractText()
                except:
                    extracted_text = ""

                # Get Page Height for coordinate conversion
                if "/MediaBox" in page:
                    media_box = page["/MediaBox"]
                else:
                    media_box = page.mediaBox
                page_height = float(media_box[3])
                
                if "/Annots" in page:
                    annots = page["/Annots"]
                    if hasattr(annots, "getObject"):
                        annots = annots.getObject()
                else:
                    annots = ArrayObject()
                    page[NameObject("/Annots")] = annots

                # 2. Iterate over all zones to add visual redactions
                for zone in zones:
                    rect_coords = zone['rect']
                    password = zone['password']
                    x, y, w, h = rect_coords
                    
                    # Store original PDF.js coords
                    target_rect = [x, y, w, h] 
                    
                    # Convert to PDF Coords
                    rect_ll_x = x
                    rect_ll_y = page_height - (y + h)
                    rect_ur_x = x + w
                    rect_ur_y = page_height - y
                    
                    # Create Black Rectangle Annotation
                    new_annot = DictionaryObject()
                    new_annot.update({
                        NameObject("/Type"): NameObject("/Annot"),
                        NameObject("/Subtype"): NameObject("/Square"),
                        NameObject("/Rect"): ArrayObject([
                            FloatObject(rect_ll_x),
                            FloatObject(rect_ll_y),
                            FloatObject(rect_ur_x),
                            FloatObject(rect_ur_y)
                        ]),
                        NameObject("/IC"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),
                        NameObject("/C"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),
                        NameObject("/F"): NumberObject(4),
                    })
                    
                    annots.append(new_annot)
                    
                    # 3. Create Encrypted Entry for this zone
                    encrypted_blob = encrypt_data(extracted_text, password)
                    new_entries.append({
                        "id": str(uuid.uuid4()),
                        "page": page_num,
                        "rect": target_rect,
                        "content": encrypted_blob
                    })

                # Update page annotations
                page[NameObject("/Annots")] = annots
                
            output.addPage(page)
    
        with open(output_pdf, "wb") as outputStream:
            output.write(outputStream)
            
    # Handle Sidecar File
    sidecar_path = output_pdf + ".secure"
    existing_data = []
    
    if os.path.exists(sidecar_path):
        try:
            with open(sidecar_path, "r") as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [] 
        except:
             existing_data = []
             
    existing_data.extend(new_entries)
    
    with open(sidecar_path, "w") as f:
        json.dump(existing_data, f)
    
    return sidecar_path

if __name__ == "__main__":
    # Support basic single-zone CLI usage by wrapping it in a list
    if len(sys.argv) < 9:
        print("Usage: python rect_redactor.py input.pdf output.pdf page x y w h password")
        sys.exit(1)
        
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    page = int(sys.argv[3])
    rect = (float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7]))
    password = sys.argv[8]
    
    zone = {'rect': rect, 'password': password}
    
    secure_path = redact_regions(input_pdf, output_pdf, page, [zone])
        
    print("Redacted region saved to " + output_pdf)

