# Verification Report: auth-401-redirect

- Date: 2026-07-04
- Verify Mode: light
- Build: frontend build passes (0 new TS errors)

## Summary

| Item | Status |
|------|--------|
| tasks.md all checked | PASS |
| Frontend build | PASS |
| `apiFetch` 401 → redirect | PASS |
| Streaming paths 401 handling | PASS |
| Login page keeps raw fetch | PASS |

## Files Changed

- `frontend/src/services/api.ts` — added `apiFetch()` + `handle401()`
- `frontend/src/features/ai-chat/services/chatApi.ts` — inline 401 check
- `frontend/src/features/ai-chat/services/agent.ts` — use `apiFetch`
- `frontend/src/features/ai-chat/hooks/useConversation.ts` — use `apiFetch`
- `frontend/src/hooks/useChat.ts` — inline 401 check
- `frontend/src/hooks/useStream.ts` — inline 401 check
