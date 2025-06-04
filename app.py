import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime
import base64
import google.generativeai as genai
from typing import Optional

# Allow OAuth over HTTP when running locally. Remove or change for production.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/script.external_request",
]
GENAI_MODEL = "models/gemini-1.5-pro-latest"

# path to OAuth2 credentials obtained from Google Cloud console
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")


def parse_analysis(text: str):
    """Extract analysis fields from Gemini response text."""
    if not text:
        return None
    cleaned = text.strip()

    # Remove Markdown code fences such as ```json
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned.split("\n", 1)[-1]
    cleaned = cleaned.strip()

    # First try to parse a JSON object directly
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: parse lines like "カテゴリ名: ..." etc.
    result = {}
    m = re.search(r"カテゴリ(?:名)?[:：]\s*(.+)", cleaned)
    if m:
        result["カテゴリ名"] = m.group(1).strip()
    m = re.search(r"タグ[:：]\s*(.+)", cleaned)
    if m:
        tags_raw = m.group(1).strip()
        tags = re.split(r"[、,\s]+", tags_raw)
        result["タグ"] = [t for t in tags if t][:2]
    m = re.search(r"サマリー[:：]\s*(.+)", cleaned)
    if m:
        result["サマリー"] = m.group(1).strip()

    return result if result else None


def validate_gemini_key(api_key: str) -> bool:
    """Return True if the Gemini API key appears valid."""
    try:
        genai.configure(api_key=api_key)
        next(genai.list_models(page_size=1))
        return True
    except Exception as e:
        print("Gemini key validation failed:", e, flush=True)
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("oauth2callback", _external=True),
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    return redirect(url_for("classify"))


@app.route("/classify", methods=["GET", "POST"])
def classify():
    error: Optional[str] = None
    creds_dict = session.get("credentials")
    if not creds_dict:
        return redirect(url_for("authorize"))
    creds = Credentials(**creds_dict)
    service = build("gmail", "v1", credentials=creds)
    if request.method == "POST":
        gemini_key = request.form["gemini_key"]
        session["gemini_key"] = gemini_key
        if not validate_gemini_key(gemini_key):
            error = "無効なGemini APIキーです。正しいキーを入力してください。"
            return render_template("classify.html", error=error)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(GENAI_MODEL)

        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        query = (
            f"after:{start_date} before:{end_date}"
            if end_date
            else f"after:{start_date}"
        )
        results = service.users().messages().list(userId="me", q=query).execute()
        messages = results.get("messages", [])
        data = []

        def extract_body(payload):
            if "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType", "").startswith("text/plain"):
                        data_b64 = part.get("body", {}).get("data")
                        if data_b64:
                            return base64.urlsafe_b64decode(data_b64).decode(
                                "utf-8", "ignore"
                            )
                    if "parts" in part:
                        text = extract_body(part)
                        if text:
                            return text
            else:
                data_b64 = payload.get("body", {}).get("data")
                if data_b64:
                    return base64.urlsafe_b64decode(data_b64).decode("utf-8", "ignore")
            return ""

        for m in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=m["id"], format="full")
                .execute()
            )
            headers = {
                h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])
            }
            snippet = msg.get("snippet", "")
            body = extract_body(msg.get("payload", {}))
            dt_ms = int(msg.get("internalDate"))
            dt = datetime.fromtimestamp(dt_ms / 1000).isoformat()

            prompt = (
                "次のメール本文からカテゴリ名、関連キーワードを2つ、"
                "15文字以内の日本語要約を含むJSONを出力してください。\n"
                '出力例: {"カテゴリ名": "...", "タグ": ["...", "..."], "サマリー": "..."}\n'
                f"件名: {headers.get('Subject', '')}\n本文: {body or snippet}"
            )

            try:
                response = model.generate_content(prompt)
                analysis = response.text.strip()
                info = parse_analysis(analysis)
            except Exception as e:
                print("Gemini API error:", e, flush=True)
                analysis = ""
                info = None
            finally:
                # Log Gemini API response and parse result even when errors occur
                print("=== Geminiの返答 ===", flush=True)
                print(analysis, flush=True)
                print("=== parse結果 ===", flush=True)
                print(info, flush=True)
                with open("gemini_log.csv", "a", encoding="utf-8") as f:
                    f.write("=== Geminiの返答 ===\n")
                    f.write(analysis + "\n")
                    f.write("=== parse結果 ===\n")
                    f.write(json.dumps(info, ensure_ascii=False) + "\n")
                    f.write("=== END ===\n\n")
            if info:
                category = info.get("カテゴリ名", "")
                tags = info.get("タグ", [])
                summary = info.get("サマリー", "")
            else:
                category = ""
                tags = []
                summary = ""

            data.append(
                {
                    "件名": headers.get("Subject", ""),
                    "送信者": headers.get("From", ""),
                    "受信日時": dt,
                    "カテゴリ名": category,
                    "タグ": json.dumps(tags, ensure_ascii=False),
                    "サマリー": summary,
                }
            )
        df = pd.DataFrame(data)
        os.makedirs("static", exist_ok=True)
        csv_file = os.path.join("static", "result.csv")
        df.to_csv(csv_file, index=False)
        return send_file(csv_file, as_attachment=True)
    return render_template("classify.html", error=error)


@app.route("/reset")
def reset_credentials():
    """Clear saved OAuth credentials from the session."""
    session.pop("credentials", None)
    session.pop("gemini_key", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
