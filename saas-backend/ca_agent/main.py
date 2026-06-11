"""
CA Agent - Phase 1: Text Chat API
FastAPI service that accepts natural language, parses intent via LLM,
and performs actions on Collective Access via its REST API.

Endpoints:
  POST /chat        — Main chat endpoint
  GET  /health      — Health check
  GET  /history     — Return conversation history for a session
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .ca_client import CAClient
from .intent import parse_intent
from .prompts import RESPONSE_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # required — OpenRouter key
LLM_MODEL   = os.getenv("LLM_MODEL", "")

CA_URL = os.getenv("CA_URL")  # required — set in .env
CA_USERNAME = os.getenv("CA_USERNAME")  # required — set in .env
CA_PASSWORD = os.getenv("CA_PASSWORD")  # required — set in .env
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")  # default * is fine for dev

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CA Agent",
    description="AI text agent for Collective Access collection management",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session history (Phase 1 — replace with Redis/DB in Phase 4)
_sessions: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    ca_url: Optional[str] = None       # Per-tenant CA URL override
    ca_username: Optional[str] = None
    ca_password: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    action_taken: Optional[str] = None
    records: Optional[list] = None
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    ca_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_ca_client(req: ChatRequest) -> CAClient:
    return CAClient(
        base_url=req.ca_url or CA_URL,
        username=req.ca_username or CA_USERNAME,
        password=req.ca_password or CA_PASSWORD,
    )


def _build_search_keyword(params: dict) -> str:
    """Construct a CA full-text search keyword from LLM-extracted params.

    CA's search endpoint is pure full-text — there are no structured filters.
    We fold date/year and type hints into the keyword so at least some
    filtering happens via the text index.

    Note: date-only filtering ("from 1940") will match any record whose
    description contains "1940", which is imperfect. True date-range
    filtering would require a CA advanced-search query syntax.
    """
    parts = []
    keyword = params.get("keyword", "").strip()
    # Strip generic type labels that would never match actual record names
    _GENERIC_KEYWORDS = {"artists", "artist", "entities", "entity", "objects", "object",
                         "organisations", "organizations", "organisation", "organization",
                         "institutions", "institution", "people", "person", "all", "everything",
                         "document", "documents", "painting", "paintings", "sculpture", "sculptures",
                         "drawing", "drawings", "photograph", "photographs", "photography",
                         "print", "prints", "film", "films", "media", "video", "videos"}
    if keyword and keyword.lower() not in _GENERIC_KEYWORDS:
        parts.append(keyword)

    # Year / date hints — CA full-text can't do true date ranges, so we
    # search for each year individually and deduplicate results.
    for key in ("date_from", "date_to", "year", "date"):
        val = params.get(key, "").strip()
        if val and val not in parts:
            parts.append(val)

    return " ".join(parts)


# Words that indicate the user wants only individual people, not organisations
_ARTIST_KEYWORDS = {"artist", "artists", "person", "people", "individual", "individuals", "creator", "creators"}
_ORG_KEYWORDS    = {"organisation", "organisations", "organization", "organizations", "institution", "institutions"}


def _entity_type_filter(params: dict) -> set[str] | None:
    """Return a set of CA entity type values to keep, or None for no filter.

    CA stores entity type internally as 'ind' or 'org' (idnos), not display
    labels like 'individual' / 'organization'.  We match against the idnos.
    """
    keyword = params.get("keyword", "").lower()
    entity_type = params.get("type", "").lower()
    combined = f"{keyword} {entity_type}".strip()
    if any(w in combined for w in _ARTIST_KEYWORDS):
        return {"individual"}
    if any(w in combined for w in _ORG_KEYWORDS):
        return {"organization"}
    return None


def _get_bundle_value(record: dict, bundle_display_name: str) -> str:
    """Return the first value of a named bundle from a CA record, lowercased."""
    for bundle in record.get("bundles") or []:
        if bundle.get("name", "").lower() == bundle_display_name.lower():
            values = bundle.get("values") or []
            if values:
                return (values[0].get("value") or "").lower()
    return ""


def _format_search_results(results: list) -> str:
    if not results:
        return "No records found."
    lines = []
    for i, r in enumerate(results[:10], 1):
        record_id = r.get("id", "?")
        # CA search returns bundles as [{name, values:[{value}]}]
        # Title lives in the bundle named 'preferred_labels' (or with table prefix)
        label = _extract_label(r)
        idno = r.get("idno") or ""
        suffix = f" `{idno}`" if idno and idno != "%" else ""
        lines.append(f"{i}. [{record_id}] {label}{suffix}")
    return "\n".join(lines)


# Bundle display names that contain the primary label, for both objects and entities
_LABEL_BUNDLES = {
    "titles", "preferred_labels", "title", "label",
    "names", "preferred names", "name",  # entities (generic)
    "entity names",                       # CA default profile: ca_entities
}


def _extract_label(record: dict) -> str:
    """Pull the preferred label from a CA GraphQL record.

    CA returns bundle display names (e.g. 'Titles', 'Names') rather than
    internal codes, so we match a broad set.
    """
    for bundle in record.get("bundles") or []:
        name = bundle.get("name", "").lower()
        if name in _LABEL_BUNDLES or "preferred_labels" in name:
            values = bundle.get("values") or []
            for v in values:
                val = v.get("value", "").strip()
                if val and val not in ("[BLANK]", ""):
                    return val
    return (
        record.get("display_label")
        or record.get("label")
        or f"Record {record.get('id', '?')}"
    )


# Bundles to show in a record detail view (lowercased display name)
_DETAIL_BUNDLES = {
    "type", "entity type",
    "medium", "description", "date created", "access", "status",
    "extent", "notes",
}


def _format_record_detail(record: dict) -> str:
    """Format key bundles from a single record into a readable summary."""
    lines = []
    for bundle in record.get("bundles") or []:
        name = bundle.get("name", "")
        # CA's description bundle returns with an empty display name in default profile
        display = name if name else "Description"
        if display.lower() in _DETAIL_BUNDLES or name == "":
            values = bundle.get("values") or []
            val = "; ".join(
                v.get("value", "") for v in values
                if v.get("value", "") not in ("", "[BLANK]")
            )
            if val:
                lines.append(f"- **{display}:** {val}")
    return "\n".join(lines) if lines else "_No additional details stored._"


def _add_to_history(session_id: str, role: str, content: str):
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content, "ts": datetime.utcnow().isoformat()})
    # Keep last 20 messages per session
    _sessions[session_id] = _sessions[session_id][-20:]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        llm_provider="openrouter",
        llm_model=LLM_MODEL,
        ca_url=CA_URL,
    )


@app.get("/history")
async def history(session_id: str):
    return {"session_id": session_id, "messages": _sessions.get(session_id, [])}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    message = req.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    _add_to_history(session_id, "user", message)

    # 1. Parse intent
    intent = await parse_intent(message, LLM_API_KEY, LLM_MODEL)
    action = intent["action"]
    entity = intent["entity"]
    params = intent["params"]

    logger.info("Intent: action=%s entity=%s params=%s", action, entity, params)

    ca = _get_ca_client(req)
    reply = ""
    action_taken = action
    records = None

    try:
        # 2. Execute action
        if action == "search":
            keyword = _build_search_keyword(params)
            # For date ranges, search each year separately and merge
            date_from = params.get("date_from", "").strip()
            date_to   = params.get("date_to", "").strip()
            if date_from and date_to and date_from != date_to:
                try:
                    years = range(int(date_from), int(date_to) + 1)
                    seen_ids = set()
                    merged = []
                    for year in years:
                        yr_results = await ca.search(entity, keyword=str(year), limit=20)
                        for r in yr_results:
                            if r.get("id") not in seen_ids:
                                seen_ids.add(r.get("id"))
                                merged.append(r)
                    results = merged[:10]
                except (ValueError, TypeError):
                    results = await ca.search(entity, keyword=keyword, limit=10)
            else:
                results = await ca.search(entity, keyword=keyword, limit=20)
            # For entities, filter by type when user asks for "artists" vs "organisations".
            # If the keyword itself is just a type label (e.g. "artists", "organisations")
            # CA full-text won't match anything — re-search with empty keyword first.
            entity_type_filter = _entity_type_filter(params) if entity == "entity" else None
            if entity_type_filter and not results:
                results = await ca.search(entity, keyword="", limit=20)
            if entity_type_filter:
                results = [
                    r for r in results
                    if _get_bundle_value(r, "entity type") in entity_type_filter
                    or _get_bundle_value(r, "type") in entity_type_filter
                ]
            # For objects, filter by type when user specifies a type (e.g. "documents", "paintings")
            if entity == "object":
                object_type = params.get("type", "").strip().lower()
                if object_type:
                    results = [
                        r for r in results
                        if _get_bundle_value(r, "type") == object_type
                    ]
            results = results[:10]
            records = results
            formatted = _format_search_results(results)
            label = keyword or "(all)"
            reply = f"Found {len(results)} result(s) for '{label}':\n\n{formatted}"

        elif action == "get":
            record_id = params.get("id", "")
            if not record_id:
                reply = "Please provide a record ID to look up."
                action_taken = "error"
            else:
                record = await ca.get(entity, record_id)
                records = [record]
                label = _extract_label(record)
                idno = record.get("idno", "")
                id_suffix = f" `{idno}`" if idno and idno != "%" else ""
                # Build a detail summary from bundles
                details = _format_record_detail(record)
                reply = f"Record #{record_id}{id_suffix}: **{label}**\n\n{details}"

        elif action == "create":
            if not params:
                reply = "I need more details to create a record. What title, type, or other information should I include?"
                action_taken = "clarify"
            else:
                # Deduplicate: search for existing records with the same title/name
                title_key = params.get("title") or params.get("name") or ""
                if title_key:
                    existing = await ca.search(entity, keyword=title_key, limit=5)
                    # Normalise for comparison — strip quotes, lowercase, remove extra spaces
                    clean = " ".join(title_key.lower().replace('"', '').split())
                    for rec in existing:
                        existing_label = _extract_label(rec)
                        clean_existing = " ".join(existing_label.lower().replace('"', '').split())
                        if clean == clean_existing:
                            existing_id = rec.get("id", "?")
                            reply = f"⚠️ **{title_key}** already exists as record #{existing_id}. No duplicate created."
                            action_taken = "duplicate_skipped"
                            # Still include the existing record in the response
                            records = [rec]
                            break
                    if reply:
                        _add_to_history(session_id, "assistant", reply)
                        return ChatResponse(
                            reply=reply,
                            session_id=session_id,
                            action_taken=action_taken,
                            records=records,
                            timestamp=datetime.utcnow().isoformat(),
                        )
                result = await ca.create(entity, params)
                new_id = result.get("id", "?")
                title = params.get("title") or params.get("name") or "new record"
                obj_type = params.get("type", "")
                type_label = f" ({obj_type})" if obj_type else ""
                reply = f"✅ Created {entity} record #{new_id}{type_label}: **{title}**"

        elif action == "edit":
            record_id = params.get("id", "")
            if not record_id:
                reply = "Please specify which record ID you'd like to update."
                action_taken = "clarify"
            else:
                update_fields = {k: v for k, v in params.items() if k != "id"}
                await ca.edit(entity, record_id, update_fields)
                reply = f"✅ Updated record #{record_id} with the new information."

        elif action == "delete":
            record_id = params.get("id", "")
            # Check if this is a confirmation follow-up — look for pending delete in session
            msg_lower = message.lower()
            pending = _sessions.get(session_id, [])
            is_confirmation = any(w in msg_lower for w in ["yes", "confirm", "delete it", "go ahead", "proceed"])
            # If no id in params, check for a pending delete in the session
            if not record_id and is_confirmation:
                # Scan recent messages for a pending deletion request
                for entry in reversed(pending):
                    if entry.get("role") == "assistant" and entry.get("content", "").startswith("⚠️ Are you sure"):
                        # Extract ID from the confirmation message: "...(#[0-9]+)..."
                        import re
                        m = re.search(r'\(#(\d+)\)', entry["content"])
                        if m:
                            record_id = m.group(1)
                            # Also restore the original entity type from the pending message
                            # e.g. "permanently delete Frida Kahlo (#4)" — entity was already
                            # resolved correctly in the first request, don't re-parse it.
                            break
                # Also restore the entity type from the original delete request.
                # Skip confirmation messages like "yes, delete" — find the
                # actual request that contained the entity reference.
                for entry in reversed(pending):
                    if entry.get("role") == "user":
                        # Skip short confirmation responses
                        msg = entry["content"].lower()
                        if msg in ("yes, delete", "yes", "confirm", "delete it", "go ahead", "proceed"):
                            continue
                        # Re-parse the original user message to get the correct entity
                        orig_intent = await parse_intent(entry["content"], LLM_API_KEY, LLM_MODEL)
                        if orig_intent["action"] == "delete":
                            entity = orig_intent["entity"]
                            break
            if not record_id:
                reply = "Please specify which record ID you'd like to delete."
                action_taken = "clarify"
            else:
                # Fetch the label so we can show what's being deleted.
                # If the record is already corrupted (500 from CA), use a fallback label.
                try:
                    record = await ca.get(entity, record_id)
                    label = _extract_label(record)
                except Exception:
                    label = f"record #{record_id}"
                if is_confirmation:
                    logger.info("Deleting %s record #%s", entity, record_id)
                    await ca.delete(entity, record_id)
                    reply = f"🗑️ Deleted **{label}** (#{record_id})."
                    action_taken = "delete"
                else:
                    reply = f"⚠️ Are you sure you want to permanently delete **{label}** (#{record_id})? Reply 'yes, delete' to confirm."
                    action_taken = "confirm_delete"

        else:  # unknown
            reply = (
                "I'm not sure what you'd like to do. You can ask me to:\n"
                "- **Search** for artworks, artists, or events\n"
                "- **Create** a new artwork or entity record\n"
                "- **Get** a specific record by ID\n"
                "- **Update** an existing record\n\n"
                "Try: *'Find all paintings'* or *'Create artwork titled Sunset, oil on canvas, 1921'*"
            )
            action_taken = "unknown"

    except Exception as e:
        logger.error("CA action failed: %s", e)
        reply = f"Something went wrong while trying to {action} the record. Please check the CA system is reachable."
        action_taken = "error"

    _add_to_history(session_id, "assistant", reply)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        action_taken=action_taken,
        records=records,
        timestamp=datetime.utcnow().isoformat(),
    )
