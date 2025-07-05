#!/usr/bin/env python3
"""
Browser Use Agent Wrapper for Self-Operating Computer
Provides unified interface between Browser Use and the existing OCR system
Maintains API compatibility while adding browser automation capabilities
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import json

# Browser Use imports
try:
    from browser_use import Agent, BrowserSession
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_google_genai import ChatGoogleGenerativeAI
    BROWSER_USE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Browser Use not available: {e}")
    BROWSER_USE_AVAILABLE = False

# File upload capability imports
try:
    from operate.utils.browser_file_upload import controller as file_upload_controller
    FILE_UPLOAD_AVAILABLE = True
    logging.info("File upload actions available for Browser Use Agent")
except ImportError as e:
    logging.warning(f"File upload actions not available: {e}")
    FILE_UPLOAD_AVAILABLE = False
    file_upload_controller = None

# Self-operating computer imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from operate.utils.task_classifier import classify_task, TaskType
except ImportError:
    # Fallback for testing - use relative import
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))
    from task_classifier import classify_task, TaskType

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class BrowserAction:
    """Represents a browser action taken by the agent"""
    action_type: str
    description: str
    target: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None
    text_input: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

class BrowserAgent:
    """
    Browser Use Agent Wrapper
    
    Provides unified interface for browser automation while maintaining
    compatibility with the existing self-operating computer system
    """
    
    def __init__(self, model_name: str = "gpt-4o", headless: bool = True):
        """
        Initialize Browser Use agent
        
        Args:
            model_name: The LLM model to use for browser automation
            headless: Whether to run browser in headless mode
        """
        self.model_name = model_name
        self.headless = headless
        self.session_id = None
        self.browser_instance = None
        self.current_llm = None
        
        # Check if Browser Use is available
        if not BROWSER_USE_AVAILABLE:
            raise ImportError("Browser Use is not installed. Run: pip install browser-use")
        
        # Initialize LLM based on model name
        self._initialize_llm()
        
        logger.info(f"BrowserAgent initialized with model: {model_name}")
    
    def _initialize_llm(self):
        """Initialize the appropriate LLM based on model name"""
        try:
            if "gpt" in self.model_name.lower() or "o1" in self.model_name.lower():
                # OpenAI models
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment")
                
                # Map self-operating computer model names to OpenAI model names
                model_mapping = {
                    'gpt-4-with-ocr': 'gpt-4o',
                    'gpt-4.1-with-ocr': 'gpt-4o',
                    'o1-with-ocr': 'o1-preview',
                    'gpt-4o': 'gpt-4o',
                    'gpt-4': 'gpt-4'
                }
                
                openai_model = model_mapping.get(self.model_name, 'gpt-4o')
                self.current_llm = ChatOpenAI(
                    model=openai_model,
                    api_key=api_key,
                    temperature=0
                )
                logger.info(f"Initialized OpenAI LLM: {openai_model}")
                
            elif "claude" in self.model_name.lower():
                # Anthropic Claude models
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not found in environment")
                
                claude_model = "claude-3-5-sonnet-20241022"  # Latest Claude model
                self.current_llm = ChatAnthropic(
                    model=claude_model,
                    api_key=api_key,
                    temperature=0
                )
                logger.info(f"Initialized Claude LLM: {claude_model}")
                
            elif "gemini" in self.model_name.lower():
                # Google Gemini models
                api_key = os.getenv('GOOGLE_API_KEY')
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not found in environment")
                
                gemini_model = "gemini-pro"
                self.current_llm = ChatGoogleGenerativeAI(
                    model=gemini_model,
                    google_api_key=api_key,
                    temperature=0
                )
                logger.info(f"Initialized Gemini LLM: {gemini_model}")
                
            else:
                # Default to GPT-4o
                logger.warning(f"Unknown model {self.model_name}, defaulting to GPT-4o")
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment")
                
                self.current_llm = ChatOpenAI(
                    model="gpt-4o",
                    api_key=api_key,
                    temperature=0
                )
                
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    async def execute_task(self, objective: str, model: str = None, 
                          session_id: str = None, user_data_dir: str = None) -> List[Dict]:
        """
        Execute a browser task using Browser Use
        
        Args:
            objective: The task to accomplish
            model: Model name (optional, uses instance default)
            session_id: Session ID for tracking
            user_data_dir: Path to existing Chrome profile directory (optional)
            
        Returns:
            List of actions taken (compatible with existing system format)
        """
        if model and model != self.model_name:
            # Reinitialize with new model if needed
            self.model_name = model
            self._initialize_llm()
        
        self.session_id = session_id or f"browser_session_{time.time()}"
        
        logger.info(f"Executing browser task: {objective}")
        logger.info(f"Using model: {self.model_name}")
        if user_data_dir:
            logger.info(f"Using existing Chrome profile: {user_data_dir}")
        
        try:
            # Import Browser Use components
            from browser_use import Agent, BrowserSession
            
            # Create Browser Use agent with Chrome profile support
            if user_data_dir:
                # Use existing Chrome profile
                browser_session = BrowserSession(
                    user_data_dir=user_data_dir,
                    headless=False,  # Show browser when using existing profile
                    channel='chrome'  # Use actual Chrome instead of Chromium
                )
                
                # Enhanced task description with file upload instructions
                enhanced_task = f"""
{objective}

