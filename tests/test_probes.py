"""SNMP and SMB probes: message encoding, response parsing, and full round trips against fake servers."""
import socket
import struct
import threading

from lanwhodis import classify, pen, recog
from lanwhodis.discovery import ber, smb, snmp
from test_core import make


# ---------------------------------------------------------------- BER / SNMP
def test_ber_integers_oids_and_lengths():
    assert ber.integer(0) == b"\x02\x01\x00" and ber.integer(128) == b"\x02\x02\x00\x80"
    assert ber.integer(-1) == b"\x02\x01\xff"
    big = ber.tlv(0x04, b"x" * 300)
    assert big[:4] == b"\x04\x82\x01\x2c" and ber.read(big)[1] == b"x" * 300
    assert ber.decode_oid(ber.oid("1.3.6.1.4.1.41112.1.6")[2:]) == "1.3.6.1.4.1.41112.1.6"


def test_snmp_get_matches_known_wire_format():
    got = snmp.build_get(1, "public", 1, (snmp.OID_SYSDESCR,))
    want = bytes.fromhex("3026020101040670756 26c6963a0190201010201000201003 00e300c06082b060102010101000500"
                         .replace(" ", ""))
    assert got == want


def _response(request_id=1, status=0, community=b"public", extra=b""):
    vbs = (ber.tlv(0x30, ber.oid(snmp.OID_SYSDESCR) + ber.octets(b"Linux ubnt 4.14 #1 SMP"))
           + ber.tlv(0x30, ber.oid(snmp.OID_SYSOBJECTID) + ber.oid("1.3.6.1.4.1.41112.1.6"))
           + ber.tlv(0x30, ber.oid(snmp.OID_SYSUPTIME) + ber.tlv(0x43, (8640000).to_bytes(3, "big")))
           + ber.tlv(0x30, ber.oid(snmp.OID_SYSNAME) + ber.tlv(0x80, b"")) + extra)   # noSuchObject: ignored
    pdu = ber.tlv(0xA2, ber.integer(request_id) + ber.integer(status) + ber.integer(0) + ber.tlv(0x30, vbs))
    return ber.tlv(0x30, ber.integer(1) + ber.octets(community) + pdu)


def test_snmp_parse_response_values_and_rejections():
    vals = snmp.parse_response(_response(), request_id=1)
    assert vals[snmp.OID_SYSDESCR] == "Linux ubnt 4.14 #1 SMP"
    assert vals[snmp.OID_SYSOBJECTID] == "1.3.6.1.4.1.41112.1.6" and vals[snmp.OID_SYSUPTIME] == 8640000
    assert snmp.OID_SYSNAME not in vals
    assert snmp.parse_response(_response(request_id=2), request_id=1) == {}      # someone else's reply
    assert snmp.parse_response(_response(status=2), request_id=1) == {}          # error-status
    assert snmp.parse_response(b"\x30\x05garbage") == {} and snmp.parse_response(b"") == {}


def test_pen_vendor_lookup():
    assert pen.vendor_for_oid("1.3.6.1.4.1.41112.1.6") == "Ubiquiti Networks, Inc."
    assert pen.vendor_for_oid("1.3.6.1.2.1.1.1") is None and pen.vendor_for_oid("junk") is None


def test_snmp_apply_feeds_vendor_and_classification():
    d = make("192.168.1.2")
    snmp.apply(d, snmp.parse_response(_response()), "public", "v2c")
    assert d.facts["snmp_vendor"] == "Ubiquiti Networks, Inc." and d.facts["snmp_uptime_days"] == "1.0"
    assert any(r.protocol == "snmp" and r.details["community"] == "public" for r in d.advertised)
    assert classify.classify(d).device_type == "access_point"


def test_snmp_round_trip_against_fake_agent():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    seen = []

    def agent():
        data, addr = srv.recvfrom(4096)
        seen.append(data)
        # echo the request id back, like a real agent
        req_id = int.from_bytes(ber.children(ber.children(ber.read(data)[1])[2][1])[0][1], "big", signed=True)
        srv.sendto(_response(request_id=req_id), addr)

    t = threading.Thread(target=agent, daemon=True)
    t.start()
    found = snmp.probe("127.0.0.1", ("public",), port=port)
    t.join(3)
    srv.close()
    assert found and found[2] == "v2c" and found[0][snmp.OID_SYSDESCR].startswith("Linux ubnt")
    assert b"public" in seen[0]


# ---------------------------------------------------------------- SMB
def _filetime(ts: float) -> int:
    return int(ts * 10_000_000) + smb._FILETIME_EPOCH


def _negotiate_response(secmode=3, dialect=0x0302, boot=1_700_000_000, now=1_700_864_000) -> bytes:
    body = struct.pack("<HHHH16sIIIIQQ", 65, secmode, dialect, 0, b"\x11" * 16, 0, 0, 0, 0,
                       _filetime(now), _filetime(boot))
    return smb._header(0, 0) + body + b"\x00" * 8


def _av(av_id: int, text: str) -> bytes:
    raw = text.encode("utf-16-le")
    return struct.pack("<HH", av_id, len(raw)) + raw


def _challenge(version=(10, 0, 22631), flags_version=True) -> bytes:
    target_info = _av(1, "LAPTOP") + _av(2, "WORKGROUP") + _av(3, "laptop.example") + struct.pack("<HH", 0, 0)
    flags = 0x00000001 | 0x00800000 | (0x02000000 if flags_version else 0)
    ver = struct.pack("<BBH", *version) + b"\x00\x00\x00" + bytes([15]) if version else b"\x00" * 8
    fixed = (smb._SIG + struct.pack("<I", 2) + struct.pack("<HHI", 0, 0, 56) + struct.pack("<I", flags)
             + b"\xaa" * 8 + b"\x00" * 8 + struct.pack("<HHI", len(target_info), len(target_info), 56) + ver)
    return fixed + target_info


