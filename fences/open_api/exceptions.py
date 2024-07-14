from fences.core.exception import ParseException, FencesException


class OpenApiException(ParseException):
    pass


class MissingDependencyException(FencesException):
    pass