IMPORTANT FILE UPLOAD INSTRUCTIONS:
When Browser Use responds with "To upload files please use a specific function to upload files", 
you need to determine if it's a real file upload or a false positive:

1. **FOR ATTACHMENT/UPLOAD BUTTONS (paperclip icons, "Attach files" buttons)**:
   Call: "Find and upload file"
   Parameters: {{"file_description": "n8n file", "selector": "button[data-tooltip='Attach files']"}}

2. **FOR SEND/SUBMIT BUTTONS (incorrectly blocked by Browser Use)**:
   Call: "Force click element" 
   Parameters: {{"index": [element_index], "reason": "Send button falsely detected as file upload"}}

How to tell the difference:
- If the element is an attachment icon (📎), "Attach files" button, or file input → Use "Find and upload file"
- If the element is a "Send" button, "Submit" button, or similar action button → Use "Force click element"

Available actions:
1. "Find and upload file" - For real file upload elements
2. "Upload specific file" - When you have exact file path
3. "Force click element" - For Send buttons falsely blocked by Browser Use

Never retry clicking blocked elements - always use the appropriate action above.
"""

                agent = Agent(
                    task=enhanced_task,
                    llm=self.current_llm,
                    browser_session=browser_session,
                    controller=file_upload_controller if FILE_UPLOAD_AVAILABLE else None,
                    use_vision=True,
                    save_conversation_path=None,
                    max_actions_per_step=10
                )
                logger.info("Browser Use will use your existing Chrome profile with saved logins")
                if FILE_UPLOAD_AVAILABLE:
                    logger.info("✓ File upload actions enabled with enhanced LLM instructions")
            else:
                # Use default Browser Use configuration (fresh Chromium instance)
                # Enhanced task description with file upload instructions
                enhanced_task = f"""
{objective}

IMPORTANT FILE UPLOAD INSTRUCTIONS:
When Browser Use responds with "To upload files please use a specific function to upload files", 
you need to determine if it's a real file upload or a false positive:

1. **FOR ATTACHMENT/UPLOAD BUTTONS (paperclip icons, "Attach files" buttons)**:
   Call: "Find and upload file"
   Parameters: {{"file_description": "n8n file", "selector": "button[data-tooltip='Attach files']"}}

2. **FOR SEND/SUBMIT BUTTONS (incorrectly blocked by Browser Use)**:
   Call: "Force click element" 
   Parameters: {{"index": [element_index], "reason": "Send button falsely detected as file upload"}}

How to tell the difference:
- If the element is an attachment icon (📎), "Attach files" button, or file input → Use "Find and upload file"
- If the element is a "Send" button, "Submit" button, or similar action button → Use "Force click element"

Available actions:
1. "Find and upload file" - For real file upload elements
2. "Upload specific file" - When you have exact file path
3. "Force click element" - For Send buttons falsely blocked by Browser Use

