from functools import lru_cache

from django.conf import settings
from google import genai
from google.genai import types


@lru_cache(maxsize=1)
def get_gemini_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _to_gemini_contents(messages):
    """Converts OpenAI-style [{role, content}] messages into Gemini's
    (system_instruction, contents) shape. role="system" (only the first one
    is used) becomes the system instruction; "assistant" maps to "model"."""
    system_instruction = None
    contents = []
    for m in messages:
        if m["role"] == "system":
            if system_instruction is None:
                system_instruction = m["content"]
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    return system_instruction, contents


def complete(messages, model, temperature=0.2, max_tokens=1024):
    """Non-streaming chat completion. Returns the assistant's text content."""
    client = get_gemini_client()
    system_instruction, contents = _to_gemini_contents(messages)
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text or ""


def stream_complete(messages, model, temperature=0.4, max_tokens=1536):
    """Streaming chat completion. Yields text deltas as they arrive."""
    client = get_gemini_client()
    system_instruction, contents = _to_gemini_contents(messages)
    stream = client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text
