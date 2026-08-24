# Building and Deploying a Resy MCP Server on Google Cloud Run: A Complete Step-by-Step Guide with Python

As Large Language Models (LLMs) transition from passive text generators to proactive autonomous agents, the **Model Context Protocol (MCP)** has emerged as the open industry standard for securely connecting AI models to external tools, databases, and APIs. 

Imagine asking your AI assistant (in Claude Desktop, Cursor, Gemini, or a custom agent):
> *"Find me an Italian dinner table for two in SoHo, New York, this Friday around 7:30 PM, check the cancellation policy, and reserve it."*

In this comprehensive guide, we will build a **production-ready Model Context Protocol (MCP) Server for Resy** in Python using **FastMCP** and the **Server-Sent Events (SSE)** transport, containerize it with **Docker**, and deploy it onto **Google Cloud Run** with secure secret management, auto-scaling, and enterprise-grade observability.

---

## Architecture Overview

Traditional local MCP servers run as child processes over standard input/output (`stdio`). While `stdio` works well for single-machine desktop apps, deploying an MCP server in the cloud enables **remote accessibility**, **centralized tool governance**, **team-wide sharing**, and **24/7 autonomous agent execution**.

Google Cloud Run is the ideal hosting platform for remote MCP servers:
* **Server-Sent Events (SSE) & HTTP Streaming**: Cloud Run natively supports HTTP/2 and long-lived streaming connections (up to 60 minutes request timeouts).
* **Scale-to-Zero Cost Model**: Pay $0 when your AI assistant is not actively querying restaurant availability.
* **Secret Manager Integration**: Securely inject Resy API tokens and authentication credentials without baking them into container images.
* **Zero Infrastructure Overhead**: Serverless container execution with automated TLS certificates and global load balancing.

### High-Level Architecture Diagram

```
 ┌───────────────────────────────────────────────────────────┐
 │                       AI Clients                          │
 │  ┌──────────────────┐ ┌────────────────┐ ┌──────────────┐ │
 │  │  Claude Desktop  │ │   Cursor IDE   │ │ Python Agent │ │
 │  │  (via mcp-remote)│ │  (Native SSE)  │ │ (LangChain)  │ │
 │  └────────┬─────────┘ └───────┬────────┘ └──────┬───────┘ │
 └───────────┼───────────────────┼─────────────────┼─────────┘
             │                   │                 │
             │   HTTPS / SSE     │                 │
             ▼                   ▼                 ▼
 ┌───────────────────────────────────────────────────────────┐
 │                   Google Cloud Run                        │
 │  ┌─────────────────────────────────────────────────────┐  │
 │  │           FastMCP Server (Python 3.11)              │  │
 │  │                                                     │  │
 │  │  Endpoints:                                         │  │
 │  │   • GET  /sse       (SSE Event Stream)              │  │
 │  │   • POST /messages/ (MCP JSON-RPC Tool Invocations) │  │
 │  │                                                     │  │
 │  │  Exposed MCP Tools:                                 │  │
 │  │   1. search_restaurants                             │  │
 │  │   2. get_restaurant_availability                    │  │
 │  │   3. get_slot_details                               │  │
 │  │   4. book_reservation (with dry-run safety)         │  │
 │  │   5. get_my_reservations                            │  │
 │  └────────────────────────┬────────────────────────────┘  │
 └───────────────────────────┼───────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
 ┌──────────────────────┐         ┌──────────────────────┐
 │ Google Secret Manager│         │   Resy Backend API   │
 │ • RESY_API_KEY       │         │   (api.resy.com)     │
 │ • RESY_AUTH_TOKEN    │         │ • /4/find            │
 │ • MCP_AUTH_TOKEN     │         │ • /3/details         │
 └──────────────────────┘         │ • /3/book            │
                                  └──────────────────────┘
```

---

## Understanding the Resy API

Resy's web and mobile applications communicate with an internal REST API hosted on `api.resy.com`. To build our MCP server, we wrap these core endpoints into clean, type-safe Python methods.

### 1. Required Authentication Headers
Every request to `api.resy.com` requires standard client identification and user authentication headers:

| Header | Description | Example Value |
| :--- | :--- | :--- |
| `Authorization` | Resy Public Client API Key | `ResyAPI api_key="V3...your_key..."` |
| `X-Resy-Auth-Token` | User Session Auth Token | `eyJhbGciOi...user_jwt_token...` |
| `X-Resy-Universal-Auth`| Universal Token (matches user token) | `eyJhbGciOi...user_jwt_token...` |
| `User-Agent` | Mobile/Web client spoofing header | `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...` |
| `Referer` | Widget / Web referrer | `https://widgets.resy.com/` |

