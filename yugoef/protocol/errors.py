class ProtocolError(ValueError):
    """Base class for typed protocol errors."""


class InvalidMagicError(ProtocolError):
    pass


class UnsupportedVersionError(ProtocolError):
    pass


class TruncatedPacketError(ProtocolError):
    pass


class InvalidPayloadLengthError(ProtocolError):
    pass


class InvalidSubcarrierCountError(ProtocolError):
    pass


class CrcMismatchError(ProtocolError):
    pass


class AuthenticationError(ProtocolError):
    pass


class InvalidMessageTypeError(ProtocolError):
    pass


class PacketTooLargeError(ProtocolError):
    pass
