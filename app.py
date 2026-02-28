"""
app.py
------
A Flask web server that serves as the backend for the population quiz app.

It does two things:
  1. Fetches and caches the top 20 most populous countries from Wikipedia
     once when the server starts up.
  2. Exposes two HTTP endpoints that the frontend can call:
       GET  /countries  → returns the full list (useful for debugging)
       POST /check      → accepts a guess and returns whether it's correct

HOW THE FRONTEND COMMUNICATES WITH THIS SERVER:
  The frontend (running in the user's browser) sends HTTP requests to this
  server using JavaScript's fetch() function. The server responds with JSON
  — a simple text format for structured data that both Python and JavaScript
  understand natively.

DEPENDENCIES:
  pip install flask flask-cors requests
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

# Import our parsing and checking functions from the parser module we built.
# This assumes app.py and wiki_parser.py are in the same directory.
from wiki_parser import fetch_wikitext, parse_top_countries, check_guess, parse_top_populations


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

# Create the Flask application instance.
# __name__ tells Flask where to look for resources relative to this file.
app = Flask(__name__)

# Enable CORS (Cross-Origin Resource Sharing).
# By default, browsers block requests from one domain to another for security
# reasons. Since our frontend is hosted on GitHub Pages (one domain) and our
# backend is on Render (a different domain), we need to explicitly allow this.
# CORS(app) permits all origins — fine for a personal project, but in a
# production app you'd restrict this to your specific frontend URL like:
#   CORS(app, origins=["https://yourusername.github.io"])
CORS(app)


# ---------------------------------------------------------------------------
# Cache the country list on startup
# ---------------------------------------------------------------------------

# We fetch the Wikipedia data once when the server starts, not on every
# request. This is called "caching" — storing the result so we don't need
# to repeat the expensive work of fetching and parsing the article each time
# a user makes a guess.
#
# top_countries will be a list of normalised (lowercase) country name strings,
# e.g. ["china", "india", "united states", ...]
print("Fetching and parsing Wikipedia data on startup...")
try:
    _wikitext = fetch_wikitext()
    top_countries = parse_top_countries(_wikitext)
    top_populations = parse_top_populations(_wikitext)
    print(f"Ready. Cached {len(top_countries)} countries.")
except Exception as e:
    # If this fails the server will still start, but the endpoints will return
    # an error. Check your internet connection and Wikipedia API access.
    top_countries = []
    print(f"ERROR: Failed to fetch country data on startup: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/countries", methods=["GET"])
def get_countries():
    """
    GET /countries

    Returns the full cached list of top 20 countries as JSON.
    This endpoint is mainly useful for debugging — you can visit it in your
    browser to confirm the server is running and the list looks correct.

    Example response:
      {
        "countries": ["china", "india", "united states", ...],
        "count": 20
      }
    """
    if not top_countries:
        # jsonify() converts a Python dictionary into a JSON HTTP response.
        # The second argument (503) is the HTTP status code:
        # 503 means "Service Unavailable" — the server is up but can't fulfil
        # the request right now.
        return jsonify({"error": "Country data unavailable. Check server logs."}), 503

    return jsonify({
        "countries": top_countries,
        "count": len(top_countries)
    })


@app.route("/check", methods=["POST"])
def check():
    """
    POST /check

    Accepts a JSON body containing a country name guess and returns whether
    it is in the top 20.

    Expected request body:
      { "guess": "Brazil" }

    Example responses:
      { "correct": true,  "rank": 7, "normalised": "brazil" }
      { "correct": false, "rank": null, "normalised": "france" }
    """
    if not top_countries:
        return jsonify({"error": "Country data unavailable. Check server logs."}), 503

    # request.get_json() parses the JSON body sent by the frontend into a
    # Python dictionary. If the body isn't valid JSON it returns None.
    data = request.get_json()

    if not data or "guess" not in data:
        # 400 means "Bad Request" — the client sent something we can't use.
        return jsonify({"error": "Request body must be JSON with a 'guess' field."}), 400

    guess = data["guess"]

    # Defend against empty or non-string guesses
    if not isinstance(guess, str) or not guess.strip():
        return jsonify({"error": "'guess' must be a non-empty string."}), 400

    # Use the check_guess function from our parser module
    result = check_guess(guess, top_countries)

    # jsonify() converts the result dictionary to a JSON response with
    # HTTP status 200 (OK) by default

    #add populatiion for correct guesses:
    if result["correct"]:
        result["population"] = top_populations[result["rank"] - 1]
    return jsonify(result)


# ---------------------------------------------------------------------------
# Run the server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # debug=True enables helpful error messages in the browser and auto-reloads
    # the server when you save changes to the file. Turn this OFF in production.
    #
    # The server will be accessible at http://127.0.0.1:5000 while running locally.
    app.run(debug=True)