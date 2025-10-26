#!/usr/bin/env python3
"""
Mock Engine - OpenAI-compatible API that returns pre-defined reasoning traces
Simulates vLLM behavior for testing qwen-code-ipc without GPU resources
"""

from flask import Flask, request, jsonify, Response
import time
import json
import re
from datetime import datetime

app = Flask(__name__)

# Configuration
PREFILL_TOKENS_PER_SEC = 1000  # Simulated prefill speed
DECODE_TOKENS_PER_SEC = 50     # Simulated decode speed

# Pre-defined reasoning traces
REASONING_TRACES = {
    "grep": {
        "pattern": r"grep|search|find",
        "response": """<think>
To search for this pattern, I'll analyze the codebase structure:
1. First, I'll identify the relevant directories
2. Then grep through source files for the pattern
3. Finally, I'll compile the matching results

Let me execute the search...
</think>

Found 3 matches:
- src/utils.py:45: def grep_pattern(text, pattern):
- src/search.py:12: # Implements grep-like functionality
- tests/test_grep.py:8: def test_grep_basic():
"""
    },
    "debug": {
        "pattern": r"debug|error|bug|fix",
        "response": """<think>
Analyzing the error trace:
1. The stack trace shows a NullPointerException
2. This occurs in the data validation layer
3. Root cause: missing null check before dereferencing

Proposed fix:
- Add defensive null checks in validate_input()
- Add test cases for null inputs
- Update documentation
</think>

The bug is in src/validator.py line 67. Add this check:
```python
if data is None:
    raise ValueError("Input cannot be None")
```
"""
    },
    "refactor": {
        "pattern": r"refactor|improve|optimize|clean",
        "response": """<think>
Code improvement analysis:
1. Current code has duplicate logic in 3 places
2. Can extract common functionality into a helper
3. This will reduce complexity and improve maintainability

Steps:
- Extract common pattern into extract_common_logic()
- Update call sites to use new helper
- Add unit tests for the extracted function
</think>

Refactoring recommendation:
Create a new function in src/helpers.py:
```python
def extract_common_logic(data, config):
    # Common validation and processing
    return processed_data
```
"""
    },
    "explain": {
        "pattern": r"explain|what|how|why",
        "response": """<think>
Breaking down the concept:
1. This is a producer-consumer pattern
2. The queue manages work items between threads
3. Synchronization prevents race conditions

Key components:
- Producer adds items to queue
- Consumer processes items from queue
- Lock ensures thread safety
</think>

This code implements a thread-safe queue where:
- Multiple producers can add work items concurrently
- Multiple consumers process items in parallel
- The threading.Lock() prevents data corruption
- The queue.Queue provides built-in synchronization
"""
    },
    "default": {
        "pattern": r".*",
        "response": """<think>
Processing the request:
1. Analyzing the input query
2. Searching relevant code patterns
3. Generating contextual response
</think>

I'll help you with that. Based on the context, here's what I found in the codebase.
"""
    }
}

# Grep-like responses for file searches
GREP_RESPONSES = {
    "function": [
        "src/main.py:23:def main():",
        "src/utils.py:45:def helper_function(x, y):",
        "src/api.py:12:def process_request(data):",
    ],
    "class": [
        "src/models.py:5:class DataModel:",
        "src/handlers.py:18:class RequestHandler:",
        "src/errors.py:3:class CustomError(Exception):",
    ],
    "import": [
        "src/main.py:1:import os",
        "src/utils.py:1:import json",
        "src/api.py:1:from flask import Flask",
    ],
    "variable": [
        "src/config.py:10:API_KEY = 'secret'",
        "src/settings.py:5:DEBUG = True",
        "src/constants.py:3:MAX_RETRIES = 5",
    ],
    "test": [
        "tests/test_main.py:15:def test_initialization():",
        "tests/test_api.py:8:class TestAPI(unittest.TestCase):",
        "tests/test_utils.py:20:def test_helper_function():",
    ]
}

def estimate_tokens(text):
    """Rough estimate: ~4 chars per token"""
    if not text:
        return 0
    return len(str(text)) // 4

def simulate_timing(prompt_tokens, completion_tokens):
    """Simulate realistic inference timing"""
    prefill_time = prompt_tokens / PREFILL_TOKENS_PER_SEC
    decode_time = completion_tokens / DECODE_TOKENS_PER_SEC
    return prefill_time + decode_time

def select_reasoning_trace(prompt):
    """Select appropriate reasoning trace based on prompt content"""
    if not prompt:
        return REASONING_TRACES["default"]["response"]
    
    prompt_lower = str(prompt).lower()
    
    for trace_name, trace_data in REASONING_TRACES.items():
        if trace_name != "default" and re.search(trace_data["pattern"], prompt_lower):
            return trace_data["response"]
    
    return REASONING_TRACES["default"]["response"]

