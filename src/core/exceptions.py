from fastapi import HTTPException, status


class InvalidCredentialsException(HTTPException):
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class CouldNotValidateCredentialsException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class InvalidRefreshTokenException(HTTPException):
    def __init__(self, detail: str = "Invalid refresh token"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class VerificationRequiredException(HTTPException):
    def __init__(self, detail: str = "Verification required"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class InvalidTokenTypeException(HTTPException):
    def __init__(self, detail: str = "Invalid token type"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidTokenPayloadException(HTTPException):
    def __init__(self, detail: str = "Invalid token payload"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class TokenExpiredException(HTTPException):
    def __init__(self, detail: str = "Token expired"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidTokenException(HTTPException):
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UserExistsException(HTTPException):
    def __init__(self, detail: str = "User already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UserNotFoundException(HTTPException):
    def __init__(self, detail: str = "User not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class VideoGenerationFailedException(HTTPException):
    def __init__(self, detail: str = "Failed to generate video"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class ObjectNotFoundException(HTTPException):
    def __init__(self, detail: str = "Object not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
