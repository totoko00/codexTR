# codexTR
ChatGPTのcodexの練習

## 2025/06/04
ためしてみる

## Gmail分類Webアプリ

このリポジトリには、Gmailのメールを期間指定で取得し、CSV出力する簡単なFlaskアプリ `app.py` が含まれています。

### 使い方
1. Google Cloud Console で Gmail API を有効化し、OAuth クライアント ID を作成して `credentials.json` をリポジトリのルートに配置してください。
2. 依存パッケージをインストールします。
   ```bash
   pip install -r requirements.txt
   ```
3. アプリのセッション情報を保護するため、Flask がセッション署名に利用する秘密鍵を
   環境変数 `FLASK_SECRET` に設定します。以下のワンライナーで 16 バイトのランダム
   文字列を生成できます。

   ```bash
   python -c "import secrets; print(secrets.token_hex(16))"
   ```

   生成した文字列を `FLASK_SECRET` に設定します。

   ```bash
   export FLASK_SECRET=<生成した文字列>  # Windows の場合は set FLASK_SECRET=<文字列>
   ```

4. 開発環境で HTTP のまま OAuth2 を利用する場合は、`OAUTHLIB_INSECURE_TRANSPORT=1`
   を設定してからアプリを起動します。本番運用では HTTPS を使用してください。

   ```bash
   export OAUTHLIB_INSECURE_TRANSPORT=1  # Windows の場合は set OAUTHLIB_INSECURE_TRANSPORT=1
   python app.py
   ```

5. ブラウザで `http://localhost:5000` にアクセスし、指示に従ってGoogleアカウントを認証します。期間を入力して「Start Classification」を押すと `static/result.csv` が生成され、ダウンロードが始まります。

### OAuth のスコープエラーが出る場合

既に保存された認証情報のスコープと `app.py` 内の `SCOPES` が一致しない場合、
`oauth2callback` で *Scope has changed* という警告が表示されて処理が失敗することがあります。
その場合は次のいずれかを行い、認証情報を削除してから再認証してください。

1. ブラウザで `http://localhost:5000/reset` にアクセスしてセッションに保存された認証情報を消去する。
2. `token.json` などのキャッシュファイルを利用している場合はそれを削除する。

再度 `/authorize` から認証を行えば、指定したスコープでトークンを取得し直せます。
