from __future__ import annotations

import json
from typing import Dict, List, Optional

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.core.prompt import SYSTEM_PROMPT
from agent.tools import build_nearby_search_tool
from config.settings import get_settings


def build_agent() -> AgentExecutor:
    settings = get_settings()
    if not settings.google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY not set. Please configure it in environment or .env"
        )

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=settings.temperature,
        top_p=settings.top_p,
    )

    tools = [build_nearby_search_tool()]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    f"{SYSTEM_PROMPT}\n\n"
                    "Available tools: {tools}\n"
                    "Tool names: {tool_names}\n"
                    "If none, answer directly."
                ),
            ),
            MessagesPlaceholder("chat_history", optional=True),
            (
                "human",
                (
                    "User Query: {input}\n"
                    "Client: {client_id}\n"
                    "Latitude: {latitude}  Longitude: {longitude}\n"
                    "Important: Keep answers local to Sangamner when relevant."
                ),
            ),
            ("ai", "{agent_scratchpad}"),
        ]
    )

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

    # Phase 2: no persistent server memory; frontend provides last 5 turns.
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )

    return executor


def to_lc_messages(history: List[dict]) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    for item in (history or [])[-5:]:
        role = (item.get("role") or "").lower()
        content = item.get("content") or ""
        if not content:
            continue
        if role in ("user", "human"):
            messages.append(HumanMessage(content=content))
        elif role in ("assistant", "ai", "bot"):
            messages.append(AIMessage(content=content))
        else:
            # Default unknown to HumanMessage for safety
            messages.append(HumanMessage(content=content))
    return messages


def _extract_search_payload(intermediate_steps: List) -> Optional[Dict]:
    for action, tool_output in intermediate_steps or []:
        if getattr(action, "tool", None) == "NearbySearchTool" and tool_output:
            try:
                return json.loads(tool_output)
            except json.JSONDecodeError:
                continue
    return None


def run_agent(executor: AgentExecutor, payload: Dict) -> Dict[str, Optional[Dict]]:
    try:
        result = executor.invoke(payload)
    except Exception as exc:
        return {"output": "", "search_payload": None, "error": str(exc)}

    return {
        "output": result.get("output", ""),
        "search_payload": _extract_search_payload(result.get("intermediate_steps")),
        "error": None,
    }
