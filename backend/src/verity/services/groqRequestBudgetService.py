import json
import logging
import time
from functools import lru_cache
from threading import Lock

import tiktoken


budgetLogger = logging.getLogger(__name__)

requestTokenBudget = 7_000
completionTokenBudget = 4_096
requestSafetyTokens = 512
requestIntervalSeconds = 65.0


@lru_cache(maxsize=1)
def getTokenEncoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("o200k_harmony")


def estimateGroqRequestTokens(
    sourceText: str,
    systemPrompt: str,
    outputSchema: dict[str, object],
    schemaName: str = "incidentExtraction",
) -> int:
    requestContent = {
        "messages": [
            {
                "role": "system",
                "content": systemPrompt,
            },
            {
                "role": "user",
                "content": sourceText,
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schemaName,
                "strict": True,
                "schema": outputSchema,
            },
        },
    }

    serializedContent = json.dumps(
        requestContent,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    inputTokens = len(
        getTokenEncoding().encode_ordinary(
            serializedContent
        )
    )

    return (
        inputTokens
        + completionTokenBudget
        + requestSafetyTokens
    )


class GroqRequestGate:
    def __init__(self) -> None:
        self.requestLock = Lock()
        self.nextRequestAt = 0.0

    def waitForSlot(self) -> None:
        with self.requestLock:
            waitSeconds = max(
                0.0,
                self.nextRequestAt - time.monotonic(),
            )

            if waitSeconds > 0:
                budgetLogger.info(
                    "Waiting %.1f seconds before the next "
                    "Groq request.",
                    waitSeconds,
                )

            while True:
                remainingSeconds = (
                    self.nextRequestAt - time.monotonic()
                )

                if remainingSeconds <= 0:
                    break

                time.sleep(min(remainingSeconds, 1.0))

            self.nextRequestAt = (
                time.monotonic() + requestIntervalSeconds
            )


groqRequestGate = GroqRequestGate()