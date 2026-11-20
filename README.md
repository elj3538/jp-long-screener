# 10年保有できる優良企業ランキング（日本株：`jp-long-screener`）

JPX「東証上場銘柄一覧」から TOPIX 500 相当（Core30 + Large70 + Mid400、約500銘柄・J-REIT除外）を抽出し、**ファンダ点（品質スコア）** と **買い時スコア** の2軸（各 0〜110点）で12業種グループ別に軍分け・可視化する静的サイト生成ツールです。

## ローカル実行方法

```powershell
# 少数テスト（先頭30銘柄）
.venv\Scripts\python.exe main.py --limit 30

# 本番フル生成（TOPIX 500 全銘柄）
.venv\Scripts\python.exe main.py --workers 3
```
