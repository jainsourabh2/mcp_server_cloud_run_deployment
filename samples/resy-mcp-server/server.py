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
