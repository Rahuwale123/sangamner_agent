from agent.tools.nearby_search import _normalize_tool_kwargs
s = '{"latitude":19.873792, "longitude":75.3270784, "client_id":"234", "query":"pharmacy"}\n'
kwargs = {'latitude': s}
print('input', kwargs)
from agent.tools.nearby_search import _nearby_search_tool
try:
    print(_normalize_tool_kwargs(kwargs))
except Exception as e:
    print('normalize error', e)
