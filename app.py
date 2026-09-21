import streamlit as st
import googlemaps
import pandas as pd
import urllib.parse
import math
import os
from datetime import datetime

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
st.title("⛳ 所要時間でゴルフ場検索(β版)")
st.caption("◆現在の道路状況や渋滞情報を考慮してゴルフ場までの時間を検索します◆")

# ---------------------------------------------------------
# 機能1: 時間指定で広域検索
# ---------------------------------------------------------
st.subheader("車の移動時間でゴルフ場を探す")
user_address = st.text_input(
    "ご自宅の住所", 
    placeholder="例: 東京都港区新橋 / 大阪府大阪市北区梅田",
    key="area_address"
)
time_option = st.selectbox(
    "車での移動時間を選択",
    options=["車で30分以内", "車で1時間以内", "車で1時間半以内", "車で2時間以内"],
    index=2
)

time_limit_mapping = {
    "車で30分以内": 30,
    "車で1時間以内": 60,
    "車で1時間半以内": 90,
    "車で2時間以内": 120,
}
max_minutes = time_limit_mapping[time_option]

if st.button("条件で探す", key="btn_area"):
    if not user_address:
        st.warning("住所を入力してください。")
    else:
        with st.spinner("近隣のゴルフ場を精査中..."):
            try:
                geocode_result = gmaps.geocode(user_address, language='ja')
                if not geocode_result:
                    st.error("入力された住所の場所を特定できませんでした。")
                    st.stop()
                    
                user_lat = geocode_result[0]['geometry']['location']['lat']
                user_lng = geocode_result[0]['geometry']['location']['lng']

                temp_courses = []
                for _, row in golf_df.iterrows():
                    dist = calculate_direct_distance(user_lat, user_lng, row['lat'], row['lng'])
                    temp_courses.append({
                        "data": row,
                        "direct_dist": dist
                    })

                temp_courses = sorted(temp_courses, key=lambda x: x['direct_dist'])[:200]

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

                results = sorted(results, key=lambda x: x['duration'])

                st.success(f"「{user_address}」から **{time_option}** で行けるゴルフ場が {len(results)} 件見つかりました！")
                st.divider()

                if results:
                    for item in results:
                        st.markdown(f"<h3 style='margin-bottom:0;'>⛳ <a href='{item['url']}' target='_blank' style='text-decoration:none; color:#1E88E5;'>{item['name']}</a></h3>", unsafe_allow_html=True)
                        st.write(f"🚗 **所要時間**: 約 {item['duration']} 分 （距離: {item['distance']}）")
                        st.markdown(f"📍 **住所**: [{item['address']}]({item['map_url']})")
                        st.divider()
                else:
                    st.info("指定された時間内で行けるゴルフ場が見つかりませんでした。時間を延ばして試してみてください。")

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

st.divider()

# ---------------------------------------------------------
# 機能2: 特定のゴルフ場を指定して距離・時間をピンポイント検索
# ---------------------------------------------------------
st.subheader("指定のゴルフ場までの時間を調べる")

user_address_single = st.text_input(
    "ご自宅の住所", 
    placeholder="例: 東京都港区新橋 / 大阪府大阪市北区梅田",
    key="single_address"
)

# ゴルフ場名一覧を作成（ドロップダウンから選択）
course_list = ["（入力して選択）"] + sorted(golf_df['golf_name'].dropna().unique().tolist())
selected_course = st.selectbox("ゴルフ場名を選択", options=course_list)

if st.button("このゴルフ場まで時間・距離を調べる", key="btn_single"):
    if not user_address_single:
        st.warning("ご自宅の住所を入力してください。")
    elif selected_course == "（選択してください）":
        st.warning("ゴルフ場名を選択してください。")
    else:
        with st.spinner("指定されたゴルフ場へのルートを計算中..."):
            try:
                # 該当するゴルフ場データをCSVから検索
                match_row = golf_df[golf_df['golf_name'] == selected_course]
                
                if not match_row.empty:
                    row = match_row.iloc[0]
                    c_name = row['golf_name']
                    c_address = row['address']
                    c_url = row['url']
                    if pd.notnull(row['lat']) and pd.notnull(row['lng']):
                        destination = (row['lat'], row['lng'])
                    else:
                        destination = f"{c_name} {c_address}"
                else:
                    c_name = selected_course
                    c_address = "住所情報"
                    c_url = f"https://www.google.com/search?q={urllib.parse.quote(c_name)}"
                    destination = c_name

                matrix_result = gmaps.distance_matrix(
                    origins=[user_address_single],
                    destinations=[destination],
                    mode="driving",
                    departure_time=datetime.now(),
                    language='ja'
                )

                element = matrix_result['rows'][0]['elements'][0]

                if element.get('status') == 'OK':
                    duration_min = round(element['duration']['value'] / 60)
                    distance_km = element['distance']['text']

                    map_query = urllib.parse.quote(f"{c_name} {c_address}")
                    map_url = f"https://www.google.com/maps/search/?api=1&query={map_query}"

                    st.success(f"「{user_address_single}」から「{c_name}」までの計算結果です！")
                    st.divider()
                    st.markdown(f"<h3 style='margin-bottom:0;'>⛳ <a href='{c_url}' target='_blank' style='text-decoration:none; color:#1E88E5;'>{c_name}</a></h3>", unsafe_allow_html=True)
                    st.write(f"🚗 **所要時間**: 約 {duration_min} 分 （距離: {distance_km}）")
                    st.markdown(f"📍 **住所**: [{c_address}]({map_url})")
                    st.divider()
                else:
                    st.error("ルートの計算に失敗しました。住所やゴルフ場名をご確認ください。")

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
