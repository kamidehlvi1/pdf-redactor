
import os
import json
import rect_redactor
from secure_redact import decrypt_data
import uuid

# Use the real PDF
input_pdf = "example_redacted.pdf"
output_pdf = "verify_precise_" + str(uuid.uuid4()) + ".pdf"

if not os.path.exists(input_pdf):
    print("Error: Input PDF not found.")
else:
    # We define a zone that likely covers the title or intro text.
    # Page size is likely Letter 612x792.
    # Title is usually at the top.
    # Browser coords: x=50, y=50, w=500, h=100 (Title area)
    
    zone = {"rect": [50, 50, 500, 100], "password": "test"}
    
    try:
        print("Running redact_regions with zone: " + str(zone['rect']))
        rect_redactor.redact_regions(input_pdf, output_pdf, 0, [zone])
        
        sidecar = output_pdf + ".secure"
        if os.path.exists(sidecar):
            with open(sidecar, "r") as f:
                data = json.load(f)
            
            content_enc = data[0]['content']
            decrypted = decrypt_data(content_enc, "test")
            val = json.loads(decrypted)
            
            print("Extracted Text Length: " + str(len(val)))
            print("--- EXTRACTED TEXT START ---")
            print(val)
            print("--- EXTRACTED TEXT END ---")
            
            if "Sample Document" in val or "Introduction" in val:
                print("SUCCESS: Found expected text in zone.")
            elif "[No text content" in val:
                 print("WARNING: No text found in this zone (might be empty margin).")
            else:
                 print("SUCCESS (Partial): Extracted some text, need visual check if it matches zone.")

        else:
            print("FAILURE: Sidecar not created.")
            
    except Exception as e:
        print("FAILURE with error: " + str(e))
        import traceback
        traceback.print_exc()

# Cleanup
if os.path.exists(output_pdf): os.remove(output_pdf)
if os.path.exists(output_pdf + ".secure"): os.remove(output_pdf + ".secure")
