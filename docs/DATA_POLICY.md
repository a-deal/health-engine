# Data Policy and Security

How Kiso handles user data, access control, and privacy. This is a living document that grows with the product.

## Principles

1. **User data is siloed.** One user cannot see another user's data. Period.
2. **Health data stays minimal.** Collect what's needed for coaching. Nothing else.
3. **Encryption at rest for secrets.** OAuth tokens, API keys, anything sensitive.
4. **Audit everything.** Every API call logged with user ID, endpoint, timestamp.
5. **Soft delete by default.** Data is recoverable. Hard delete available on request.

## Data Architecture

### Two Storage Systems

**SQLite** (`data/kasane.db`): Relational entities that sync between Kasane (iOS) and Milo (agent).
- Person profiles, habits, check-ins, focus plans, coaching messages
- Per-person isolation enforced at the API layer
- All mutations logged to audit trail

**CSVs** (`data/users/<user_id>/`): Health tracking data per user.
- Weight, meals, labs, blood pressure, supplements, wearable snapshots
- Each user has their own directory. No cross-directory access.
- Written by Milo's MCP tools, read by the context endpoint.

### The Bridge

`person.healthEngineUserId` links a Kasane person record (SQLite) to a health data directory (CSVs). The context endpoint merges both into a single read.

## Access Control

### Current State (Phase 0, 0-2 users)

Single shared API token in `gateway.yaml`. All authenticated requests can access all data.

**Known limitation**: No per-person authorization. Being addressed in Phase 0 (see Roadmap below).

### Phase 0 Improvements (Before External Users)

1. **Per-user API tokens**: Each user/device gets a unique token mapped to their person IDs. Token A can only access person records it owns.
2. **Token rotation**: Admin can rotate tokens without downtime.
3. **v1 audit logging**: All sync and CRUD calls logged with user ID, endpoint, result.

### Phase 1 (5-10 users)

1. **JWT auth**: Replace static tokens with JWTs. HMAC-SHA256, 1hr access + 7d refresh.
2. **Per-user claims**: JWT contains `personId` and `userId`. API validates ownership on every request.
3. **Supabase RLS**: Row-level security at the database level. Even if the API has a bug, the database enforces isolation.

## Encryption

### At Rest

| Data | Encrypted? | Method |
|------|-----------|--------|
| OAuth tokens (Garmin, Oura, etc.) | Yes | Fernet (AES-128-CBC + HMAC) |
| API token | No (config file, 0600 perms) | File permissions only |
| SQLite database | No | Disk-level encryption (macOS FileVault) |
| CSV health data | No | Disk-level encryption (macOS FileVault) |

### In Transit

All external traffic goes through Cloudflare Tunnel (TLS 1.3). Internal traffic on Mac Mini is localhost only.

### Key Management

- Encryption key stored at `~/.config/health-engine/token.key` (0600 permissions)
- Can be overridden via `HE_TOKEN_KEY` environment variable
- Auto-generated if missing. Not derived from any other secret.

## Audit Trail

### What's Logged

| Event | Location | Fields |
|-------|----------|--------|
| MCP tool calls | `data/admin/api_audit.jsonl` | timestamp, tool, user_id, params (token stripped), status, latency_ms |
| v1 API calls | Planned (not yet implemented) | Same format |
| Auth attempts | Server logs | IP, user, success/failure |

### What's Not Logged

- Full request/response bodies (too large, may contain PHI)
- Wearable OAuth tokens (sensitive)
- Password entries (Garmin auth)

## Data Retention

### Soft Delete

All entities use `deletedAt` timestamp. Soft-deleted records:
- Excluded from GET endpoints
- Included in sync responses (so clients know to delete locally)
- Remain in database until hard-deleted

### Hard Delete

Not yet implemented. Planned:
- `POST /api/v1/persons/:id/purge` for full person data erasure
- CLI: `python3 cli.py purge-person <id>`
- Cascade: deletes person + all habits, check-ins, messages, focus plans, CSV directory
- Irreversible. Requires admin token.

### Retention Policy (Planned)

- Soft-deleted records: hard-deleted after 90 days
- Audit logs: retained indefinitely (no PHI in logs)
- CSV health data: retained until user requests deletion
- Wearable tokens: revoked and deleted when user disconnects

## PHI Considerations

Kiso handles health data that may qualify as Protected Health Information (PHI) under HIPAA:
- Lab results, medications, conditions, family history
- Wearable metrics (HRV, sleep, activity)
- Weight, blood pressure, nutrition logs

### Current Posture (Pre-Product)

We are not a covered entity or business associate under HIPAA. We don't bill insurance, don't have clinical relationships, and don't process claims.

We handle health data responsibly anyway:
- Data stays on Andrew's Mac Mini (no third-party cloud until Supabase migration)
- No data shared with third parties
- No data used for advertising
- Users can request full data export or deletion

### When HIPAA Matters

If we add:
- Clinical partnerships (doctors referring patients)
- Insurance billing
- EHR integration

Then we need BAAs, HIPAA-compliant hosting, and formal security controls. Not there yet. Supabase (Phase 1) is HIPAA-eligible with their Pro plan.

## Milo-Specific Data Rules

Milo (the coaching agent) has access to all of a user's data through Kiso's MCP tools. Rules:

1. **Never share one user's data with another.** Multi-user routing via `user_id` parameter. Each WhatsApp number maps to exactly one user.
2. **Never persist conversation content beyond the session.** Milo's chat history is ephemeral (OpenClaw session). Session resets clear it.
3. **Always call `checkin()` for current data.** Never rely on cached values from earlier in the conversation.
4. **Meal totals come from CSVs, not memory.** Session resets lose context. The CSV is the source of truth.

## Security Roadmap

| Phase | When | What |
|-------|------|------|
| 0 (now) | This week | Per-user tokens, v1 audit logging, token rotation from workspace files |
| 0.5 | Next 2 weeks | JWT auth, rate limiting on all auth endpoints, input validation tightening |
| 1 (5-10 users) | When CloudKit disabled | Supabase RLS, realtime subscriptions, background job queue |
| 2 (50+ users) | When paying users | Penetration test, formal data policy, GDPR compliance, Litestream backups verified |

## iOS Integration Notes

When building SyncService.swift:
- Store the API token in iOS Keychain, not UserDefaults or config files
- Use `URLSession` with certificate pinning to the Cloudflare Tunnel domain
- Track `lastSyncAt` in Keychain or CoreData (survives app reinstall)
- Handle 403 gracefully (token rotation, re-auth flow)
- Never log API tokens or full health data to console in production builds
