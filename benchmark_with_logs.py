#!/usr/bin/env python3
"""
Benchmark with log parsing - Shows both qwen time AND mock-engine API time
"""

import subprocess
import time
import json
import sys
import os
import re
from pathlib import Path
from threading import Thread
from queue import Queue

# Set environment variables
os.environ['OPENAI_BASE_URL'] = 'http://localhost:8000/v1'
os.environ['OPENAI_API_KEY'] = 'mock-key'

GREP_QUERIES = [
    "search for class definitions",
    "find function declarations", 
    "grep for import statements",
    "search for variable declarations",
    "find test functions",
]

CONFIGS = [
    {"prefill": 500, "decode": 25, "name": "Slow"},
    {"prefill": 10000000, "decode": 10000000, "name": "Instant"},
]

# Store mock-engine log output
log_queue = Queue()

def tail_mock_engine_logs(log_file="mock_engine.log"):
    """Tail mock-engine logs in background"""
    try:
        with open(log_file, 'r') as f:
            # Go to end
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    log_queue.put(line.strip())
                time.sleep(0.01)
    except:
        pass

def extract_api_time_from_logs():
    """Extract the last API response time from logs"""
    lines = []
    
    # Drain queue
    while not log_queue.empty():
        lines.append(log_queue.get())
    
    # Find last "Response sent in X.XXXs"
    for line in reversed(lines):
        match = re.search(r'Response sent in ([\d.]+)s', line)
        if match:
            return float(match.group(1))
    
    return None

def update_mock_engine_speeds(prefill_speed, decode_speed):
    """Update token speeds in mock_engine.py"""
    mock_engine_path = Path("mock_engine.py")
    
    if not mock_engine_path.exists():
        print("❌ Error: mock_engine.py not found")
        sys.exit(1)
    
    content = mock_engine_path.read_text()
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if 'PREFILL_TOKENS_PER_SEC' in line and '=' in line:
            lines[i] = f"PREFILL_TOKENS_PER_SEC = {prefill_speed}  # Simulated prefill speed"
        elif 'DECODE_TOKENS_PER_SEC' in line and '=' in line:
            lines[i] = f"DECODE_TOKENS_PER_SEC = {decode_speed}     # Simulated decode speed"
    
    mock_engine_path.write_text('\n'.join(lines))
    print(f"✅ Updated: PREFILL={prefill_speed}, DECODE={decode_speed}")

def run_qwen_query(query):
    """Run qwen query and measure total time"""
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ['qwen', '-p', query],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        end_time = time.time()
        qwen_time = end_time - start_time
        
        # Give logs a moment to update
        time.sleep(0.1)
        
        # Extract API time from logs
        api_time = extract_api_time_from_logs()
        
        success = result.returncode == 0
        
        return {
            "success": success,
            "qwen_time": qwen_time,
            "api_time": api_time,
            "overhead": qwen_time - api_time if api_time else None,
            "query": query
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "qwen_time": 30.0,
            "api_time": None,
            "overhead": None,
            "query": query,
            "error": "timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "qwen_time": 0,
            "api_time": None,
            "overhead": None,
            "query": query,
            "error": str(e)
        }

def run_benchmark(config_name, num_queries=5):
    """Run benchmark suite"""
    print(f"\n{'='*80}")
    print(f"🔧 Testing: {config_name}")
    print(f"{'='*80}")
    print(f"{'Query':<45} {'Qwen':<10} {'API':<10} {'Overhead':<10}")
    print(f"{'-'*80}")
    
    results = []
    
    for i, query in enumerate(GREP_QUERIES[:num_queries], 1):
        result = run_qwen_query(query)
        results.append(result)
        
        if result["success"] and result["api_time"]:
            print(f"{query[:44]:<45} "
                  f"{result['qwen_time']:.3f}s{' '*4} "
                  f"{result['api_time']:.3f}s{' '*4} "
                  f"{result['overhead']:.3f}s")
        elif result["success"]:
            print(f"{query[:44]:<45} "
                  f"{result['qwen_time']:.3f}s{' '*4} "
                  f"N/A{' '*7} N/A")
        else:
            print(f"{query[:44]:<45} FAILED")
        
        time.sleep(0.2)
    
    return results

