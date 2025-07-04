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

class PerformanceTracker:
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
        print(f"\n=== STARTING PERFORMANCE TEST: {test_name} ===")
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
        print("-" * 60)
        print(f"=== TEST RESULTS: {self.test_name} ===")
        print(f"Total Test Duration: {total_duration:.2f}s")
        print(f"EasyOCR Initializations: {self.easyocr_init_count}")
        print(f"Total EasyOCR Init Time: {self.total_easyocr_init_time:.2f}s")
        print(f"Average EasyOCR Init Time: {self.total_easyocr_init_time/max(1, self.easyocr_init_count):.2f}s")
        print(f"Actions Executed: {self.action_count}")
        print(f"EasyOCR Overhead: {(self.total_easyocr_init_time/total_duration)*100:.1f}%")
        
        # Save results to file
        results = {
            'test_name': self.test_name,
            'total_duration': total_duration,
            'easyocr_init_count': self.easyocr_init_count,
            'total_easyocr_init_time': self.total_easyocr_init_time,
            'action_count': self.action_count,
            'measurements': self.measurements,
            'timestamp': datetime.now().isoformat()
        }
        
        filename = f"performance_test_{self.test_name.lower().replace(' ', '_')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {filename}")
        
        return results

# Global performance tracker
tracker = PerformanceTracker()

def mock_easyocr_reader(*args, **kwargs):
    """Mock EasyOCR Reader to track initialization time"""
    init_start = time.time()
    
    # Simulate EasyOCR initialization time (actual loading time)
    time.sleep(2.5)  # Simulate realistic EasyOCR loading time
    
    init_duration = time.time() - init_start
    tracker.log_easyocr_init(init_duration)
    
    # Create a mock reader with readtext method
    mock_reader = MagicMock()
    mock_reader.readtext = MagicMock(return_value=[
        # Mock OCR results - simulate finding text elements
        [[[100, 100], [200, 100], [200, 150], [100, 150]], "Login", 0.9],
        [[[300, 200], [400, 200], [400, 250], [300, 250]], "Submit", 0.8],
        [[[150, 300], [250, 300], [250, 350], [150, 350]], "Next", 0.7],
    ])
    
    return mock_reader

def mock_screenshot_capture(*args, **kwargs):
    """Mock screenshot capture to avoid actual screen capture"""
    # Create a dummy screenshot file
    screenshot_path = args[0] if args else "screenshots/screenshot.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    
    # Create a minimal valid PNG file (1x1 pixel)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
    
    with open(screenshot_path, 'wb') as f:
        f.write(png_data)

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

async def run_performance_test():
    """Run a comprehensive performance test"""
    
    # Start tracking
    tracker.start_test("Current System Performance")
    
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
    print()
    
    # Patch all the external dependencies
    with patch('operate.models.apis.easyocr.Reader', side_effect=mock_easyocr_reader), \
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
                    tracker.log_action(operation_type, action_duration)
                    
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
    return tracker.finish_test()

async def main():
    """Main test function"""
    print("🚀 Starting Performance Test for Current System")
    print("=" * 60)
    
    results = await run_performance_test()
    
    print("\n🎯 KEY FINDINGS:")
    print(f"• EasyOCR was initialized {results['easyocr_init_count']} times")
    print(f"• Total wasted time on initialization: {results['total_easyocr_init_time']:.2f}s")
    print(f"• Average initialization time: {results['total_easyocr_init_time']/max(1, results['easyocr_init_count']):.2f}s")
    print(f"• Performance overhead: {(results['total_easyocr_init_time']/results['total_duration'])*100:.1f}%")
    
    print("\n📊 This test proves the EasyOCR repetition issue!")
    print("Next step: Optimize the code and run the same test again.")
    
    return results

if __name__ == "__main__":
    # Run the performance test
    results = asyncio.run(main()) 