
import sys
import json
import base64
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import DictionaryObject, NumberObject, FloatObject, NameObject, ArrayObject
from secure_redact import encrypt_data
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

import uuid
import os

def get_text_in_rect(pdf_path, page_num, rect_bbox):
    """
    Extracts text from a specific page within a bounding box using pdfminer.six.
    rect_bbox: (x0, y0, x1, y1) in PDF coordinates (bottom-left origin).
    """
    x0, y0, x1, y1 = rect_bbox
    extracted_text = []

    try:
        # pdfminer.high_level.extract_pages yields LTPage objects
        # We assume 0-indexed page_num matches the generator order
        for i, page_layout in enumerate(extract_pages(pdf_path)):
            if i != page_num: 
                if i > page_num: break # Optimization: stop if passed
                continue
            
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    # element.bbox is (x0, y0, x1, y1)
                    ex0, ey0, ex1, ey1 = element.bbox
                    
                    # Simple AABB intersection or inclusion check
                    # We check if the text element's center is within our rect, 
                    # or if there is significant overlap.
                    # Given users draw boxes AROUND text, inclusion is best.
                    
                    # Check if the element overlaps significantly with the redaction zone
                    # Overlap logic:
                    if (ex0 < x1 and ex1 > x0 and ey0 < y1 and ey1 > y0):
                         extracted_text.append(element.get_text())
            break 
            
        return "".join(extracted_text)
    except Exception as e:
        sys.stderr.write("Error extracting text with pdfminer: " + str(e) + "\n")
        return ""

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
    
        new_entries = []
    
        for i in range(input1.getNumPages()):
            page = input1.getPage(i)
            
            if i == page_num:
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

                # Iterate over all zones to add visual redactions AND extract text per zone
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
                    
                    # Extract text specifically for this zone
                    extracted_text = get_text_in_rect(input_pdf, page_num, (rect_ll_x, rect_ll_y, rect_ur_x, rect_ur_y))

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
                    
                    # Create Encrypted Entry for this zone
                    if not extracted_text or not extracted_text.strip():
                        content_to_store = "[No text content extracted from this area]"
                    else:
                        content_to_store = extracted_text
                        
                    json_data = json.dumps(content_to_store)
                    encrypted_blob = encrypt_data(json_data, password)
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

