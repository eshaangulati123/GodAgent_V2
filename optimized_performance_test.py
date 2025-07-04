import time
import os
import json
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import threading

# Add the operate module to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from operate.models.apis import get_next_action, call_gpt_4o_with_ocr
from operate.config import Config
from operate.utils.ocr_manager import get_ocr_reader, get_ocr_stats, reset_ocr_manager

class OptimizedPerformanceTracker:
    def __init__(self):
        self.measurements = []
        self.easyocr_init_count = 0
        self.total_easyocr_init_time = 0
        self.action_count = 0
        self.start_time = None
        self.lock = threading.Lock()
    
    def start_test(self, test_name):
        """Start tracking a new test"""
        self.test_name = test_name
        self.start_time = time.time()
        self.measurements = []
        self.easyocr_init_count = 0
        self.total_easyocr_init_time = 0
        self.action_count = 0
        print(f"\n=== STARTING OPTIMIZED PERFORMANCE TEST: {test_name} ===")
        print(f"Test started at: {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 60)
    
    def log_easyocr_init(self, duration):
        """Log EasyOCR initialization"""
        with self.lock:
            self.easyocr_init_count += 1
            self.total_easyocr_init_time += duration
            print(f"🔥 EasyOCR Init #{self.easyocr_init_count}: {duration:.2f}s")
    
    def log_action(self, action_type, duration):
        """Log action execution"""
        with self.lock:
            self.action_count += 1
            self.measurements.append({
                'action': action_type,
                'duration': duration,
                'timestamp': time.time() - self.start_time
            })
            print(f"⚡ Action #{self.action_count} ({action_type}): {duration:.2f}s")
    
    def finish_test(self):
        """Finish test and show results"""
        total_duration = time.time() - self.start_time
        
        # Get OCR manager statistics
        ocr_stats = get_ocr_stats()
        
        print("-" * 60)
        print(f"=== OPTIMIZED TEST RESULTS: {self.test_name} ===")
        print(f"Total Test Duration: {total_duration:.2f}s")
        print(f"EasyOCR Initializations: {ocr_stats['total_readers']}")
        print(f"Total EasyOCR Init Time: {ocr_stats['total_init_time']:.2f}s")
        print(f"Total EasyOCR Usage: {ocr_stats['total_usage']}")
        print(f"Average EasyOCR Init Time: {ocr_stats['average_init_time']:.2f}s")
        print(f"Actions Executed: {self.action_count}")
        print(f"EasyOCR Overhead: {(ocr_stats['total_init_time']/total_duration)*100:.1f}%")
        
        # Additional optimization metrics
        if ocr_stats['total_usage'] > 0:
            reuse_efficiency = (ocr_stats['total_usage'] - ocr_stats['total_readers']) / ocr_stats['total_usage'] * 100
            print(f"OCR Reuse Efficiency: {reuse_efficiency:.1f}%")
        
        # Save results to file
        results = {
            'test_name': self.test_name,
            'total_duration': total_duration,
            'action_count': self.action_count,
            'measurements': self.measurements,
            'ocr_stats': ocr_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        filename = f"optimized_performance_test_{self.test_name.lower().replace(' ', '_')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {filename}")
        
        return results

# Global performance tracker
optimized_tracker = OptimizedPerformanceTracker()

# Track OCR manager calls
original_get_ocr_reader = get_ocr_reader

def tracked_get_ocr_reader(*args, **kwargs):
    """Track OCR manager calls"""
    start_time = time.time()
    result = original_get_ocr_reader(*args, **kwargs)
    duration = time.time() - start_time
    
    # Only log if there was actual initialization (> 0.1s)
    if duration > 0.1:
        optimized_tracker.log_easyocr_init(duration)
    
    return result

def mock_screenshot_capture(*args, **kwargs):
    """Mock screenshot capture to avoid actual screen capture"""
    # Create a dummy screenshot file
    screenshot_path = args[0] if args else "screenshots/screenshot.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    
    # Create a minimal valid PNG file (1x1 pixel)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
    
    with open(screenshot_path, 'wb') as f:
        f.write(png_data)

def mock_easyocr_reader(*args, **kwargs):
    """Mock EasyOCR Reader with realistic initialization time"""
    init_start = time.time()
    
    # Simulate EasyOCR initialization time (actual loading time)
    time.sleep(2.5)  # Simulate realistic EasyOCR loading time
    
    # Create a mock reader with readtext method
    mock_reader = MagicMock()
    mock_reader.readtext = MagicMock(return_value=[
        # Mock OCR results - simulate finding text elements
        [[[100, 100], [200, 100], [200, 150], [100, 150]], "Login", 0.9],
        [[[300, 200], [400, 200], [400, 250], [300, 250]], "Submit", 0.8],
        [[[150, 300], [250, 300], [250, 350], [150, 350]], "Next", 0.7],
    ])
    
    return mock_reader

def mock_openai_response(*args, **kwargs):
    """Mock OpenAI API response"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    
    # Simulate different actions in sequence
    action_sequence = [
        '[{"thought": "I need to click the login button", "operation": "click", "text": "Login"}]',
        '[{"thought": "Now I need to type the username", "operation": "write", "content": "testuser"}]',
        '[{"thought": "I need to click submit", "operation": "click", "text": "Submit"}]',
        '[{"thought": "Task completed successfully", "operation": "done", "summary": "Login completed"}]'
    ]
    
    # Cycle through actions
    action_index = getattr(mock_openai_response, '_action_index', 0)
    mock_response.choices[0].message.content = action_sequence[action_index % len(action_sequence)]
    mock_openai_response._action_index = action_index + 1
    
    return mock_response

async def run_optimized_performance_test():
    """Run a comprehensive optimized performance test"""
    
    # Reset OCR manager to ensure clean state
    reset_ocr_manager()
    
    # Start tracking
    optimized_tracker.start_test("Optimized System Performance")
    
    # Set up config
    config = Config()
    config.verbose = True
    
    # Create mock messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    
    objective = "Login to application with username and password"
    model = "gpt-4-with-ocr"
    
    print("📋 Simulating task: Login to application")
    print("🎯 Expected actions: Click Login -> Type Username -> Click Submit -> Done")
    print("🚀 Using optimized OCR manager with singleton pattern")
    print()
    
    # Patch dependencies with optimized tracking
    with patch('operate.utils.ocr_manager.get_ocr_reader', side_effect=tracked_get_ocr_reader), \
         patch('easyocr.Reader', side_effect=mock_easyocr_reader), \
         patch('operate.utils.screenshot.capture_screen_with_cursor', side_effect=mock_screenshot_capture), \
         patch('operate.config.Config.initialize_openai') as mock_openai_init:
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_openai_response
        mock_openai_init.return_value = mock_client
        
        # Simulate the main loop (similar to operate.py)
        loop_count = 0
        max_loops = 4  # Simulate 4 actions
        
        while loop_count < max_loops:
            print(f"\n--- LOOP {loop_count + 1} ---")
            
            action_start = time.time()
            
            try:
                # This is what gets called in the real system
                operations, session_id = await get_next_action(model, messages, objective, None)
                
                action_duration = time.time() - action_start
                
                # Log this action
                if operations and len(operations) > 0:
                    operation_type = operations[0].get('operation', 'unknown')
                    optimized_tracker.log_action(operation_type, action_duration)
                    
                    # Simulate processing the operation
                    if operation_type == 'done':
                        print(f"✅ Task completed: {operations[0].get('summary', '')}")
                        break
                    else:
                        print(f"🔄 Executed: {operation_type}")
                
                # Add operation response to messages (simulate conversation)
                if operations:
                    messages.append({"role": "assistant", "content": str(operations)})
                
                loop_count += 1
                
            except Exception as e:
                print(f"❌ Error in loop {loop_count + 1}: {e}")
                break
        
        # Wait a moment to ensure all logging is complete
        time.sleep(0.1)
    
    # Finish test and return results
    return optimized_tracker.finish_test()

def compare_results(baseline_file, optimized_file):
    """Compare baseline vs optimized results"""
    
    print("\n" + "="*60)
    print("📊 PERFORMANCE COMPARISON")
    print("="*60)
    
    try:
        # Load baseline results
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        
        # Load optimized results
        with open(optimized_file, 'r') as f:
            optimized = json.load(f)
        
        # Compare key metrics
        baseline_duration = baseline['total_duration']
        optimized_duration = optimized['total_duration']
        
        baseline_init_time = baseline['total_easyocr_init_time']
        optimized_init_time = optimized['ocr_stats']['total_init_time']
        
        baseline_init_count = baseline['easyocr_init_count']
        optimized_init_count = optimized['ocr_stats']['total_readers']
        
        # Calculate improvements
        duration_improvement = ((baseline_duration - optimized_duration) / baseline_duration) * 100
        init_time_improvement = ((baseline_init_time - optimized_init_time) / baseline_init_time) * 100
        init_count_improvement = ((baseline_init_count - optimized_init_count) / baseline_init_count) * 100
        
        print(f"📈 TOTAL DURATION:")
        print(f"   Baseline: {baseline_duration:.2f}s")
        print(f"   Optimized: {optimized_duration:.2f}s")
        print(f"   Improvement: {duration_improvement:.1f}% faster")
        
        print(f"\n🔥 EASYOCR INITIALIZATION:")
        print(f"   Baseline Inits: {baseline_init_count}")
        print(f"   Optimized Inits: {optimized_init_count}")
        print(f"   Reduction: {init_count_improvement:.1f}% fewer initializations")
        
        print(f"\n⏱️  INITIALIZATION TIME:")
        print(f"   Baseline: {baseline_init_time:.2f}s")
        print(f"   Optimized: {optimized_init_time:.2f}s")
        print(f"   Saved: {init_time_improvement:.1f}% less time")
        
        print(f"\n🎯 EFFICIENCY GAINS:")
        print(f"   OCR Reuse: {optimized['ocr_stats']['total_usage'] - optimized['ocr_stats']['total_readers']} times")
        print(f"   Memory Savings: {baseline_init_count - optimized_init_count} fewer EasyOCR instances")
        
        # Calculate absolute savings
        time_saved = baseline_duration - optimized_duration
        print(f"\n💰 ABSOLUTE SAVINGS:")
        print(f"   Time Saved: {time_saved:.2f} seconds")
        print(f"   Speedup Factor: {baseline_duration/optimized_duration:.1f}x")
        
    except FileNotFoundError as e:
        print(f"❌ Could not find result files: {e}")
    except Exception as e:
        print(f"❌ Error comparing results: {e}")

async def main():
    """Main optimized test function"""
    print("🚀 Starting Optimized Performance Test")
    print("=" * 60)
    
    # Run optimized test
    results = await run_optimized_performance_test()
    
    print("\n🎯 OPTIMIZED KEY FINDINGS:")
    print(f"• EasyOCR was initialized {results['ocr_stats']['total_readers']} times")
    print(f"• EasyOCR was reused {results['ocr_stats']['total_usage']} times total")
    print(f"• Total initialization time: {results['ocr_stats']['total_init_time']:.2f}s")
    print(f"• Performance overhead: {(results['ocr_stats']['total_init_time']/results['total_duration'])*100:.1f}%")
    
    # Compare with baseline if available
    baseline_file = "performance_test_current_system_performance.json"
    optimized_file = f"optimized_performance_test_{results['test_name'].lower().replace(' ', '_')}.json"
    
    if os.path.exists(baseline_file):
        compare_results(baseline_file, optimized_file)
    else:
        print(f"\n⚠️  Baseline file not found: {baseline_file}")
        print("Run the original performance test first to compare results.")
    
    return results

if __name__ == "__main__":
    # Run the optimized performance test
    results = asyncio.run(main()) 