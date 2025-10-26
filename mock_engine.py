#!/usr/bin/env python3
from flask import Flask, request, jsonify, Response
import time
import json
import re

app = Flask(__name__)

# Configuration - SET TO INSTANT for realistic performance
PREFILL_TOKENS_PER_SEC = 10000000
DECODE_TOKENS_PER_SEC = 10000000

# Pre-defined reasoning traces
REASONING_TRACES = {
    "grep": {
        "pattern": r"grep|search|find",
        "response": "<think>Searching codebase...</think>\nFound matches:\n- src/utils.py:45: def grep_pattern()\n- src/search.py:12: grep functionality"
    },
    "debug": {
        "pattern": r"debug|error|bug|fix",
        "response": "<think>Analyzing error...</think>\nBug found in src/validator.py line 67\nFix: Add null check"
    },
    "default": {
        "pattern": r".*",
        "response": "<think>Processing request...</think>\nHere's what I found in the codebase."
    }
}

GREP_RESPONSES = {
    "function": ["src/main.py:23:def main():", "src/utils.py:45:def helper_function():"],
    "class": ["src/models.py:5:class DataModel:", "src/handlers.py:18:class RequestHandler:"],
}

def estimate_tokens(text):
    if not text:
        return 0
    return len(str(text)) // 4

def simulate_timing(prompt_tokens, completion_tokens):
    prefill_time = prompt_tokens / PREFILL_TOKENS_PER_SEC
    decode_time = completion_tokens / DECODE_TOKENS_PER_SEC
    return prefill_time + decode_time

def select_reasoning_trace(prompt):
    if not prompt:
        return REASONING_TRACES["default"]["response"]
    prompt_lower = str(prompt).lower()
    for trace_name, trace_data in REASONING_TRACES.items():
        if trace_name != "default" and re.search(trace_data["pattern"], prompt_lower):
            return trace_data["response"]
    return REASONING_TRACES["default"]["response"]

def grep_search(query):
    if not query:
        return "No query provided"
    query_lower = str(query).lower()
    results = []
    keyword_map = {
        "function": ["function", "def", "method"],
        "class": ["class", "classes"],
    }
    for category, keywords in keyword_map.items():
        if any(kw in query_lower for kw in keywords):
            if category in GREP_RESPONSES:
                results.extend(GREP_RESPONSES[category])
    if not results:
        results = ["No matches found"]
    return "\n".join(results)

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    request_start = time.time()
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        messages = data.get('messages', [])
        
        print(f"\n{'='*60}")
        print(f"📥 Request at {time.strftime('%H:%M:%S')}")
        
        user_message = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        if isinstance(item, dict):
                            if 'text' in item:
                                texts.append(str(item['text']))
                        elif isinstance(item, str):
                            texts.append(item)
                    user_message = ' '.join(texts)
                else:
                    user_message = str(content) if content else ""
                break
        
        if 'grep' in str(user_message).lower() or 'search' in str(user_message).lower() or 'find' in str(user_message).lower():
            grep_results = grep_search(user_message)
            response_text = f"{select_reasoning_trace(user_message)}\n\nGrep results:\n{grep_results}"
        else:
            response_text = select_reasoning_trace(user_message)
        
        prompt_tokens = sum(estimate_tokens(msg.get('content', '')) for msg in messages)
        completion_tokens = estimate_tokens(response_text)
        
        timing_delay = simulate_timing(prompt_tokens, completion_tokens)
        print(f"⏱️  API delay: {timing_delay:.6f}s (tokens: {prompt_tokens}+{completion_tokens})")
        time.sleep(timing_delay)
        
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
        
        request_end = time.time()
        total_time = request_end - request_start
        print(f"✅ Total API time: {total_time:.6f}s")
        print(f"{'='*60}\n")
        
        return jsonify(response)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/v1/models', methods=['GET'])
def models():
    return jsonify({
        "object": "list",
        "data": [{
            "id": "qwen-coder",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "mock-engine"
        }]
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "engine": "mock-engine"})

if __name__ == '__main__':
    print("=" * 60)
    print("Mock Engine - INSTANT MODE (10M tokens/sec)")
    print("=" * 60)
    print(f"Listening on: http://0.0.0.0:8000")
    print(f"Config: PREFILL={PREFILL_TOKENS_PER_SEC}, DECODE={DECODE_TOKENS_PER_SEC}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8000, debug=False)
