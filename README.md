Sangamner AI Search Assistant - Phase 2

Overview
- Conversational AI for Sangamner built with FastAPI + LangChain + Gemini.
- Phase 2 adds a Nearby Search tool so the agent can fetch business data.
- Agent decides when to call `NearbySearchTool` and fuses results into natural replies.

Quick Start
- Prereqs: Python 3.10+
- Install deps: `pip install -r requirements.txt`
- Configure environment:
  - Copy `.env.example` to `.env`
  - Set `GOOGLE_API_KEY`, optional `GEMINI_MODEL`
  - Set `SEARCH_API_URL` if your data service is hosted elsewhere
- Run API: `uvicorn app.main:app --reload` (default `http://127.0.0.1:8000`)
- Health: `GET /health`

Request Example (frontend manages last 5 turns)
POST /agent/chat
{
  "latitude": 19.5678,
  "longitude": 74.2121,
  "client_id": "rahul_001",
  "query": "Can you tell me the best restaurants nearby?",
  "conversation_history": [
    {"role": "assistant", "content": "Hi there! How can I help you find something in Sangamner today?"},
    {"role": "user", "content": "i am rahul"},
    {"role": "assistant", "content": "Nice to meet you Rahul!"},
    {"role": "user", "content": "Looking for restaurants"}
  ]
}

Response Example (search triggered)
{
  "status": "success",
  "search_params": {
    "latitude": 19.5678,
    "longitude": 74.2121,
    "client_id": "rahul_001",
    "query": "Can you tell me the best restaurants nearby?"
  },
  "results": [
    {
      "entity_id": "3",
      "entity_type": "business",
      "score": 0.812,
      "distance_km": 1.2,
      "payload": {
        "type": "business",
        "business_id": "3",
        "business_name": "Sai Palace",
        "phone": "+91-9123456789",
        "description": "Popular family dining with veg and non-veg options.",
        "business_type": "Restaurant",
        "city": "Sangamner",
        "country": "India"
      }
    }
  ],
  "total": 1,
  "ai_response": "I found a nice option nearby called Sai Palace. It's popular with families and about 1.2 km away. Want more places like this?"
}

Response Example (no search triggered)
{
  "ai_response": "Hello Rahul! I'm here to help you explore Sangamner. Let me know what you're looking for."
}

Structure
- `app/main.py` - FastAPI app, request handling, response fusion
- `agent/agent.py` - Builds Gemini ReAct agent and parses tool output
- `agent/core/prompt.py` - System prompt with Phase 2 tool guidance
- `agent/tools/nearby_search.py` - LangChain StructuredTool wrapping Nearby search API
- `agent/core/memory.py` - Placeholder; history stays frontend-managed
- `config/settings.py` - Centralized configuration (API keys, endpoints)
- `.env.example` - Environment template (includes `SEARCH_API_URL`)
- `requirements.txt` - Python dependencies (LangChain, FastAPI, httpx)
- `frontend/` - Simple chat UI (updated after backend validation)

Notes
- Frontend must send the last 5 turns (user + assistant). Backend stays stateless.
- Agent calls `NearbySearchTool` only for business/service queries and receives raw JSON.
- Only business name, phone, and distance are surfaced in replies; raw payload returns to client alongside `ai_response`.
- Ensure the data service is reachable at `SEARCH_API_URL` (default `http://127.0.0.1:8000/data/search/nearby`).

Frontend
- Copy `frontend/config.example.js` to `frontend/config.js` and set `API_BASE_URL` and `CLIENT_ID` (defaults to `234`).
- Serve `frontend/index.html` (e.g., `cd frontend && python -m http.server 5173`).
- The chat stream shows `ai_response` messages, and when search results are returned, they render as Sangamner business cards (name, phone, distance, description).
