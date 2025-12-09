
import os
import rect_redactor
from PyPDF2 import PdfFileWriter

# Create a dummy PDF
def create_dummy_pdf(filename):
    pdf = PdfFileWriter()
    pdf.addBlankPage(width=612, height=792)
    with open(filename, "wb") as f:
        pdf.write(f)

input_pdf = "test_input.pdf"
output_pdf = "test_output.pdf"
create_dummy_pdf(input_pdf)

zones = [
    {"rect": [100, 100, 50, 50], "password": "pass1"},
    {"rect": [200, 200, 50, 50], "password": "pass2"}
]

try:
    print("Running redact_regions...")
    sidecar = rect_redactor.redact_regions(input_pdf, output_pdf, 0, zones)
    print("Success! Sidecar created at: " + str(sidecar))
    
    import json
    with open(sidecar, "r") as f:
        data = json.load(f)
        print("Sidecar entries: " + str(len(data)))
        if len(data) == 2:
            print("Verification Passed: 2 entries found.")
        else:
            print("Verification Failed: Expected 2 entries, found " + str(len(data)))

except Exception as e:
    print("Verification Failed with error: " + str(e))
    import traceback
    traceback.print_exc()

# Cleanup
if os.path.exists(input_pdf): os.remove(input_pdf)
if os.path.exists(output_pdf): os.remove(output_pdf)
if os.path.exists(output_pdf + ".secure"): os.remove(output_pdf + ".secure")
