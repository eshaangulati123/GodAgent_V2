import sys
import os
import time
import asyncio
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit import prompt
from operate.exceptions import ModelNotRecognizedException
import platform
import logging

# from operate.models.prompts import USER_QUESTION, get_system_prompt
from operate.models.prompts import (
    USER_QUESTION,
    get_system_prompt,
)
from operate.config import Config
from operate.utils.style import (
    ANSI_GREEN,
    ANSI_RESET,
    ANSI_YELLOW,
    ANSI_RED,
    ANSI_BRIGHT_MAGENTA,
    ANSI_BLUE,
    style,
)
from operate.utils.operating_system import OperatingSystem
from operate.models.apis import get_next_action

# Browser Use integration imports
try:
    from operate.agents.browser_agent import BrowserAgent, smart_task_router
    BROWSER_AGENT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Browser Use agent not available: {e}")
    BROWSER_AGENT_AVAILABLE = False

# Load configuration
config = Config()
operating_system = OperatingSystem()


def main(model, terminal_prompt, voice_mode=False, verbose_mode=False, 
         browser_agent=False, no_browser_agent=False, browser_threshold=0.6, chrome_profile_dir=None):
    """
    Main function for the Self-Operating Computer with Browser Use integration.

    Parameters:
    - model: The model used for generating responses.
    - terminal_prompt: A string representing the prompt provided in the terminal.
    - voice_mode: A boolean indicating whether to enable voice mode.
    - verbose_mode: A boolean indicating whether to enable verbose output.
    - browser_agent: Force use Browser Use for all tasks.
    - no_browser_agent: Disable Browser Use, use OCR only.
    - browser_threshold: Confidence threshold for browser detection (0.0-1.0).
    - chrome_profile_dir: Path to existing Chrome profile directory (optional).

    Returns:
    None
    """

    mic = None
    # Initialize `WhisperMic`, if `voice_mode` is True

    config.verbose = verbose_mode
    config.validation(model, voice_mode)
    
    # CHROME AUTHENTICATION MANAGEMENT
    # Handle Chrome profile authentication for browser tasks
    if not chrome_profile_dir and (browser_agent or not no_browser_agent):
        try:
            from operate.utils.chrome_auth_manager import ensure_chrome_authentication
            
            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Initializing Chrome authentication...")
            
            # Check and setup Chrome authentication
            auth_success, managed_profile_path, auth_message = ensure_chrome_authentication()
            
            if auth_success:
                # Use the managed Chrome profile for browser tasks
                chrome_profile_dir = managed_profile_path
                print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Chrome profile ready: {chrome_profile_dir}")
            else:
                print(f"{ANSI_YELLOW}[Self-Operating Computer]{ANSI_RESET} Chrome authentication setup incomplete")
                print(f"{ANSI_YELLOW}[Self-Operating Computer]{ANSI_RESET} Browser tasks may require manual sign-in")
                # Continue without managed profile - browser tasks will use fresh sessions
                
        except ImportError:
            print(f"{ANSI_YELLOW}[Self-Operating Computer]{ANSI_RESET} Chrome authentication manager not available")
            print(f"{ANSI_YELLOW}[Self-Operating Computer]{ANSI_RESET} Browser tasks will use fresh Chrome sessions")
        except Exception as e:
            print(f"{ANSI_YELLOW}[Self-Operating Computer]{ANSI_RESET} Chrome authentication setup failed: {e}")
            print(f"{ANSI_YELLOW}[Self-Operating Computer]{ANSI_RESET} Continuing with fresh Chrome sessions")
    elif chrome_profile_dir:
        print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Using provided Chrome profile: {chrome_profile_dir}")

    if voice_mode:
        try:
            from whisper_mic import WhisperMic

            # Initialize WhisperMic if import is successful
            mic = WhisperMic()
        except ImportError:
            print(
                "Voice mode requires the 'whisper_mic' module. Please install it using 'pip install -r requirements-audio.txt'"
            )
            sys.exit(1)

    # Skip message dialog if prompt was given directly
    if not terminal_prompt:
        message_dialog(
            title="Self-Operating Computer",
            text="An experimental framework to enable multimodal models to operate computers",
            style=style,
        ).run()

    else:
        print("Running direct prompt...")

    # # Clear the console
    if platform.system() == "Windows":
        os.system("cls")
    else:
        print("\033c", end="")

    if terminal_prompt:  # Skip objective prompt if it was given as an argument
        objective = terminal_prompt
    elif voice_mode:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Listening for your command... (speak now)"
        )
        try:
            objective = mic.listen()
        except Exception as e:
            print(f"{ANSI_RED}Error in capturing voice input: {e}{ANSI_RESET}")
            return  # Exit if voice input fails
    else:
        print(
            f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model}{ANSI_RESET}]\n{USER_QUESTION}"
        )
        print(f"{ANSI_YELLOW}[User]{ANSI_RESET}")
        objective = prompt(style=style)

    # SEQUENTIAL TASK PROCESSING: Check for sequential tasks first
    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Checking for sequential tasks...")
    
    try:
        from operate.utils.task_classifier import TaskClassifier, TaskType
        print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Task classifier imported successfully")
        
        classifier = TaskClassifier()
        classification_result = classifier.classify_task(objective)
        print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Task classified as: {classification_result.task_type}")
    except Exception as e:
        print(f"{ANSI_RED}[Self-Operating Computer][Error] Task classification failed: {e}{ANSI_RESET}")
        # Fall back to original routing
        classification_result = None
    
    if classification_result and classification_result.task_type == TaskType.SEQUENTIAL:
        print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Sequential task detected with {len(classification_result.subtasks)} subtasks")
        
        # Execute subtasks in sequence
        for i, subtask in enumerate(classification_result.subtasks):
            print(f"\n{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Executing subtask {subtask.order}/{len(classification_result.subtasks)}: {subtask.description}")
            
            # Route each subtask appropriately
            if subtask.task_type == TaskType.BROWSER and BROWSER_AGENT_AVAILABLE and not no_browser_agent:
                print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Routing subtask to Browser Use Agent")
                try:
                    session_id = f"browser_subtask_{i}_{int(time.time())}"
                    result = asyncio.run(smart_task_router(subtask.description, model, session_id, chrome_profile_dir))
                    
                    if result and len(result) > 0:
                        final_action = result[-1]
                        if final_action.get('success', False):
                            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Subtask {subtask.order} completed successfully")
                        else:
                            print(f"{ANSI_RED}[Self-Operating Computer][Error] Subtask {subtask.order} failed{ANSI_RESET}")
                            return  # Exit on subtask failure
                    
                except Exception as e:
                    print(f"{ANSI_RED}[Self-Operating Computer][Error] Subtask {subtask.order} failed: {e}{ANSI_RESET}")
                    return
                    
            elif subtask.task_type == TaskType.DESKTOP or no_browser_agent:
                print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Routing subtask to OCR system")
                
                # Execute subtask with OCR system
                system_prompt = get_system_prompt(model, subtask.description)
                system_message = {"role": "system", "content": system_prompt}
                messages = [system_message]
                
                loop_count = 0
                subtask_session_id = None
                subtask_complete = False
                
                while not subtask_complete and loop_count < 10:
                    try:
                        operations, subtask_session_id = asyncio.run(
                            get_next_action(model, messages, subtask.description, subtask_session_id)
                        )
                        
                        subtask_complete = operate(operations, model)
                        loop_count += 1
                        
                    except Exception as e:
                        print(f"{ANSI_RED}[Self-Operating Computer][Error] Subtask {subtask.order} failed: {e}{ANSI_RESET}")
                        return
                
                if subtask_complete:
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Subtask {subtask.order} completed successfully")
                else:
                    print(f"{ANSI_RED}[Self-Operating Computer][Error] Subtask {subtask.order} exceeded maximum attempts{ANSI_RESET}")
                    return
        
        print(f"\n{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} All sequential subtasks completed successfully!")
        print(f"{ANSI_BLUE}Sequential Objective Complete: {ANSI_RESET}Executed {len(classification_result.subtasks)} subtasks\n")
        return
    
    # BROWSER USE INTEGRATION: Smart Task Routing (for non-sequential tasks)
    if BROWSER_AGENT_AVAILABLE and not no_browser_agent:
        try:
            # Check if this should be routed to Browser Use
            should_use_browser = False
            
            if browser_agent:
                # Force browser mode
                should_use_browser = True
                print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Forcing Browser Use Agent mode")
            else:
                # Smart detection
                should_use_browser = BrowserAgent.is_browser_task(objective, browser_threshold)
                if should_use_browser:
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Browser task detected - routing to Browser Use Agent")
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Browser Use will automatically launch browser and handle navigation")
                else:
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Desktop task detected - using OCR system")
            
            if should_use_browser:
                # Execute with Browser Use
                try:
                    session_id = f"browser_{int(time.time())}"
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Starting browser automation...")
                    
                    result = asyncio.run(smart_task_router(objective, model, session_id, chrome_profile_dir))
                    
                    # Display results
                    if result and len(result) > 0:
                        final_action = result[-1]
                        
                        # Check if fallback is required
                        if final_action.get('fallback_required', False):
                            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[Warning] Browser Use failed - this is likely due to API configuration{ANSI_RESET}")
                            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[Info] For browser tasks, please ensure API keys are configured for Browser Use{ANSI_RESET}")
                            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[Info] OCR fallback not recommended for browser tasks as it's less efficient{ANSI_RESET}")
                            return  # Exit instead of falling back to OCR for browser tasks
                        elif final_action.get('success', False) and final_action.get('action') != 'error':
                            print(f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model} + Browser Use{ANSI_RESET}]")
                            print(f"{ANSI_BLUE}Objective Complete: {ANSI_RESET}{final_action.get('description', 'Browser task completed successfully')}\n")
                            return  # Exit after successful browser task completion
                        else:
                            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Warning] Browser automation encountered issues{ANSI_RESET}")
                            print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[Info] For browser tasks, Browser Use is more efficient than OCR fallback{ANSI_RESET}")
                            return  # Exit instead of falling back for browser tasks
                    else:
                        print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BLUE}Browser task completed{ANSI_RESET}")
                        return  # Exit after browser task completion
                    
                except Exception as e:
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] Browser automation failed: {e}{ANSI_RESET}")
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[Info] Browser tasks are best handled by Browser Use agent{ANSI_RESET}")
                    print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[Info] Please check API configuration or use --no-browser-agent to force OCR{ANSI_RESET}")
                    return  # Exit instead of falling back for browser tasks
            
        except Exception as e:
            if verbose_mode:
                print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Warning] Browser routing failed: {e}{ANSI_RESET}")
            # Continue to OCR system
    
    elif no_browser_agent and verbose_mode:
        print(f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Browser Use disabled - using OCR system")
    
    # ORIGINAL OCR SYSTEM (fallback or desktop tasks)
    system_prompt = get_system_prompt(model, objective)
    system_message = {"role": "system", "content": system_prompt}
    messages = [system_message]

    loop_count = 0

    session_id = None

    while True:
        if config.verbose:
            print("[Self Operating Computer] loop_count", loop_count)
        try:
            operations, session_id = asyncio.run(
                get_next_action(model, messages, objective, session_id)
            )

            stop = operate(operations, model)
            if stop:
                break

            loop_count += 1
            if loop_count > 10:
                break
        except ModelNotRecognizedException as e:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] -> {e} {ANSI_RESET}"
            )
            break
        except Exception as e:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] -> {e} {ANSI_RESET}"
            )
            break


