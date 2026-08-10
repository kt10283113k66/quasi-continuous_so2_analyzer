# 阿蘇山 SO₂ 5点観測・準定常ガス拡散モデル逆解析

Streamlitアプリです。

## 入力

- SC1～SC5のSO₂カラム濃度
- GPV txt の u/v ファイル
- 必要に応じて stations.csv

GPVファイル名例:

- `202303060330p900u.txt`
- `202303060330p900v.txt`
- `2023121203p900u.txt`
- `2023121203p900v.txt`

ファイル名から日時・気圧面・u/v・30分解析/毎時解析を自動判別します。

## モデル

- 仮定放出率 1000 t/day
- 主軸長 初期値 5 km
- 火口風向補正 -12～+12度（2度刻み、13パターン）
- GPV気圧面 最大3パターン
- 最大39パターン
- 風速依存拡散幅（河波ら2023 式11）またはSutton固定パラメータ
- 5地点切片0固定回帰
- RMSE最小を最適解
- 推定放出率 = 1000 × 回帰傾き

## Streamlit Community Cloud

1. GitHubで新しいリポジトリを作成
2. このフォルダの内容をリポジトリ直下へアップロード
3. Streamlit Community CloudにGitHubでサインイン
4. Create app
5. Repository / branch / `app.py` を指定
6. Deploy

GPVファイルはアプリ画面から都度アップロードします。
巨大なGPV txtをGitHubへ置く必要はありません。
