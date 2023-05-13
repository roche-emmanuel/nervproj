"""Utility functions"""
import base64

from nvp.nvp_context import NVPContext

_F64 = 1 << 63
_F32 = 1 << 31


def to_int64(val):
    """Convert an uint64 value to a int64"""
    return val if (val & _F64) == 0 else val - 2 * _F64


def to_int32(val):
    """Convert an uint32 value to a int32"""
    return val if (val & _F32) == 0 else val - 2 * _F32


def to_uint64(val):
    """Convert an int64 to an uint64 value"""
    return val if val >= 0 else val + 2 * _F64


def to_uint32(val):
    """Convert an int32 to an uint32 value"""
    return val if val >= 0 else val + 2 * _F32


def bytes_to_hex(data):
    """Convert bytes to an hex string"""
    return data.hex()


def string_to_hex(data):
    """Convert string to an hex string"""
    return bytes_to_hex(data.encode("utf-8"))


def hex_to_bytes(data):
    """Convert an hex string to bytes"""
    return bytes.fromhex(data)


def hex_to_string(data):
    """Convert an hex string to a string"""
    return bytes.fromhex(data).decode("utf-8")


def b64_to_bytes(data):
    """Convert base64 to bytes"""
    base64_bytes = data.encode("ascii")
    message_bytes = base64.b64decode(base64_bytes)
    return message_bytes


def b64_to_string(data):
    """Convert base64 to string"""
    return b64_to_bytes(data).decode("utf-8")


def bytes_to_b64(message_bytes):
    """Covnert bytes to base64"""
    base64_bytes = base64.b64encode(message_bytes)
    return base64_bytes.decode("ascii")


def string_to_b64(data):
    """Convert string to base64"""
    return bytes_to_b64(data.encode("utf-8"))


def send_rocketchat_message(msg, channel=None, max_retries=2):
    """Send a message on rocket chat"""
    ctx = NVPContext.get()
    rchat = ctx.get_component("rchat")
    return rchat.send_message(msg, channel=channel, max_retries=max_retries)
