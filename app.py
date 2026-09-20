import streamlit as st
import googlemaps
import pandas as pd
import urllib.parse
import math
from datetime import datetime

# ---------------------------------------------------------
# 1. APIキーの設定
# ---------------------------------------------------------
import os
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
        return 9999  # 緯度経度がない場合は後回し
    
    rad_lat1 = math.radians(lat1)
    rad_lon1 = math.radians(lon1)
    rad_lat2 = math.radians(lat2)
    rad_lon2 = math.radians(lon2)
    
    dlat = rad_lat2 - rad_lat1
    dlon = rad_lon2 - rad_lon1
    
    a = math.sin(dlat/2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return 6371 * c # 地球の半径 km

# ---------------------------------------------------------
# 2. 画面UIの作成
# ---------------------------------------------------------
st.title("⛳ ゴルフ場案内チャット")

st.subheader("検索条件を入力してください")
user_address = st.text_input(
    "ご自宅の住所", 
    placeholder="例: 東京都港区新橋 / 大阪府大阪市北区梅田"
)
time_option = st.selectbox(
    "許容できる移動時間",
    options=["車で30分以内", "車で1時間以内", "車で1時間半以内", "車で2時間以内"],
    index=1
)

time_limit_mapping = {
    "車で30分以内": 30,
    "車で1時間以内": 60,
    "車で1時間半以内": 90,
    "車で2時間以内": 120,
}
max_minutes = time_limit_mapping[time_option]

# ---------------------------------------------------------
# 3. 検索処理 (200件判定版)
# ---------------------------------------------------------
if st.button("ゴルフ場を探す"):
    if not user_address:
        st.warning("住所を入力してください。")
    else:
        with st.spinner("近隣のゴルフ場を精査中..."):
            try:
                # 1. 自宅住所の緯度経度を取得
                geocode_result = gmaps.geocode(user_address, language='ja')
                if not geocode_result:
                    st.error("入力された住所の場所を特定できませんでした。")
                    st.stop()
                    
                user_lat = geocode_result[0]['geometry']['location']['lat']
                user_lng = geocode_result[0]['geometry']['location']['lng']

                # 2. 全ゴルフ場との直線距離を一括計算（Python内部処理で一瞬）
                temp_courses = []
                for _, row in golf_df.iterrows():
                    dist = calculate_direct_distance(user_lat, user_lng, row['lat'], row['lng'])
                    temp_courses.append({
                        "data": row,
                        "direct_dist": dist
                    })

                # ★ 3. 直線距離が近い上位200件へ枠を大幅拡大
                temp_courses = sorted(temp_courses, key=lambda x: x['direct_dist'])[:200]

                # 4. 200件に対して Google API で実際の車移動時間を計算
                results = []
                batch_size = 10
                
                for i in range(0, len(temp_courses), batch_size):
                    batch = temp_courses[i:i + batch_size]
                    destinations = []
                    
                    for item in batch:
                        row = item['data']
                        if pd.notnull(row['lat']) and pd.notnull(row['lng']):
                            destinations.append((row['lat'], row['lng']))
                        else:
                            destinations.append(f"{row['golf_name']} {row['address']}")

                    matrix_result = gmaps.distance_matrix(
                        origins=[(user_lat, user_lng)],
                        destinations=destinations,
                        mode="driving",
                        departure_time=datetime.now(),
                        language='ja'
                    )

                    rows = matrix_result['rows'][0]['elements']

                    for idx, element in enumerate(rows):
                        if element.get('status') == 'OK':
                            duration_min = round(element['duration']['value'] / 60)
                            distance_km = element['distance']['text']
                            course = batch[idx]['data']

                            if duration_min <= max_minutes:
                                map_query = urllib.parse.quote(f"{course['golf_name']} {course['address']}")
                                map_url = f"https://www.google.com/maps/search/?api=1&query={map_query}"

                                results.append({
                                    "name": course['golf_name'],
                                    "address": course['address'],
                                    "url": course['url'],
                                    "map_url": map_url,
                                    "duration": duration_min,
                                    "distance": distance_km
                                })

                # 移動時間が短い順にソート
                results = sorted(results, key=lambda x: x['duration'])

                st.success(f"「{user_address}」から **{time_option}** で行けるゴルフ場が {len(results)} 件見つかりました！")
                st.divider()

                if results:
                    for item in results:
                        st.markdown(f"### ⛳ [{item['name']}]({item['url']})")
                        st.write(f"🚗 **所要時間**: 約 {item['duration']} 分 （距離: {item['distance']}）")
                        st.markdown(f"📍 **住所**: [{item['address']}]({item['map_url']})")
                        st.divider()
                else:
                    st.info("指定された時間内で行けるゴルフ場が見つかりませんでした。時間を延ばして試してみてください。")

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