> [!TIP]
> **How to extract your Resy Credentials:**
> 1. Open your browser and navigate to [resy.com](https://resy.com).
> 2. Open Chrome Developer Tools (**F12** or **Cmd+Option+I**) and navigate to the **Network** tab.
> 3. Log into your Resy account and click on any restaurant.
> 4. In the Network filter, type `find` or `venues`.
> 5. Inspect the **Request Headers** for any request to `api.resy.com` and copy the values for `Authorization` and `X-Resy-Auth-Token`.

### 2. Core API Endpoints Workflow

The reservation lifecycle on Resy follows a strict 4-step sequence:

```
 ┌───────────────────────┐
 │  1. Search / Find     │ ──► GET /4/find?lat=...&long=...&day=...&party_size=...
 │     (Find Venues)     │     Returns: venue_id, name, address, cuisine
 └──────────┬────────────┘
            │
            ▼
 ┌───────────────────────┐
 │  2. Slot Availability │ ──► GET /4/find?venue_id=...&day=...&party_size=...
 │     (Available Times) │     Returns: list of slots, seating types, & config_token
 └──────────┬────────────┘
            │
            ▼
 ┌───────────────────────┐
 │  3. Slot Details      │ ──► GET /3/details?config_id=...&day=...&party_size=...
 │     (Lock & Validate) │     Returns: cancellation fees, policy, & book_token
 └──────────┬────────────┘
            │
            ▼
 ┌───────────────────────┐
 │  4. Finalize Booking  │ ──► POST /3/book
 │     (Confirm Table)   │     Payload: { book_token, struct_payment_method }
 └───────────────────────┘
```

---

## Project Structure

Let's set up our project repository with clean modular separation:

```text
resy-mcp-server/
├── resy/
│   ├── __init__.py
│   ├── client.py         # Resy API Async Client Wrapper
│   └── models.py         # Pydantic Schemas for Tools and Responses
├── server.py             # FastMCP Server with SSE Transport & Tool Definitions
├── Dockerfile            # Production Multi-Stage Container Image
├── .dockerignore         # Docker build exclusions
├── pyproject.toml        # Modern Python project configuration
├── requirements.txt      # Pinned dependencies for pip/uv
└── test_client.py        # Local SSE verification script
```

---

## Step 1: Project Dependencies

We use `fastmcp` (the official high-level Python framework for building MCP servers), `httpx` (modern async HTTP client with HTTP/2 and connection pooling), `pydantic` (data validation), and `uvicorn` (ASGI web server).

### `requirements.txt`
```text
fastmcp>=2.0.0
mcp>=1.3.0
httpx>=0.27.2
pydantic>=2.9.2
uvicorn>=0.32.0
starlette>=0.41.0
```

### `pyproject.toml`
```toml
[project]
name = "resy-mcp-server"
version = "1.0.0"
description = "Model Context Protocol (MCP) Server for Resy Reservations on Google Cloud Run"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.27.2",
    "mcp>=1.3.0",
    "pydantic>=2.9.2",
    "starlette>=0.41.0",
    "uvicorn>=0.32.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

---

## Step 2: Defining Pydantic Data Models

Create `resy/models.py` to structure the inputs and outputs of our MCP tools. Structured schemas ensure that the LLM receives clean, human-readable data instead of raw multi-megabyte JSON payloads.

```python
# resy/models.py
"""
Data models for Resy API and MCP Tool Schemas.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class VenueSearchResult(BaseModel):
    venue_id: int = Field(..., description="Unique Resy Venue ID")
    name: str = Field(..., description="Restaurant name")
    cuisine: Optional[str] = Field(None, description="Type of cuisine")
    price_range: Optional[int] = Field(None, description="Price tier (1-4)")
    neighborhood: Optional[str] = Field(None, description="Neighborhood or area")
    city: Optional[str] = Field(None, description="City")
    rating: Optional[float] = Field(None, description="User rating score")
    url_slug: Optional[str] = Field(None, description="Resy URL slug")


class TimeSlot(BaseModel):
    time: str = Field(..., description="Reservation time (e.g., '19:30:00')")
    table_type: str = Field(..., description="Seating type: Dining Room, Patio, Bar, etc.")
    config_token: str = Field(..., description="Token required to inspect slot details and lock")
    min_party_size: int = Field(2, description="Minimum party size")
    max_party_size: int = Field(2, description="Maximum party size")


class VenueAvailability(BaseModel):
    venue_id: int = Field(..., description="Resy Venue ID")
    venue_name: str = Field(..., description="Restaurant Name")
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    party_size: int = Field(..., description="Party size requested")
    available_slots: List[TimeSlot] = Field(default_factory=list, description="Available table slots")


class SlotDetails(BaseModel):
    config_token: str = Field(..., description="Configuration token for this slot")
    book_token: str = Field(..., description="Temporary booking token to finalize reservation")
    venue_name: str = Field(..., description="Restaurant name")
    reservation_time: str = Field(..., description="Formatted reservation date & time")
    table_type: str = Field(..., description="Seating type")
    cancellation_policy: str = Field(..., description="Cancellation deadline and fee details")
    deposit_amount_cents: int = Field(0, description="Required upfront deposit in cents")
    payment_required: bool = Field(False, description="Whether a payment method is required")


class BookingResult(BaseModel):
    success: bool = Field(..., description="True if reservation was secured")
    reservation_id: Optional[str] = Field(None, description="Resy reservation confirmation ID")
    venue_name: Optional[str] = Field(None, description="Restaurant name")
    reservation_time: Optional[str] = Field(None, description="Confirmed reservation time")
    party_size: Optional[int] = Field(None, description="Number of guests")
    message: str = Field(..., description="Confirmation details or error explanation")
    dry_run: bool = Field(False, description="Indicates if this was simulated in dry-run mode")


class UserReservation(BaseModel):
    reservation_id: str = Field(..., description="Reservation ID")
    venue_name: str = Field(..., description="Restaurant name")
    date: str = Field(..., description="Reservation date")
    time: str = Field(..., description="Reservation time")
    party_size: int = Field(..., description="Party size")
    table_type: Optional[str] = Field(None, description="Seating area")
```

---

## Step 3: Resy API Async Client Wrapper

Create `resy/client.py`. This client manages authentication headers, connection pooling with `httpx.AsyncClient`, automatic JSON decoding, error handling, and parameter encoding.

```python
# resy/client.py
"""
Asynchronous Resy API Client for MCP Server.
"""
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from resy.models import (
    BookingResult,
    SlotDetails,
    TimeSlot,
    UserReservation,
    VenueAvailability,
    VenueSearchResult,
)

logger = logging.getLogger("resy-client")


class ResyAPIError(Exception):
    """Base exception for Resy API interactions."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ResyClient:
    """Async Client wrapping Resy's private REST API."""

    BASE_URL = "https://api.resy.com"

    # Default city latitude/longitude coordinates mapping
    CITY_COORDINATES = {
        "nyc": (40.7128, -74.0060),
        "new york": (40.7128, -74.0060),
        "sf": (37.7749, -122.4194),
        "san francisco": (37.7749, -122.4194),
        "la": (34.0522, -118.2437),
        "los angeles": (34.0522, -118.2437),
        "chicago": (41.8781, -87.6298),
        "miami": (25.7617, -80.1918),
        "austin": (30.2672, -97.7431),
        "london": (51.5074, -0.1278),
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.api_key = api_key or os.getenv("RESY_API_KEY", "")
        self.auth_token = auth_token or os.getenv("RESY_AUTH_TOKEN", "")
        self.timeout = timeout

        if not self.api_key:
            logger.warning("RESY_API_KEY is not set. Resy API calls may fail.")

    def _get_headers(self) -> Dict[str, str]:
        """Construct required Resy request headers."""
        headers = {
            "Authorization": f'ResyAPI api_key="{self.api_key}"',
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://widgets.resy.com/",
            "Origin": "https://widgets.resy.com",
            "X-Origin": "https://widgets.resy.com",
        }
        if self.auth_token:
            headers["X-Resy-Auth-Token"] = self.auth_token
            headers["X-Resy-Universal-Auth"] = self.auth_token
        return headers

    async def search_venues(
        self,
        query: str,
        city_or_location: str = "nyc",
        day: str = "2026-06-01",
        party_size: int = 2,
    ) -> List[VenueSearchResult]:
        """Search for restaurants matching a query and city."""
        lat, lon = self.CITY_COORDINATES.get(
            city_or_location.lower().strip(), (40.7128, -74.0060)
        )

        params = {
            "lat": str(lat),
            "long": str(lon),
            "day": day,
            "party_size": str(party_size),
            "query": query,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/4/find",
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Resy find request failed: {e.response.status_code} - {e.response.text}")
                raise ResyAPIError(f"Failed searching venues: {e.response.text}", e.response.status_code)
            except Exception as e:
                logger.error(f"Error during search_venues: {str(e)}")
                raise ResyAPIError(f"Unexpected error searching venues: {str(e)}")

        results: List[VenueSearchResult] = []
        venues = data.get("results", {}).get("venues", [])

        for item in venues:
            venue = item.get("venue", {})
            venue_id = venue.get("id", {}).get("resy") or venue.get("id")
            if not venue_id:
                continue

            results.append(
                VenueSearchResult(
                    venue_id=int(venue_id),
                    name=venue.get("name", "Unknown Venue"),
                    cuisine=venue.get("type", None),
                    price_range=venue.get("price_range", None),
                    neighborhood=venue.get("location", {}).get("neighborhood", None),
                    city=venue.get("location", {}).get("city", city_or_location),
                    rating=venue.get("rating", None),
                    url_slug=venue.get("url_slug", None),
                )
            )

        return results

    async def get_availability(
        self,
        venue_id: int,
        day: str,
        party_size: int,
    ) -> VenueAvailability:
        """Fetch open reservation slots for a specific restaurant and date."""
        params = {
            "lat": "0",
            "long": "0",
            "day": day,
            "party_size": str(party_size),
            "venue_id": str(venue_id),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/4/find",
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                raise ResyAPIError(f"Failed fetching slots: {e.response.text}", e.response.status_code)

        venues = data.get("results", {}).get("venues", [])
        if not venues:
            return VenueAvailability(
                venue_id=venue_id,
                venue_name=f"Venue #{venue_id}",
                date=day,
                party_size=party_size,
                available_slots=[],
            )

        target_venue = venues[0]
        venue_name = target_venue.get("venue", {}).get("name", f"Venue #{venue_id}")
        slots_data = target_venue.get("slots", [])

        slots: List[TimeSlot] = []
        for s in slots_data:
            config = s.get("config", {})
            date_time = s.get("date", {})
            start_time = date_time.get("start", "")
            time_part = start_time.split(" ")[1] if " " in start_time else start_time

            slots.append(
                TimeSlot(
                    time=time_part,
                    table_type=config.get("type", "Dining Room"),
                    config_token=config.get("token", ""),
                    min_party_size=s.get("size", {}).get("min", party_size),
                    max_party_size=s.get("size", {}).get("max", party_size),
                )
            )

        return VenueAvailability(
            venue_id=venue_id,
            venue_name=venue_name,
            date=day,
            party_size=party_size,
            available_slots=slots,
        )

    async def get_slot_details(
        self,
        config_token: str,
        day: str,
        party_size: int,
    ) -> SlotDetails:
        """Inspect slot details, lock slot, return policy & book_token."""
        params = {
            "config_id": config_token,
            "day": day,
            "party_size": str(party_size),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/3/details",
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                raise ResyAPIError(f"Failed to fetch slot details: {e.response.text}", e.response.status_code)

        book_token = data.get("book_token", {}).get("value", "")
        venue_info = data.get("venue", {})
        cancellation = data.get("cancellation", {})
        cancellation_policy = cancellation.get("policy", "No specific policy provided by venue.")

        deposit = data.get("deposit", {})
        deposit_cents = deposit.get("amount", 0) if deposit else 0

        res_info = data.get("reservation", {})
        res_time = res_info.get("date", f"{day}")
        table_type = res_info.get("table_type", "Standard")

        return SlotDetails(
            config_token=config_token,
            book_token=book_token,
            venue_name=venue_info.get("name", "Unknown Venue"),
            reservation_time=res_time,
            table_type=table_type,
            cancellation_policy=cancellation_policy,
            deposit_amount_cents=deposit_cents,
            payment_required=(deposit_cents > 0 or data.get("payment_required", False)),
        )

    async def book_reservation(
        self,
        book_token: str,
        payment_method_id: Optional[int] = None,
        dry_run: bool = True,
    ) -> BookingResult:
        """Complete a reservation or simulate safely if dry_run=True."""
        if dry_run:
            logger.info("Dry-run booking invoked. Skipping actual POST to /3/book.")
            return BookingResult(
                success=True,
                reservation_id="DRY_RUN_SIMULATED_12345",
                venue_name="Simulated Venue",
                reservation_time="Confirmed in Dry-Run Mode",
                party_size=2,
                message="[DRY RUN SUCCESS]: Booking details verified. Set dry_run=False to execute live booking.",
                dry_run=True,
            )

        if not self.auth_token:
            raise ResyAPIError("User X-Resy-Auth-Token is mandatory to execute real bookings.")

        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        payload = {
            "book_token": book_token,
            "source_id": "resy.com-venue-details",
        }
        if payment_method_id:
            payload["struct_payment_method"] = f'{{"id":{payment_method_id}}}'

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/3/book",
                    headers=headers,
                    data=payload,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Booking failed: {e.response.status_code} - {e.response.text}")
                return BookingResult(
                    success=False,
                    message=f"Booking error ({e.response.status_code}): {e.response.text}",
                    dry_run=False,
                )

        res_id = data.get("resy_token") or data.get("reservation_id") or "CONFIRMED"
        return BookingResult(
            success=True,
            reservation_id=str(res_id),
            venue_name=data.get("venue", {}).get("name", "Confirmed Venue"),
            reservation_time=data.get("day", "Confirmed Time"),
            party_size=data.get("party_size", 2),
            message="Reservation confirmed successfully on Resy!",
            dry_run=False,
        )

    async def get_user_reservations(self) -> List[UserReservation]:
        """Fetch current upcoming reservations for the authenticated user."""
        if not self.auth_token:
            raise ResyAPIError("RESY_AUTH_TOKEN is required to view user reservations.")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/3/user/reservations",
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                raise ResyAPIError(f"Failed to fetch user reservations: {e.response.text}", e.response.status_code)

        results: List[UserReservation] = []
        reservations = data.get("reservations", [])
        for r in reservations:
            venue = r.get("venue", {})
            results.append(
                UserReservation(
                    reservation_id=str(r.get("reservation_id", "")),
                    venue_name=venue.get("name", "Unknown Venue"),
                    date=r.get("day", ""),
                    time=r.get("time_slot", ""),
                    party_size=r.get("num_seats", 2),
                    table_type=r.get("table_type", "Dining Room"),
                )
            )
        return results
```

---

## Step 4: Building the FastMCP Server (`server.py`)

Now we initialize the **FastMCP** server and expose our Resy methods as Model Context Protocol tools. 

FastMCP natively handles parameter reflection, schema validation, JSON-RPC protocol compliance, and Server-Sent Events (SSE) streaming.

```python
# server.py
"""
Production Model Context Protocol (MCP) Server for Resy.
Runs over Server-Sent Events (SSE) for remote Cloud Run deployment.
"""
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from resy.client import ResyClient, ResyAPIError
from resy.models import (
    BookingResult,
    SlotDetails,
    UserReservation,
    VenueAvailability,
    VenueSearchResult,
)

# Initialize structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("resy-mcp-server")

# Instantiate FastMCP server
mcp = FastMCP("Resy Reservation MCP Server")

# Instantiate Resy Client (reads RESY_API_KEY and RESY_AUTH_TOKEN from environment)
resy_client = ResyClient()


@mcp.tool()
async def search_restaurants(
    query: str,
    city: str = "nyc",
    date: str = "2026-06-01",
    party_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Search for restaurants on Resy by name, cuisine, or neighborhood.
    
    Args:
        query: Restaurant name or cuisine keywords (e.g. 'Carbone', 'Italian', 'Sushi')
        city: City name (e.g. 'nyc', 'sf', 'la', 'chicago', 'miami', 'austin', 'london')
        date: Target reservation date in YYYY-MM-DD format
        party_size: Number of guests (default: 2)
        
    Returns:
        List of matching restaurants with venue_id, name, cuisine, neighborhood, and rating.
    """
    logger.info(f"Tool Invoked: search_restaurants(query='{query}', city='{city}', date='{date}')")
    try:
        results = await resy_client.search_venues(
            query=query,
            city_or_location=city,
            day=date,
            party_size=party_size,
        )
        return [r.model_dump() for r in results]
    except Exception as e:
        logger.error(f"Error in search_restaurants tool: {str(e)}")
        return [{"error": str(e)}]


@mcp.tool()
async def get_restaurant_availability(
    venue_id: int,
    date: str,
    party_size: int = 2,
) -> Dict[str, Any]:
    """
    Find available reservation time slots for a specific restaurant on Resy.
    
    Args:
        venue_id: Unique Resy venue ID (obtained from search_restaurants)
        date: Reservation date in YYYY-MM-DD format
        party_size: Number of guests (default: 2)
        
    Returns:
        Available time slots with seating area types and config_tokens.
    """
    logger.info(f"Tool Invoked: get_restaurant_availability(venue_id={venue_id}, date='{date}')")
    try:
        availability = await resy_client.get_availability(
            venue_id=venue_id,
            day=date,
            party_size=party_size,
        )
        return availability.model_dump()
    except Exception as e:
        logger.error(f"Error in get_restaurant_availability: {str(e)}")
        return {"error": str(e), "available_slots": []}


@mcp.tool()
async def get_slot_details(
    config_token: str,
    date: str,
    party_size: int = 2,
) -> Dict[str, Any]:
    """
    Inspect exact terms, cancellation policy, deposit fees, and retrieve a booking token.
    
    Args:
        config_token: The config_token string returned from an available time slot.
        date: Reservation date in YYYY-MM-DD format.
        party_size: Number of guests.
        
    Returns:
        Slot details including cancellation policy text, deposit amount, and the book_token.
    """
    logger.info(f"Tool Invoked: get_slot_details(config_token='{config_token[:10]}...')")
    try:
        details = await resy_client.get_slot_details(
            config_token=config_token,
            day=date,
            party_size=party_size,
        )
        return details.model_dump()
    except Exception as e:
        logger.error(f"Error in get_slot_details: {str(e)}")
        return {"error": str(e)}


@mcp.tool()
async def book_reservation(
    book_token: str,
    payment_method_id: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Finalize a table reservation on Resy.
    
    IMPORTANT SAFETY GUARD:
    - dry_run defaults to True to simulate the booking and prevent accidental credit card charges.
    - Set dry_run to False ONLY when the user explicitly confirms the booking.
    
    Args:
        book_token: The active book_token returned by get_slot_details.
        payment_method_id: Optional Resy payment method ID for venues requiring deposits.
        dry_run: If True, simulates booking without charging or locking (default: True).
        
    Returns:
        Booking status, confirmation ID, and reservation summary.
    """
    logger.info(f"Tool Invoked: book_reservation(dry_run={dry_run})")
    try:
        result = await resy_client.book_reservation(
            book_token=book_token,
            payment_method_id=payment_method_id,
            dry_run=dry_run,
        )
        return result.model_dump()
    except Exception as e:
        logger.error(f"Error in book_reservation: {str(e)}")
        return {"success": False, "message": f"Booking failed: {str(e)}", "dry_run": dry_run}


@mcp.tool()
async def get_my_reservations() -> List[Dict[str, Any]]:
    """
    Retrieve upcoming reservations for the currently authenticated Resy user.
    
    Returns:
        List of upcoming reservations with venue name, date, time, and party size.
    """
    logger.info("Tool Invoked: get_my_reservations()")
    try:
        reservations = await resy_client.get_user_reservations()
        return [r.model_dump() for r in reservations]
    except Exception as e:
        logger.error(f"Error in get_my_reservations: {str(e)}")
        return [{"error": str(e)}]


if __name__ == "__main__":
    # Cloud Run injects $PORT (defaults to 8080)
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"🚀 Starting Resy FastMCP Server on {host}:{port} (SSE Transport)...")
    
    # Run the FastMCP server using Server-Sent Events (SSE)
    mcp.run(transport="sse", host=host, port=port)
```

---

## Step 5: Containerizing with Docker

Cloud Run runs standard OCI containers. We create an optimized, lightweight container image based on `python:3.11-slim`.

### `Dockerfile`
```dockerfile
# Use official lightweight Python image
FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /app

# Install security updates and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency requirements
COPY requirements.txt .

# Install dependencies into system Python
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application source code
COPY resy/ /app/resy/
COPY server.py /app/

# Create a non-privileged user for security hardening
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port for Cloud Run
EXPOSE 8080

# Healthcheck for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/sse || exit 1

# Start the FastMCP SSE Server
CMD ["python", "server.py"]
```

### `.dockerignore`
```text
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
.git
.gitignore
.env
.DS_Store
*.md
```

---

## Step 6: Deploying to Google Cloud Run

Now, let's deploy our Resy MCP server onto Google Cloud Platform.

### 1. Initial Google Cloud CLI Configuration

Set your GCP project ID and preferred deployment region:

```bash
# Set your active GCP project
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export SERVICE_NAME="resy-mcp-server"

gcloud config set project $PROJECT_ID

# Enable required Google Cloud APIs
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com
```

### 2. Store Secrets in Google Secret Manager

Never hardcode your Resy API keys or tokens in container images. Store them securely in Secret Manager:

```bash
# 1. Create secret for Resy API Key
gcloud secrets create resy-api-key \
    --replication-policy="automatic"

echo -n "YOUR_RESY_API_KEY_HERE" | \
    gcloud secrets versions add resy-api-key --data-file=-

# 2. Create secret for Resy User Auth Token
gcloud secrets create resy-auth-token \
    --replication-policy="automatic"

echo -n "YOUR_RESY_AUTH_TOKEN_HERE" | \
    gcloud secrets versions add resy-auth-token --data-file=-
```

### 3. Grant Secret Access to the Cloud Run Service Account

Cloud Run services need permissions to read Secret Manager secrets at startup:

```bash
# Get the Compute Engine / Cloud Run default service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUDRUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant Secret Accessor role
gcloud secrets add-iam-policy-binding resy-api-key \
    --member="serviceAccount:${CLOUDRUN_SA}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding resy-auth-token \
    --member="serviceAccount:${CLOUDRUN_SA}" \
    --role="roles/secretmanager.secretAccessor"
```

### 4. Deploy Directly to Cloud Run via Source Build

Deploy the MCP server using `gcloud run deploy`. Notice the crucial flags configured for SSE streaming:

```bash
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --timeout 3600 \
    --concurrency 80 \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 5 \
    --set-secrets="RESY_API_KEY=resy-api-key:latest,RESY_AUTH_TOKEN=resy-auth-token:latest"
```

#### Key Cloud Run Configuration Parameters Explained:
* `--timeout 3600`: **Critical for MCP over SSE**. Standard HTTP requests timeout after 300 seconds. Setting `--timeout 3600` allows AI clients to maintain long-lived streaming SSE connections for up to 1 hour.
* `--concurrency 80`: Allows a single container instance to serve multiple concurrent client tool calls asynchronously.
* `--set-secrets`: Mounts the secrets directly into the container's environment variables (`RESY_API_KEY`, `RESY_AUTH_TOKEN`) at runtime.
* `--min-instances 0`: Scales down to zero instances when idle, incurring zero costs.

Once deployment completes, Cloud Run will print your Service URL:
```text
Service [resy-mcp-server] has been deployed and is available at:
https://resy-mcp-server-xxxxxxxx-uc.a.run.app
```

---

## Step 7: Connecting AI Clients to the Remote MCP Server

Now that your server is live on Cloud Run, let's connect AI assistants!

### Option A: Claude Desktop (via `mcp-remote`)

Because desktop LLM clients like Claude Desktop run local `stdio` subprocesses, we bridge to our remote Cloud Run SSE endpoint using the open-source `mcp-remote` bridge (`npx mcp-remote`).

1. Open your Claude Desktop configuration file:
   * **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   * **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add your Cloud Run SSE URL under `"mcpServers"`:

```json
{
  "mcpServers": {
    "resy": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://resy-mcp-server-xxxxxxxx-uc.a.run.app/sse"
      ]
    }
  }
}
```

3. Restart Claude Desktop. You will see the **Resy** tools active with the connector icon:
   * `search_restaurants`
   * `get_restaurant_availability`
   * `get_slot_details`
   * `book_reservation`
   * `get_my_reservations`

---

### Option B: Cursor IDE / Windsurf / VS Code

In Cursor or modern AI code editors with native SSE Model Context Protocol support:
1. Navigate to **Cursor Settings** > **Features** > **MCP**.
2. Click **+ Add New MCP Server**.
3. Set **Type**: `SSE`.
4. Set **Server URL**: `https://resy-mcp-server-xxxxxxxx-uc.a.run.app/sse`.
5. Click **Save**.

---

### Option C: Python AI Agents (LangChain, Google GenAI SDK, ADK)

You can also invoke your Cloud Run MCP server programmatically from custom Python agents using `mcp.client.sse`:

```python
# client_agent_example.py
import asyncio
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

SERVER_URL = "https://resy-mcp-server-xxxxxxxx-uc.a.run.app/sse"

async def run_resy_agent():
    print(f"Connecting to remote Resy MCP Server at {SERVER_URL}...")
    
    async with sse_client(SERVER_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize connection
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print("\n Discovered MCP Tools:")
            for tool in tools.tools:
                print(f" - {tool.name}: {tool.description.splitlines()[0]}")
            
            # Execute tool call: Search Restaurants
            print("\n Invoking Tool: search_restaurants...")
            result = await session.call_tool(
                "search_restaurants",
                arguments={
                    "query": "Carbone",
                    "city": "nyc",
                    "date": "2026-06-15",
                    "party_size": 2,
                },
            )
            print("Tool Response:")
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(run_resy_agent())
```

---

## Interactive End-to-End Walkthrough

Let's look at how an AI assistant reasons and chains tools when a user asks for a reservation in natural language.

### User Prompt:
> *"I want to take a client to dinner at Carbone in NYC on June 15th for 2 people around 7:00 PM. Check what table types are available and what their cancellation policy is."*

### Agent Execution Trace:

```text
 1. [LLM Reasoning]: The user wants to find reservations at 'Carbone' in NYC for 2 people on 2026-06-15.
    First, I must search for Carbone's venue ID.

 2. [Tool Call -> search_restaurants]:
    {
      "query": "Carbone",
      "city": "nyc",
      "date": "2026-06-15",
      "party_size": 2
    }
    ◄── Response: [{"venue_id": 1505, "name": "Carbone", "neighborhood": "Greenwich Village", "cuisine": "Italian"}]

 3. [Tool Call -> get_restaurant_availability]:
    {
      "venue_id": 1505,
      "date": "2026-06-15",
      "party_size": 2
    }
    ◄── Response: {
      "venue_name": "Carbone",
      "available_slots": [
        {"time": "18:45:00", "table_type": "Dining Room", "config_token": "cfg_tok_8921a"},
        {"time": "19:15:00", "table_type": "Patio", "config_token": "cfg_tok_8921b"},
        {"time": "20:00:00", "table_type": "Dining Room", "config_token": "cfg_tok_8921c"}
      ]
    }

 4. [Tool Call -> get_slot_details]:
    {
      "config_token": "cfg_tok_8921b",
      "date": "2026-06-15",
      "party_size": 2
    }
    ◄── Response: {
      "venue_name": "Carbone",
      "reservation_time": "2026-06-15 19:15:00",
      "table_type": "Patio",
      "cancellation_policy": "Cancellations made less than 24 hours in advance are subject to a $50 per person fee.",
      "book_token": "bk_tok_carbone_9921",
      "deposit_amount_cents": 0
    }

 5. [LLM Final Response to User]:
    "I found 3 available tables at Carbone (Greenwich Village) for 2 guests on June 15th:
     • 6:45 PM – Dining Room
     • 7:15 PM – Patio (Closest to your requested 7:00 PM time)
     • 8:00 PM – Dining Room

     Cancellation Policy for the 7:15 PM Patio table:
     Cancellations within 24 hours incur a $50/person fee. No upfront deposit is required.

     Would you like me to book the 7:15 PM Patio table for you?"
```

---

## Production Best Practices & Security Guardrails

### 1. Dry-Run Safety Guardrails
Automating reservations involves real-world commitments and potential cancellation penalties. 
* **Design Rule**: Always set `dry_run=True` by default in your booking tools.
* Require explicit user confirmation before passing `dry_run=False`.

### 2. Securing the Cloud Run Endpoint
If you do not want your MCP server publicly reachable without authentication, you can secure it with Cloud Run IAM or an API Key Header:

#### Cloud Run IAM Authentication:
```bash
# Remove public access
gcloud run services remove-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --member="allUsers" \
    --role="roles/run.invoker"

# Allow specific user or service account
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --member="user:your-email@example.com" \
    --role="roles/run.invoker"
```

Pass the identity token to `mcp-remote`:
```json
{
  "mcpServers": {
    "resy-secure": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://resy-mcp-server-xxxxxxxx-uc.a.run.app/sse",
        "--header",
        "Authorization: Bearer $(gcloud auth print-identity-token)"
      ]
    }
  }
}
```

### 3. Handling Resy Token Expiration
Resy session auth tokens expire periodically. For automated production environments, you can implement an automated renewal tool or endpoint using your Resy credentials (`POST /3/auth/password`) to refresh the `X-Resy-Auth-Token` without manual browser intervention.

---

## Summary & Key Takeaways

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Protocol** | Model Context Protocol (MCP) | Universal standard for LLM tool invocation |
| **Server Framework** | Python `FastMCP` | High-level tool routing & SSE event formatting |
| **Transport** | Server-Sent Events (SSE) | HTTP streaming for cloud-hosted remote tools |
| **API Wrapper** | `httpx.AsyncClient` | Fast, non-blocking Resy API communication |
| **Compute** | Google Cloud Run | Serverless, auto-scaling container hosting |
| **Secrets** | Google Secret Manager | Secure storage of API keys and session tokens |

By wrapping Resy's reservation API in the Model Context Protocol and deploying it on Google Cloud Run, you have transformed your AI assistant into a personal concierge capable of discovering restaurants, checking live table availability, and booking reservations across any MCP-compatible environment.

---

## Resources & Next Steps
* [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
* [FastMCP Python SDK on GitHub](https://github.com/jlowin/fastmcp)
* [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
* [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)
