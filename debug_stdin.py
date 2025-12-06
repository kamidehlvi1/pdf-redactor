import sys

if sys.version_info < (3,):
    stdin = sys.stdin
else:
    stdin = sys.stdin.buffer

data = stdin.read()
print("Read {} bytes".format(len(data)))
if len(data) > 0:
    print("First 10 bytes: {}".format(repr(data[:10])))
