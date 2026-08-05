from flask import Flask, request, jsonify
import requests
import json
import time
import os

app = Flask(__name__)

# ========== ENVIRONMENT VARIABLES ==========
API_KEY = os.environ.get("API_KEY", "mysecretkey123")
BASE_URL = os.environ.get("BASE_URL", "https://movements-invoice-amanda-victoria.trycloudflare.com/search/number")
MAX_RETRIES = 3
RETRY_DELAY = 1

CREDIT = {
    "owner": "@DG_DRIFT",
    "main_channel": "@DGDRIFT",
    "likes_group": "@DGDRIFTFF",
    "apis_channel": "@driftfreeapis"
}

# ========== CUSTOM EXCEPTIONS ==========
class APIError(Exception): pass
class InvalidNumberError(APIError): pass
class RateLimitError(APIError): pass
class ServerError(APIError): pass

# ========== FETCH WITH RETRY ==========
def fetch_with_retry(number):
    if not number or not number.strip():
        raise InvalidNumberError("Phone number cannot be empty.")
    url = f"{BASE_URL}?number={number}&key={API_KEY}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # verify=False only needed for self-signed/cloudflare tunnels; remove if not needed
            resp = requests.get(url, timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json()

            # Check for API error
            if data.get("status") == "error":
                error_msg = data.get("message") or "Unknown API error"
                if "invalid" in error_msg.lower() or "not found" in error_msg.lower():
                    raise InvalidNumberError(error_msg)
                elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                    raise RateLimitError(error_msg)
                else:
                    raise APIError(error_msg)
            return data

        except requests.exceptions.Timeout:
            if attempt == MAX_RETRIES:
                raise APIError("Request timed out after multiple retries.")
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
        except requests.exceptions.ConnectionError:
            if attempt == MAX_RETRIES:
                raise APIError("Network connection error.")
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status in (400, 401, 403, 404):
                if status in (401, 403):
                    raise APIError("Invalid API key or permission denied.")
                elif status == 404:
                    raise InvalidNumberError("Number not found or invalid endpoint.")
                else:
                    raise APIError(f"Client error (HTTP {status})")
            elif 500 <= status < 600:
                if attempt == MAX_RETRIES:
                    raise ServerError(f"Server error (HTTP {status}) after retries.")
                time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
            else:
                raise APIError(f"HTTP error {status}")
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                raise APIError(f"Request failed: {e}")
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
    return None

# ========== GET NUMBER INFO ==========
def get_number_info(number):
    try:
        raw = fetch_with_retry(number)
        if not raw:
            return [], 0, None

        # Expected: { "status": "success", "result": [...] }
        records = raw.get("result", [])
        if not isinstance(records, list):
            records = []
        found = len(records)
        return records, found, None

    except (InvalidNumberError, RateLimitError, ServerError, APIError) as e:
        return [], 0, str(e)
    except Exception as e:
        return [], 0, f"Unexpected error: {e}"

# ========== ROUTES ==========
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "API is running! Use /number?num=YOUR_NUMBER",
        "credit": CREDIT
    }), 200

@app.route('/number', methods=['GET'])
def lookup_number():
    num = request.args.get('num')
    if not num:
        return jsonify({
            "error": "Missing 'num' parameter",
            "credit": CREDIT
        }), 400

    records, found, error = get_number_info(num)
    if error:
        return jsonify({
            "error": error,
            "credit": CREDIT
        }), 404 if "not found" in error.lower() else 500

    return jsonify({
        "found": found,
        "data": records,
        "credit": CREDIT
    }), 200

# ==========================================
# Vercel uses the 'app' object directly.
# The 'if __name__' block is NOT needed for Vercel,
# but you can keep it for local testing.
# ==========================================
if __name__ == "__main__":
    # Only runs when you execute 'python app.py' locally
    app.run(host="0.0.0.0", port=5000, debug=True)