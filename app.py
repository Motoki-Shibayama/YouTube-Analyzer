from apiclient.discovery import build
from datetime import datetime as dt
import json
import pandas as pd
import streamlit as st

# secret.json読み込み
with open("secret.json") as f:
    secret = json.load(f)

DEVELOPER_KEY = secret["YOUTUBE_API"]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# YouTube APIインスタンス化
youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)

def get_videoId(youtube, query, maxResults=50):
    # 動画検索
    response = youtube.search().list(
        q=query,
        part="id, snippet",
        type="video",
        maxResults=maxResults
    ).execute()

    # データ取得 ＆ 整形
    item_ids = []
    for item in response["items"]:
            item_id = {}
            item_id["video_id"] = item["id"]["videoId"]
            item_id["channel_id"] = item["snippet"]["channelId"]
            item_id["title"] = item["snippet"]["title"]
            item_ids.append(item_id)
    df_video = pd.DataFrame(item_ids)
    return df_video

def get_result(df_video, threshold=1000000):
    # チャンネル登録者数取得
    channel_ids = df_video["channel_id"].unique().tolist()

    # チャンネル情報取得
    channel_data = youtube.channels().list(
        id=",".join(channel_ids),
        part="id, snippet, statistics, brandingSettings",
        fields="items(id, snippet(publishedAt), statistics(subscriberCount), brandingSettings(channel(keywords)))"
    ).execute()

    # チャンネル情報格納
    channel_info = []
    # 日付変換フォーマット
    time_format = "%Y-%m-%d"
    for item in channel_data["items"]:
        channel_data = {}
        channel_data["channel_id"] = item["id"]
        # ミリ秒形式と秒形式の両方のデータがあるため、それらを分岐させて一旦datetime型へ変換
        if len(item["snippet"]["publishedAt"]) > 20:
            tdatetime = dt.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            tdatetime = dt.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
        # 所定のフォーマットへ変換
        channel_data["channel_published_date"] = tdatetime.strftime(time_format)
        if len(item["statistics"]) > 0:
            channel_data["subscriber_count"] = int(item["statistics"]["subscriberCount"])
        if len(item["brandingSettings"]["channel"]) > 0:
            channel_data["keywords"] = item["brandingSettings"]["channel"]["keywords"]
        channel_info.append(channel_data)

    # データ整形
    df_channelInfo = pd.DataFrame(channel_info)

    # 結果を結合
    df = pd.merge(left=df_video, right=df_channelInfo, on="channel_id")

    # チャンネル登録者数の制限
    df_extracted = df[df["subscriber_count"] < threshold]

    # チャンネル登録者数の制限を適用後の動画情報取得
    video_ids = df_extracted["video_id"].tolist()
    video_data = youtube.videos().list(
        part="id, snippet, contentDetails, statistics",
        id=",".join(video_ids),
        fields="items(id, snippet(publishedAt), contentDetails(duration), statistics(viewCount), statistics(likeCount), statistics(favoriteCount), statistics(commentCount))"
    ).execute()

    # 動画情報格納
    video_info = []
    for video in video_data["items"]:
        video_contents = {}
        video_contents["video_id"] = video["id"]
        # ミリ秒形式と秒形式の両方のデータがあるため、それらを分岐させて一旦datetime型へ変換
        if len(video["snippet"]["publishedAt"]) > 20:
            tdatetime = dt.strptime(video["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            tdatetime = dt.strptime(video["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
        # 所定のフォーマットへ変換
        video_contents["upload_date"] = tdatetime.strftime(time_format)
        video_contents["duration"] = (video["contentDetails"]["duration"]).replace("PT", "").replace("H", "時間").replace("M", "分").replace("S", "秒")
        video_contents["view_count"] = video["statistics"]["viewCount"]
        video_contents["like_count"] = video["statistics"]["likeCount"]
        # commentCountのキー自体がない場合に備えて分岐
        if "commentCount" in video["statistics"].keys():
            video_contents["comment_count"] = video["statistics"]["commentCount"]
        video_info.append(video_contents)

    # データ整形
    df_videoInfo = pd.DataFrame(video_info)

    # 動画情報結合
    results = pd.merge(left=df_videoInfo, right=df_extracted, on="video_id")

    # 並び替え
    results = results.loc[:, ["video_id", "title", "duration", "upload_date", "view_count", "like_count", "comment_count", "keywords", "channel_id", "subscriber_count", "channel_published_date"]]
    return results


# Streamlitの開発
st.title("YouTube Analyzer")

# sidebarの設定
st.sidebar.write("## クエリと閾値の設定")
st.sidebar.write("### クエリの入力")
query = st.sidebar.text_input("検索ワードを入力してください", "ポケモン 対戦")

st.sidebar.write("### 閾値の設定")
threshold = st.sidebar.slider("チャンネル登録者数の閾値", 100, 3000000, 1000000)

# メイン画面の開発
st.write("### 選択中のパラメータ")
st.markdown(f"""
- 検索クエリ：{query}
- 登録者数の閾値：{threshold}
""")

# データ取得
df_video = get_videoId(youtube, query, maxResults=50)
results = get_result(df_video, threshold)

# 分析結果の表示
st.write("### 分析結果", results)

# 動画再生ボタン
st.write("### 動画再生")
video_id = st.text_input("動画IDを入力してください")

# YouTubeリンクの作成
url = f"https://youtu.be/{video_id}"

video_field = st.empty()
video_field.write("こちらに動画が表示されます")

if st.button("ビデオ表示"):
    if len(video_id) > 0:
        try:
            video_field.video(url)
        except:
            st.error("指定された動画が見つかりません")
