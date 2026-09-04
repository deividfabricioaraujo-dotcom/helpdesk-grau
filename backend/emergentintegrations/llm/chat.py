"""
LLM integration using LiteLLM for flexible provider support.
"""
import pathlib
import litellm
import base64
import json
import logging
import os
from dataclasses import dataclass
from litellm import ModelResponse
from typing import Callable, Dict, Any, List, Optional, Union
from emergentintegrations.llm.utils import get_app_identifier, get_integration_proxy_url

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A tool the model wants the customer to execute and report back on.

    `arguments` is the JSON-decoded dict (or {} on parse failure).
    `raw_arguments` is the original JSON string from the model — preserved so
    the assistant message can be round-tripped into history with byte-for-byte
    fidelity (providers reject any drift).
    """
    id: str
    name: str
    arguments: Dict[str, Any]
    raw_arguments: str


@dataclass
class Usage:
    """Token counts for cost / observability."""
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class ChatResponse:
    """Return type of LlmChat.send_message_with_tools().

    `content` is the assistant text (may be None on pure tool-call turns).
    `tool_calls` is None when the model did not call any custom function;
        for provider-hosted tools (web_search, googleSearch, etc.) the result
        is on `raw`, not here.
    `raw` is the full LiteLLM ModelResponse — escape hatch for provider-specific
        fields (citations, grounding_metadata, etc.).
    """
    content: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    finish_reason: str
    usage: Usage
    raw: Any  # litellm.ModelResponse; using Any to avoid import-time complications


@dataclass
class TextDelta:
    """A piece of assistant text. Append to your UI as it arrives."""
    content: str


@dataclass
class ToolCallStart:
    """Fired once when the model begins emitting a tool call.
    `arguments` is NOT available yet — wait for ToolCallReady."""
    id: str
    name: str
    index: int


@dataclass
class ToolCallReady:
    """Fired when a tool call's argument JSON is fully assembled.
    `tool_call.arguments` is now a parsed dict."""
    tool_call: ToolCall


@dataclass
class StreamDone:
    """Fired exactly once at the end of the stream. Contains the final state —
    equivalent to what send_message_with_tools() would have returned non-streamingly.
    `content` may be None on a pure tool-call turn."""
    content: Optional[str]
    tool_calls: Optional[List[ToolCall]]
    finish_reason: str
    usage: Usage
    raw: Any


ChatStreamEvent = Union[TextDelta, ToolCallStart, ToolCallReady, StreamDone]


class FileContent:
    def __init__(self, content_type: str, file_content_base64: str) -> None:
        self.content_type = content_type
        self.file_content_base64 = file_content_base64
    
class ImageContent(FileContent):
    def __init__(self, image_base64: str) -> None:
        super().__init__("image", image_base64)

    @staticmethod
    def get_mime_type(file_content_base64) -> str:
        if file_content_base64.startswith('iVBORw0KGgo'):
            return 'image/png'
        elif file_content_base64.startswith('/9j/'):
            return 'image/jpeg'
        elif file_content_base64.startswith('R0lGOD'):
            return 'image/gif'
        elif file_content_base64.startswith('UklGR'):
            return 'image/webp'
        return 'image/png'  # Default to PNG for backwards compatibility
        
class FileContentWithMimeType(FileContent):
    def __init__(self, mime_type: str, file_path: str) -> None:
        file_bytes = pathlib.Path(file_path).read_bytes()
        file_content_base64 = base64.b64encode(file_bytes).decode('utf-8')
        super().__init__(mime_type, file_content_base64)

class UserMessage:
    def __init__(self, text: str = None, file_contents: list[FileContent] = None) -> None:
        self.text = text
        self.file_contents = file_contents or []  # Initialize as empty list if None

class LlmChat:
    """
    LLM integration using LiteLLM for generating chat completions.
    This class provides compatibility with OpenAI's API while supporting
    multiple LLM providers through LiteLLM.
    """

    def __init__(self, api_key: str, session_id: str, system_message: str, initial_messages: List[Dict[str, Any]] = None, custom_headers: Dict[str, str] = None):
        self.api_key = api_key    
        self.model = "gpt-4o" 
        self.messages = initial_messages or [{"role": "system", "content": system_message}]
        self.session_id = session_id
        self.provider = "openai"
        self.extra_params = {}
        self.custom_headers = custom_headers or {}
        self.tools: Optional[List[Dict[str, Any]]] = None
        self.tool_choice: Optional[Union[str, Dict[str, Any]]] = None

        app_url = get_app_identifier()
        if app_url:
            self.custom_headers['X-App-ID'] = app_url

    def with_model(self, provider: str, model: str) -> "LlmChat":
        self.provider = provider
        self.model = model
        return self

    def with_params(self, **params) -> "LlmChat":
        self.extra_params.update(params)
        return self

    def with_tools(
        self,
        tools: List[Dict[str, Any]],
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> "LlmChat":
        """Configure tools for subsequent send_message_with_tools() calls.

        Pass-through to LiteLLM; accepts both OpenAI custom function shape
        ({"type": "function", "function": {...}}) and provider-hosted tool dicts
        (e.g. {"type": "web_search_20250305", "name": "web_search"} for Anthropic,
        {"googleSearch": {}} for Gemini).

        `tool_choice` defaults to None and is only forwarded to LiteLLM when set.
        Pass "auto", "required", "none", or a forced-call dict per the provider.

        Raises ChatError if tools is None, empty, not a list, or contains an
        entry whose shape isn't a recognised tool definition. To clear tools
        from a session, create a fresh LlmChat instance.
        """
        self._validate_tools(tools)
        self.tools = tools
        self.tool_choice = tool_choice
        return self

    @staticmethod
    def _validate_tools(tools: Any) -> None:
        """Validate the shape of the tools list passed to with_tools().

        Accepts:
          - custom functions:        {"type": "function", "function": {"name": ...}}
          - provider-hosted (typed): {"type": "web_search_20250305", "name": ...}
          - provider-hosted (Gemini):{"googleSearch": {}}  (non-empty dict, no "type")

        Rejects None / non-list / empty list, and any entry that isn't a
        non-empty dict. A "function"-typed entry must carry a "function" dict
        with a non-empty "name" — otherwise it fails opaquely inside the
        provider instead of here.
        """
        if not isinstance(tools, list) or len(tools) == 0:
            raise ChatError("with_tools requires a non-empty list of tool definitions")
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict) or len(tool) == 0:
                raise ChatError(
                    f"with_tools: tool at index {i} must be a non-empty dict"
                )
            if tool.get("type") == "function":
                fn = tool.get("function")
                if not isinstance(fn, dict) or not fn.get("name"):
                    raise ChatError(
                        f"with_tools: function tool at index {i} must have a "
                        "'function' dict with a 'name'"
                    )

    def add_tool_result(self, tool_call_id: str, content: str) -> "LlmChat":
        """Append a tool-result message to history for the next send_message_with_tools() call.

        `tool_call_id` must match an ID emitted in the most recent assistant message's
        tool_calls. `content` is an arbitrary string — JSON-encode structured results
        yourself (json.dumps(...)).

        For parallel tool calls, call this once per result.

        Raises ChatError if no recent assistant message has tool_calls containing the
        given ID. Catches the common typo where customers hand-copy IDs.
        """
        valid_ids = self._last_assistant_tool_call_ids()
        if tool_call_id not in valid_ids:
            raise ChatError(
                f"tool_call_id '{tool_call_id}' does not match any pending tool call"
            )
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })
        return self

    def _last_assistant_tool_call_ids(self) -> set:
        """Return the set of tool_call IDs from the most recent assistant message
        (empty set if no assistant message or no tool_calls)."""
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant":
                tcs = msg.get("tool_calls") or []
                return {tc["id"] for tc in tcs if "id" in tc}
        return set()

    async def send_message_with_tools(
        self,
        user_message: Optional["UserMessage"] = None,
    ) -> ChatResponse:
        """Tool-aware variant of send_message().

        Returns a ChatResponse exposing content, tool_calls, finish_reason, usage,
        and the raw LiteLLM ModelResponse.

        `user_message` may be None on continuation turns AFTER add_tool_result()
        has appended a tool-result message. Raises ChatError if called with no
        user message and no pending tool result.

        Auto-appends the assistant response (including any tool_calls block) to
        self.messages. Customer drives the loop:
            while response.tool_calls:
                for tc in response.tool_calls:
                    result = my_tool(**tc.arguments)
                    chat.add_tool_result(tc.id, json.dumps(result))
                response = await chat.send_message_with_tools()
        """
        messages = await self.get_messages()
        if user_message is not None:
            await self._add_user_message(messages, user_message)
        elif not messages or messages[-1].get("role") != "tool":
            raise ChatError(
                "send_message_with_tools called without a user message "
                "and no pending tool results"
            )

        params = self._build_completion_params(messages, include_tools=True)
        try:
            raw = await litellm.acompletion(**params)
        except Exception as e:
            raise ChatError(f"Failed to generate chat completion: {str(e)}") from e
        response = self._parse_tool_response(raw)
        messages.append(
            self._assistant_history_message(response.content, response.tool_calls)
        )
        return response

    async def stream_message(
        self,
        user_message: Optional["UserMessage"] = None,
    ):
        """Stream the assistant response. Yields TextDelta as tokens arrive;
        ToolCallStart / ToolCallReady if tools are configured and the model
        chooses to call any; StreamDone exactly once at the end.

        `user_message=None` is allowed on continuation turns AFTER add_tool_result()
        has appended a tool-result message. Raises ChatError if called with no
        user message and no pending tool result.

        Auto-appends the assistant response to self.messages on StreamDone. If
        the consumer abandons the async iterator before StreamDone fires
        (raise, break, GC), the assistant message is NOT appended.
        """
        messages = await self.get_messages()
        if user_message is not None:
            await self._add_user_message(messages, user_message)
        elif not messages or messages[-1].get("role") != "tool":
            raise ChatError(
                "stream_message called without a user message "
                "and no pending tool results"
            )

        params = self._build_completion_params(messages, include_tools=True)
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}

        try:
            stream = await litellm.acompletion(**params)
        except Exception as e:
            raise ChatError(f"Failed to start streaming completion: {str(e)}") from e

        text_buf: List[str] = []
        tool_state: Dict[int, Dict[str, Any]] = {}
        started: set = set()
        finish_reason: str = "stop"
        usage: Optional[Usage] = None
        last_chunk: Any = None

        try:
            async for chunk in stream:
                last_chunk = chunk

                if getattr(chunk, "usage", None):
                    usage = self._extract_usage(chunk)

                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta
                if delta is None:
                    continue

                if delta.content:
                    text_buf.append(delta.content)
                    yield TextDelta(content=delta.content)

                if delta.tool_calls:
                    for tcd in delta.tool_calls:
                        idx = tcd.index
                        st = tool_state.setdefault(
                            idx, {"id": None, "name": None, "args": []}
                        )
                        if tcd.id:
                            st["id"] = tcd.id
                        if tcd.function and tcd.function.name:
                            st["name"] = tcd.function.name
                        if tcd.function and tcd.function.arguments:
                            st["args"].append(tcd.function.arguments)
                        if idx not in started and st["id"] and st["name"]:
                            started.add(idx)
                            yield ToolCallStart(id=st["id"], name=st["name"], index=idx)
        except Exception as e:
            raise ChatError(f"Error during streaming: {str(e)}") from e

        # Stream exhausted — assemble final tool_calls
        final_tcs: List[ToolCall] = []
        for idx in sorted(tool_state):
            st = tool_state[idx]
            if not (st["id"] and st["name"]):
                continue
            raw_args = "".join(st["args"]) or "{}"
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                logger.warning(
                    "Tool call %s had unparseable arguments: %r", st["id"], raw_args
                )
                parsed = {}
            tc = ToolCall(
                id=st["id"], name=st["name"],
                arguments=parsed, raw_arguments=raw_args,
            )
            final_tcs.append(tc)
            yield ToolCallReady(tool_call=tc)

        full_text = "".join(text_buf) or None
        self.messages.append(
            self._assistant_history_message(full_text, final_tcs or None)
        )

        yield StreamDone(
            content=full_text,
            tool_calls=final_tcs or None,
            finish_reason=finish_reason,
            usage=usage or Usage(0, 0, 0),
            raw=last_chunk,
        )

    def _build_completion_params(
        self,
        messages: List[Dict[str, Any]],
        include_tools: bool = False,
    ) -> Dict[str, Any]:
        """Build the kwargs for a litellm completion call, including the proxy
        plumbing for emergent keys and extra params.

        Single source of truth for the request shape. Tools are opt-in:
        the tool-aware / streaming paths pass include_tools=True; the legacy
        send_message paths use the default (False), which never attached tools
        even when with_tools() was configured."""
        params: Dict[str, Any] = {
            "model": f"{self.provider}/{self.model}",
            "messages": messages,
            "api_key": self.api_key,
        }
        if self._is_emergent_key(self.api_key):
            proxy_url = get_integration_proxy_url()
            params["api_base"] = proxy_url + "/llm"
            params["custom_llm_provider"] = "openai"
            params["model"] = (
                f"gemini/{self.model}" if self.provider == "gemini" else self.model
            )
            if self.custom_headers:
                params["extra_headers"] = self.custom_headers
        if include_tools and self.tools:
            params["tools"] = self.tools
            if self.tool_choice is not None:
                params["tool_choice"] = self.tool_choice
        params.update(self.extra_params)
        return params

    def _parse_tool_response(self, raw: Any) -> ChatResponse:
        """Pure transform: convert a LiteLLM ModelResponse into a ChatResponse.

        No side effects — recording the assistant turn to history is the
        caller's responsibility (see _assistant_history_message)."""
        choice = raw.choices[0]
        message = choice.message
        content = getattr(message, "content", None)
        finish_reason = getattr(choice, "finish_reason", "stop")
        raw_tool_calls = getattr(message, "tool_calls", None) or None

        parsed_tool_calls = (
            [self._parse_tool_call(tc) for tc in raw_tool_calls]
            if raw_tool_calls else None
        )

        usage = self._extract_usage(raw)
        return ChatResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            raw=raw,
        )

    @staticmethod
    def _assistant_history_message(
        content: Optional[str],
        tool_calls: Optional[List["ToolCall"]],
    ) -> Dict[str, Any]:
        """Build the assistant message dict to append to history.

        Single source of truth for the recorded shape, shared by the tool-aware
        (send_message_with_tools) and streaming (stream_message) paths. Uses each
        tool call's raw_arguments verbatim — providers reject any drift."""
        message: Dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": tc.raw_arguments}}
                for tc in tool_calls
            ]
        return message

    def _parse_tool_call(self, tc: Any) -> ToolCall:
        """Convert a single LiteLLM tool_call object into our ToolCall dataclass.
        Defensively parses the arguments JSON — on parse failure, returns {} and
        logs a warning, preserving raw_arguments for inspection."""
        raw_args = tc.function.arguments
        try:
            parsed = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            logger.warning(
                "Tool call %s had unparseable arguments: %r", tc.id, raw_args
            )
            parsed = {}
        return ToolCall(
            id=tc.id,
            name=tc.function.name,
            arguments=parsed,
            raw_arguments=raw_args,
        )

    def _extract_usage(self, raw: Any) -> Usage:
        """Read token counts from a LiteLLM ModelResponse. Handles both
        OpenAI-style (prompt_tokens/completion_tokens) and Anthropic-style
        (input_tokens/output_tokens) naming."""
        u = getattr(raw, "usage", None)
        if u is None:
            return Usage(0, 0, 0)
        input_tokens = getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", 0) or 0
        output_tokens = getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", 0) or 0
        total = getattr(u, "total_tokens", input_tokens + output_tokens)
        return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total)
    
    async def _add_assistant_message(self, messages: List[Dict[str, Any]], message: str):
        messages.append({"role": "assistant", "content": message})
        await self._save_messages(messages)
    
    async def _add_user_message(self, messages, message: UserMessage):
        # Check if file contents are being used with non-Gemini provider
        if message.file_contents and any(isinstance(content, FileContentWithMimeType) for content in message.file_contents):
            if self.provider != "gemini":
                raise ChatError("File attachments are only supported with Gemini provider")
        
        if message.text:
            messages.append({"role": "user", "content": [{"type": "text", "text": message.text}]})
        for content in message.file_contents:
            if content.content_type == "image":
                mime_type = ImageContent.get_mime_type(content.file_content_base64)
                messages.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{content.file_content_base64}"}}]})
            else:
                messages.append({"role": "user", "content": [{"type": "file", "file": { "file_data": "data:{};base64,{}".format(content.content_type, content.file_content_base64) }}]})
        await self._save_messages(messages)
        
    async def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages
    
    async def _save_messages(self, messages):
        self.messages = messages

    async def _execute_completion(self, messages: List[Dict[str, Any]]) -> ModelResponse:
        """Execute the (non-tool) completion request and return the raw response.

        Shares the request-shape construction with the tool-aware paths via
        _build_completion_params. Uses the default include_tools=False, preserving
        this path's historical behaviour of never attaching tools."""
        params = self._build_completion_params(messages)
        return await litellm.acompletion(**params)

    async def send_message(self, user_message: UserMessage) -> str:
        messages = await self.get_messages()
        await self._add_user_message(messages, user_message)
        try:
            response = await self._execute_completion(messages)
            response_text = await self._extract_response_text(response)
            await self._add_assistant_message(messages, response_text)  # Pass both messages and response_text
            return response_text
        except Exception as e:
            raise ChatError(f"Failed to generate chat completion: {str(e)}")
        

    async def _extract_response_text(self, response: ModelResponse) -> str:
        """
        Extract the text or content from a chat completion response.
        Handles various response formats including text and images.

        Args:
            response (Dict[str, Any]): The response from a chat completion request.

        Returns:
            str: The extracted content, which could be text or a structured representation
                 of images/multimodal content.
        """
        try:
            if len(response.choices) > 0 and response.choices[0].message:
                return response.choices[0].message.content
            raise ChatError(f"Failed to extract response text")
        except Exception as e:
            raise ChatError(f"Failed to extract response text: {str(e)}")

    def _is_emergent_key(self, api_key):
        return api_key.startswith("sk-emergent-")
    
    async def send_message_multimodal_response(self, user_message: UserMessage) -> tuple[str, List[Dict[str, str]]]:
        """
        Send a message and extract both text and images from the response.
        
        Returns:
            Tuple of (text, images) where images is a list of dicts with 'mime_type' and 'data' keys.
        """
        messages = await self.get_messages()
        await self._add_user_message(messages, user_message)
        try:
            response = await self._execute_completion(messages)
            
            # Extract multimodal content
            text = None
            images = []

            if len(response.choices) > 0 and response.choices[0].message:
                message = response.choices[0].message

                # Extract images from separate field (Gemini's LiteLLM format)
                if hasattr(message, 'images') and message.images:
                    for img_data in message.images:
                        if 'image_url' in img_data and 'url' in img_data['image_url']:
                            url = img_data['image_url']['url']
                            # Parse data URL: data:image/png;base64,<base64data>
                            if 'data:' in url and ';base64,' in url:
                                parts = url.split(';base64,', 1)
                                mime_type = parts[0].replace('data:', '')
                                base64_data = parts[1]
                                images.append({"mime_type": mime_type, "data": base64_data})

                # Extract text from content if present
                if message.content:
                    text = message.content
            
            # Save assistant message if text was returned
            if text:
                await self._add_assistant_message(messages, text)
            
            return text, images
            
        except Exception as e:
            raise ChatError(f"Failed to generate multimodal completion: {str(e)}")

class ChatError(Exception):
    """Exception raised for errors in the LLM chat integration."""
    pass
