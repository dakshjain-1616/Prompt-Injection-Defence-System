"""
FastAPI Proxy for Prompt Injection Defense System.
Intercepts OpenAI-compatible chat completion requests, scores them for injections,
and blocks malicious ones or forwards clean ones to a backend LLM.
"""

import os
import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
import httpx
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Import the InputSanitizer from the security module
from security.input_guard import InputSanitizer, SecurityViolation

# Initialize FastAPI app
app = FastAPI(
    title="Prompt Injection Defense Proxy",
    description="OpenAI-compatible API proxy with prompt injection detection",
    version="1.0.0"
)

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:11434/v1/chat/completions")

# Initialize the input sanitizer
sanitizer = InputSanitizer()

# Prometheus metrics
REQUESTS_TOTAL = Counter(
    'prompt_defense_requests_total',
    'Total number of requests received',
    ['status', 'attack_type']
)

INJECTIONS_BLOCKED = Counter(
    'prompt_defense_injections_blocked_total',
    'Total number of prompt injections blocked',
    ['category']
)

REQUEST_DURATION = Histogram(
    'prompt_defense_request_duration_seconds',
    'Time spent processing requests',
    ['status']
)

INJECTION_RATE = Gauge(
    'prompt_defense_injection_rate',
    'Current rate of injection detection (0-1)'
)

# Track injection rate calculation
total_requests = 0
blocked_requests = 0


# Pydantic models for OpenAI-compatible API
class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender (system/user/assistant)")
    content: str = Field(..., description="Content of the message")


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model identifier")
    messages: List[ChatMessage] = Field(..., description="List of messages in the conversation")
    temperature: Optional[float] = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1)
    stream: Optional[bool] = False
    top_p: Optional[float] = Field(1.0, ge=0, le=1)
    n: Optional[int] = Field(1, ge=1, le=10)


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]


def extract_user_input(messages: List[ChatMessage]) -> str:
    """Extract user input from messages for security scanning."""
    user_messages = [m.content for m in messages if m.role == "user"]
    return " ".join(user_messages)


def check_for_injection(text: str) -> tuple[bool, str, Dict[str, Any]]:
    """
    Check if text contains prompt injection attempts.
    Returns: (is_blocked, attack_category, report)
    """
    try:
        cleaned_text, report = sanitizer.sanitize(text, strict=False)
        
        # Determine if this is a security risk
        if report["security_risk"] == "HIGH":
            # Get the attack category
            attack_category = "unknown"
            if report.get("injections_detected"):
                attack_category = report["injections_detected"][0].get("category", "unknown")
            elif report.get("blacklist_matches"):
                attack_category = "blacklist"
            
            return True, attack_category, report
        
        return False, "none", report
        
    except SecurityViolation as e:
        # Strict mode violation
        attack_category = e.violation_type.lower()
        return True, attack_category, e.details


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint with prompt injection detection.
    Blocks malicious requests with 403 error, forwards clean ones to backend.
    """
    global total_requests, blocked_requests
    
    start_time = time.time()
    total_requests += 1
    
    # Extract user input for security scanning
    user_input = extract_user_input(request.messages)
    
    # Check for prompt injection
    is_blocked, attack_category, report = check_for_injection(user_input)
    
    if is_blocked:
        # Update metrics
        blocked_requests += 1
        REQUESTS_TOTAL.labels(status="blocked", attack_type=attack_category).inc()
        INJECTIONS_BLOCKED.labels(category=attack_category).inc()
        
        # Update injection rate gauge
        if total_requests > 0:
            INJECTION_RATE.set(blocked_requests / total_requests)
        
        # Record duration
        duration = time.time() - start_time
        REQUEST_DURATION.labels(status="blocked").observe(duration)
        
        # Return 403 Forbidden
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "message": f"Prompt injection detected: {attack_category}",
                    "type": "security_violation",
                    "param": None,
                    "code": "content_filter"
                },
                "security_report": report
            }
        )
    
    # Forward to backend
    try:
        async with httpx.AsyncClient() as client:
            backend_request = {
                "model": request.model,
                "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": request.stream,
                "top_p": request.top_p,
                "n": request.n
            }
            
            response = await client.post(
                BACKEND_URL,
                json=backend_request,
                timeout=60.0
            )
            
            if response.status_code != 200:
                # Backend error
                REQUESTS_TOTAL.labels(status="backend_error", attack_type="none").inc()
                duration = time.time() - start_time
                REQUEST_DURATION.labels(status="error").observe(duration)
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Backend service error"
                )
            
            # Update success metrics
            REQUESTS_TOTAL.labels(status="success", attack_type="none").inc()
            duration = time.time() - start_time
            REQUEST_DURATION.labels(status="success").observe(duration)
            
            # Return backend response
            return response.json()
            
    except httpx.RequestError as e:
        REQUESTS_TOTAL.labels(status="connection_error", attack_type="none").inc()
        duration = time.time() - start_time
        REQUEST_DURATION.labels(status="error").observe(duration)
        raise HTTPException(
            status_code=503,
            detail=f"Backend connection error: {str(e)}"
        )


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint for monitoring.
    Returns counters for requests, injections, and rates.
    """
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "prompt-injection-defense-proxy",
        "backend_url": BACKEND_URL
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Prompt Injection Defense Proxy",
        "version": "1.0.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "metrics": "/metrics",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
