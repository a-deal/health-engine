/**
 * Message log hook: writes inbound/outbound messages to kasane.db
 * via the health engine API running on localhost.
 *
 * Events: message:received, message:sent
 */

const API_BASE = "http://localhost:18800/api/ingest_message";
const API_TOKEN = "NZCT4pzvxC36OSaCztUYjq2_LAkqdC5_LmTFysa9VAY";

async function postMessage(payload) {
  const url = `${API_BASE}?token=${API_TOKEN}`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
      console.error(`[message-log] API error ${res.status}: ${await res.text()}`);
    }
  } catch (err) {
    // Fire and forget. Don't let logging failures break message flow.
    console.error(`[message-log] Failed to log message: ${err.message}`);
  }
}

const handler = async (event) => {
  const ctx = event.context || {};

  if (event.type === "message" && event.action === "received") {
    await postMessage({
      role: "user",
      sender_id: ctx.metadata?.senderId || ctx.metadata?.senderE164 || ctx.from || "",
      sender_name: ctx.metadata?.senderName || "",
      channel: ctx.metadata?.provider || "",
      channel_id: ctx.channelId || "",
      content: ctx.content || "",
      message_id: ctx.messageId || "",
      session_key: event.sessionKey || "",
      timestamp: ctx.timestamp || event.timestamp || new Date().toISOString(),
    });
  }

  if (event.type === "message" && event.action === "sent") {
    await postMessage({
      role: "assistant",
      sender_id: "milo",
      sender_name: "Milo",
      channel: ctx.metadata?.channel || ctx.metadata?.provider || "",
      channel_id: ctx.channelId || "",
      content: ctx.content || ctx.text || "",
      message_id: ctx.messageId || "",
      session_key: event.sessionKey || "",
      timestamp: ctx.timestamp || event.timestamp || new Date().toISOString(),
    });
  }
};

export default handler;