def operate(operations, model):
    if config.verbose:
        print("[Self Operating Computer][operate]")
    for operation in operations:
        if config.verbose:
            print("[Self Operating Computer][operate] operation", operation)
        # wait one second
        time.sleep(1)
        operate_type = operation.get("operation").lower()
        operate_thought = operation.get("thought")
        operate_detail = ""
        if config.verbose:
            print("[Self Operating Computer][operate] operate_type", operate_type)

        if operate_type == "press" or operate_type == "hotkey":
            keys = operation.get("keys")
            operate_detail = keys
            operating_system.press(keys)
        elif operate_type == "write":
            content = operation.get("content")
            operate_detail = content
            operating_system.write(content)
        elif operate_type == "click":
            x = operation.get("x")
            y = operation.get("y")
            click_detail = {"x": x, "y": y}
            operate_detail = click_detail

            operating_system.mouse(click_detail)
        elif operate_type == "done":
            summary = operation.get("summary")

            print(
                f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model}{ANSI_RESET}]"
            )
            print(f"{ANSI_BLUE}Objective Complete: {ANSI_RESET}{summary}\n")
            return True

        else:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] unknown operation response :({ANSI_RESET}"
            )
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] AI response {ANSI_RESET}{operation}"
            )
            return True

        print(
            f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model}{ANSI_RESET}]"
        )
        print(f"{operate_thought}")
        print(f"{ANSI_BLUE}Action: {ANSI_RESET}{operate_type} {operate_detail}\n")

    return False
