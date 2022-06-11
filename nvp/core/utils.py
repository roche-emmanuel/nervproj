"""Utility functions"""
import base64

from nvp.nvp_context import NVPContext


def bytes_to_hex(data):
    """Convert bytes to an hex string"""
    return data.hex()


def string_to_hex(data):
    """Convert string to an hex string"""
    return bytes_to_hex(data.encode('utf-8'))


def hex_to_bytes(data):
    """Convert an hex string to bytes"""
    return bytes.fromhex(data)


def hex_to_string(data):
    """Convert an hex string to a string"""
    return bytes.fromhex(data).decode('utf-8')


def b64_to_bytes(data):
    """Convert base64 to bytes"""
    base64_bytes = data.encode('ascii')
    message_bytes = base64.b64decode(base64_bytes)
    return message_bytes


def b64_to_string(data):
    """Convert base64 to string"""
    return b64_to_bytes(data).decode('utf-8')


def bytes_to_b64(message_bytes):
    """Covnert bytes to base64"""
    base64_bytes = base64.b64encode(message_bytes)
    return base64_bytes.decode('ascii')


def string_to_b64(data):
    """Convert string to base64"""
    return bytes_to_b64(data.encode('utf-8'))


def send_rocketchat_message(msg):
    """Send a message on rocket chat"""
    ctx = NVPContext.get()
    rchat = ctx.get_component('rchat')
    rchat.send_message(msg)