def _session_response(blob: bytes) -> bytes:
    hdr = bytearray(smb._header(1, 1))
    struct.pack_into("<I", hdr, 8, 0xC0000016)         # STATUS_MORE_PROCESSING_REQUIRED
    return bytes(hdr) + struct.pack("<HHHH", 9, 0, 72, len(blob)) + blob


def test_smb_request_builders():
    neg = smb.negotiate_request()
    assert len(neg) == 4 + 64 + 36 + 8 and neg[0] == 0 and int.from_bytes(neg[1:4], "big") == len(neg) - 4
    assert neg[4:8] == b"\xfeSMB"
    ntlm = smb.ntlm_negotiate()
    assert len(ntlm) == 40 and ntlm.startswith(smb._SIG)
    wrapped = smb.spnego_init(ntlm)
    tag, value, end = ber.read(wrapped)
    assert tag == 0x60 and end == len(wrapped) and ntlm in value and smb._NTLM_OID in value
    ss = smb.session_setup_request(wrapped)
    assert struct.unpack_from("<H", ss, 4 + 64 + 12)[0] == 88          # security buffer offset


def test_smb_parse_negotiate_dialect_signing_and_boot_time():
    info = smb.parse_negotiate(_negotiate_response())
    assert info["dialect"] == "3.0.2" and info["signing"] == "required"
    assert (info["system_time"] - info["boot_time"]).days == 10
    assert smb.parse_negotiate(_negotiate_response(secmode=1))["signing"] == "enabled"
    assert smb.parse_negotiate(b"\xffSMB" + b"\x00" * 200) is None and smb.parse_negotiate(b"") is None


def test_smb_parse_challenge_windows_and_samba():
    win = smb.parse_challenge(b"\x00" * 90 + _challenge())            # found anywhere in the response
    assert win["ntlm_version"] == (10, 0, 22631) and win["computer"] == "LAPTOP"
    assert win["domain"] == "WORKGROUP" and win["dns_name"] == "laptop.example"
    samba = smb.parse_challenge(_challenge(version=None))
    assert samba["ntlm_version"] is None and samba["computer"] == "LAPTOP"
    assert smb.parse_challenge(b"no ntlm here") is None


def test_windows_version_names():
    assert smb.windows_name(10, 0, 22631) == "Windows 11 (build 22631)"
    assert smb.windows_name(10, 0, 19045) == "Windows 10 (build 19045)"
    assert smb.windows_name(10, 0, 20348).startswith("Windows Server 2022")
    assert smb.windows_name(6, 1, 7601).startswith("Windows 7")


def test_smb_apply_names_os_and_ambiguity_resolution():
    d = make("192.168.1.64", hostname="Alex-Arm64")
    smb.apply(d, {**smb.parse_negotiate(_negotiate_response()), "ntlm_version": (10, 0, 26100),
                  "computer": "ALEX-ARM64", "domain": "ALEX-ARM64"})
    classify.classify(d)
    assert d.names["smb"] == "ALEX-ARM64" and d.facts["smb_uptime_days"] == "10.0"
    assert d.device_type == "computer" and d.os_hint == "Windows"
    assert d.os_detail == "Windows 11 (build 26100)" and d.os_label == "Windows 11 (build 26100)"

    s = make("192.168.1.65", hostname="sql-server-01")
    smb.apply(s, {**smb.parse_negotiate(_negotiate_response()), "ntlm_version": (10, 0, 26100), "computer": "SQL"})
    classify.classify(s)
    assert s.device_type == "server" and s.os_detail == "Windows Server 2025 (build 26100)"


def test_samba_hint_alone_is_not_shown():
    d = make()
    smb.apply(d, {**smb.parse_negotiate(_negotiate_response()), "ntlm_version": None, "computer": "NAS"})
    classify.classify(d)
    assert d.os_hint is None        # 0.22 < the minimum confidence: needs corroboration


def test_smb_round_trip_against_fake_server():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got = []

    def serve():
        conn, _ = srv.accept()
        with conn:
            def recv_frame():
                head = conn.recv(4)
                n = int.from_bytes(head[1:], "big")
                data = b""
                while len(data) < n:
                    data += conn.recv(n - len(data))
                return data
            got.append(recv_frame())                                           # NEGOTIATE
            resp = _negotiate_response()
            conn.sendall(smb._frame(resp))
            got.append(recv_frame())                                           # SESSION_SETUP
            conn.sendall(smb._frame(_session_response(_challenge())))

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    info = smb.probe("127.0.0.1", port=port)
    t.join(3)
    srv.close()
    assert info["ntlm_version"] == (10, 0, 22631) and info["computer"] == "LAPTOP" and info["dialect"] == "3.0.2"
    assert got[0][:4] == b"\xfeSMB" and smb._SIG in got[1]                     # we sent NTLM NEGOTIATE only
    assert smb.probe("127.0.0.1", timeout=0.3, port=port) is None             # nothing listening: no crash


def test_printer_firmware_line_is_not_reported_as_an_os():
    d = make()
    d.facts["snmp_sysdescr"] = "HP ETHERNET MULTI-ENVIRONMENT,SN:XXXXXXXXXX,FN:0000000,SVCID:10099,PID:HP Color LaserJet MFP M283fdw"
    recog.annotate(d)
    classify.classify(d)
    assert d.device_type == "printer" and d.os_hint is None
