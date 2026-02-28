"""
wiki_parser.py
--------------
Fetches the Wikipedia article "List of countries and dependencies by population"
and parses out the top 20 most populous countries.

HOW IT WORKS AT A HIGH LEVEL:
  1. We send an HTTP request to Wikipedia's free API asking for the raw text of
     the article (called "wikitext" — Wikipedia's own markup language).
  2. We search that raw text for the data table, which lists countries row by row.
  3. We extract the country name from each row until we have the top 20.
  4. We store those names in a normalised (lowercased, stripped) form so that
     later we can do forgiving comparisons against user guesses.

DEPENDENCIES:
  pip install requests
"""

import re
import requests


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# This is the Wikipedia API endpoint. It's a free, public URL — no key needed.
# Parameters explained:
#   action=parse  → we want parsed article content
#   page=...      → the exact article title (spaces replaced with underscores)
#   prop=wikitext → we want the raw wikitext markup, not rendered HTML
#   format=json   → return the response as JSON so Python can read it easily
WIKIPEDIA_API_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=parse"
    "&page=List_of_countries_and_dependencies_by_population"
    "&prop=wikitext"
    "&format=json"
)

# How many top entries we want to extract
TOP_N = 20

# A dictionary of common alternate names/spellings that users might type,
# mapped to the canonical name as it appears (normalised) from Wikipedia.
# You can expand this list as you discover gaps during testing.
ALIASES = {
    "usa":                              "united states",
    "us":                               "united states",
    "america":                          "united states",
    "united states of america":         "united states",
    "dr congo":                         "democratic republic of the congo",
    "drc":                              "democratic republic of the congo",
    "congo":                            "democratic republic of the congo",
    "republic of the congo":            "democratic republic of the congo",
    "uk":                               "united kingdom",
    "britain":                          "united kingdom",
    "great britain":                    "united kingdom",
    "england":                          "united kingdom",
    "south korea":                      "korea, south",   # adjust if Wikipedia uses a different form
    "north korea":                      "korea, north",
    "iran":                             "iran",
    "persia":                           "iran",
    "myanmar":                          "myanmar",
    "burma":                            "myanmar",
}


# ---------------------------------------------------------------------------
# Step 1: Fetch the raw wikitext from Wikipedia
# ---------------------------------------------------------------------------

def fetch_wikitext() -> str:
    """
    Sends a GET request to the Wikipedia API and returns the raw wikitext
    string for the population article.

    Returns:
        The raw wikitext as a string.

    Raises:
        RuntimeError if the request fails or the expected data isn't found.
    """
    print("Fetching article from Wikipedia API...")

    # Wikipedia's API requires a descriptive User-Agent header, or it returns 403.
    # This is part of their API etiquette policy. The string should identify your
    # app and provide a contact point. Adjust the name/email to your own details.
    headers = {
        "User-Agent": "PopulationQuizApp/1.0 (https://github.com/victornorton/113proj2; vanorton@andrew.cmu.edu)"
    }

    # requests.get() sends an HTTP GET request — like your browser visiting a URL.
    # The response object holds the status code and body of the reply.
    response = requests.get(WIKIPEDIA_API_URL, timeout=10)

    # HTTP status 200 means "OK". Anything else (404, 500, etc.) is a problem.
    if response.status_code != 200:
        raise RuntimeError(
            f"Wikipedia API returned status code {response.status_code}. "
            "Check your internet connection or the article name."
        )

    # response.json() parses the JSON body into a Python dictionary.
    data = response.json()

    # Navigate the nested dictionary to get to the wikitext.
    # The structure is: data → "parse" → "wikitext" → "*"
    try:
        wikitext = data["parse"]["wikitext"]["*"]
    except KeyError:
        raise RuntimeError(
            "Unexpected API response structure. Wikipedia may have changed its format."
        )

    print(f"Successfully fetched wikitext ({len(wikitext):,} characters).")
    return wikitext


# ---------------------------------------------------------------------------
# Step 2: Parse the wikitext to extract country names
# ---------------------------------------------------------------------------