Never retry clicking blocked elements - always use the appropriate action above.
"""
                
                agent = Agent(
                    task=enhanced_task,
                    llm=self.current_llm,
                    controller=file_upload_controller if FILE_UPLOAD_AVAILABLE else None,
                    use_vision=True,
                    save_conversation_path=None,
                    max_actions_per_step=10
                )
                logger.info("Browser Use will launch a fresh browser instance")
                if FILE_UPLOAD_AVAILABLE:
                    logger.info("✓ File upload actions enabled with enhanced LLM instructions")
            
            # Execute the task
            logger.info("Starting browser task execution...")
            result = await agent.run()
            
            # Convert Browser Use result to self-operating computer format
            actions = self._convert_browser_use_result(result)
            
            logger.info(f"Browser task completed successfully with {len(actions)} actions")
            return actions
            
        except Exception as e:
            logger.error(f"Browser task execution failed: {e}")
            # Return error action in expected format
            return [{
                'action': 'error',
                'description': f"Browser automation failed: {str(e)}",
                'success': False,
                'error_message': str(e),
                'fallback_recommended': True
            }]
    
    def _convert_browser_use_result(self, result: Any) -> List[Dict]:
        """
        Convert Browser Use result to self-operating computer action format
        
        Args:
            result: Browser Use execution result
            
        Returns:
            List of actions in self-operating computer format
        """
        actions = []
        
        try:
            # If result has action history, process it
            if hasattr(result, 'history') and result.history:
                for i, action_item in enumerate(result.history):
                    action_dict = {
                        'action': 'browser_action',
                        'step': i + 1,
                        'description': getattr(action_item, 'description', f"Browser action {i+1}"),
                        'success': True,
                        'timestamp': time.time()
                    }
                    
                    # Add specific action details if available
                    if hasattr(action_item, 'action_type'):
                        action_dict['action_type'] = action_item.action_type
                    
                    if hasattr(action_item, 'element'):
                        action_dict['target_element'] = str(action_item.element)
                    
                    actions.append(action_dict)
            
            # Add final completion action
            actions.append({
                'action': 'task_completed',
                'description': f"Browser task completed successfully",
                'success': True,
                'total_steps': len(actions),
                'execution_time': time.time(),
                'agent_type': 'browser_use'
            })
            
        except Exception as e:
            logger.warning(f"Error converting Browser Use result: {e}")
            # Fallback action format
            actions = [{
                'action': 'browser_task',
                'description': "Browser task executed (details unavailable)",
                'success': True,
                'result': str(result) if result else "Task completed",
                'agent_type': 'browser_use'
            }]
        
        return actions
    
    @staticmethod
    def is_browser_task(objective: str, confidence_threshold: float = 0.6) -> bool:
        """
        Check if a task should be handled by browser automation
        
        Args:
            objective: Task description
            confidence_threshold: Minimum confidence for browser classification
            
        Returns:
            True if task should use browser automation
        """
        try:
            result = classify_task(objective)
            
            # Browser tasks or mixed tasks should use browser agent
            if result.task_type in [TaskType.BROWSER, TaskType.MIXED]:
                return True
            
            # Ambiguous tasks with browser fallback
            if (result.task_type == TaskType.AMBIGUOUS and 
                result.fallback_recommendation == TaskType.BROWSER):
                return True
            
            # High confidence browser tasks
            if (result.task_type == TaskType.BROWSER and 
                result.confidence >= confidence_threshold):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Task classification failed: {e}")
            # Conservative fallback - check for obvious browser indicators
            objective_lower = objective.lower()
            browser_indicators = ['http', 'www', 'gmail', 'youtube', 'google', 'website', 'browser']
            return any(indicator in objective_lower for indicator in browser_indicators)
    
    @staticmethod
    async def fallback_to_ocr(objective: str, model: str, session_id: str = None) -> List[Dict]:
        """
        Fallback to the original OCR system when browser automation fails
        
        Args:
            objective: Task description
            model: Model name to use
            session_id: Session ID for tracking
            
        Returns:
            Actions from OCR system
        """
        logger.info("Falling back to OCR system for task execution")
        
        try:
            # Use a simplified fallback approach
            # Return an action that indicates OCR fallback should be used
            return [{
                'action': 'fallback_to_ocr',
                'description': f"Browser automation failed, OCR system should handle: {objective}",
                'success': True,
                'objective': objective,
                'model': model,
                'session_id': session_id,
                'fallback_required': True
            }]
            
        except Exception as e:
            logger.error(f"OCR fallback preparation failed: {e}")
            return [{
                'action': 'error',
                'description': f"Both browser and OCR systems failed: {str(e)}",
                'success': False,
                'error_message': str(e)
            }]
    
    async def close(self):
        """Clean up browser resources"""
        try:
            if self.browser_instance:
                await self.browser_instance.close()
                logger.info("Browser instance closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported model names"""
        return [
            'gpt-4-with-ocr',
            'gpt-4.1-with-ocr', 
            'o1-with-ocr',
            'claude-3',
            'gemini-pro-vision',
            'gpt-4o',
            'gpt-4'
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            'agent_type': 'browser_use',
            'model': self.model_name,
            'session_id': self.session_id,
            'headless': self.headless,
            'llm_initialized': self.current_llm is not None,
            'browser_use_available': BROWSER_USE_AVAILABLE,
            'file_upload_available': FILE_UPLOAD_AVAILABLE
        }

