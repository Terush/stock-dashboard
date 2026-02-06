#!/usr/bin/env python3
"""
GitHub Pages用の株式ダッシュボードHTMLを生成する

Usage:
    python generate_site.py
    python generate_site.py --password YOUR_PASSWORD
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

import yfinance as yf
import pandas as pd
import numpy as np

# 保有銘柄リスト
WATCHLIST = [
    {"symbol": "7011.T", "name": "三菱重工業", "sector": "防衛"},
    {"symbol": "7013.T", "name": "IHI", "sector": "防衛"},
    {"symbol": "8306.T", "name": "三菱UFJ", "sector": "金融"},
    {"symbol": "8750.T", "name": "第一生命", "sector": "金融"},
    {"symbol": "6701.T", "name": "NEC", "sector": "電機"},
    {"symbol": "2768.T", "name": "双日", "sector": "商社"},
]


class TrendScreener:
    """トレンド銘柄を判定するクラス"""

    def __init__(self):
        self.ma_short = 20
        self.ma_mid = 50
        self.ma_long = 200

    def analyze(self, df: pd.DataFrame) -> dict:
        if len(df) < self.ma_long:
            return {
                'trend_type': 'UNKNOWN',
                'score': 0,
                'reasons': ['データ不足'],
                'metrics': {}
            }

        metrics = self._calculate_metrics(df)
        score, reasons = self._calculate_score(metrics)

        if score >= 75:
            trend_type = 'STRONG_TREND'
        elif score >= 50:
            trend_type = 'WEAK_TREND'
        elif score >= 25:
            trend_type = 'SIDEWAYS'
        else:
            trend_type = 'DOWNTREND'

        return {
            'trend_type': trend_type,
            'score': score,
            'reasons': reasons,
            'metrics': metrics
        }

    def _calculate_metrics(self, df: pd.DataFrame) -> dict:
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values

        ma20 = pd.Series(close).rolling(self.ma_short).mean().values
        ma50 = pd.Series(close).rolling(self.ma_mid).mean().values
        ma200 = pd.Series(close).rolling(self.ma_long).mean().values

        current_price = close[-1]
        current_ma20 = ma20[-1]
        current_ma50 = ma50[-1]
        current_ma200 = ma200[-1]

        ma50_slope_1m = (ma50[-1] - ma50[-20]) / ma50[-20] * 100 if ma50[-20] > 0 else 0
        ma50_slope_3m = (ma50[-1] - ma50[-60]) / ma50[-60] * 100 if len(ma50) > 60 and ma50[-60] > 0 else 0
        ma200_slope = (ma200[-1] - ma200[-60]) / ma200[-60] * 100 if len(ma200) > 60 and ma200[-60] > 0 else 0

        price_vs_ma20 = (current_price - current_ma20) / current_ma20 * 100
        price_vs_ma50 = (current_price - current_ma50) / current_ma50 * 100
        price_vs_ma200 = (current_price - current_ma200) / current_ma200 * 100

        perfect_order = current_price > current_ma20 > current_ma50 > current_ma200

        period = len(close) // 3
        if period > 20:
            highs_p1 = np.max(high[-period*3:-period*2])
            highs_p2 = np.max(high[-period*2:-period])
            highs_p3 = np.max(high[-period:])
            lows_p1 = np.min(low[-period*3:-period*2])
            lows_p2 = np.min(low[-period*2:-period])
            lows_p3 = np.min(low[-period:])
            higher_highs = highs_p1 < highs_p2 < highs_p3
            higher_lows = lows_p1 < lows_p2 < lows_p3
        else:
            higher_highs = False
            higher_lows = False

        yearly_return = (current_price - close[0]) / close[0] * 100 if close[0] > 0 else 0
        days_above_ma50 = np.sum(close[-120:] > ma50[-120:]) / 120 * 100 if len(close) >= 120 else 0

        return {
            'current_price': current_price,
            'ma20': current_ma20,
            'ma50': current_ma50,
            'ma200': current_ma200,
            'ma50_slope_1m': ma50_slope_1m,
            'ma50_slope_3m': ma50_slope_3m,
            'ma200_slope': ma200_slope,
            'price_vs_ma20': price_vs_ma20,
            'price_vs_ma50': price_vs_ma50,
            'price_vs_ma200': price_vs_ma200,
            'perfect_order': perfect_order,
            'higher_highs': higher_highs,
            'higher_lows': higher_lows,
            'yearly_return': yearly_return,
            'days_above_ma50': days_above_ma50,
        }

    def _calculate_score(self, m: dict) -> tuple:
        score = 0
        reasons = []

        if m['perfect_order']:
            score += 15
            reasons.append("+ パーフェクトオーダー")
        else:
            reasons.append("- パーフェクトオーダーではない")

        slope = m['ma50_slope_3m']
        if slope > 10:
            score += 20
            reasons.append(f"+ MA50強上昇 (+{slope:.1f}%)")
        elif slope > 5:
            score += 15
            reasons.append(f"= MA50上昇 (+{slope:.1f}%)")
        elif slope > 0:
            score += 8
            reasons.append(f"= MA50やや上昇 (+{slope:.1f}%)")
        elif slope > -5:
            score += 3
            reasons.append(f"= MA50横ばい ({slope:.1f}%)")
        else:
            reasons.append(f"- MA50下落 ({slope:.1f}%)")

        slope200 = m['ma200_slope']
        if slope200 > 5:
            score += 15
            reasons.append(f"+ 長期上昇 (+{slope200:.1f}%)")
        elif slope200 > 0:
            score += 10
            reasons.append(f"= 長期やや上昇 (+{slope200:.1f}%)")
        elif slope200 > -3:
            score += 5
            reasons.append(f"= 長期横ばい ({slope200:.1f}%)")
        else:
            reasons.append(f"- 長期下落 ({slope200:.1f}%)")

        if m['higher_highs'] and m['higher_lows']:
            score += 15
            reasons.append("+ 高値・安値切り上げ")
        elif m['higher_highs']:
            score += 10
            reasons.append("= 高値切り上げ")
        elif m['higher_lows']:
            score += 8
            reasons.append("= 安値切り上げ")
        else:
            reasons.append("- 高値・安値切り上げなし")

        yr = m['yearly_return']
        if yr > 50:
            score += 20
            reasons.append(f"+ 年間優秀 (+{yr:.0f}%)")
        elif yr > 20:
            score += 15
            reasons.append(f"= 年間良好 (+{yr:.0f}%)")
        elif yr > 0:
            score += 8
            reasons.append(f"= 年間プラス (+{yr:.0f}%)")
        else:
            reasons.append(f"- 年間マイナス ({yr:.0f}%)")

        days = m['days_above_ma50']
        if days > 80:
            score += 15
            reasons.append(f"+ MA50上維持 ({days:.0f}%)")
        elif days > 60:
            score += 10
            reasons.append(f"= 概ねMA50上 ({days:.0f}%)")
        elif days > 40:
            score += 5
            reasons.append(f"= MA50上下 ({days:.0f}%)")
        else:
            reasons.append(f"- MA50下多い ({days:.0f}%)")

        return score, reasons


def analyze_stocks():
    """全銘柄を分析"""
    screener = TrendScreener()
    results = []

    for stock in WATCHLIST:
        symbol = stock['symbol']
        print(f"分析中: {symbol}...")

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y")

            if df.empty or len(df) < 200:
                print(f"  警告: {symbol} のデータが不足しています")
                continue

            analysis = screener.analyze(df)

            if len(df) >= 2:
                prev_close = df['Close'].iloc[-2]
                curr_close = df['Close'].iloc[-1]
                daily_change = (curr_close - prev_close) / prev_close * 100
            else:
                daily_change = 0

            results.append({
                'symbol': symbol,
                'name': stock['name'],
                'sector': stock['sector'],
                'price': analysis['metrics'].get('current_price', 0),
                'daily_change': daily_change,
                'score': analysis['score'],
                'trend_type': analysis['trend_type'],
                'reasons': analysis['reasons'],
                'metrics': analysis['metrics'],
            })

        except Exception as e:
            print(f"  エラー: {symbol} - {e}")

    return results


def get_trend_display(trend_type):
    """トレンドタイプの表示情報を取得"""
    displays = {
        'STRONG_TREND': {'label': '強いトレンド', 'color': 'green', 'action': '保有継続', 'action_class': ''},
        'WEAK_TREND': {'label': '弱いトレンド', 'color': 'blue', 'action': '様子見', 'action_class': ''},
        'SIDEWAYS': {'label': '横ばい', 'color': 'orange', 'action': '売却検討', 'action_class': 'sell'},
        'DOWNTREND': {'label': '下降トレンド', 'color': 'red', 'action': '売却', 'action_class': 'sell'},
        'UNKNOWN': {'label': '判定不能', 'color': 'gray', 'action': '-', 'action_class': ''},
    }
    return displays.get(trend_type, displays['UNKNOWN'])


def generate_html(results, password_hash=None):
    """HTMLを生成"""
    now = datetime.now().strftime('%Y.%m.%d %H:%M')

    # 売却シグナル（下降トレンド）
    sell_signals = [r for r in results if r['trend_type'] == 'DOWNTREND']
    # 売却検討（横ばい）
    sell_candidates = [r for r in results if r['trend_type'] == 'SIDEWAYS']

    # カウント
    count_strong = len([r for r in results if r['trend_type'] == 'STRONG_TREND'])
    count_weak = len([r for r in results if r['trend_type'] == 'WEAK_TREND'])
    count_sideways = len([r for r in results if r['trend_type'] == 'SIDEWAYS'])
    count_down = len([r for r in results if r['trend_type'] == 'DOWNTREND'])

    # アラートメッセージ
    alert_html = ""
    if sell_signals:
        names = " / ".join([f"<strong>{r['symbol']} {r['name']}</strong>" for r in sell_signals])
        alert_html = f'<div class="alert">{names} — 下降トレンド、売却シグナル</div>'
    elif sell_candidates:
        names = " / ".join([f"<strong>{r['symbol']} {r['name']}</strong>" for r in sell_candidates])
        alert_html = f'<div class="alert">{names} — トレンド弱化、売却検討</div>'

    # カード生成
    cards_html = ""
    for r in sorted(results, key=lambda x: x['score'], reverse=True):
        display = get_trend_display(r['trend_type'])
        change_class = 'up' if r['daily_change'] >= 0 else 'down'
        change_sign = '+' if r['daily_change'] >= 0 else ''
        action_class = f' class="sell"' if display['action_class'] else ''

        cards_html += f'''
                <div class="card {display['color']}">
                    <div class="card-head">
                        <div class="card-name">{r['name']}</div>
                        <div class="card-code">{r['symbol']} / {r['sector']}</div>
                    </div>
                    <div class="card-price">
                        <span class="price">¥{r['price']:,.0f}</span>
                        <span class="change {change_class}">{change_sign}{r['daily_change']:.2f}%</span>
                    </div>
                    <div class="card-score">
                        <div class="score-bar"><div class="score-fill" style="width:{r['score']}%; background:var(--{display['color']})"></div></div>
                        <div class="score-text"><span>スコア</span><span>{r['score']}</span></div>
                    </div>
                    <div class="card-status">
                        <span class="badge {display['color']}">{display['label']}</span>
                        <span class="action"><strong{action_class}>{display['action']}</strong></span>
                    </div>
                </div>
'''

    # パスワード保護
    password_js = ""
    if password_hash:
        password_js = f'''
    <script>
    (function() {{
        const H = '{password_hash}';
        if (sessionStorage.getItem('auth') === H) {{
            document.getElementById('login-overlay').style.display = 'none';
            document.getElementById('content').style.display = 'block';
            return;
        }}
        document.getElementById('login-form').addEventListener('submit', function(e) {{
            e.preventDefault();
            const hash = CryptoJS.SHA256(document.getElementById('password').value).toString();
            if (hash === H) {{
                sessionStorage.setItem('auth', H);
                document.getElementById('login-overlay').style.display = 'none';
                document.getElementById('content').style.display = 'block';
            }} else {{
                document.getElementById('error-msg').textContent = 'パスワードが違います';
            }}
        }});
    }})();
    </script>'''
        login_html = '''
    <div id="login-overlay" class="login-overlay">
        <div class="login-box">
            <h2>PORTFOLIO</h2>
            <form id="login-form">
                <input type="password" id="password" placeholder="Password" required>
                <button type="submit">Enter</button>
            </form>
            <p id="error-msg" class="error"></p>
        </div>
    </div>'''
        content_style = 'style="display: none;"'
    else:
        login_html = ''
        content_style = ''

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>
    <style>
        :root {{
            --bg: #000;
            --bg-card: #111;
            --border: #222;
            --text: #fff;
            --text-sub: #777;
            --text-muted: #444;
            --red: #e54;
            --orange: #f90;
            --green: #3c8;
            --blue: #48f;
            --gray: #666;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Hiragino Sans', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        .title {{
            font-size: 1rem;
            font-weight: 500;
            letter-spacing: 0.1em;
            color: var(--text-sub);
        }}
        .meta {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        .alert {{
            background: rgba(238, 85, 68, 0.08);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 32px;
            font-size: 0.85rem;
            color: var(--text-sub);
        }}
        .alert strong {{
            color: var(--red);
        }}
        .stats {{
            display: flex;
            gap: 32px;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        .stat {{
            display: flex;
            align-items: baseline;
            gap: 8px;
        }}
        .stat-num {{
            font-size: 1.5rem;
            font-weight: 600;
        }}
        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }}
        .card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border-left: 3px solid var(--border);
        }}
        .card.green {{ border-left-color: var(--green); }}
        .card.blue {{ border-left-color: var(--blue); }}
        .card.orange {{ border-left-color: var(--orange); }}
        .card.red {{ border-left-color: var(--red); }}
        .card-head {{ margin-bottom: 16px; }}
        .card-name {{
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .card-code {{
            font-size: 0.7rem;
            color: var(--text-muted);
        }}
        .card-price {{
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin-bottom: 16px;
        }}
        .price {{
            font-size: 1.25rem;
            font-weight: 600;
        }}
        .change {{ font-size: 0.8rem; }}
        .change.up {{ color: var(--green); }}
        .change.down {{ color: var(--red); }}
        .card-score {{ margin-bottom: 12px; }}
        .score-bar {{
            height: 4px;
            background: var(--border);
            border-radius: 2px;
            overflow: hidden;
            margin-bottom: 6px;
        }}
        .score-fill {{
            height: 100%;
            border-radius: 2px;
        }}
        .score-text {{
            font-size: 0.7rem;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
        }}
        .card-status {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }}
        .badge {{
            font-size: 0.65rem;
            font-weight: 500;
            padding: 4px 10px;
            border-radius: 100px;
        }}
        .badge.green {{ background: rgba(51, 204, 136, 0.15); color: var(--green); }}
        .badge.blue {{ background: rgba(68, 136, 255, 0.15); color: var(--blue); }}
        .badge.orange {{ background: rgba(255, 153, 0, 0.15); color: var(--orange); }}
        .badge.red {{ background: rgba(238, 85, 68, 0.15); color: var(--red); }}
        .action {{
            font-size: 0.7rem;
            color: var(--text-muted);
        }}
        .action strong {{
            color: var(--text-sub);
        }}
        .action strong.sell {{
            color: var(--red);
        }}
        .login-overlay {{
            position: fixed;
            inset: 0;
            background: var(--bg);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 100;
        }}
        .login-box {{
            width: 280px;
            text-align: center;
        }}
        .login-box h2 {{
            font-size: 0.9rem;
            font-weight: 500;
            letter-spacing: 0.1em;
            color: var(--text-sub);
            margin-bottom: 32px;
        }}
        .login-box input {{
            width: 100%;
            padding: 14px 16px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--bg-card);
            color: var(--text);
            font-size: 0.9rem;
            margin-bottom: 12px;
        }}
        .login-box input:focus {{
            outline: none;
            border-color: var(--text-muted);
        }}
        .login-box button {{
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 8px;
            background: var(--text);
            color: var(--bg);
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
        }}
        .login-box .error {{
            color: var(--red);
            font-size: 0.8rem;
            margin-top: 12px;
        }}
        @media (max-width: 1200px) {{
            .grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 600px) {{
            .grid {{ grid-template-columns: 1fr; }}
            .stats {{ flex-wrap: wrap; gap: 16px; }}
        }}
    </style>
</head>
<body>
    {login_html}
    <div id="content" {content_style}>
        <div class="container">
            <header>
                <div class="title">PORTFOLIO</div>
                <div class="meta">{now}</div>
            </header>

            {alert_html}

            <div class="stats">
                <div class="stat">
                    <span class="stat-num" style="color: var(--green)">{count_strong}</span>
                    <span class="stat-label">強い</span>
                </div>
                <div class="stat">
                    <span class="stat-num" style="color: var(--blue)">{count_weak}</span>
                    <span class="stat-label">弱い</span>
                </div>
                <div class="stat">
                    <span class="stat-num" style="color: var(--orange)">{count_sideways}</span>
                    <span class="stat-label">横ばい</span>
                </div>
                <div class="stat">
                    <span class="stat-num" style="color: var(--red)">{count_down}</span>
                    <span class="stat-label">下降</span>
                </div>
            </div>

            <div class="grid">
{cards_html}
            </div>
        </div>
    </div>
{password_js}
</body>
</html>'''

    return html


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--password', help='認証用パスワード')
    parser.add_argument('--output', default='index.html', help='出力ファイル名')
    args = parser.parse_args()

    print("株式ダッシュボード生成中...")
    print()

    results = analyze_stocks()

    if not results:
        print("エラー: 分析結果がありません")
        sys.exit(1)

    password_hash = None
    if args.password:
        password_hash = hashlib.sha256(args.password.encode()).hexdigest()
        print(f"\nパスワード保護を有効化")

    html = generate_html(results, password_hash)

    output_path = Path(args.output)
    output_path.write_text(html, encoding='utf-8')

    print(f"\n生成完了: {output_path}")
    print(f"銘柄数: {len(results)}")

    # 売却シグナル
    sell_signals = [r for r in results if r['trend_type'] == 'DOWNTREND']
    sell_candidates = [r for r in results if r['trend_type'] == 'SIDEWAYS']

    if sell_signals:
        print(f"\n!! 売却シグナル:")
        for s in sell_signals:
            print(f"   {s['symbol']} ({s['name']}) - スコア {s['score']}")

    if sell_candidates:
        print(f"\n! 売却検討:")
        for s in sell_candidates:
            print(f"   {s['symbol']} ({s['name']}) - スコア {s['score']}")


if __name__ == "__main__":
    main()
