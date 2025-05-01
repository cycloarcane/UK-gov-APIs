from flask import Flask, jsonify, render_template
from archives_lucky_dip import pick_online_record      # reuse our logic

app = Flask(__name__)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/random")
def api_random():
    rec = pick_online_record()
    return jsonify(
        title=rec.get("title"),
        description=rec.get("description"),
        heldBy=", ".join(rec.get("heldBy", [])),
        url=rec["view_url"],
    )

if __name__ == "__main__":
    app.run(debug=True)           # Disable debug in prod