# Convenience functions for easy integration
async def execute_browser_task(objective: str, model: str = "gpt-4o", 
                              session_id: str = None) -> List[Dict]:
    """
    Convenience function to execute a browser task
    
    Args:
        objective: Task to accomplish
        model: Model name to use
        session_id: Session ID for tracking
        
    Returns:
        List of actions taken
    """
    agent = BrowserAgent(model_name=model)
    try:
        return await agent.execute_task(objective, model, session_id)
    finally:
        await agent.close()

def is_browser_task(objective: str) -> bool:
    """Simple check if task should use browser automation"""
    return BrowserAgent.is_browser_task(objective)

async def smart_task_router(objective: str, model: str = "gpt-4o", 
                           session_id: str = None, user_data_dir: str = None) -> List[Dict]:
    """
    Smart task router that automatically chooses browser or desktop automation
    
    Args:
        objective: Task to accomplish
        model: Model name to use
        session_id: Session ID for tracking
        user_data_dir: Path to existing Chrome profile directory (optional)
        
    Returns:
        List of actions taken
    """
    if BrowserAgent.is_browser_task(objective):
        logger.info("Routing task to Browser Use Agent")
        agent = BrowserAgent(model_name=model)
        try:
            result = await agent.execute_task(objective, model, session_id, user_data_dir)
            
            # Check if browser automation failed and fallback is recommended
            if (result and len(result) > 0 and 
                result[0].get('success') == False and 
                result[0].get('fallback_recommended')):
                logger.info("Browser automation failed, falling back to OCR system")
                return await BrowserAgent.fallback_to_ocr(objective, model, session_id)
            
            return result
        finally:
            await agent.close()
    else:
        logger.info("Routing task to Desktop OCR System")
        return await BrowserAgent.fallback_to_ocr(objective, model, session_id)

if __name__ == "__main__":
    # Test the browser agent
    async def test_browser_agent():
        """Test browser agent functionality"""
        print("🧪 Testing Browser Agent")
        print("=" * 50)
        
        # Test task classification
        test_tasks = [
            "Go to Gmail and check my inbox",
            "Open calculator and compute 5+5",
            "Navigate to https://youtube.com",
            "Create a new folder on desktop"
        ]
        
        for task in test_tasks:
            is_browser = BrowserAgent.is_browser_task(task)
            print(f"📝 Task: {task}")
            print(f"🎯 Route to: {'Browser Use' if is_browser else 'Desktop OCR'}")
            print()
        
        # Test agent initialization
        try:
            agent = BrowserAgent(model_name="gpt-4o")
            status = agent.get_status()
            print("✅ Browser Agent Status:")
            for key, value in status.items():
                print(f"   {key}: {value}")
            await agent.close()
        except Exception as e:
            print(f"❌ Browser Agent Error: {e}")
    
    # Run test
    asyncio.run(test_browser_agent()) 