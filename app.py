# app.py
import os
import json
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# === Configuration (env-driven) ===
MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss")
DEFAULT_PROMPT = os.getenv("OLLAMA_DEFAULT_PROMPT", "Hello! 👋 How can I help you today?")
TIMEOUT = float(os.getenv("OLLAMA_CONNECTION_TIMEOUT", "60"))

# Resolve Ollama base URL from either OLLAMA_URL or OLLAMA_HOST/OLLAMA_PORT
base_url = os.getenv("OLLAMA_URL", "").strip()
if not base_url:
    host = os.getenv("OLLAMA_HOST", "127.0.0.1")
    port = os.getenv("OLLAMA_PORT", "11434")
    base_url = f"http://{host}:{port}"
OLLAMA_CHAT_URL = f"{base_url}/api/chat"

# Streaming / generation tuning
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")         # keep model warm between calls
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))  # cap output tokens for faster replies

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8080"))

# === FastAPI app ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX_HTML = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Chat with gpt-oss (via Ollama)</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #0b1220; color: #e7ecf3; }}
  .wrap {{ max-width: 880px; margin: 0 auto; padding: 16px; }}
  .chat {{ display: flex; flex-direction: column; gap: 12px; margin-bottom: 96px; }}
  .msg {{ padding: 12px 14px; border-radius: 12px; line-height: 1.45; white-space: pre-wrap; }}
  .user {{ align-self: flex-end; background: #2a3450; }}
  .ai   {{ align-self: flex-start; background: #1a2236; }}
  form  {{ position: fixed; left: 0; right: 0; bottom: 0; background: #0f172a; padding: 12px; }}
  .row  {{ max-width: 880px; margin: 0 auto; display: flex; gap: 8px; }}
  textarea {{ flex: 1; resize: none; min-height: 46px; padding: 10px; border-radius: 8px; border: 1px solid #26304a; background: #0b1220; color: #e7ecf3; }}
  button {{ padding: 12px 16px; border-radius: 8px; border: 0; background: #3b82f6; color: white; font-weight: 600; }}
  button:disabled {{ opacity: .6; }}
  .hint {{ opacity:.75; font-size:.9rem; }}
</style>
</head>
<body>
  <div class="wrap">
    <h2>💬 Chat with <code>{MODEL}</code> (via Ollama @ <code>{base_url}</code>)</h2>
    <p class="hint">Streaming is enabled. We filter out "thinking" tokens and render only assistant content.</p>
    <div class="chat" id="chat"></div>
  </div>

  <form id="f">
    <div class="row">
      <textarea id="t" placeholder="Type your message…" required></textarea>
      <button id="b">Send</button>
    </div>
  </form>

<script>
const chat = document.getElementById('chat');
const form = document.getElementById('f');
const box  = document.getElementById('t');
const btn  = document.getElementById('b');

let history = [];

function bubble(role, text) {{
  const d = document.createElement('div');
  d.className = 'msg ' + (role === 'user' ? 'user' : 'ai');
  d.textContent = text;
  chat.appendChild(d);
  window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
  return d;
}}

// Optional greeting
if ({'true' if bool(DEFAULT_PROMPT) else 'false'}) {{
  history.push({{ role: 'assistant', content: `{DEFAULT_PROMPT}` }});
  bubble('assistant', `{DEFAULT_PROMPT}`);
}}

form.addEventListener('submit', async (e) => {{
  e.preventDefault();
  const content = box.value.trim();
  if (!content) return;

  bubble('user', content);
  history.push({{ role: 'user', content }});
  btn.disabled = true;
  box.value = '';

  // Prepare the assistant bubble that we'll progressively update:
  const aiDiv = bubble('assistant', '');

  try {{
    const res = await fetch('/api/chat-stream', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        model: '{MODEL}',
        messages: history
      }})
    }});

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';

    while (true) {{
      const {{ value, done }} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {{ stream: true }});

      // Server sends Server-Sent Events (SSE): "data: <chunk>\\n\\n"
      const parts = buf.split('\\n\\n');
      buf = parts.pop(); // last may be partial

      for (const p of parts) {{
        if (p.startsWith('data: ')) {{
          const chunk = p.slice(6);
          // Append chunk
          aiDiv.textContent += chunk;
        }}
        // ignore "event: done" lines here
      }}
    }}

    history.push({{ role: 'assistant', content: aiDiv.textContent }});
  }} catch (err) {{
    aiDiv.textContent = 'Error: ' + err;
  }} finally {{
    btn.disabled = false;
  }}
}});
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML

@app.post("/api/chat")  # Non-streaming fallback (returns a single JSON at end)
async def chat_once(req: Request):
    body = await req.json()
    model = body.get("model", MODEL)
    messages = body.get("messages", [])

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "num_predict": NUM_PREDICT
        }
    }
    try:
        r = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        msg = (data.get("message") or {}).get("content", "")
        return JSONResponse({"message": msg})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/chat-stream")  # Streams tokens and filters out thinking
async def chat_stream(req: Request):
    body = await req.json()
    model = body.get("model", MODEL)
    messages = body.get("messages", [])

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,           # NDJSON streaming
        "keep_alive": KEEP_ALIVE, # keep model loaded
        "options": {
            "num_predict": NUM_PREDICT
        }
    }

    # stream=True here is "stream the HTTP response", not the Ollama flag above
    upstream = requests.post(OLLAMA_CHAT_URL, json=payload, stream=True, timeout=None)

    def sse():
        """
        Proxy NDJSON from Ollama as Server-Sent Events (SSE).
        We only emit assistant content (ignore 'thinking' and empty content).
        """
        for line in upstream.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            # Stop on done
            if obj.get("done"):
                break

            msg = obj.get("message") or {}
            content = msg.get("content") or ""
            # Many reasoning models also send msg.get("thinking"), which we intentionally ignore
            if content:
                # send as SSE data
                yield f"data: {content}\n\n"

        # signal completion
        yield "event: done\ndata: end\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=APP_HOST, port=APP_PORT, reload=True)
