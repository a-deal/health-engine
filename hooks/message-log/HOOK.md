---
name: message-log
description: "Log all inbound and outbound messages to kasane.db for transcript auditing"
metadata:
  {
    "openclaw":
      {
        "events": ["message:received", "message:sent"],
      },
  }
---

# Message Log Hook

Writes every inbound user message and outbound Milo reply to the
`conversation_message` table in kasane.db. This gives us a queryable
transcript index without scanning JSONL session files.
