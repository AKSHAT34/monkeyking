"""Location hierarchy and aliases for geographic matching.

Usage:
  from location_data import location_matches
  location_matches("Bangalore, India", ["India"])  # True
  location_matches("Bengaluru", ["Bangalore"])      # True
  location_matches("San Francisco, CA", ["US"])     # True
  location_matches("Remote", ["Remote - India"])    # needs job to mention India
  location_matches("Remote", ["Remote - Worldwide"]) # True
"""

# Country → cities/states mapping
COUNTRY_CITIES: dict[str, set[str]] = {
    "india": {
        "bangalore", "bengaluru", "mumbai", "bombay", "delhi", "new delhi",
        "hyderabad", "pune", "chennai", "madras", "kolkata", "calcutta",
        "gurgaon", "gurugram", "noida", "ghaziabad", "greater noida",
        "ahmedabad", "jaipur", "lucknow", "chandigarh", "indore", "bhopal",
        "kochi", "cochin", "thiruvananthapuram", "trivandrum", "coimbatore",
        "nagpur", "visakhapatnam", "vizag", "mysore", "mysuru", "mangalore",
        "mangaluru", "surat", "vadodara", "baroda", "rajkot", "nashik",
        "patna", "ranchi", "bhubaneswar", "guwahati", "dehradun",
        "shimla", "jammu", "srinagar", "amritsar", "ludhiana",
        "karnataka", "maharashtra", "tamil nadu", "telangana", "andhra pradesh",
        "kerala", "west bengal", "uttar pradesh", "rajasthan", "gujarat",
        "madhya pradesh", "haryana", "punjab", "bihar", "odisha",
        "delhi ncr", "ncr",
    },
    "us": {
        "san francisco", "new york", "nyc", "manhattan", "brooklyn",
        "los angeles", "la", "seattle", "austin", "boston", "chicago",
        "denver", "portland", "san diego", "san jose", "silicon valley",
        "palo alto", "mountain view", "sunnyvale", "cupertino", "menlo park",
        "redwood city", "santa clara", "oakland", "berkeley",
        "washington dc", "dc", "arlington", "reston", "mclean",
        "atlanta", "dallas", "houston", "phoenix", "philadelphia",
        "miami", "tampa", "orlando", "minneapolis", "detroit",
        "pittsburgh", "raleigh", "durham", "charlotte", "nashville",
        "salt lake city", "columbus", "indianapolis", "kansas city",
        "california", "texas", "washington", "massachusetts",
        "new york state", "illinois", "colorado", "oregon",
        "georgia", "florida", "virginia", "north carolina",
        "pennsylvania", "ohio", "michigan", "minnesota",
    },
    "uk": {
        "london", "manchester", "birmingham", "edinburgh", "glasgow",
        "bristol", "leeds", "liverpool", "cambridge", "oxford",
        "reading", "cardiff", "belfast", "nottingham", "sheffield",
        "england", "scotland", "wales", "northern ireland",
    },
    "canada": {
        "toronto", "vancouver", "montreal", "ottawa", "calgary",
        "edmonton", "winnipeg", "quebec", "halifax", "victoria",
        "ontario", "british columbia", "alberta", "quebec province",
    },
    "singapore": {"singapore"},
    "uae": {
        "dubai", "abu dhabi", "sharjah",
        "united arab emirates",
    },
    "germany": {
        "berlin", "munich", "münchen", "hamburg", "frankfurt",
        "cologne", "köln", "stuttgart", "düsseldorf", "dortmund",
    },
    "australia": {
        "sydney", "melbourne", "brisbane", "perth", "adelaide",
        "canberra", "gold coast",
    },
    "japan": {"tokyo", "osaka", "kyoto", "yokohama"},
    "ireland": {"dublin", "cork", "galway"},
    "netherlands": {"amsterdam", "rotterdam", "the hague", "eindhoven"},
    "france": {"paris", "lyon", "marseille", "toulouse"},
    "israel": {"tel aviv", "jerusalem", "haifa"},
}

# City aliases (both directions)
CITY_ALIASES: dict[str, str] = {
    "bengaluru": "bangalore",
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "mumbai": "bombay",
    "madras": "chennai",
    "chennai": "madras",
    "calcutta": "kolkata",
    "kolkata": "calcutta",
    "gurugram": "gurgaon",
    "gurgaon": "gurugram",
    "cochin": "kochi",
    "kochi": "cochin",
    "trivandrum": "thiruvananthapuram",
    "thiruvananthapuram": "trivandrum",
    "vizag": "visakhapatnam",
    "visakhapatnam": "vizag",
    "mysuru": "mysore",
    "mysore": "mysuru",
    "mangaluru": "mangalore",
    "mangalore": "mangaluru",
    "baroda": "vadodara",
    "vadodara": "baroda",
    "nyc": "new york",
    "new york": "nyc",
    "la": "los angeles",
    "los angeles": "la",
    "dc": "washington dc",
    "washington dc": "dc",
    "münchen": "munich",
    "munich": "münchen",
    "köln": "cologne",
    "cologne": "köln",
}

