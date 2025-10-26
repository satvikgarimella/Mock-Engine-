"""
Benchmark Script for Testing qwen-code-ipc with Mock vLLM
Runs 10 grep operations back-to-back and measures performance
"""

import subprocess
import time
import json
import statistics
from typing import List, Dict
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Test different token generation speeds
TOKEN_SPEEDS_TO_TEST = [25, 50, 100, 200, 500]  # tokens per second

# Grep queries to test (10 variations)
GREP_QUERIES = [
    "search for 'function' in the codebase",
    "find all instances of 'import'",
    "grep for 'export' keyword",
    "search for 'async' functions",
    "find 'class' definitions",
    "grep for 'interface' declarations",
    "search for 'const' variables",
    "find 'type' aliases",
    "grep for 'return' statements",
    "search for 'await' keywords"
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def update_mock_engine_speed(tokens_per_sec: int):
    """Update the DECODE_TOKENS_PER_SEC in mock_engine.py"""
    with open('mock_engine.py', 'r') as f:
        content = f.read()
    
    # Replace the speed setting
    import re
    content = re.sub(
        r'DECODE_TOKENS_PER_SEC = \d+',
        f'DECODE_TOKENS_PER_SEC = {tokens_per_sec}',
        content
    )
    
    with open('mock_engine.py', 'w') as f:
        f.write(content)
    
    print(f"✅ Updated mock_engine.py: DECODE_TOKENS_PER_SEC = {tokens_per_sec}")

def start_mock_server():
    """Start the mock vLLM server in background"""
    print("🚀 Starting mock vLLM server...")
    process = subprocess.Popen(
        ['python', 'mock_engine.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)  # Wait for server to start
    return process

def stop_mock_server(process):
    """Stop the mock vLLM server"""
    print("🛑 Stopping mock vLLM server...")
    process.terminate()
    process.wait()

def run_grep_query(query: str) -> Dict:
    """Run a single grep query using qwen-code CLI and measure timing"""
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ['qwen-code', 'query', query],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                'OPENAI_BASE_URL': 'http://localhost:8000/v1',
                'OPENAI_API_KEY': 'mock-key'
            }
        )
        
        elapsed_time = time.time() - start_time
        
        return {
            'success': result.returncode == 0,
            'elapsed_time': elapsed_time,
            'output_length': len(result.stdout),
            'query': query
        }
    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        return {
            'success': False,
            'elapsed_time': elapsed_time,
            'output_length': 0,
            'query': query,
            'error': 'timeout'
        }
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            'success': False,
            'elapsed_time': elapsed_time,
            'output_length': 0,
            'query': query,
            'error': str(e)
        }

def run_benchmark_suite(tokens_per_sec: int) -> Dict:
    """Run all 10 grep queries and collect statistics"""
    print(f"\n{'='*70}")
    print(f"📊 BENCHMARK: {tokens_per_sec} tokens/sec")
    print(f"{'='*70}")
    
    results = []
    
    for i, query in enumerate(GREP_QUERIES, 1):
        print(f"\n[{i}/10] Running: {query[:50]}...")
        result = run_grep_query(query)
        results.append(result)
        
        status = "✅" if result['success'] else "❌"
        print(f"        {status} Completed in {result['elapsed_time']:.3f}s")
    
    # Calculate statistics
    times = [r['elapsed_time'] for r in results if r['success']]
    
    if not times:
        return {
            'tokens_per_sec': tokens_per_sec,
            'total_queries': len(GREP_QUERIES),
            'successful_queries': 0,
            'failed_queries': len(GREP_QUERIES),
            'error': 'All queries failed'
        }
    
    stats = {
        'tokens_per_sec': tokens_per_sec,
        'total_queries': len(GREP_QUERIES),
        'successful_queries': len(times),
        'failed_queries': len(GREP_QUERIES) - len(times),
        'total_time': sum(times),
        'avg_time': statistics.mean(times),
        'median_time': statistics.median(times),
        'min_time': min(times),
        'max_time': max(times),
        'stddev_time': statistics.stdev(times) if len(times) > 1 else 0,
        'queries_per_minute': 60 / statistics.mean(times) if times else 0,
        'individual_results': results
    }
    
    return stats

def print_summary(all_results: List[Dict]):
    """Print a summary comparison of all speed tests"""
    print("\n" + "="*70)
    print("📈 BENCHMARK SUMMARY")
    print("="*70)
    print(f"\n{'Speed (t/s)':<12} {'Avg Time':<12} {'Min Time':<12} {'Max Time':<12} {'Q/min':<12}")
    print("-"*70)
    
    for result in all_results:
        if 'error' not in result:
            print(f"{result['tokens_per_sec']:<12} "
                  f"{result['avg_time']:<12.3f} "
                  f"{result['min_time']:<12.3f} "
                  f"{result['max_time']:<12.3f} "
                  f"{result['queries_per_minute']:<12.1f}")
    
    print("="*70)
    
    # Find optimal speed
    valid_results = [r for r in all_results if 'error' not in r]
    if valid_results:
        fastest_avg = min(valid_results, key=lambda x: x['avg_time'])
        most_throughput = max(valid_results, key=lambda x: x['queries_per_minute'])
        
        print(f"\n🏆 Best Results:")
        print(f"   • Fastest average: {fastest_avg['tokens_per_sec']} t/s "
              f"({fastest_avg['avg_time']:.3f}s per query)")
        print(f"   • Best throughput: {most_throughput['tokens_per_sec']} t/s "
              f"({most_throughput['queries_per_minute']:.1f} queries/min)")

def save_results(all_results: List[Dict], filename: str = None):
    """Save benchmark results to JSON file"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'test_queries': GREP_QUERIES,
            'results': all_results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {filename}")

# ============================================================================
# MAIN BENCHMARK
# ============================================================================

def main():
    print("="*70)
    print("🚀 qwen-code-ipc Mock vLLM Benchmark")
    print("="*70)
    print(f"📝 Test Configuration:")
    print(f"   • Number of queries: {len(GREP_QUERIES)}")
    print(f"   • Speed settings: {TOKEN_SPEEDS_TO_TEST} tokens/sec")
    print(f"   • Total tests: {len(GREP_QUERIES) * len(TOKEN_SPEEDS_TO_TEST)}")
    print("="*70)
    
    all_results = []
    server_process = None
    
    try:
        for speed in TOKEN_SPEEDS_TO_TEST:
            # Update mock engine speed
            update_mock_engine_speed(speed)
            
            # Restart server with new speed
            if server_process:
                stop_mock_server(server_process)
            server_process = start_mock_server()
            
            # Run benchmark suite
            results = run_benchmark_suite(speed)
            all_results.append(results)
            
            # Small delay between test suites
            time.sleep(1)
        
        # Print summary
        print_summary(all_results)
        
        # Save results
        save_results(all_results)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during benchmark: {e}")
    finally:
        if server_process:
            stop_mock_server(server_process)
    
    print("\n✨ Benchmark complete!\n")

if __name__ == "__main__":
    main()