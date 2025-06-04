import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime

# Allow OAuth over HTTP when running locally. Remove or change for production.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly","https://mail.google.com/","https://www.googleapis.com/auth/script.external_request"]

# path to OAuth2 credentials obtained from Google Cloud console
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    return redirect(url_for('classify'))

@app.route('/classify', methods=['GET', 'POST'])
def classify():
    creds_dict = session.get('credentials')
    if not creds_dict:
        return redirect(url_for('authorize'))
    creds = Credentials(**creds_dict)
    service = build('gmail', 'v1', credentials=creds)
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        query = f"after:{start_date} before:{end_date}" if end_date else f"after:{start_date}"
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        data = []
        for m in messages:
            msg = service.users().messages().get(userId='me', id=m['id'], format='metadata').execute()
            headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
            labels = msg.get('labelIds', [])
            snippet = msg.get('snippet', '')
            dt_ms = int(msg.get('internalDate'))
            dt = datetime.fromtimestamp(dt_ms/1000).isoformat()
            data.append({
                'Date': dt,
                'From': headers.get('From', ''),
                'Subject': headers.get('Subject', ''),
                'Labels': ','.join(labels),
                'Snippet': snippet
            })
        df = pd.DataFrame(data)
        os.makedirs('static', exist_ok=True)
        csv_file = os.path.join('static', 'result.csv')
        df.to_csv(csv_file, index=False)
        return send_file(csv_file, as_attachment=True)
    return render_template('classify.html')

@app.route('/reset')
def reset_credentials():
    """Clear saved OAuth credentials from the session."""
    session.pop('credentials', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
