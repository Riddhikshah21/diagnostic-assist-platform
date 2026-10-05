"""HTTP client for the local Ollama service."""

from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError


class OllamaError(RuntimeError):
    """The local model could not return a usable response."""


class _GenerateResponse(BaseModel):
    response: str = Field(min_length=1)
    done: bool
    done_reason: str | None = None


class OllamaClient:
    def __init__(
        self,
        model: str = "llama3.1:latest",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not model.strip():
            raise ValueError("Model name must not be empty.")
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive.")

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        schema: dict[str, Any] | None = None,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
                "num_predict": 768,
            },
        }
        if schema is not None:
            payload["format"] = schema

        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
                trust_env=False,
            ) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise OllamaError("The local model timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaError("Could not connect to local Ollama.") from exc

        try:
            result = _GenerateResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise OllamaError("Ollama returned an invalid response.") from exc

        if not result.done:
            raise OllamaError("Ollama did not finish the response.")

        if result.done_reason != "stop":
            raise OllamaError(
                f"The model response was incomplete: "
                f"done_reason={result.done_reason!r}."
            )
        text = result.response.strip()
        if not text:
            raise OllamaError("The model returned an empty response.")

        return text