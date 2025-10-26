"""
Mock vLLM Engine for qwen-code-ipc Testing
Simulates OpenAI-compatible API with configurable token generation speeds
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import time
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import asyncio
import random

# ============================================================================
# CONFIGURATION - Adjust these to test different speeds
# ============================================================================
PREFILL_TOKENS_PER_SEC = 500  # Tokens/sec for prompt processing
DECODE_TOKENS_PER_SEC = 50    # Tokens/sec for generation
BASE_LATENCY_MS = 10          # Base network/processing latency

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = 0.0
    presence_penalty: Optional[float] = 0.0

# ============================================================================
# PRE-DEFINED REASONING TRACES AND GREP RESPONSES
# ============================================================================

REASONING_TRACES = {
    "grep_search": """<thinking>
To search for patterns in the codebase, I'll use the grep function to find relevant files.
Let me search for the term that was requested...
</thinking>

I'll search for that pattern across the codebase.

<grep pattern="{pattern}" case_sensitive="false">
Searching recursively through project files...
</grep>

Found {num_results} matches across {num_files} files:
{results}
""",
    
    "code_analysis": """<thinking>
Analyzing the code structure to understand the implementation...
The pattern suggests this is related to {topic}.
Let me examine the relevant sections...
</thinking>

Based on my analysis:

{analysis}

The key findings are:
{findings}
""",
    
    "default": """<thinking>
Processing the request...
Understanding the context and requirements...
Formulating a response...
</thinking>

