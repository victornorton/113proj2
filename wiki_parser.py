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
    "persia":                           "iran",
    "burma":                            "myanmar",
    "dprk":                             "north korea",
    "prc":                              "china"

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
    response = requests.get(WIKIPEDIA_API_URL, headers=headers, timeout=10)

    # HTTP status 200 means "OK". Anything else (404, 500, etc.) is a problem.
    if response.status_code != 200:
        print(response.text[:500])
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
    # Split the wikitext into table rows. Each row begins with "|-"
    rows = wikitext.split("|-")

    # This pattern matches Wikipedia internal links of the form:
    # [[Some Article Title|Display Name]]
    # We capture the display name (the part after the "|")
    # The \[\[ and \]\] match literal double square brackets
    link_pattern = re.compile(r"\[\[[^\]]+\|([^\]]+)\]\]")

    # This pattern checks whether a row contains a flagicon template,
    # which is how we identify rows that represent a country.
    # Every country row starts with {{flagicon|Country Name}}
    flagicon_pattern = re.compile(r"\{\{flagicon\|", re.IGNORECASE)

    countries = []

    for row in rows:
        if len(countries) >= top_n:
            break

        # Skip rows that don't contain a flagicon — these are headers,
        # footers, or other non-country rows
        if not flagicon_pattern.search(row):
            continue

        # Find all internal links in this row and take the first one,
        # which corresponds to the country name
        matches = link_pattern.findall(row)
        if not matches:
            continue

        country_name = matches[0].strip().lower()
        countries.append(country_name)
        print(f"  #{len(countries):>2}: {country_name}")

    if len(countries) < top_n:
        print(
            f"\nWARNING: Only found {len(countries)} countries instead of {top_n}. "
            "You may need to inspect more rows in wikitext_sample.txt."
        )

    return countries


def parse_top_populations(wikitext: str, top_n: int = TOP_N) -> list[str]:
    """
    Parses the wikitext to extract the population figure for each of the
    top N countries, in the same rank order as parse_top_countries().

    The population figures are stored in the wikitext inside templates like:
        {{n+p|341784857|{{worldpop}}|sigfig=2|disp=table}}
    We extract the first argument (the raw number) from each such template.

    Returns a list of population strings in rank order, e.g.:
        ["1,419,321,278", "1,407,563,842", ...]
    The figures are formatted with commas for readability.
    """

    # This pattern matches the n+p template and captures the raw number.
    # \{\{n\+p\|  → matches the literal opening "{{n+p|"
    # (\d+)       → CAPTURE GROUP: the population number (digits only)
    # \|          → matches the "|" that follows the number
    population_pattern = re.compile(r"\{\{n\+p\|(\d+)\|")

    # Reuse the same row-splitting and flagicon-detection logic as
    # parse_top_countries() so we're iterating over exactly the same rows
    # in the same order, guaranteeing the two lists stay in sync.
    flagicon_pattern = re.compile(r"\{\{flagicon\|", re.IGNORECASE)

    rows = wikitext.split("|-")
    populations = []

    for row in rows:
        if len(populations) >= top_n:
            break

        if not flagicon_pattern.search(row):
            continue

        pop_match = population_pattern.search(row)
        if not pop_match:
            continue

        # Format the raw number string with commas for readability
        # e.g. "341784857" → "341,784,857"
        raw_number = int(pop_match.group(1))
        formatted  = f"{raw_number:,}"
        populations.append(formatted)

    if len(populations) < top_n:
        print(
            f"WARNING: Only found {len(populations)} population figures "
            f"instead of {top_n}. Check the wikitext structure."
        )

    return populations

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

    #human written test:
    print("\nTesting Population:\n")
    pop = parse_top_populations(wikitext)
    for x in pop:
        print(f"{x}\n")
