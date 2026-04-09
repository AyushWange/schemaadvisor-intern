"""
Middleware and utilities for request/response handling.
Provides request ID tracking, timing, and structured logging.
"""

import time
import logging
import uuid
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request IDs and timing to all requests"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            response = await call_next(request)
            elapsed = time.time() - start_time
            
            # Add request ID and timing to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
            response.headers["X-Process-Time"] = f"{elapsed * 1000:.0f}ms"
            
            # Log response
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} "
                f"→ {response.status_code} ({elapsed:.3f}s)"
            )
            
            return response
        except Exception as exc:
            elapsed = time.time() - start_time
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} "
                f"failed after {elapsed:.3f}s: {type(exc).__name__}"
            )
            raise

class CircuitBreaker:
    """
    Simple circuit breaker for external services.
    Tracks failures and prevents cascading failures.
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.is_open = False
    
    def record_success(self):
        """Record a successful call"""
        self.failures = 0
        self.is_open = False
    
    def record_failure(self):
        """Record a failed call"""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker OPEN after {self.failures} failures. "
                f"Service will be unavailable for {self.timeout}s."
            )
    
    def is_available(self) -> bool:
        """Check if the service is available"""
        if not self.is_open:
            return True
        
        # Check if timeout has passed
        if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
            self.failures = 0
            self.is_open = False
            logger.info("Circuit breaker CLOSED. Service recovered.")
            return True
        
        return False
    
    def get_status(self) -> dict:
        """Get circuit breaker status"""
        return {
            "is_open": self.is_open,
            "failures": self.failures,
            "threshold": self.failure_threshold,
            "available": self.is_available()
        }

# Circuit breakers for external services
llm_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
neo4j_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
pg_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
