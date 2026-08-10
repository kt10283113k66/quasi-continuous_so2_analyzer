# 阿蘇山 SO₂ 5点観測アプリ — 日本語文字化け修正版

## 修正内容

以前は japanize_matplotlib を import するだけだったため、
Streamlit Cloudの環境によってはMatplotlibの日本語フォントが
DejaVu Sansへ戻り、□表示になることがありました。

修正版では次の処理を行います。

1. japanize-matplotlibパッケージ内のIPAexGothicフォントを探索
2. matplotlib.font_manager.fontManager.addfont() で明示登録
3. rcParams["font.family"] へ実際のフォント名を明示指定
4. 軸タイトル・軸ラベル・目盛・凡例・annotationへFontPropertiesを再適用

アプリ上部の「日本語フォント設定」を開くと、
Matplotlibが使用しているフォント名を確認できます。

GitHub / Streamlit Cloudでは app.py と requirements.txt の両方を
今回のファイルへ置き換えてください。
