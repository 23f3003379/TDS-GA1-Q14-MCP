import hashlib
import json

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

EMAIL = "23f3003379@ds.study.iitm.ac.in".strip().lower()
DEFAULT_PROTOCOL = "2025-03-26"
SUPPORTED = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

TOOL = {
    "name": "solve_challenge",
    "description": "Reads the exam challenge from the HTTP request headers and returns the answer.",
    "inputSchema": {"type": "object", "properties": {}},
}


def answer_for(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]


def ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(msg: dict, headers):
    method = msg.get("method")
    req_id = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        wanted = (msg.get("params") or {}).get("protocolVersion")
        return ok(req_id, {
            "protocolVersion": wanted if wanted in SUPPORTED else DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "challenge-server", "version": "1.0.0"},
        })
    if method == "ping":
        return ok(req_id, {})
    if method == "tools/list":
        return ok(req_id, {"tools": [TOOL]})
    if method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        if name != "solve_challenge":
            return err(req_id, -32602, f"Unknown tool: {name}")
        challenge = (headers.get("x-exam-challenge") or "").strip()
        if not challenge:
            return ok(req_id, {
                "content": [{"type": "text", "text": "Missing X-Exam-Challenge header"}],
                "isError": True,
            })
        return ok(req_id, {
            "content": [{"type": "text", "text": answer_for(challenge)}],
            "isError": False,
        })
    if is_notification:
        return None  # notifications/initialized, notifications/cancelled, ...
    return err(req_id, -32601, f"Method not found: {method}")


@app.post("/mcp")
@app.post("/")
async def mcp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return Response(
            json.dumps(err(None, -32700, "Parse error")),
            media_type="application/json", status_code=400,
        )

    if isinstance(body, list):
        replies = [r for r in (handle(m, request.headers) for m in body) if r is not None]
        if not replies:
            return Response(status_code=202)
        return Response(json.dumps(replies), media_type="application/json")

    reply = handle(body, request.headers)
    if reply is None:
        return Response(status_code=202)
    return Response(json.dumps(reply), media_type="application/json")


@app.get("/mcp")
async def mcp_get():
    # No server-initiated stream in this minimal server.
    return Response(status_code=405, headers={"Allow": "POST"})


@app.delete("/mcp")
async def mcp_delete():
    return Response(status_code=405, headers={"Allow": "POST"})


@app.get("/")
async def health():
    return {"status": "ok", "mcp_endpoint": "/mcp"}
