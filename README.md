# 阿蘇山 SO₂ 5点観測アプリ — Noto CJK日本語フォント版

## なぜ前回DejaVu Sansになったか

Streamlit Cloud環境に日本語フォントが存在せず、
MatplotlibがDejaVu Sansへフォールバックしていました。

## 今回の修正

GitHubリポジトリ直下に packages.txt を追加し、

fonts-noto-cjk

をOSパッケージとしてインストールします。

app.pyでは、起動時にMatplotlibのフォント一覧を再取得し、
Noto Sans CJK JP を優先して使用します。

## GitHubで置き換えるファイル

- app.py
- requirements.txt
- packages.txt

3ファイルともリポジトリ直下へ置いてください。

Streamlit CloudではCommit後、Manage app → Reboot appを実行してください。
「日本語フォント設定」を開いて

Matplotlib使用フォント：Noto Sans CJK JP

またはNoto Sans CJK系の名称になれば成功です。
