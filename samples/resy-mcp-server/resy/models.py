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
