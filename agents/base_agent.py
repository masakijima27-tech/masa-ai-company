import anthropic
from config.settings import ANTHROPIC_API_KEY, MODEL


class BaseAgent:
    def __init__(self, name: str, role: str, system_prompt: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.conversation_history: list[dict] = []

    def run(self, user_message: str, tools: list | None = None) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})

        kwargs = {
            "model": MODEL,
            "max_tokens": 4096,
            "system": self.system_prompt,
            "messages": self.conversation_history,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        # Handle tool use loop
        while response.stop_reason == "tool_use" and tools:
            tool_results = self._handle_tool_use(response, tools)
            self.conversation_history.append({"role": "assistant", "content": response.content})
            self.conversation_history.append({"role": "user", "content": tool_results})
            response = self.client.messages.create(**kwargs)

        reply = self._extract_text(response)
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply

    def _extract_text(self, response) -> str:
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _handle_tool_use(self, response, tools: list) -> list:
        """Override in subclasses to handle specific tool calls."""
        results = []
        for block in response.content:
            if block.type == "tool_use":
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Tool execution not implemented.",
                })
        return results

    def reset(self):
        self.conversation_history = []
