
import sys
import os

# PyPDF2
try:
    from PyPDF2 import PdfFileReader
    print("Testing PyPDF2...")
    with open("example_redacted.pdf", "rb") as f:
        reader = PdfFileReader(f)
        page = reader.getPage(0)
        text = page.extractText()
        print("PyPDF2 Extracted (" + str(len(text)) + " chars):")
        print(text[:100].replace('\n', ' '))
except Exception as e:
    print("PyPDF2 Failed: " + str(e))

print("-" * 20)

# pdf_redactor (pdfrw)
try:
    import pdf_redactor
    from pdfrw import PdfReader
    print("Testing pdf_redactor...")
    
    options = pdf_redactor.RedactorOptions()
    options.input_stream = open("example_redacted.pdf", "rb")
    
    # We need to manually invoke the text layer building logic
    document = PdfReader(options.input_stream)
    text_layer = pdf_redactor.build_text_layer(document, options)
    # text_layer is (text_tokens, page_tokens)
    text_tokens = text_layer[0]
    
    full_text = "".join([t.value for t in text_tokens])
    print("pdf_redactor Extracted (" + str(len(full_text)) + " chars):")
    print(full_text[:100].replace('\n', ' '))
except Exception as e:
    print("pdf_redactor Failed: " + str(e))
