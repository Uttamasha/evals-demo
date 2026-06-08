"""Fake tool schemas exposed to the model. This is the 'system under test'."""

SEARCH_FLIGHTS = {
    "name": "search_flights",
    "description": "Search for flights to a destination on a given date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dest": {"type": "string", "description": "City or airport code."},
            "date": {"type": "string", "description": "Departure date, e.g. 2026-06-15."},
        },
        "required": ["dest"],
    },
}

SEARCH_HOTELS = {
    "name": "search_hotels",
    "description": "Search for hotels in a city for a number of nights.",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name."},
            "nights": {"type": "integer", "description": "Number of nights."},
        },
        "required": ["city"],
    },
}

TOOL_SCHEMAS = [SEARCH_FLIGHTS, SEARCH_HOTELS]
