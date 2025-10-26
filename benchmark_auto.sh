#!/bin/bash
# Automated benchmark runner for Mock Engine

echo "🚀 Mock Engine Automated Benchmark"
echo "===================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check requirements
if ! command -v qwen &> /dev/null; then
    echo -e "${RED}❌ Error: qwen command not found${NC}"
    exit 1
fi

if [ ! -f "mock_engine.py" ]; then
    echo -e "${RED}❌ Error: mock_engine.py not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment check passed${NC}"

# Kill any existing mock-engine processes
echo "🧹 Cleaning up existing mock-engine processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1


# Configurations to test
declare -a CONFIGS=(
    "10000000:10000000:Instant_10M"
    "1000000:1000000:VeryFast_1M"
    "100000:100000:Fast_100K"
    "10000:10000:Normal_10K"
)
# Test queries
declare -a QUERIES=(
    "search for class definitions"
    "find function declarations"
    "grep for import statements"
    "search for variable declarations"
    "find test functions"
    "grep for class methods"
    "search for error handlers"
    "find utility functions"
    "grep for constants"
    "search for API endpoints"
)

# Results file
RESULTS_FILE="benchmark_results.txt"
echo "Mock Engine Benchmark Results" > $RESULTS_FILE
echo "Generated: $(date)" >> $RESULTS_FILE
echo "======================================" >> $RESULTS_FILE

# Function to update mock_engine.py speeds
update_speeds() {
    local prefill=$1
    local decode=$2
    
    sed -i.bak "s/PREFILL_TOKENS_PER_SEC = [0-9]*/PREFILL_TOKENS_PER_SEC = $prefill/g" mock_engine.py
    sed -i.bak "s/DECODE_TOKENS_PER_SEC = [0-9]*/DECODE_TOKENS_PER_SEC = $decode/g" mock_engine.py
    
    echo -e "${GREEN}✅ Updated speeds: PREFILL=$prefill, DECODE=$decode${NC}"
}

# Function to start mock-engine
start_mock_engine() {
    echo "🔄 Starting mock-engine..."
    python3 mock_engine.py > /dev/null 2>&1 &
    MOCK_PID=$!
    
    # Wait for server to be ready
    sleep 3
    
    # Check if it's running
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${GREEN}✅ Mock-engine running on PID: $MOCK_PID${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to start mock-engine${NC}"
        return 1
    fi
}

# Function to stop mock-engine
stop_mock_engine() {
    echo "🛑 Stopping mock-engine..."
    kill $MOCK_PID 2>/dev/null
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 1
}

# Function to run benchmark for a configuration
run_benchmark() {
    local config_name=$1
    local prefill=$2
    local decode=$3
    
    echo ""
    echo "========================================"
    echo "🔧 Testing: $config_name"
    echo "   Prefill: $prefill tokens/sec"
    echo "   Decode:  $decode tokens/sec"
    echo "========================================"
    
    # Update speeds
    update_speeds $prefill $decode
    
    # Stop any existing instance
    stop_mock_engine
    
    # Start new instance
    if ! start_mock_engine; then
        echo -e "${RED}❌ Skipping $config_name - failed to start mock-engine${NC}"
        return
    fi
    
    # Set environment variables
    export OPENAI_BASE_URL=http://localhost:8000/v1
    export OPENAI_API_KEY=mock-key
    
    # Run queries and measure time
    local total_time=0
    local success_count=0
    local query_times=()
    
    echo ""
    echo "Running 10 queries..."
    
    for i in {0..9}; do
        local query="${QUERIES[$i]}"
        echo -n "  [$((i+1))/10] '$query'... "
        
        local start_time=$(date +%s.%N)
        
        if timeout 10 qwen -p "$query" > /dev/null 2>&1; then
            local end_time=$(date +%s.%N)
            local elapsed=$(echo "$end_time - $start_time" | bc)
            query_times+=($elapsed)
            total_time=$(echo "$total_time + $elapsed" | bc)
            success_count=$((success_count + 1))
            echo -e "${GREEN}✅ ${elapsed}s${NC}"
        else
            echo -e "${RED}❌ Failed${NC}"
        fi
        
        sleep 0.2
    done
    
    # Calculate statistics
    if [ $success_count -gt 0 ]; then
        local avg_time=$(echo "scale=3; $total_time / $success_count" | bc)
        
        # Find min and max
        local min_time=${query_times[0]}
        local max_time=${query_times[0]}
        
        for time in "${query_times[@]}"; do
            if (( $(echo "$time < $min_time" | bc -l) )); then
                min_time=$time
            fi
            if (( $(echo "$time > $max_time" | bc -l) )); then
                max_time=$time
            fi
        done
        
        # Print results
        echo ""
        echo "📊 Results for $config_name:"
        echo "   Average time:  ${avg_time}s"
        echo "   Min time:      ${min_time}s"
        echo "   Max time:      ${max_time}s"
        echo "   Total time:    ${total_time}s"
        echo "   Success rate:  $((success_count * 10))%"
        
        # Append to results file
        echo "" >> $RESULTS_FILE
        echo "$config_name (Prefill: $prefill, Decode: $decode)" >> $RESULTS_FILE
        echo "  Average: ${avg_time}s" >> $RESULTS_FILE
        echo "  Min: ${min_time}s" >> $RESULTS_FILE
        echo "  Max: ${max_time}s" >> $RESULTS_FILE
        echo "  Total: ${total_time}s" >> $RESULTS_FILE
        echo "  Success: $success_count/10" >> $RESULTS_FILE
    else
        echo -e "${RED}❌ All queries failed for $config_name${NC}"
    fi
    
    # Stop mock-engine
    stop_mock_engine
}

# Main benchmark loop
echo ""
echo "Starting benchmarks..."
echo ""

for config in "${CONFIGS[@]}"; do
    IFS=':' read -r prefill decode name <<< "$config"
    run_benchmark "$name" "$prefill" "$decode"
    sleep 2
done

# Print summary
echo ""
echo "========================================"
echo "✨ Benchmark Complete!"
echo "========================================"
echo ""
echo "Results saved to: $RESULTS_FILE"
cat $RESULTS_FILE

# Restore original mock_engine.py
if [ -f "mock_engine.py.bak" ]; then
    mv mock_engine.py.bak mock_engine.py
    echo ""
    echo "✅ Restored original mock_engine.py"
fi

echo ""
echo "🎉 All done!"