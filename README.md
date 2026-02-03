# Stock Dashboard - GitHub Pages

保有銘柄のトレンド状況を毎日自動更新するプライベートダッシュボード。

## セットアップ手順

### 1. GitHubリポジトリを作成

```bash
# このフォルダをGitリポジトリとして初期化
cd stock-dashboard
git init
git add .
git commit -m "Initial commit"

# GitHubで新しいリポジトリを作成し、プッシュ
git remote add origin https://github.com/YOUR_USERNAME/stock-dashboard.git
git branch -M main
git push -u origin main
```

### 2. GitHub Pagesを有効化

1. GitHubでリポジトリを開く
2. **Settings** → **Pages** を開く
3. **Source** で「Deploy from a branch」を選択
4. **Branch** で「main」を選択し、「/ (root)」を選択
5. **Save** をクリック

数分後に `https://YOUR_USERNAME.github.io/stock-dashboard/` でアクセス可能になります。

### 3. パスワードを設定（推奨）

1. GitHubでリポジトリを開く
2. **Settings** → **Secrets and variables** → **Actions** を開く
3. **New repository secret** をクリック
4. 以下を入力:
   - Name: `DASHBOARD_PASSWORD`
   - Secret: 任意のパスワード
5. **Add secret** をクリック

### 4. 動作確認

1. **Actions** タブを開く
2. **Update Stock Dashboard** ワークフローを選択
3. **Run workflow** をクリックして手動実行
4. 完了後、GitHub Pagesにアクセスして確認

## 自動更新スケジュール

- **実行時間**: 毎日17:00 JST（日本株式市場終了後）
- **実行日**: 平日のみ（月〜金）

## 保有銘柄の変更

`generate_site.py` の `WATCHLIST` を編集してください:

```python
WATCHLIST = [
    {"symbol": "7011.T", "name": "三菱重工業", "sector": "防衛"},
    {"symbol": "7013.T", "name": "IHI", "sector": "防衛"},
    # 追加・変更...
]
```

## ローカルでの実行

```bash
# 必要なパッケージをインストール
pip install yfinance pandas numpy

# パスワードなしで生成
python generate_site.py

# パスワード付きで生成
python generate_site.py --password YOUR_PASSWORD

# index.html をブラウザで開いて確認
```

## トレンド判定基準

| スコア | 判定 | 推奨アクション |
|--------|------|----------------|
| 75点以上 | 🚀 強いトレンド | 保有継続 |
| 50-74点 | 📈 弱いトレンド | 様子見 |
| 25-49点 | ➡️ 横ばい | 売却検討 |
| 25点未満 | 📉 下降トレンド | 売却 |

## ファイル構成

```
stock-dashboard/
├── generate_site.py        # HTML生成スクリプト
├── index.html              # 生成されるダッシュボード
├── README.md               # このファイル
└── .github/
    └── workflows/
        └── update.yml      # GitHub Actions設定
```
