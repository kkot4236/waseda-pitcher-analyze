import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# --- 2. データ読み込み ---
@st.cache_data
def load_all_data_from_folder(folder_path):
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not all_files: return None
    
    list_df = []
    for filename in all_files:
        try:
            temp_df = pd.read_csv(filename, encoding='utf-8')
        except:
            temp_df = pd.read_csv(filename, encoding='cp932')
            
        fname_lower = os.path.basename(filename).lower()
        if "sbp" in fname_lower: category = "SBP"
        elif "vs" in fname_lower: category = "vs"
        elif "pbp" in fname_lower: category = "PBP"
        elif "pitching" in fname_lower: category = "pitching"
        else: category = "その他"
        
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight',
            'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        temp_df['DataCategory'] = category

        if 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip()
        else:
            temp_df['Pitcher'] = "Unknown"

        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)

        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)

        if 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date
        else:
            temp_df['Date'] = pd.Timestamp.now().date()

        list_df.append(temp_df)
    
    if not list_df: return None
    data = pd.concat(list_df, axis=0, ignore_index=True)
    # 💥 ブラウザエラー対策：LargeUtf8を避けるための変換
    data = data.convert_dtypes(dtype_backend="numpy_nullable")
    return data

# --- 3. リスク管理グラフの描画 ---
def render_risk_management(f_data):
    st.write("### 📊 リスク管理 (打球結果)")
    
    def classify_result(row):
        res = str(row.get('PlayResult', '')).lower()
        call = str(row.get('PitchCall', '')).lower()
        hit_type = str(row.get('TaggedHitType', '')).lower()
        
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit_type:
            return '完全アウト(三振+内野フライ)'
        elif 'home' in res:
            return '本塁打'
        elif 'walk' in res or 'hitby' in res:
            return '四死球'
        elif 'ground' in hit_type:
            return 'ゴロ'
        elif 'fly' in hit_type or 'line' in hit_type:
            return '外野フライ+ライナー'
        return None

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    f_risk = f_risk.dropna(subset=['ResultCategory'])

    if f_risk.empty:
        return st.info("リスク管理グラフ用のデータがありません（PlayResult/TaggedHitTypeが必要）")

    risk_summary = []
    for side in ['Left', 'Right']:
        side_data = f_risk[f_risk['BatterSide'] == side]
        if not side_data.empty:
            counts = side_data['ResultCategory'].value_counts(normalize=True) * 100
            for cat, val in counts.items():
                risk_summary.append({'対象': f'対{side}打者', 'カテゴリ': cat, '割合(%)': val})
    
    total_counts = f_risk['ResultCategory'].value_counts(normalize=True) * 100
    for cat, val in total_counts.items():
        risk_summary.append({'対象': '全体平均', 'カテゴリ': cat, '割合(%)': val})

    risk_df = pd.DataFrame(risk_summary)
    color_map = {
        '完全アウト(三振+内野フライ)': '#6495ED', 'ゴロ': '#ADFF2F',
        '外野フライ+ライナー': '#FFD700', '四死球': '#F4A460', '本塁打': '#FF0000'
    }

    fig = px.bar(risk_df, y='対象', x='割合(%)', color='カテゴリ', 
                 orientation='h', color_discrete_map=color_map,
                 category_orders={'カテゴリ': ['完全アウト(三振+内野フライ)', 'ゴロ', '外野フライ+ライナー', '四死球', '本塁打']},
                 height=300)
    fig.update_layout(xaxis_title="割合 (%)", yaxis_title="", legend_title="", 
                      margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

# --- 4. メインタブ描画 ---
def render_stats_tab(f_data, key_suffix):
    if f_data.empty: return st.warning("データがありません。")
    
    # 💥 上部メトリクス
    m1, m2, m3, m4, m5 = st.columns(5)
    fb_data = f_data[f_data['TaggedPitchType'].isin(["Fastball", "FB"])]
    avg_fb = fb_data['RelSpeed'].mean() if not fb_data.empty else 0.0
    max_spd = f_data['RelSpeed'].max() if not f_data.empty else 0.0
    fs = f_data[f_data['is_first_pitch'] == 1]
    f_str_pct = (fs['is_strike'].mean() * 100) if not fs.empty else 0.0
    
    m1.metric("投球数", f"{len(f_data)} 球")
    m2.metric("平均球速(直球)", f"{avg_fb:.1f} km/h")
    m3.metric("最高速度", f"{max_spd:.1f} km/h")
    m4.metric("ストライク率", f"{(f_data['is_strike'].mean()*100):.1f} %")
    m5.metric("初球スト率", f"{f_str_pct:.1f} %")
    
    # 💥 球種別分析データの作成
    summary = f_data.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean', 'max'], 'is_strike': 'mean', 'is_swing': 'mean', 'is_whiff': 'sum'})
    summary.columns = ['投球数', '平均球速', '最速', 'ストライク率', 'スイング率', '空振り数']
    summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
    summary['Whiff %'] = (summary['空振り数'] / f_data.groupby('TaggedPitchType')['is_swing'].sum() * 100).fillna(0)
    summary['ストライク率'] *= 100; summary['スイング率'] *= 100
    PITCH_ORDER = ["Fastball", "FB", "Slider", "SL", "Cutter", "CT", "Curveball", "CB", "Splitter", "SPL", "ChangeUp", "CH", "TwoSeamFastBall", "OneSeam"]
    summary = summary.reindex([p for p in PITCH_ORDER if p in summary.index] + [p for p in summary.index if p not in PITCH_ORDER]).dropna(subset=['投球数'])

    display_df = summary.copy()
    display_df['平均球速'] = display_df['平均球速'].apply(lambda x: f"{x:.1f}")
    display_df['最速'] = display_df['最速'].apply(lambda x: f"{x:.1f}")
    for col in ['投球割合', 'ストライク率', 'スイング率', 'Whiff %']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.1f} %")
    display_df['投球数'] = display_df['投球数'].astype(int)

    # 💥 レイアウト配置
    col_left, col_right = st.columns([1.8, 1])
    with col_left:
        st.write("### 📊 球種別分析")
        st.table(display_df[['投球数', '投球割合', '平均球速', '最速', 'ストライク率', 'スイング率', 'Whiff %']])
        
        # 💥 ここにリスク管理を配置（表の下）
        render_risk_management(f_data)

    with col_right:
        st.write("### 🥧 投球割合")
        plt.clf(); fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, colors=plt.get_cmap('Pastel1').colors)
        st.pyplot(fig)

    st.divider()

    # 💥 カウント別分析
    st.write("### 🗓 カウント別 投球割合")
    mode = st.radio("表示モード", ["全カウント", "2ストライク時のみ"], horizontal=True, key=f"mode_{key_suffix}")
    f_data['Count'] = f_data['Balls'].fillna(0).astype(int).astype(str) + "-" + f_data['Strikes'].fillna(0).astype(int).astype(str)
    
    if mode == "2ストライク時のみ":
        subset = f_data[f_data['Strikes'] == 2]
        labels = ["0-2", "1-2", "2-2", "3-2", "2スト全体"]
    else:
        subset = f_data
        labels = ["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2", "全体"]
    
    if not subset.empty:
        cnt_map = pd.crosstab(subset['Count'], subset['TaggedPitchType'])
        total = pd.DataFrame(subset['TaggedPitchType'].value_counts()).T
        total.index = [labels[-1]]
        final_map = pd.concat([cnt_map, total]).reindex(index=labels, fill_value=0)
        st.bar_chart(final_map.div(final_map.sum(axis=1).replace(0,1), axis=0)*100)

# --- 5. メイン実行 ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tabs = st.tabs(["🔹 SBP", "🔹 オープン戦", "⚾ 実戦/PBP", "🔥 pitching", "📊 比較"])
    
    def get_filters(data, k):
        p_list = sorted([str(p) for p in data['Pitcher'].unique() if p != "Unknown"])
        c1, c2 = st.columns(2)
        with c1: p = st.selectbox("投手", ["すべて"] + p_list, key=f"p_{k}")
        with c2: d = st.selectbox("日付", ["すべて"] + sorted(data['Date'].unique().astype(str), reverse=True), key=f"d_{k}")
        res = data.copy()
        if p != "すべて": res = res[res['Pitcher'] == p]
        if d != "すべて": res = res[res['Date'].astype(str) == d]
        return res

    with tabs[0]: render_stats_tab(get_filters(df[df['DataCategory']=="SBP"], "sbp"), "sbp")
    with tabs[1]: render_stats_tab(get_filters(df[df['DataCategory']=="vs"], "vs"), "vs")
else:
    st.error("dataフォルダにCSVが見つかりません。")
