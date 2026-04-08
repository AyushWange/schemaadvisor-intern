"""
Error handling and graceful degradation module for SchemaAdvisor.
Provides structured error responses and fallback behaviors.
"""

import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

class SchemaAdvisorException(Exception):
    """Base exception for SchemaAdvisor"""
    def __init__(self, message: str, status_code: int = 500, detail: str = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)

class ValidationError(SchemaAdvisorException):
    """Raised when input validation fails"""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

class ServiceUnavailableError(SchemaAdvisorException):
    """Raised when a service (Neo4j, LLM) is unavailable"""
    def __init__(self, service: str):
        message = f"{service} is unavailable or not responding"
        super().__init__(message, status_code=503, detail=message)

class TimeoutError(SchemaAdvisorException):
    """Raised when an operation times out"""
    def __init__(self, operation: str, seconds: int):
        message = f"{operation} exceeded {seconds} second timeout"
        super().__init__(message, status_code=504, detail=message)

def register_exception_handlers(app: FastAPI):
    """Register all exception handlers with the FastAPI app"""
    
    @app.exception_handler(SchemaAdvisorException)
    async def schema_advisor_exception_handler(request: Request, exc: SchemaAdvisorException):
        """Handle custom SchemaAdvisor exceptions"""
        logger.warning(f"SchemaAdvisor error ({exc.status_code}): {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "detail": exc.detail,
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError - typically from Pydantic validation"""
        logger.warning(f"Validation error: {str(exc)}")
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "detail": f"Invalid request: {str(exc)[:100]}",
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.error(f"Unexpected error: {type(exc).__name__}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "detail": "Internal server error - details logged for investigation",
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        )