# Country name aliases
COUNTRY_ALIASES: dict[str, str] = {
    "united states": "us",
    "usa": "us",
    "united states of america": "us",
    "america": "us",
    "united kingdom": "uk",
    "great britain": "uk",
    "britain": "uk",
    "england": "uk",
    "united arab emirates": "uae",
    "deutschland": "germany",
}


def _normalize(s: str) -> str:
    """Lowercase, strip, remove extra spaces."""
    return " ".join(s.lower().strip().split())


def _get_country_for_city(city: str) -> str | None:
    """Find which country a city belongs to."""
    city_n = _normalize(city)
    for country, cities in COUNTRY_CITIES.items():
        if city_n in cities:
            return country
    return None


def _expand_location(loc: str) -> set[str]:
    """Expand a user's preferred location into all matching terms.
    
    'India' → {'india', 'bangalore', 'bengaluru', 'mumbai', ...}
    'Bangalore' → {'bangalore', 'bengaluru'}
    'Remote - India' → special handling
    """
    loc_n = _normalize(loc)
    terms = {loc_n}

    # Handle remote variants
    if loc_n.startswith("remote"):
        terms.add("remote")
        return terms  # Remote matching is handled separately

    # Check if it's a country alias
    resolved_country = COUNTRY_ALIASES.get(loc_n, loc_n)

    # If it's a country, add all its cities
    if resolved_country in COUNTRY_CITIES:
        terms.add(resolved_country)
        terms.update(COUNTRY_CITIES[resolved_country])
        return terms

    # It's a city — add aliases
    if loc_n in CITY_ALIASES:
        terms.add(CITY_ALIASES[loc_n])

    # Also add the country this city belongs to (for matching "Bangalore, India")
    country = _get_country_for_city(loc_n)
    if country:
        terms.add(country)
    alias = CITY_ALIASES.get(loc_n)
    if alias:
        country2 = _get_country_for_city(alias)
        if country2:
            terms.add(country2)

    return terms


def location_matches(job_location: str, preferred_locations: list[str]) -> bool:
    """Check if a job location matches any of the user's preferred locations.
    
    Handles:
    - Country matching: "India" matches "Bangalore, India", "Mumbai", etc.
    - City aliases: "Bangalore" matches "Bengaluru"
    - Remote variants: "Remote - India" matches "Remote (India)" but not "Remote (US)"
    - "Remote - Worldwide" matches any remote job
    """
    if not preferred_locations:
        return True  # No preference = match everything

    job_n = _normalize(job_location)
    if not job_n:
        return True  # Unknown location = don't filter out

    for pref in preferred_locations:
        pref_n = _normalize(pref)

        # Handle "Remote - Worldwide"
        if pref_n == "remote - worldwide" or pref_n == "remote worldwide":
            if "remote" in job_n:
                return True
            continue

        # Handle "Remote - India" (or any "Remote - Country")
        if pref_n.startswith("remote - ") or pref_n.startswith("remote "):
            country_part = pref_n.replace("remote - ", "").replace("remote ", "").strip()
            if "remote" in job_n:
                # Check if the remote job is in the specified country
                resolved = COUNTRY_ALIASES.get(country_part, country_part)
                if resolved in COUNTRY_CITIES:
                    country_terms = COUNTRY_CITIES[resolved] | {resolved}
                    # If job says "Remote" with no country qualifier, accept it
                    if job_n == "remote" or job_n == "remote work":
                        return True
                    # If job says "Remote, India" or "Remote - Bangalore"
                    if any(term in job_n for term in country_terms):
                        return True
                else:
                    # Unknown country, just check if it's in the string
                    if country_part in job_n or "remote" in job_n:
                        return True
            continue

        # Handle "Remote" (plain)
        if pref_n == "remote":
            if "remote" in job_n:
                return True
            continue

        # Standard location matching
        expanded = _expand_location(pref)
        # Check if any expanded term appears in the job location
        job_words = set(job_n.replace(",", " ").replace("-", " ").replace("/", " ").split())
        # Also check substrings for multi-word locations
        for term in expanded:
            if term in job_n or term in job_words:
                return True

    return False
