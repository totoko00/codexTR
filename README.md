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
3. アプリのセッション情報を保護するため、環境変数 `FLASK_SECRET` に秘密鍵として使う適当な文字列を設定します。設定後、下記のコマンドでアプリを起動します。
   ```bash
   export FLASK_SECRET=your_secret  # Windows の場合は set FLASK_SECRET=your_secret
   python app.py
   ```
4. ブラウザで `http://localhost:5000` にアクセスし、指示に従ってGoogleアカウントを認証します。期間を入力して「Start Classification」を押すと `static/result.csv` が生成され、ダウンロードが始まります。
