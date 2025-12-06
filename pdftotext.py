# Example file to print the text layer of a PDF.

import re, io, sys

import pdf_redactor

## Set options.

def printer(m):
	s = m.group(0)
	if sys.version_info < (3,):
		s = s.encode("utf8")
	print(s)
	return ""

if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("-i", "--input", help="Source PDF file")
	args = parser.parse_args()

	options = pdf_redactor.RedactorOptions()
	if args.input:
		options.input_stream = open(args.input, "rb")
	options.output_stream = io.BytesIO() # null
	options.content_filters = [(re.compile("[\w\W]+"), printer)]
	pdf_redactor.redactor(options)
