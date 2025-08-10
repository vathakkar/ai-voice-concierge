# 🚀 AI Voice Concierge Performance Testing

This document explains how to use the performance testing script to identify bottlenecks in your AI Voice Concierge system.

## 📋 What the Test Does

The performance test simulates **5 complete call flows** and measures:

1. **TTS Generation** - Azure Speech Services performance
2. **AI Processing** - Azure OpenAI (GPT-4o-mini) response time  
3. **Endpoint Latencies** - Each Twilio webhook endpoint
4. **Memory Usage** - System resource consumption
5. **Total Call Flow Time** - End-to-end performance

## 🎯 Key Features

- **Real Azure Services**: Uses your actual Azure Speech Services and OpenAI endpoints
- **Twilio Integration**: Simulates real Twilio webhook calls with proper signature validation
- **Comprehensive Metrics**: Captures timing from your existing logging infrastructure
- **Bottleneck Analysis**: Automatically identifies performance issues
- **Statistical Analysis**: Provides averages, medians, min/max values

## 🚀 How to Run

### Option 1: Use the Shell Script (Recommended)
```bash
./run_performance_test.sh
```

### Option 2: Manual Execution
```bash
# Load environment variables
export $(cat .env | grep -E '^(BASE_URL|TWILIO_AUTH_TOKEN|TEST_CALLER_ID|TEST_SPEECH)=' | xargs)

# Run the test
python3 performance_test.py
```

## 📊 What You'll See

The test will show:

```
🚀 AI Voice Concierge Performance Testing
==================================================
Testing against: https://ai-voice-concierge-canadacentral.azurewebsites.net
Using GPT-4o-mini (from your config)
Using Azure Speech Services (from your config)

[TEST 1] Starting call flow simulation...
  [TEST 1.1] POST /twilio/voice
    ✅ Success: 200 (1489ms)
    📋 Session ID: abc123...
  [TEST 1.2] POST /twilio/ai-response
    ✅ Success: 200 (821ms)
  [TEST 1.3] POST /twilio/process-ai
    ✅ Success: 200 (3825ms)
    📊 AI Processing: 2634ms
    📊 TTS Generation: 1207ms
  [TEST 1] ✅ Call flow completed in 6143ms

... (4 more tests)

================================================================================
PERFORMANCE TEST RESULTS (5 simulated calls)
================================================================================

TTS Generation (Azure Speech Services):
  Average: 1250.00ms
  Median:  1207.00ms
  Min:     1207.00ms
  Max:     1450.00ms

AI Processing (Azure OpenAI):
  Average: 3205.00ms
  Median:  3622.00ms
  Min:     2243.00ms
  Max:     4342.00ms

BOTTLENECK ANALYSIS:
  ⚠️  AI Processing is the MAJOR bottleneck (3205ms vs TTS 1250ms)
  ✅ TTS Generation is acceptable (1250ms)
  ✅ Total call flow is acceptable (6143ms)
```

## 🔍 Understanding the Results

### TTS Generation (Azure Speech Services)
- **Good**: < 2000ms (2 seconds)
- **Warning**: > 2000ms - Check Azure Speech Services performance

### AI Processing (Azure OpenAI)
- **Good**: < 3000ms (3 seconds)  
- **Warning**: > 3000ms - Consider switching to faster model (GPT-4o)
- **Critical**: > 5000ms - Major bottleneck

### Total Call Flow
- **Good**: < 10000ms (10 seconds)
- **Warning**: > 10000ms - Optimize endpoint latencies

## 🛠️ Troubleshooting

### Common Issues

1. **"Cannot connect to service"**
   - Check if your Azure Web App is running
   - Verify BASE_URL in .env file

2. **"TWILIO_AUTH_TOKEN must be set"**
   - Ensure your .env file has TWILIO_AUTH_TOKEN
   - Check token validity

3. **"No timing data captured"**
   - The script extracts timing from your existing logs
   - Make sure your app is logging timing information

### Environment Variables Required

```bash
BASE_URL=https://your-app.azurewebsites.net
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TEST_CALLER_ID=+1234567890
TEST_SPEECH="Your test speech text here"
```

## 💡 Optimization Recommendations

Based on your current setup (GPT-4o-mini):

1. **If AI processing > 3s**: Consider switching to GPT-4o for better speed
2. **If TTS > 2s**: Check Azure Speech Services performance
3. **If total > 10s**: Optimize endpoint latencies and network

## 🔧 Next Steps After Testing

1. **Identify the bottleneck** (AI, TTS, or network)
2. **Check Azure service performance** in Azure Portal
3. **Consider model changes** if AI is the bottleneck
4. **Monitor production performance** with real calls
5. **Run tests regularly** to track improvements

## 📁 Files Created

- `performance_test.py` - Main performance testing script
- `run_performance_test.sh` - Easy execution script  
- `PERFORMANCE_TEST_README.md` - This documentation

## 🎯 Mission Accomplished

This script will help you:
- ✅ **Find the bottleneck** in your call flow
- ✅ **Measure real performance** with actual Azure services
- ✅ **Get actionable data** for optimization
- ✅ **Test 5 simulated calls** with statistical analysis

Run the test and let the data guide your optimization decisions! 🚀 