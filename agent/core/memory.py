from __future__ import annotations

"""Phase 1 note: No server-side memory.

The frontend is responsible for sending the last N (e.g., 5) conversation
turns in the request. We keep this module for Phase 2 expansion (e.g.,
persistent memory or user-specific stores), but it is intentionally unused
in Phase 1 to keep the API stateless.
"""

