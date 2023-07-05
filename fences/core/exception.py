class FencesException(Exception):
    """
    Base class of all exceptions thrown by fences.
    """
    pass


class ResolveReferenceException(FencesException):
    """
    Thrown by Node.resolve()
    """

    def __init__(self, message: str, node_id: str) -> None:
        super().__init__(message)
        self.node_id = node_id


class ParseException(FencesException):
    """
    Base class for all exceptions occurring during schema parsing
    """
    pass


class InternalException(FencesException):
    """
    Raised if fences reaches an invalid internal state.
    This hopefully never happens.
    """
    pass


class ConfigException(FencesException):
    """
    All config related exceptions
    """
    pass


class NormalizationException(FencesException):
    pass


class JsonPointerException(FencesException):
    pass