def parse_top_countries(wikitext: str, top_n: int = TOP_N) -> list[str]:
    """
    Parses raw Wikipedia wikitext to extract the top N country names by
    population, in ranked order.

    HOW THE WIKITEXT TABLE WORKS:
    Wikipedia tables use a specific markup syntax. Each row starts with "|-"
    and cells are separated by "||" or start with "|". A typical data row
    for a country looks roughly like this (simplified):

        |-
        | 1 || {{flag|China}} || ... population figures ...

    The country name is wrapped in a template like {{flag|China}} or
    {{flagcountry|United States}}. We use a regular expression (regex) to
    find these templates and pull out the country name.

    Args:
        wikitext: The raw wikitext string from the Wikipedia API.
        top_n:    How many countries to extract (default 20).

    Returns:
        A list of country name strings, normalised to lowercase, in rank order.
    """

    # A regex pattern to find country names inside flag templates.
    # Breakdown of the pattern:
    #   \{\{          → matches the literal opening "{{"
    #   flag[^\|]*    → matches "flag", "flagcountry", "flagdeco", etc. (any flag template)
    #   \|            → matches the "|" separator inside the template
    #   ([^\|\}]+)    → CAPTURE GROUP: the country name (anything that isn't "|" or "}")
    #   [\|\}]        → matches the next "|" or "}" that ends the name
    #
    # Example match: {{flag|India}} → captures "India"
    flag_pattern = re.compile(r"\{\{flag[^\|]*\|([^\|\}]+)[\|\}]", re.IGNORECASE)

    # We also want to capture rank numbers so we can confirm we're reading rows
    # in order. Rows with a rank number look like: | 1 || or | 1\n
    rank_pattern = re.compile(r"^\|\s*(\d+)\s*[\|\n]", re.MULTILINE)

    # Split the wikitext into lines for row-by-row processing.
    # Table rows begin with "|-", so we split on that to get individual rows.
    rows = wikitext.split("|-")

    countries = []  # We'll build up our list here

    for row in rows:
        # Stop once we have enough countries
        if len(countries) >= top_n:
            break

        # Check if this row contains a rank number in the expected range.
        # This helps us skip header rows, footer rows, and footnotes.
        rank_match = rank_pattern.search(row)
        if not rank_match:
            continue  # No rank found — skip this row

        rank = int(rank_match.group(1))

        # We only care about ranks 1 through top_n
        if rank < 1 or rank > top_n:
            continue

        # Look for a flag template in this row to get the country name
        flag_match = flag_pattern.search(row)
        if not flag_match:
            continue  # No country name found in this row — skip

        # Extract and clean the country name
        country_name = flag_match.group(1).strip()

        # Normalise to lowercase so comparisons are case-insensitive
        country_name_normalised = country_name.lower()

        countries.append(country_name_normalised)
        print(f"  #{rank:>2}: {country_name}")

    if len(countries) < top_n:
        print(
            f"\nWARNING: Only found {len(countries)} countries instead of {top_n}. "
            "The Wikipedia article structure may have changed. "
            "You may need to update the regex patterns in parse_top_countries()."
        )

    return countries


# ---------------------------------------------------------------------------
# Step 3: Normalise a user's guess for comparison
# ---------------------------------------------------------------------------

def normalise_guess(guess: str) -> str:
    """
    Cleans up a user's guess so it can be fairly compared against our list.

    Steps:
      - Strip leading/trailing whitespace
      - Convert to lowercase
      - Check the ALIASES dictionary for known alternate names

    Args:
        guess: The raw string the user typed.

    Returns:
        A normalised string ready for comparison.
    """
    cleaned = guess.strip().lower()

    # If the user typed a known alias (e.g. "USA"), replace it with the
    # canonical form (e.g. "united states") before checking
    if cleaned in ALIASES:
        cleaned = ALIASES[cleaned]

    return cleaned


# ---------------------------------------------------------------------------
# Step 4: The main checking function (this is what Flask will call later)
# ---------------------------------------------------------------------------

def check_guess(guess: str, top_countries: list[str]) -> dict:
    """
    Checks whether a user's guess is in the top 20 countries list.

    Args:
        guess:         The raw string the user typed.
        top_countries: The normalised list returned by parse_top_countries().

    Returns:
        A dictionary with:
          "correct" (bool)   → True if the guess is in the top 20
          "rank"    (int|None) → The 1-based rank if correct, else None
          "normalised" (str) → The normalised form of the guess (useful for debugging)
    """
    normalised = normalise_guess(guess)

    if normalised in top_countries:
        # list.index() returns the 0-based position; add 1 for human-readable rank
        rank = top_countries.index(normalised) + 1
        return {"correct": True, "rank": rank, "normalised": normalised}
    else:
        return {"correct": False, "rank": None, "normalised": normalised}


# ---------------------------------------------------------------------------
# Quick test — runs only when you execute this file directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Fetch and parse the list
    wikitext = fetch_wikitext()
    print("\nParsing top 20 countries...\n")
    top_countries = parse_top_countries(wikitext)

    print(f"\nFinal list ({len(top_countries)} countries):")
    for i, country in enumerate(top_countries, start=1):
        print(f"  {i:>2}. {country}")

    # Test a few guesses
    print("\nTesting guess checks:")
    test_guesses = ["India", "USA", "usa", "France", "DR Congo", "  pakistan  "]
    for g in test_guesses:
        result = check_guess(g, top_countries)
        status = f"CORRECT (rank #{result['rank']})" if result["correct"] else "WRONG"
        print(f"  '{g}' → normalised to '{result['normalised']}' → {status}")