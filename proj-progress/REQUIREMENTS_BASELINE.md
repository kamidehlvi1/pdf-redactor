# Requirements Baseline (Frozen)

**Date**: 2026-02-02
**Status**: Frozen

This document serves as the frozen snapshot of requirements. Any deviation requires explicit discussion and approval.

## Core Documentation
The primary description of the system is found in `README.md` (content below).

### README.md Snapshot
```markdown
pdf-redactor
============

A general-purpose PDF text-layer redaction tool, in pure Python, by Joshua Tauberer and Antoine McGrath.

pdf-redactor uses [pdfrw](https://github.com/pmaupin/pdfrw) under the hood to parse and write out the PDF.

* * *

This Python module is a general tool to help you automatically redact text from PDFs. The tool operates on:

* the text layer of the document's pages (content stream text)
* plain text annotations
* link target URLs
* the Document Information Dictionary, a.k.a. the PDF metadata like Title and Author
* embedded XMP metadata, if present

Graphical elements, images, and other embedded resources are not touched.

You can:

* Use regular expressions to perform text substitution on the text layer (e.g. replace social security numbers with "XXX-XX-XXXX").
* Rewrite, remove, or add new metadata fields on a field-by-field basis (e.g. wipe out all metadata except for certain fields).
* Rewrite, remove, or add XML metadata using functions that operate on the parsed XMP DOM (e.g. wipe out XMP metadata).

## How to use pdf-redactor

Get this module and then install its dependencies with:

	pip3 install -r requirements.txt
    
## Running the Web Application

To start the Secure PDF Redactor web interface:

**Using PowerShell:**
./run_app.ps1

Or manually:
python web_app/app.py

The application will be available at `http://localhost:5000`.
- **Login**: Use default admin credentials `admin` / `admin`.
- **MinIO**: Ensure MinIO is running (`docker run ...`) and configured in `.env`.
```

## Additional References
- **Version 3.0 Requirements**: See `version3.0 requirements.rtf` in the project root for detailed V3.0 specs.
- **Current Requirements**: See `requirements.txt` for python dependencies.

## Key Constraints
-   Redaction must be permanent and secure.
-   Original data must be encrypted and stored separately.
-   Web interface must support visual selection and secure viewing.
