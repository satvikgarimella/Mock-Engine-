#!/usr/bin/env python3
"""
Benchmark script for Mock Engine
Tests performance with different token generation speeds
"""

import subprocess
import time
import json
import sys
from pathlib import Path

# Test queries
GREP_QUERIES = [
    "search for class definitions",
    "find function declarations",
    "grep for import statements",
    "search for variable declarations",
    "find test functions",
    "grep for class methods",
    "search for error handlers",
    "find utility functions",
    "grep for constants",
    "search for API endpoints"
]

# Token speed configurations to test
TOKEN_CONFIGS = [
    {"prefill": 500, "decode": 25, "name": "Slow"},
    {"prefill": 10000000, "decode": 10000000, "name": "Instant"},
]

def update_mock_engine_speeds(prefill_speed, decode_speed):
    """Update token speeds in mock_engine.py"""
    mock_engine_path = Path("mock_engine.py")
    
    if not mock_engine_path.exists():
        print("❌ Error: mock_engine.py not found in current directory")
        sys.exit(1)
    
    content = mock_engine_path.read_text()
    
    # Replace the speed values
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'PREFILL_TOKENS_PER_SEC' in line and '=' in line:
            lines[i] = f"PREFILL_TOKENS_PER_SEC = {prefill_speed}  # Simulated prefill speed"
        elif 'DECODE_TOKENS_PER_SEC' in line and '=' in line:
            lines[i] = f"DECODE_TOKENS_PER_SEC = {decode_speed}     # Simulated decode speed"
    
    mock_engine_path.write_text('\n'.join(lines))
    print(f"✅ Updated speeds: PREFILL={prefill_speed}, DECODE={decode_speed}")

def run_grep_query(query):
    """Run a single grep query and measure time"""
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ['qwen', '-p', query],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        success = result.returncode == 0
        
        return {
            "success": success,
            "time": elapsed,
            "query": query
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "time": 30.0,
            "query": query,
            "error": "timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "time": 0,
            "query": query,
            "error": str(e)
        }

def run_benchmark_suite(config_name, num_queries=10):
    """Run all grep queries and collect timing data"""
    print(f"\n{'='*60}")
    print(f"Running {num_queries} queries with {config_name} config...")
    print(f"{'='*60}")
    
    results = []
    
    for i, query in enumerate(GREP_QUERIES[:num_queries], 1):
        print(f"  [{i}/{num_queries}] Running: '{query}'...", end=" ", flush=True)
        
        result = run_grep_query(query)
        results.append(result)
        
        if result["success"]:
            print(f"✅ {result['time']:.3f}s")
        else:
            print(f"❌ Failed ({result.get('error', 'unknown')})")
        
        # Small delay between requests
        time.sleep(0.1)
    
    return results

def calculate_stats(results):
    """Calculate benchmark statistics"""
    times = [r["time"] for r in results if r["success"]]
    
    if not times:
        return {
            "avg": 0,
            "min": 0,
            "max": 0,
            "total": 0,
            "success_rate": 0
        }
    
    return {
        "avg": sum(times) / len(times),
        "min": min(times),
        "max": max(times),
        "total": sum(times),
        "success_rate": (len(times) / len(results)) * 100
    }

def print_results(config_name, stats):
    """Print formatted benchmark results"""
    print(f"\n📊 Results for {config_name}:")
    print(f"  Average time:  {stats['avg']:.3f}s")
    print(f"  Min time:      {stats['min']:.3f}s")
    print(f"  Max time:      {stats['max']:.3f}s")
    print(f"  Total time:    {stats['total']:.3f}s")
    print(f"  Success rate:  {stats['success_rate']:.1f}%")

def print_comparison(all_results):
    """Print comparison table of all configurations"""
    print(f"\n{'='*80}")
    print("📈 BENCHMARK COMPARISON")
    print(f"{'='*80}")
    print(f"{'Config':<15} {'Prefill':<10} {'Decode':<10} {'Avg Time':<12} {'Total Time':<12}")
    print(f"{'-'*80}")
    
    for config_name, config, stats in all_results:
        print(f"{config_name:<15} {config['prefill']:<10} {config['decode']:<10} "
              f"{stats['avg']:.3f}s{' '*6} {stats['total']:.3f}s")
    
    # Find fastest
    fastest = min(all_results, key=lambda x: x[2]['avg'])
    print(f"\n🏆 Fastest config: {fastest[0]} (avg: {fastest[2]['avg']:.3f}s)")
    
    # Calculate speedup
    slowest = max(all_results, key=lambda x: x[2]['avg'])
    speedup = slowest[2]['avg'] / fastest[2]['avg']
    print(f"⚡ Speedup: {speedup:.2f}x faster than slowest")

def main():
    """Main benchmark runner"""
    print("🚀 Mock Engine Benchmark Tool")
    print("=" * 60)
    
    # Check if qwen is available
    try:
        subprocess.run(['qwen', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: 'qwen' command not found. Please install qwen-code.")
        sys.exit(1)
    
    # Check if mock_engine.py exists
    if not Path("mock_engine.py").exists():
        print("❌ Error: mock_engine.py not found in current directory")
        sys.exit(1)
    
    print("✅ Environment check passed")
    print("\n⚠️  Make sure mock-engine is NOT running before starting!")
    print("    This script will need to restart it with different configs.")
    
    input("\nPress Enter to continue...")
    
    all_results = []
    
    # Run benchmarks for each configuration
    for config in TOKEN_CONFIGS:
        print(f"\n{'='*60}")
        print(f"🔧 Testing configuration: {config['name']}")
        print(f"{'='*60}")
        
        # Update mock_engine.py with new speeds
        update_mock_engine_speeds(config['prefill'], config['decode'])
        
        print("\n⏳ Please restart mock-engine manually:")
        print("   1. Stop the current mock-engine (Ctrl+C)")
        print("   2. Run: python3 mock_engine.py")
        print("   3. Wait for 'Running on http://127.0.0.1:8000'")
        
        input("\nPress Enter when mock-engine is ready...")
        
        # Run benchmark suite
        results = run_benchmark_suite(config['name'])
        
        # Calculate statistics
        stats = calculate_stats(results)
        
        # Print results
        print_results(config['name'], stats)
        
        # Store for comparison
        all_results.append((config['name'], config, stats))
        
        # Small break between configs
        time.sleep(1)
    
    # Print final comparison
    print_comparison(all_results)
    
    # Save results to JSON
    output_file = "benchmark_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "configs": [
                {
                    "name": name,
                    "config": config,
                    "stats": stats
                }
                for name, config, stats in all_results
            ]
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("\n✨ Benchmark complete!")

if __name__ == '__main__':
    main()