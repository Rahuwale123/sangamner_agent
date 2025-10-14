from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from pydantic import BaseModel, Field

from agent.agent import build_agent, run_agent, to_lc_messages
from config.settings import get_settings


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("sangamner")

app = FastAPI(title="Sangamner AI Search Assistant", version="1.0.0")

# CORS: allow local frontend during development
settings = get_settings()
if settings.app_env.lower() in {"dev", "development", "local"}:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class ChatTurn(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    latitude: float = Field(..., description="User's latitude location")
    longitude: float = Field(..., description="User's longitude location")
    client_id: str = Field(..., description="Unique identifier for user/session")
    query: str = Field(..., description="User's latest message")
    conversation_history: Optional[List[ChatTurn]] = Field(
        default_factory=list,
        description="Last 5 turns including both user and assistant messages (frontend-managed)",
    )


@app.post("/agent/chat")
def chat(req: ChatRequest) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.google_api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing GOOGLE_API_KEY in environment or .env",
        )

    try:
        logger.info(
            "Config: model=%s key_set=%s",
            settings.gemini_model,
            bool(settings.google_api_key),
        )
        logger.info(
            "Incoming chat: client_id=%s lat=%.5f lon=%.5f history_turns=%s",
            req.client_id,
            req.latitude,
            req.longitude,
            len(req.conversation_history or []),
        )
        executor = build_agent()
        chat_history_messages = to_lc_messages(
            [t.model_dump() for t in (req.conversation_history or [])]
        )
        payload = {
            "input": req.query,
            "client_id": req.client_id,
            "latitude": req.latitude,
            "longitude": req.longitude,
        }
        if chat_history_messages:
            # Only include chat_history key if we actually have turns
            payload["chat_history"] = chat_history_messages
        logger.info(
            "Payload prepared: keys=%s query_len=%s",
            list(payload.keys()),
            len(req.query or ""),
        )
        agent_result = run_agent(executor, payload)
        output_text = (agent_result.get("output") or "").strip()
        search_payload = agent_result.get("search_payload")
        error_text = agent_result.get("error")

        if error_text:
            logger.warning("Agent execution reported error: %s", error_text)
            fallback = output_text or "I couldn't complete that search just now, but you can try again shortly."
            clean_error = " ".join(str(error_text).split())[:500]
            return {"ai_response": fallback, "error": clean_error}

        if search_payload and isinstance(search_payload.get("raw"), dict):
            response_body: Dict[str, Any] = dict(search_payload["raw"])
            response_body["ai_response"] = output_text
            total = None
            simplified = search_payload.get("simplified")
            if isinstance(simplified, dict):
                total = simplified.get("total")
            if total is None:
                total = response_body.get("total")
            logger.info(
                "Model responded with search data (total=%s) and %s chars",
                total,
                len(output_text),
            )
            return response_body

        logger.info("Model responded without search data: %s chars", len(output_text))
        return {"ai_response": output_text}
    except Exception as e:
        logger.exception("Chat processing failed: %s", e)
        # Still return the error detail to caller, but full traceback is in server logs
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
