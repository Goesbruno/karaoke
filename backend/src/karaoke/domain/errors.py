class DomainError(Exception): pass
class NotFound(DomainError): pass
class InvalidTransition(DomainError): pass
class RetryLimit(DomainError): pass
class Conflict(DomainError): pass
class InvalidUrl(DomainError): pass

class ProviderUnavailable(DomainError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

class UploadRejected(DomainError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

class Duplicate(DomainError):
    def __init__(self, code: str, message: str, existing_id: str | None = None):
        super().__init__(message)
        self.code, self.existing_id = code, existing_id
