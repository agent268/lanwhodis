"""Minimal BER/DER encoding and decoding: just enough for SNMP messages and SPNEGO wrappers."""
from __future__ import annotations


def length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def tlv(tag: int, payload: bytes) -> bytes:
    return bytes([tag]) + length(len(payload)) + payload


def integer(n: int) -> bytes:
    size = max(1, (n.bit_length() + 8) // 8)          # room for the sign bit
    return tlv(0x02, n.to_bytes(size, "big", signed=True))


def octets(b: bytes) -> bytes:
    return tlv(0x04, b)


NULL = b"\x05\x00"


def oid(dotted: str) -> bytes:
    parts = [int(x) for x in dotted.split(".")]
    body = bytearray([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.append(0x80 | (p & 0x7F))
            p >>= 7
        body += bytes(reversed(chunk))
    return tlv(0x06, bytes(body))


def decode_oid(b: bytes) -> str:
    if not b:
        return ""
    arc1 = min(b[0] // 40, 2)
    out, val = [arc1, b[0] - 40 * arc1], 0
    for x in b[1:]:
        val = (val << 7) | (x & 0x7F)
        if not x & 0x80:
            out.append(val)
            val = 0
    return ".".join(map(str, out))


def read(data: bytes, pos: int = 0) -> tuple[int, bytes, int]:
    """Read one TLV at pos -> (tag, value, next position). Raises ValueError on truncated input."""
    if pos + 2 > len(data):
        raise ValueError("truncated BER")
    tag, n = data[pos], data[pos + 1]
    pos += 2
    if n & 0x80:
        count = n & 0x7F
        if count == 0 or count > 4 or pos + count > len(data):
            raise ValueError("bad BER length")
        n = int.from_bytes(data[pos:pos + count], "big")
        pos += count
    if pos + n > len(data):
        raise ValueError("BER value overruns buffer")
    return tag, data[pos:pos + n], pos + n


def children(value: bytes) -> list[tuple[int, bytes]]:
    out, pos = [], 0
    while pos < len(value):
        tag, val, pos = read(value, pos)
        out.append((tag, val))
    return out
