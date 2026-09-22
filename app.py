import streamlit as st
import googlemaps
import pandas as pd
import urllib.parse
import math
import os

# ---------------------------------------------------------
# 1. APIキーの設定 (Streamlit Secrets / 環境変数)
# ---------------------------------------------------------
API_KEY = st.secrets.get("GOOGLE_MAPS_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY"))
gmaps = googlemaps.Client(key=API_KEY)

# CSVデータの読み込み
@st.cache_data
def load_golf_data():
    return pd.read_csv("golf_courses.csv")

golf_df = load_golf_data()

# 直線距離計算用の関数 (ヒュベニの公式)
def calculate_direct_distance(lat1, lon1, lat2, lon2):
    if pd.isnull(lat1) or pd.isnull(lon1) or pd.isnull(lat2) or pd.isnull(lon2):
        return 9999
    
    rad_lat1 = math.radians(lat1)
    rad_lon1 = math.radians(lon1)
    rad_lat2 = math.radians(lat2)
    rad_lon2 = math.radians(lon2)
    
    dlat = rad_lat2 - rad_lat1
    dlon = rad_lon2 - rad_lon1
    
    a = math.sin(dlat/2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return 6371 * c

# ---------------------------------------------------------
# UI設定
# ---------------------------------------------------------
st.title("⛳ 距離でゴルフ場検索(β版)")
st.caption("■入力地点から直線距離が近い順にゴルフ場を表示します。住所をクリックするとルート案内画面が開きます。")

# ---------------------------------------------------------
# 直線距離での広域検索（APIコスト約0.75円/回）
# ---------------------------------------------------------
st.subheader("距離でゴルフ場を調べる")
user_address = st.text_input(
    "出発地点の住所(ご自宅など)", 
    placeholder="例: 東京都港区新橋 / 大阪市北区梅田",
    key="area_address"
)

# 距離指定の選択肢
distance_option = st.selectbox(
    "検索範囲（直線距離）を選択　◆各ゴルフ場の住所をクリックすると車のルートや時間が表示されます",
    options=["直線で 20km 以内", "直線で 30km 以内", "直線で 50km 以内", "直線で 100km 以内"],
    index=2
)

dist_limit_mapping = {
    "直線で 20km 以内": 20,
    "直線で 30km 以内": 30,
    "直線で 50km 以内": 50,
    "直線で 100km 以内": 100,
}
max_km = dist_limit_mapping[distance_option]

if st.button("この条件で調べる", key="btn_area"):
    if not user_address:
        st.warning("住所を入力してください。")
    else:
        with st.spinner("近隣のゴルフ場を精査中..."):
            try:
                # 1回だけGeocoding APIを呼び出して入力住所の座標を取得
                geocode_result = gmaps.geocode(user_address, language='ja')
                if not geocode_result:
                    st.error("入力された住所の場所を特定できませんでした。")
                    st.stop()
                    
                user_lat = geocode_result[0]['geometry']['location']['lat']
                user_lng = geocode_result[0]['geometry']['location']['lng']

                results = []
                # 全ゴルフ場データに対してPython内部で直線距離を計算
                for _, row in golf_df.iterrows():
                    dist = calculate_direct_distance(user_lat, user_lng, row['lat'], row['lng'])
                    
                    if dist <= max_km:
                        origin_param = urllib.parse.quote(user_address)
                        dest_param = urllib.parse.quote(f"{row['golf_name']} {row['address']}")
                        map_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_param}&destination={dest_param}&travelmode=driving"

                        results.append({
                            "name": row['golf_name'],
                            "address": row['address'],
                            "url": row['url'],
                            "map_url": map_url,
                            "distance_km": round(dist, 1)
                        })

                # 直線距離が近い順にソート
                results = sorted(results, key=lambda x: x['distance_km'])

                st.success(f"「{user_address}」から **{distance_option}** にあるゴルフ場が {len(results)} 件見つかりました！")
                st.divider()

                if results:
                    for item in results:
                        title_html = f"""
                            <h3 style='margin-bottom:0; display:flex; align-items:center;'>
                                ⛳&nbsp;<a href='{item['url']}' target='_blank' style='text-decoration:none; color:#1E88E5; margin-right: 12px;'>{item['name']}</a>
                                <a href='{item['url']}' target='_blank' style='font-size: 0.7em; font-weight: normal; color: #757575; text-decoration: none;'>
                                    ◆会員権価格を見る
                                </a>
                            </h3>
                        """
                        st.markdown(title_html, unsafe_allow_html=True)
                        st.write(f"📏 **直線距離**: 約 {item['distance_km']} km")
                        st.markdown(f"📍 **住所**: [{item['address']}]({item['map_url']})")
                        st.divider()
                else:
                    st.info("指定された範囲内に行けるゴルフ場が見つかりませんでした。距離を広げて試してみてください。")

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
