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
