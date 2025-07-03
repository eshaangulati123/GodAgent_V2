"""
Self-Operating Computer
"""
import argparse
from operate.utils.style import ANSI_BRIGHT_MAGENTA
from operate.operate import main


def main_entry():
    parser = argparse.ArgumentParser(
        description="Run the self-operating-computer with a specified model."
    )
    parser.add_argument(
        "-m",
        "--model",
        help="Specify the model to use",
        required=False,
        default="gpt-4-with-ocr",
    )

    # Add a voice flag
    parser.add_argument(
        "--voice",
        help="Use voice input mode",
        action="store_true",
    )
    
    # Add a flag for verbose mode
    parser.add_argument(
        "--verbose",
        help="Run operate in verbose mode",
        action="store_true",
    )
    
    # Allow for direct input of prompt
    parser.add_argument(
        "--prompt",
        help="Directly input the objective prompt",
        type=str,
        required=False,
    )
    
    # Browser Use integration flags
    parser.add_argument(
        "--browser-agent",
        help="Force use Browser Use for all tasks",
        action="store_true",
    )
    
    parser.add_argument(
        "--no-browser-agent",
        help="Disable Browser Use, use OCR only",
        action="store_true",
    )
    
    parser.add_argument(
        "--browser-threshold",
        help="Set confidence threshold for browser detection (0.0-1.0)",
        type=float,
        default=0.6,
    )
    
    parser.add_argument(
        "--chrome-profile",
        help="Path to existing Chrome profile directory (e.g., 'C:/Users/Username/AppData/Local/Google/Chrome/User Data')",
        type=str,
        required=False,
    )

    try:
        args = parser.parse_args()
        main(
            args.model,
            terminal_prompt=args.prompt,
            voice_mode=args.voice,
            verbose_mode=args.verbose,
            browser_agent=args.browser_agent,
            no_browser_agent=args.no_browser_agent,
            browser_threshold=args.browser_threshold,
            chrome_profile_dir=args.chrome_profile
        )
    except KeyboardInterrupt:
        print(f"\n{ANSI_BRIGHT_MAGENTA}Exiting...")


if __name__ == "__main__":
    main_entry()
