#!/usr/bin/env python3
"""
Continuous Chat Interface for Agent

This script provides a command-line chat interface to interact with the Agent.
"""

import os
import requests
import json
import sys
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AgentChatClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def check_health(self) -> bool:
        """Check if the agent is running and healthy."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def send_message(self, prompt: str) -> Dict[str, Any]:
        """Send a message to the agent and return the response."""
        try:
            payload = {"prompt": prompt}
            response = self.session.post(
                f"{self.base_url}/invoke", json=payload, timeout=3000
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response: {str(e)}"}

    def format_response(self, response: Dict[str, Any]) -> str:
        """Format the agent's response for display."""
        if "error" in response:
            return f"❌ Error: {response['error']}"

        if "result" in response:
            result = response["result"]
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", "No text content found")
            elif isinstance(result, str):
                return result

        return "❓ Unexpected response format"

    def run_chat(self):
        """Run the continuous chat interface."""
        print("🤖 Agent Chat Interface")
        print("=" * 50)

        # Check if agent is running
        print("🔍 Checking agent health...")
        if not self.check_health():
            print("❌ Agent is not running or not healthy!")
            print("   Please start the agent with: python run_agent.py")
            sys.exit(1)

        print("✅ Agent is running and healthy!")
        print("\n💡 Tips:")
        print("   - Type your message and press Enter")
        print("   - Type 'quit', 'exit', or 'bye' to end the chat")
        print("   - Type 'help' for assistance")
        print("   - Press Ctrl+C to force quit")
        print("\n" + "=" * 50)

        try:
            while True:
                # Get user input
                try:
                    user_input = input("\n🧑 You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\n👋 Goodbye!")
                    break

                # Handle special commands
                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == "help":
                    self.show_help()
                    continue

                if not user_input:
                    print("💭 Please enter a message or type 'help' for assistance.")
                    continue

                # Send message to agent
                print("🤖 Agent: ", end="", flush=True)
                response = self.send_message(user_input)
                formatted_response = self.format_response(response)
                print(formatted_response)

        except KeyboardInterrupt:
            print("\n\n👋 Chat interrupted. Goodbye!")

    def show_help(self):
        """Show help information."""
        print("\n📚 Help - Available Commands:")
        print("   help     - Show this help message")
        print("   quit     - Exit the chat")
        print("   exit     - Exit the chat")
        print("   bye      - Exit the chat")
        print("\n💡 Example questions you can ask:")
        print("   - What are Docker best practices?")
        print("   - How do I design a microservices architecture?")
        print("   - Explain the difference between REST and GraphQL")
        print("   - What are the benefits of cloud computing?")
        print("   - How do I implement CI/CD pipelines?")


def main():
    """Main entry point."""
    import argparse

    # Get default URL from environment variables
    agent_port = os.getenv("AGENT_PORT", 8888)
    default_url = f"http://localhost:{agent_port}"

    parser = argparse.ArgumentParser(description="Continuous chat interface for Agent")
    parser.add_argument(
        "--url",
        default=default_url,
        help=f"Base URL of the agent (default: {default_url})",
    )

    args = parser.parse_args()

    client = AgentChatClient(args.url)
    client.run_chat()


if __name__ == "__main__":
    main()