def calculate_stats(results):
    """Calculate statistics"""
    qwen_times = [r["qwen_time"] for r in results if r["success"]]
    api_times = [r["api_time"] for r in results if r["success"] and r["api_time"]]
    overhead_times = [r["overhead"] for r in results if r["success"] and r["overhead"]]
    
    if not qwen_times:
        return None
    
    stats = {
        "qwen": {
            "avg": sum(qwen_times) / len(qwen_times),
            "total": sum(qwen_times)
        }
    }
    
    if api_times:
        stats["api"] = {
            "avg": sum(api_times) / len(api_times),
            "total": sum(api_times)
        }
    
    if overhead_times:
        stats["overhead"] = {
            "avg": sum(overhead_times) / len(overhead_times),
            "total": sum(overhead_times)
        }
    
    return stats

def print_comparison(all_results):
    """Print comparison"""
    print(f"\n{'='*80}")
    print("📊 BENCHMARK COMPARISON")
    print(f"{'='*80}")
    print(f"{'Config':<15} {'Qwen Avg':<12} {'API Avg':<12} {'Overhead':<12} {'Speedup':<10}")
    print(f"{'-'*80}")
    
    for config_name, config, stats in all_results:
        if stats and "api" in stats:
            qwen_avg = stats["qwen"]["avg"]
            api_avg = stats["api"]["avg"]
            overhead = stats["overhead"]["avg"]
            
            print(f"{config_name:<15} {qwen_avg:.3f}s{' '*6} "
                  f"{api_avg:.3f}s{' '*6} "
                  f"{overhead:.3f}s{' '*6}")
    
    print(f"{'-'*80}")
    
    # Calculate speedup on API time only
    api_results = [(name, cfg, stats) for name, cfg, stats in all_results 
                   if stats and "api" in stats]
    
    if len(api_results) >= 2:
        fastest = min(api_results, key=lambda x: x[2]["api"]["avg"])
        slowest = max(api_results, key=lambda x: x[2]["api"]["avg"])
        
        api_speedup = slowest[2]["api"]["avg"] / fastest[2]["api"]["avg"]
        
        print(f"\n🏆 API Time Results:")
        print(f"   Fastest: {fastest[0]} - {fastest[2]['api']['avg']:.3f}s")
        print(f"   Slowest: {slowest[0]} - {slowest[2]['api']['avg']:.3f}s")
        print(f"   ⚡ API Speedup: {api_speedup:.0f}x faster")
        
        print(f"\n📈 Qwen Total Time Results:")
        print(f"   Fastest: {fastest[0]} - {fastest[2]['qwen']['avg']:.3f}s")
        print(f"   Slowest: {slowest[0]} - {slowest[2]['qwen']['avg']:.3f}s")
        print(f"   ⚡ Total Speedup: {slowest[2]['qwen']['avg'] / fastest[2]['qwen']['avg']:.2f}x faster")
        
        print(f"\n💡 Overhead: ~{fastest[2]['overhead']['avg']:.2f}s constant qwen CLI overhead")

def main():
    print("🚀 Qwen + Mock-Engine Benchmark")
    print("="*80)
    print("This measures BOTH qwen total time AND mock-engine API time")
    print("="*80)
    
    # Check qwen
    try:
        subprocess.run(['qwen', '--version'], capture_output=True, check=True)
    except:
        print("❌ Error: 'qwen' not found")
        sys.exit(1)
    
    if not Path("mock_engine.py").exists():
        print("❌ Error: mock_engine.py not found")
        sys.exit(1)
    
    print("✅ Environment ready")
    print("\n⚠️  Make sure mock-engine is running with output redirected:")
    print("    python3 mock_engine.py 2>&1 | tee mock_engine.log")
    print("\n   This allows us to capture API timing from logs")
    
    input("\nPress Enter to continue...")
    
    # Start log tailer
    log_thread = Thread(target=tail_mock_engine_logs, daemon=True)
    log_thread.start()
    
    all_results = []
    
    for config in CONFIGS:
        print(f"\n📝 Configuring: {config['name']}")
        update_mock_engine_speeds(config['prefill'], config['decode'])
        
        print("\n⏳ Restart mock-engine with log capture:")
        print("   python3 mock_engine.py 2>&1 | tee mock_engine.log")
        
        input("\nPress Enter when ready...")
        
        results = run_benchmark(config['name'])
        stats = calculate_stats(results)
        
        all_results.append((config['name'], config, stats))
    
    print_comparison(all_results)
    
    print(f"\n✨ Benchmark complete!")

if __name__ == '__main__':
    main()