def grep_search(query):
    """Simulate grep functionality"""
    if not query:
        return "No query provided"
    
    query_lower = str(query).lower()
    results = []
    
    # Keyword mapping for better matching
    keyword_map = {
        "function": ["function", "def", "method"],
        "class": ["class", "classes"],
        "import": ["import", "imports", "dependencies"],
        "variable": ["variable", "var", "declaration", "const", "constant"],
        "test": ["test", "tests", "testing"]
    }
    
    # Check each keyword category
    for category, keywords in keyword_map.items():
        if any(kw in query_lower for kw in keywords):
            if category in GREP_RESPONSES:
                results.extend(GREP_RESPONSES[category])
    
    if not results:
        results = ["No matches found"]
    
    return "\n".join(results)

@app.route('/v1/completions', methods=['POST'])
def completions():
    """OpenAI-compatible completions endpoint"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        prompt = data.get('prompt', '')
        max_tokens = data.get('max_tokens', 500)
        temperature = data.get('temperature', 0.7)
        
        # Check if this is a grep-style query
        if 'grep' in str(prompt).lower() or 'search' in str(prompt).lower():
            grep_query = str(prompt).split()[-1] if str(prompt).split() else ''
            grep_results = grep_search(grep_query)
            response_text = f"{select_reasoning_trace(prompt)}\n\nGrep results:\n{grep_results}"
        else:
            response_text = select_reasoning_trace(prompt)
        
        # Simulate timing
        prompt_tokens = estimate_tokens(prompt)
        completion_tokens = estimate_tokens(response_text)
        timing_delay = simulate_timing(prompt_tokens, completion_tokens)
        
        time.sleep(min(timing_delay, 2.0))  # Cap at 2 seconds for reasonable response time
        
        response = {
            "id": f"cmpl-{int(time.time())}",
            "object": "text_completion",
            "created": int(time.time()),
            "model": data.get('model', 'qwen-coder'),
            "choices": [{
                "text": response_text,
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }
        
        return jsonify(response)
    except Exception as e:
        print(f"Error in completions endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """OpenAI-compatible chat completions endpoint"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        messages = data.get('messages', [])
        max_tokens = data.get('max_tokens', 500)
        stream = data.get('stream', False)
        
        # Extract the last user message
        user_message = ""
        try:
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    content = msg.get('content', '')
                    # Handle both string and list content formats
                    if isinstance(content, list):
                        # Extract text from list items
                        texts = []
                        for item in content:
                            if isinstance(item, dict):
                                if 'text' in item:
                                    texts.append(str(item['text']))
                                elif 'content' in item:
                                    texts.append(str(item['content']))
                            elif isinstance(item, str):
                                texts.append(item)
                        user_message = ' '.join(texts)
                    else:
                        user_message = str(content) if content else ""
                    break
            
            # Ensure user_message is a string
            if not isinstance(user_message, str):
                user_message = str(user_message)
        except Exception as e:
            print(f"Error extracting message: {e}")
            import traceback
            traceback.print_exc()
            user_message = "default query"
        
        # Check if this is a grep-style query
        if 'grep' in str(user_message).lower() or 'search' in str(user_message).lower() or 'find' in str(user_message).lower():
            grep_results = grep_search(user_message)
            response_text = f"{select_reasoning_trace(user_message)}\n\nGrep results:\n{grep_results}"
        else:
            response_text = select_reasoning_trace(user_message)
        
        # Calculate tokens
        prompt_tokens = sum(estimate_tokens(msg.get('content', '')) for msg in messages)
        completion_tokens = estimate_tokens(response_text)
        
        if stream:
            return stream_response(response_text, data.get('model', 'qwen-coder'), prompt_tokens, completion_tokens)
        
        # Simulate timing
        timing_delay = simulate_timing(prompt_tokens, completion_tokens)
        time.sleep(min(timing_delay, 2.0))
        
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": data.get('model', 'qwen-coder'),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }
        
        return jsonify(response)
    except Exception as e:
        print(f"Error in chat completions endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def stream_response(text, model, prompt_tokens, completion_tokens):
    """Generate streaming response"""
    def generate():
        try:
            words = str(text).split()
            chunk_size = 3
            
            for i in range(0, len(words), chunk_size):
                chunk = ' '.join(words[i:i+chunk_size]) + ' '
                
                data = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None
                    }]
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(0.05)  # Simulate streaming delay
            
            # Final chunk
            final_data = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"Error in stream_response: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/v1/models', methods=['GET'])
def models():
    """List available models"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "qwen-coder",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "mock-engine"
            }
        ]
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "engine": "mock-engine"})

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler"""
    print(f"Unhandled exception: {e}")
    import traceback
    traceback.print_exc()
    return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("Mock Engine - OpenAI-Compatible Test Server")
    print("=" * 60)
    print(f"Listening on: http://0.0.0.0:8000")
    print(f"OpenAI-compatible endpoints:")
    print(f"  - POST /v1/chat/completions")
    print(f"  - POST /v1/completions")
    print(f"  - GET  /v1/models")
    print(f"  - GET  /health")
    print(f"\nConfigure qwen-code with:")
    print(f"  export OPENAI_BASE_URL=http://localhost:8000/v1")
    print(f"  export OPENAI_API_KEY=mock-key")
    print("=" * 60)
    print("\nServer starting with error logging enabled...")
    app.run(host='0.0.0.0', port=8000, debug=True)