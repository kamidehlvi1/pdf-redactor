
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
import sys

# Rect is [x, y, w, h] (PDF.js / browser coordinates - usually top-left origin?)
# Or PDF coordinates (bottom-left origin)?
# Browser: Top-Left (y increases downwards)
# PDF: Bottom-Left (y increases upwards)
# We need to confirm. PyPDF2 logic in rect_redactor already converts:
# rect_ll_y = page_height - (y + h)
# So we must use PDF coordinates for pdfminer.

def extract_text_in_rect(pdf_path, page_num, rect_pdf_coords):
    """
    rect_pdf_coords: [x0, y0, x1, y1] (Bottom-Left logic)
    """
    x0, y0, x1, y1 = rect_pdf_coords
    extracted = []
    
    try:
        for i, page_layout in enumerate(extract_pages(pdf_path)):
            if i != page_num: continue
            
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    # Check overlap (simple bounding box check)
                    # element.bbox is (x0, y0, x1, y1)
                    ex0, ey0, ex1, ey1 = element.bbox
                    
                    # Check intersection
                    if (ex0 < x1 and ex1 > x0 and ey0 < y1 and ey1 > y0):
                        # For now, just take the whole text if it touches/is inside?
                        # Or stricter? Let's take it if center is inside or significant overlap.
                        # Simple inclusion for now.
                         extracted.append(element.get_text())
            break
        return "".join(extracted)
    except Exception as e:
        return "Error: " + str(e)

if __name__ == "__main__":
    # Test coordinates... hard to guess without real file knowledge.
    # We will try to just run it on "example_redacted.pdf" page 0 and see what we get for a full page rect.
    pdf_path = "example_redacted.pdf"
    # Full page approximate 0,0 to 600,800
    print("Full page text:")
    print(extract_text_in_rect(pdf_path, 0, [0, 0, 600, 800])[:100])
