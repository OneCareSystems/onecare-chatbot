class ServiceError(Exception):
    status = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ValidationFailed(ServiceError):
    status, code = 400, "VALIDATION_ERROR"


class NotFound(ServiceError):
    status, code = 404, "NOT_FOUND"


class Conflict(ServiceError):
    status, code = 409, "CONFLICT"


class AuditUnavailable(ServiceError):
    status, code = 503, "AUDIT_UNAVAILABLE"