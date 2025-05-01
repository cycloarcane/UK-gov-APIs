#!/usr/bin/env python3
"""
Flask wrapper for the lucky-dip helper.

Routes:
  • /           – HTML interface
  • /api/random – JSON -> {query, title, description, heldBy, url}
"""

from flask import Flask, jsonify, render_template
from archives_lucky_dip import pick_online_record

app = Flask(__name__)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/random")
def api_random():
    rec = pick_online_record()
    return jsonify(
        query       = rec["query"],
        title       = rec.get("title"),
        description = rec.get("description"),
        heldBy      = ", ".join(rec.get("heldBy", [])),
        url         = rec["view_url"],
    )

if __name__ == "__main__":
    app.run(debug=True)   # turn off debug in production
