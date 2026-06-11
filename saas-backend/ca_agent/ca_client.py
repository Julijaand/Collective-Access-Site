"""
CA Agent - Collective Access GraphQL API Client
CA 2.x uses GraphQL + JWT
Endpoint: POST /service.php/<Controller>
Auth:     POST /service.php/Auth  → returns jwt token
"""
import httpx
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Valid type idnos per table confirmed from the CA database.
# Any LLM-supplied type not in this set is silently replaced with the default.
_VALID_TYPES: dict[str, set[str]] = {
    "ca_objects": {
        "document",
        "drawing",
        "film_media",
        "painting",
        "photography",
        "print",
        "sculpture",
    },
    "ca_entities":    {"individual", "organization"},
    "ca_occurrences": {"event"},
    "ca_collections": {"collection"},
}

# Maps human-friendly type words → CA idno
_TYPE_ALIASES: dict[str, str] = {
    "document":    "document",
    "drawing":     "drawing",
    "film":        "film_media",
    "film_media":  "film_media",
    "film & media":"film_media",
    "video":       "film_media",
    "media":       "film_media",
    "painting":    "painting",
    "photo":       "photography",
    "photograph":  "photography",
    "photography": "photography",
    "print":       "print",
    "etching":     "print",
    "lithograph":  "print",
    "sculpture":   "sculpture",
    "statue":      "sculpture",
    "bronze":      "sculpture",
    "ceramic":     "sculpture",
    # entities
    "individual":  "ind",
    "person":      "ind",
    "ind":         "ind",
    "org":         "org",
    "organisation":"org",
    "organization":"org",
}

_DEFAULT_TYPE: dict[str, str] = {
    "ca_objects":     "document",
    "ca_entities":    "individual",
    "ca_occurrences": "event",
    "ca_collections": "collection",
}

CA_RECORD_TYPES = {
    "object": "ca_objects",
    "entity": "ca_entities",
    "occurrence": "ca_occurrences",
    "collection": "ca_collections",
}


