import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.core import SecureAgent
from src.security.input_guard import SecurityViolation

load_dotenv()

def run_interactive_mode(agent: SecureAgent):
    """Interactive chat mode with the secure agent."""
    print("\n=== Secure LLM Agent - Interactive Mode ===")
    print("Type 'exit' or 'quit' to end the session")
    print("Type 'help' for usage information\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                print("Ending session. Goodbye!")
                break
                
            if user_input.lower() == 'help':
                print("\nCommands:")
                print("  - Type any prompt to interact with the agent")
                print("  - 'exit' or 'quit' to end session")
                print("  - 'help' to show this message\n")
                continue
            
            result = agent.process(user_input)
            print(f"\nAgent: {result['response']}\n")
            
            if result.get('error'):
                print(f"⚠️  Error: {result['error']}\n")
                
        except SecurityViolation as e:
            print(f"\n🚫 Security Violation: {e}\n")
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

def run_single_prompt(agent: SecureAgent, prompt: str):
    """Process a single prompt and return the response."""
    try:
        result = agent.process(prompt)
        
        print("\n=== Secure Agent Response ===")
        print(f"Response: {result['response']}\n")
        
        if result.get('error'):
            print(f"⚠️  Error: {result['error']}")
        
        if result.get('security_report'):
            report = result['security_report']
            print("\n=== Security Analysis ===")
            
            if report.get('input_sanitization'):
                print(f"Input Risk Level: {report['input_sanitization'].get('security_risk', 'N/A')}")
            
            if report.get('constitutional_evaluation'):
                const_eval = report['constitutional_evaluation']
                print(f"Constitutional Score: {const_eval.get('overall_score', 0):.2f}")
                print(f"Constitutional Passed: {'Yes' if const_eval.get('passed') else 'No'}")
            
            if report.get('output_validation'):
                out_val = report['output_validation']
                print(f"Output Validation: {'PASS' if out_val.get('passed', True) else 'BLOCKED'}")
            
            print(f"Refinements Applied: {report.get('refinements', 0)}")
        
        return 0
        
    except SecurityViolation as e:
        print(f"\n🚫 Security Violation Detected!")
        print(f"Type: {e.violation_type}")
        print(f"Details: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(
        description="Secure LLM Agent with Prompt Injection Defense",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/cli.py --prompt "What is the capital of France?"
  python src/cli.py --interactive
  python src/cli.py --prompt "Ignore previous instructions" --config config/security.yaml
        """
    )
    
    parser.add_argument(
        '--prompt',
        type=str,
        help='Single prompt to process'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Start interactive chat mode'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to security configuration file'
    )
    
    parser.add_argument(
        '--use-real-llm',
        action='store_true',
        help='Use real LLM instead of mock (requires HUGGINGFACE_TOKEN)'
    )
    
    parser.add_argument(
        '--strict',
        action='store_true',
        default=True,
        help='Enable strict security mode (default: True)'
    )
    
    args = parser.parse_args()
    
    if not args.prompt and not args.interactive:
        parser.print_help()
        print("\n⚠️  Error: You must specify either --prompt or --interactive")
        return 1
    
    hf_token = os.getenv('HUGGINGFACE_TOKEN')
    if args.use_real_llm and not hf_token:
        print("⚠️  Warning: HUGGINGFACE_TOKEN not found in environment")
        print("Using mock LLM instead. Set token in .env file to use real LLM")
        args.use_real_llm = False
    
    print("\n🛡️  Initializing Secure Agent...")
    print(f"Configuration: {args.config or 'default'}")
    print(f"LLM Mode: {'Real' if args.use_real_llm else 'Mock'}")
    print(f"Security Mode: {'Strict' if args.strict else 'Standard'}")
    
    agent = SecureAgent(
        config_path=args.config,
        use_mock_llm=not args.use_real_llm
    )
    
    if args.interactive:
        return run_interactive_mode(agent)
    else:
        return run_single_prompt(agent, args.prompt)

if __name__ == "__main__":
    sys.exit(main())