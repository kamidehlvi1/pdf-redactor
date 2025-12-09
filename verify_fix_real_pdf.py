
import os
import json
import rect_redactor
from secure_redact import decrypt_data
import uuid

# Use the real PDF that was failing
input_pdf = "example_redacted.pdf"
output_pdf = "verify_output_" + str(uuid.uuid4()) + ".pdf"

# If input doesn't exist, we can't test completely, but we can try to find another one.
if not os.path.exists(input_pdf):
    print("Warning: " + input_pdf + " not found. Checking directory.")
    # Fallback to creating a simple PDF if needed, but we prefer the real one
    # Assuming the user has it.
else:
    print("Using " + input_pdf)
    
    zones = [{"rect": [10,10,10,10], "password": "test"}]
    
    try:
        rect_redactor.redact_regions(input_pdf, output_pdf, 0, zones)
        
        sidecar = output_pdf + ".secure"
        if os.path.exists(sidecar):
            with open(sidecar, "r") as f:
                data = json.load(f)
            
            content_enc = data[0]['content']
            decrypted = decrypt_data(content_enc, "test")
            val = json.loads(decrypted)
            
            print("Extracted Text Length: " + str(len(val)))
            if "No text content extracted" in val:
                print("FAILURE: Still getting placeholder.")
            elif len(val) > 0:
                print("SUCCESS: Extracted text successfully!")
                print("Sample: " + val[:50] + "...")
            else:
                 print("FAILURE: Empty text (but not placeholder).")
        else:
            print("FAILURE: Sidecar not created.")
            
    except Exception as e:
        print("FAILURE with error: " + str(e))
        import traceback
        traceback.print_exc()

# Cleanup
if os.path.exists(output_pdf): os.remove(output_pdf)
if os.path.exists(output_pdf + ".secure"): os.remove(output_pdf + ".secure")