class CAClient:
    """Client for the Collective Access GraphQL API (CA 2.x)."""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._jwt: Optional[str] = None

    async def _get_jwt(self) -> str:
        """Authenticate and return JWT token."""
        if self._jwt:
            return self._jwt

        query = """
        query Login($username: String!, $password: String!) {
            login(username: $username, password: $password) {
                jwt
                refresh
            }
        }
        """
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/service.php/Auth",
                json={
                    "query": query,
                    "variables": {
                        "username": self.username,
                        "password": self.password,
                    },
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            errors = data.get("errors")
            if errors:
                raise RuntimeError(f"CA login failed: {errors}")
            jwt = data.get("data", {}).get("login", {}).get("jwt")
            if not jwt:
                raise RuntimeError(f"CA login: no jwt in response: {data}")
            self._jwt = jwt
            return jwt

    async def _graphql(self, controller: str, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL request against the given controller.

        CA sometimes returns HTTP 500 with a valid JSON body containing
        GraphQL errors — do NOT raise_on_status, parse the body instead.
        """
        jwt = await self._get_jwt()
        async with httpx.AsyncClient(verify=False, timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/service.php/{controller}",
                json={"query": query, "variables": variables or {}},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {jwt}",
                },
            )
            if resp.status_code == 401:
                # JWT expired — refresh and retry once
                self._jwt = None
                jwt = await self._get_jwt()
                resp = await client.post(
                    f"{self.base_url}/service.php/{controller}",
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {jwt}",
                    },
                )
            # CA can return 500 with a valid JSON error body — parse it
            try:
                data = resp.json()
            except Exception:
                resp.raise_for_status()
                raise
            errors = data.get("errors")
            if errors:
                logger.error("CA GraphQL error on %s: %s", controller, errors)
                raise RuntimeError(f"CA GraphQL error: {errors}")
            if resp.status_code >= 500:
                raise RuntimeError(
                    f"CA server error (HTTP {resp.status_code}): "
                    f"{data.get('message', 'unknown')}"
                )
            return data.get("data", {})

    async def search(
        self,
        entity: str,
        keyword: str = "",
        extra_params: Optional[dict] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search for records by keyword."""
        table = CA_RECORD_TYPES.get(entity, "ca_objects")
        q = keyword or "*"

        query = """
        query Search($table: String!, $search: String!, $start: Int, $limit: Int) {
            search(table: $table, search: $search, start: $start, limit: $limit) {
                count
                result {
                    id
                    table
                    idno
                    bundles { name values { value } }
                }
            }
        }
        """
        try:
            data = await self._graphql(
                "Search",
                query,
                {"table": table, "search": q, "start": 0, "limit": limit},
            )
            results = data.get("search", {}).get("result", [])
            return results
        except Exception as e:
            logger.error("CA search error: %s", e)
            raise

    async def get(self, entity: str, record_id: str) -> dict:
        """Retrieve a single record by ID."""
        table = CA_RECORD_TYPES.get(entity, "ca_objects")
        query = """
        query GetItem($table: String!, $id: Int!) {
            get(table: $table, id: $id) {
                id
                table
                idno
                bundles { name values { value } }
            }
        }
        """
        try:
            data = await self._graphql(
                "Item",
                query,
                {"table": table, "id": int(record_id)},
            )
            return data.get("get", {})
        except Exception as e:
            logger.error("CA get error: %s", e)
            raise

    async def create(self, entity: str, fields: dict) -> dict:
        """Create a new record."""
        table = CA_RECORD_TYPES.get(entity, "ca_objects")

        # `type` is a top-level arg on the add mutation, not a bundle.
        # Extract from fields if provided, normalise via aliases, then
        # validate — invalid types fall back to the table default.
        record_type = fields.pop("type_id", fields.pop("type", None))
        if record_type:
            record_type = _TYPE_ALIASES.get(record_type.lower().strip(), record_type)
        valid = _VALID_TYPES.get(table, set())
        if not record_type or record_type not in valid:
            record_type = _DEFAULT_TYPE.get(table, "document")

        # Map human-friendly field names to CA bundle names
        fields = _map_field_names(fields)
        bundles_literal = _bundles_to_literal(fields)
        query = f"""
        mutation {{
            add(table: "{table}", type: "{record_type}", bundles: {bundles_literal}) {{
                id
                idno
                errors {{ code message bundle }}
            }}
        }}
        """
        try:
            data = await self._graphql("Edit", query)
            result = data.get("add", {})
            errors = result.get("errors", [])
            if errors:
                raise RuntimeError(f"CA create errors: {errors}")
            # id/idno come back as arrays — unwrap first element
            result["id"] = (result.get("id") or [None])[0]
            result["idno"] = (result.get("idno") or [None])[0]
            return result
        except Exception as e:
            logger.error("CA create error: %s", e)
            raise

    async def delete(self, entity: str, record_id: str) -> dict:
        """Delete a record by ID.

        CA 2.x uses 'delete' as the mutation name
        """
        table = CA_RECORD_TYPES.get(entity, "ca_objects")
        query = f"""
        mutation {{
            delete(table: "{table}", id: {int(record_id)}) {{
                id
                errors {{ code message bundle }}
            }}
        }}
        """
        try:
            data = await self._graphql("Edit", query)
            result = data.get("delete", {})
            errors = result.get("errors", [])
            if errors:
                raise RuntimeError(f"CA delete errors: {errors}")
            return result
        except Exception as e:
            logger.error("CA delete error: %s", e)
            raise

    async def edit(self, entity: str, record_id: str, fields: dict) -> dict:
        """Update an existing record."""
        table = CA_RECORD_TYPES.get(entity, "ca_objects")
        bundles_literal = _bundles_to_literal(fields, replace=True)
        query = f"""
        mutation {{
            edit(table: "{table}", id: {int(record_id)}, bundles: {bundles_literal}) {{
                id
                idno
                errors {{ code message bundle }}
            }}
        }}
        """
        try:
            data = await self._graphql("Edit", query)
            result = data.get("edit", {})
            errors = result.get("errors", [])
            if errors:
                raise RuntimeError(f"CA edit errors: {errors}")
            result["id"] = (result.get("id") or [None])[0]
            result["idno"] = (result.get("idno") or [None])[0]
            return result
        except Exception as e:
            logger.error("CA edit error: %s", e)
            raise


# Human-friendly field names → CA bundle codes.
# Only 'preferred_labels' and 'description' are confirmed to save in the
# default CA install profile. Everything else (medium, date, etc.) is folded
# into description so it is at least stored and full-text searchable.
_FIELD_MAP = {
    "title":        "preferred_labels",
    "name":         "preferred_labels",
    "description":  "description",
    "notes":        "description",
}

# Fields that get folded into the description text rather than stored as
# separate bundles (because the default profile has no bundle for them).
_DESC_FIELDS = {
    "medium", "date", "date_created", "year",
    "artist", "creator", "author", "photographer",
    "location", "provenance", "dimensions", "material",
}


def _map_field_names(fields: dict) -> dict:
    """Translate user-supplied field names to CA bundle codes.

    Fields in _DESC_FIELDS are combined into description so they are
    stored as searchable text even if no dedicated CA bundle exists.
    """
    result = {}
    desc_parts = []
    for k, v in fields.items():
        if k in _DESC_FIELDS:
            desc_parts.append(f"{k.capitalize()}: {v}")
        else:
            result[_FIELD_MAP.get(k, k)] = v
    if desc_parts:
        existing = result.get("description", "")
        combined = "; ".join(filter(None, [existing] + desc_parts))
        result["description"] = combined
    return result


def _bundles_to_literal(fields: dict, replace: bool = False) -> str:
    """Convert flat field dict to a GraphQL inline bundle list literal."""
    parts = []
    replace_str = ", replace: true" if replace else ""
    for key, value in fields.items():
        if key == "id":
            continue
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'{{name: "{key}", value: "{escaped}"{replace_str}}}')
    return "[" + ", ".join(parts) + "]"


def _build_bundles(fields: dict) -> list[dict]:
    """Convert flat field dict to CA GraphQL BundleInput list."""
    bundles = []
    for key, value in fields.items():
        if key == "id":
            continue
        bundles.append({"name": key, "value": str(value)})
    return bundles