
import argparse
import json
import os
import re
import sys
import hashlib
from base64 import b64encode, b64decode

# Try to import pycryptodome, standard crypto library fallback or error
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
except ImportError:
    sys.stderr.write("Error: 'pycryptodome' is required. Install with: pip install pycryptodome\n")
    sys.exit(1)

import pdf_redactor

# Global list to store redacted items
REDACTED_ITEMS = []

def encrypt_data(data, password):
    """Encrypts a string or bytes using AES-256-CBC."""
    key = hashlib.sha256(password.encode()).digest()
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    if isinstance(data, str):
        data = data.encode('utf-8')
    ciphertext = cipher.encrypt(pad(data, AES.block_size))
    return b64encode(iv + ciphertext).decode('utf-8')

def decrypt_data(encrypted_data, password):
    """Decrypts a base64 string using AES-256-CBC."""
    try:
        data = b64decode(encrypted_data)
        iv = data[:16]
        ciphertext = data[16:]
        key = hashlib.sha256(password.encode()).digest()
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception as e:
        if "Padding is incorrect" in str(e):
             return "Error: Incorrect Password"
        return "Decryption Failed: " + str(e)

def redaction_handler(match):
    """
    Callback for regex match.
    Stores original text and returns a placeholder.
    """
    original_text = match.group(0)
    index = len(REDACTED_ITEMS)
    REDACTED_ITEMS.append(original_text)
    return "[SECURE %d]" % index

def run_encrypt(args):
    """
    Runs the redaction process:
    1. Redact PDF matched content.
    2. Save original content to an encrypted JSON file.
    """
    options = pdf_redactor.RedactorOptions()
    
    # regex for SSN (simplified from example.py)
    # Matches XXX-XX-XXXX or similar patterns
    ssn_regex = re.compile(r"(?<!\d)(?!666|000|9\d{2})([0-9]{3})([\s-]?)(?!00)([0-9]{2})\2(?!0{4})([0-9]{4})(?!\d)")

    # You could add more regexes here
    options.content_filters = [
        (ssn_regex, redaction_handler)
    ]
    
    options.input_stream = open(args.input, "rb")
    options.output_stream = open(args.output, "wb")
    
    print("Redacting and encrypting...")
    pdf_redactor.redactor(options)
    
    # Now save the redacted items
    if REDACTED_ITEMS:
        json_data = json.dumps(REDACTED_ITEMS)
        encrypted_blob = encrypt_data(json_data, args.password)
        
        secure_file = args.output + ".secure"
        with open(secure_file, "w") as f:
            f.write(encrypted_blob)
        
        print("Done.")
        print("Output PDF: " + args.output)
        print("Secure Data: " + secure_file)
    else:
        print("No sensitive data found to redact.")

def run_decrypt(args):
    """
    Reads the .secure file and displays original data.
    """
    secure_file = args.input
    
    # If the user passed the PDF filename, check if a .secure version exists
    if not secure_file.endswith(".secure") and os.path.exists(secure_file + ".secure"):
        secure_file = secure_file + ".secure"
    
    if not os.path.exists(secure_file):
        print("Error: Secure file not found: " + secure_file)
        return

    try:
        with open(secure_file, "r") as f:
            encrypted_blob = f.read()
    except UnicodeDecodeError:
        print("Error: Could not read '%s'. Are you sure this is the secure text file and not the PDF?" % secure_file)
        return
            
    print("Decrypting data from " + secure_file + "...")
    json_data = decrypt_data(encrypted_blob, args.password)
    
    if json_data.startswith("Decryption Failed"):
        print(json_data)
    else:
        try:
            items = json.loads(json_data)
            print("\n--- Original Redacted Data ---")
            for i, item in enumerate(items):
                print("[SECURE %d]: %s" % (i, item))
            print("------------------------------")
        except json.JSONDecodeError:
            print("Error: Invalid decrypted data format. Wrong password?")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secure Redaction Tool")
    parser.add_argument("--mode", choices=["encrypt", "decrypt"], required=True, help="Mode of operation")
    parser.add_argument("-i", "--input", required=True, help="Input PDF (encrypt mode) or Secure File (decrypt mode)")
    parser.add_argument("-o", "--output", help="Output PDF (encrypt mode only)")
    parser.add_argument("-p", "--password", required=True, help="Encryption/Decryption password")
    
    args = parser.parse_args()
    
    if args.mode == "encrypt":
        if not args.output:
            parser.error("--output is required for encrypt mode")
        run_encrypt(args)
    elif args.mode == "decrypt":
        run_decrypt(args)