{response}
"""
}

GREP_RESPONSES = [
    "src/core/engine.ts:45:    async function executeGrep(pattern: string) {",
    "src/utils/search.ts:12:    // Grep implementation for pattern matching",
    "tests/grep.test.ts:8:    describe('grep functionality', () => {",
    "lib/tools/grep.ts:23:    export const grepTool = createTool('grep', async (args) => {",
    "docs/api.md:156:### Grep Tool",
]

CODE_ANALYSIS_FINDINGS = [
    "- The implementation uses a recursive tree-walking algorithm",
    "- Pattern matching is handled by the regex engine with Unicode support",
    "- Results are cached to improve subsequent search performance",
    "- The system supports both case-sensitive and case-insensitive searches"
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def count_tokens(text: str) -> int:
    """Approximate token count (rough estimate: ~4 chars per token)"""
    return len(text) // 4

def generate_grep_response(user_message: str) -> str:
    """Generate a grep-like response based on the user message"""
    # Extract potential search pattern from message
    pattern = "function"  # Default
    if "search" in user_message.lower() or "find" in user_message.lower():
        words = user_message.split()
        for i, word in enumerate(words):
            if word.lower() in ["for", "search", "find"] and i + 1 < len(words):
                pattern = words[i + 1].strip('",.:;')
                break
    
    num_results = random.randint(3, 7)
    selected_results = random.sample(GREP_RESPONSES, min(num_results, len(GREP_RESPONSES)))
    
    return REASONING_TRACES["grep_search"].format(
        pattern=pattern,
        num_results=num_results,
        num_files=random.randint(2, 5),
        results="\n".join(f"  {i+1}. {res}" for i, res in enumerate(selected_results))
    )

def generate_code_analysis(user_message: str) -> str:
    """Generate a code analysis response"""
    topic = "pattern matching and search functionality"
    analysis = "The codebase implements a sophisticated search system with multiple optimization layers."
    
    return REASONING_TRACES["code_analysis"].format(
        topic=topic,
        analysis=analysis,
        findings="\n".join(CODE_ANALYSIS_FINDINGS)
    )

def generate_response(messages: List[Message]) -> str:
    """Generate appropriate response based on conversation context"""
    last_message = messages[-1].content.lower()
    
    if any(word in last_message for word in ["grep", "search", "find", "pattern"]):
        return generate_grep_response(messages[-1].content)
    elif any(word in last_message for word in ["analyze", "explain", "code", "implementation"]):
        return generate_code_analysis(messages[-1].content)
    else:
        return REASONING_TRACES["default"].format(
            response=f"I understand you're asking about: {messages[-1].content[:100]}...\n\nLet me help with that."
        )

async def simulate_generation_timing(prompt_tokens: int, completion_tokens: int):
    """Simulate realistic token generation timing"""
    # Base latency
    await asyncio.sleep(BASE_LATENCY_MS / 1000.0)
    
    # Prefill phase (process prompt)
    prefill_time = prompt_tokens / PREFILL_TOKENS_PER_SEC
    await asyncio.sleep(prefill_time)
    
    # Decode phase (generate tokens)
    decode_time = completion_tokens / DECODE_TOKENS_PER_SEC
    await asyncio.sleep(decode_time)

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Mock vLLM Engine", version="1.0.0")

@app.get("/")
async def root():
    return {
        "status": "running",
        "engine": "mock_vllm",
        "config": {
            "prefill_tokens_per_sec": PREFILL_TOKENS_PER_SEC,
            "decode_tokens_per_sec": DECODE_TOKENS_PER_SEC,
            "base_latency_ms": BASE_LATENCY_MS
        }
    }

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "object": "list",
        "data": [
            {
                "id": "qwen2.5-coder-32b-instruct",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "mock_vllm"
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""
    
    # Calculate token counts
    prompt_text = "\n".join([msg.content for msg in request.messages])
    prompt_tokens = count_tokens(prompt_text)
    
    # Generate response
    response_text = generate_response(request.messages)
    completion_tokens = count_tokens(response_text)
    
    # Measure actual generation time
    start_time = time.time()
    
    # Simulate realistic timing
    await simulate_generation_timing(prompt_tokens, completion_tokens)
    
    generation_time = time.time() - start_time
    
    # Non-streaming response
    if not request.stream:
        return {
            "id": f"chatcmpl-mock-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            "system_fingerprint": f"mock_vllm_{DECODE_TOKENS_PER_SEC}tps",
            "x_timing": {
                "generation_time_seconds": generation_time,
                "tokens_per_second": completion_tokens / generation_time if generation_time > 0 else 0,
                "prefill_tokens_per_sec": PREFILL_TOKENS_PER_SEC,
                "decode_tokens_per_sec": DECODE_TOKENS_PER_SEC
            }
        }
    
    # Streaming response
    async def generate_stream():
        # Simulate token-by-token streaming
        words = response_text.split()
        for i, word in enumerate(words):
            chunk = {
                "id": f"chatcmpl-mock-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": word + " "},
                        "finish_reason": None
                    }
                ]
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            
            # Simulate per-token delay
            await asyncio.sleep(1.0 / DECODE_TOKENS_PER_SEC)
        
        # Send final chunk
        final_chunk = {
            "id": f"chatcmpl-mock-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }
            ]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "engine": "mock_vllm"}

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🚀 Mock vLLM Engine Starting")
    print("=" * 70)
    print(f"📊 Configuration:")
    print(f"   • Prefill Speed: {PREFILL_TOKENS_PER_SEC} tokens/sec")
    print(f"   • Decode Speed:  {DECODE_TOKENS_PER_SEC} tokens/sec")
    print(f"   • Base Latency:  {BASE_LATENCY_MS}ms")
    print("=" * 70)
    print(f"🌐 Server will run at: http://localhost:8000")
    print(f"📝 API Endpoint: http://localhost:8000/v1/chat/completions")
    print(f"📚 Models Endpoint: http://localhost:8000/v1/models")
    print("=" * 70)
    print("\n💡 To use with qwen-code-ipc, set:")
    print("   export OPENAI_BASE_URL=http://localhost:8000/v1")
    print("   export OPENAI_API_KEY=mock-key")
    print("\n⚡ To change speed, edit DECODE_TOKENS_PER_SEC at the top of this file")
    print("=" * 70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()