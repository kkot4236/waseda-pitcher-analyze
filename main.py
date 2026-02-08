import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob

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

        if 'Pitcher First Name' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher First Name'].fillna("Unknown").astype(str)
        elif 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip()

        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)

        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)

        if 'Pitch Created At' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Pitch Created At']).dt.date
        elif 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date

        list_df.append(temp_df)
    
    data = pd.concat(list_df, axis=0, ignore_index=True)
    for col in ['RelSpeed', 'InducedVertBreak', 'HorzBreak', 'PlateLocSide', 'PlateLocHeight', 'Balls', 'Strikes']:
        if col in data.columns: data[col] = pd.to_numeric(data[col], errors='coerce')
    return data

df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))

if df is not None:
    PITCH_ORDER = ["Fastball", "FB", "Slider", "SL", "Cutter", "CT", "Curveball", "CB", "Splitter", "SPL", "ChangeUp", "CH", "TwoSeamFastBall", "OneSeam"]
    tabs = st.tabs(["🔹 SBP", "🔹 オープン戦", "⚾ 実戦/PBP", "🔥 pitching", "📊 比較"])

    # 💥 フィルター関数の修正：引数で表示項目を制御 💥
    def render_filters(data_subset, key_suffix, show_side=True, show_runner=True):
        raw_p_list = data_subset['Pitcher'].unique()
        p_list = sorted([str(p) for p in raw_p_list if str(p).strip().lower() not in ['nan', 'unknown', '']])
        
        # 画面の幅を動的に調整
        cols_count = 2 + (1 if show_side else 0) + (1 if show_runner else 0)
        cols = st.columns(cols_count)
        
        with cols[0]: sel_pitcher = st.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{key_suffix}")
        with cols[1]:
            d_list = sorted([str(d) for d in data_subset['Date'].unique()], reverse=True)
            sel_date = st.selectbox("日付を選択", ["すべて"] + [str(d) for d in d_list], key=f"d_{key_suffix}")
        
        f = data_subset.copy()
        if sel_pitcher != "すべて": f = f[f['Pitcher'] == sel_pitcher]
        if sel_date != "すべて": f = f[f['Date'].astype(str) == sel_date]

        current_col = 2
        if show_side:
            with cols[current_col]:
                if 'BatterSide' in f.columns:
                    sel_side = st.selectbox("左右打者", ["すべて", "Right", "Left"], key=f"s_{key_suffix}")
                    if sel_side != "すべて": f = f[f['BatterSide'] == sel_side]
            current_col += 1
            
        if show_runner:
            with cols[current_col]:
                sel_runner = st.radio("ランナー状況", ["すべて", "通常", "クイック"], horizontal=True, key=f"r_{key_suffix}")
                runner_col = next((col for col in f.columns if "runn" in col.lower()), None)
                if runner_col:
                    f['has_runner'] = f[runner_col].apply(lambda x: 0 if pd.isna(x) or str(x).strip().lower() in ['0', '0.0', 'none', '', 'nan'] else 1)
                    if sel_runner == "通常": f = f[f['has_runner'] == 0]
                    elif sel_runner == "クイック": f = f[f['has_runner'] == 1]
        return f

    # (render_stats_tab, render_visual_tab などの描画ロジックは前回同様)
    def render_stats_tab(f_data):
        if f_data.empty: return st.warning("データがありません。")
        m1, m2, m3, m4 = st.columns(4)
        fs = f_data[f_data['is_first_pitch']==1]
        m1.metric("投球数", f"{len(f_data)} 球"); m2.metric("平均球速", f"{f_data['RelSpeed'].mean():.1f} km/h")
        m3.metric("ストライク率", f"{(f_data['is_strike'].mean()*100):.1f} %"); m4.metric("初球スト率", f"{(fs['is_strike'].mean()*100):.1f} %" if not fs.empty else "0.0 %")
        
        summary = f_data.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean'], 'is_strike': 'mean', 'is_swing': 'mean', 'is_whiff': 'sum'})
        summary.columns = ['投球数', '平均球速', 'ストライク率', 'スイング率', '空振り数']
        summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
        summary['Whiff %'] = (summary['空振り数'] / f_data.groupby('TaggedPitchType')['is_swing'].sum() * 100).fillna(0)
        summary['ストライク率'] *= 100; summary['スイング率'] *= 100
        summary = summary.reindex([p for p in PITCH_ORDER if p in summary.index] + [p for p in summary.index if p not in PITCH_ORDER]).dropna(subset=['投球数'])

        col_table, col_pie = st.columns([2, 1])
        with col_table:
            st.write("### 📊 球種別サマリー")
            st.table(summary[['投球数', '投球割合', '平均球速', 'ストライク率', 'スイング率', 'Whiff %']].style.format('{:.1f}'))
        with col_pie:
            st.write("### 🥧 投球割合")
            plt.clf(); fig_p, ax_p = plt.subplots(figsize=(4, 4)); ax_p.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, colors=plt.get_cmap('Pastel1').colors); st.pyplot(fig_p)

        st.write("### 🗓 カウント別 投球割合")
        f_data['Count'] = f_data['Balls'].fillna(0).astype(int).astype(str) + "-" + f_data['Strikes'].fillna(0).astype(int).astype(str)
        count_data = pd.crosstab(f_data['Count'], f_data['TaggedPitchType']).reindex(index=["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"], fill_value=0)
        if not count_data.empty:
            st.bar_chart(count_data.div(count_data.sum(axis=1).replace(0, 1), axis=0) * 100)

    def render_visual_tab(f_data):
        if f_data.empty: return st.warning("データがありません。")
        m1, m2, m3 = st.columns(3); m1.metric("投球数", f"{len(f_data)} 球"); m2.metric("平均球速", f"{f_data['RelSpeed'].mean():.1f} km/h"); m3.metric("最高速度", f"{f_data['RelSpeed'].max():.1f} km/h")
        col1, col2 = st.columns(2)
        with col1:
            st.write("🎯 **ムーブメント (変化量)**")
            plt.clf(); fig, ax = plt.subplots(figsize=(5, 5)); ax.axhline(0, color='black', lw=1); ax.axvline(0, color='black', lw=1)
            for pt in f_data['TaggedPitchType'].unique():
                sub = f_data[f_data['TaggedPitchType'] == pt]
                ax.scatter(sub['HorzBreak'], sub['InducedVertBreak'], label=pt, alpha=0.6)
            ax.set_xlim(-80, 80); ax.set_ylim(-80, 80); ax.legend(); ax.grid(True, alpha=0.3); st.pyplot(fig)
        with col2:
            st.write("📍 **到達位置 (コントロール)**")
            plt.clf(); fig, ax = plt.subplots(figsize=(5, 5)); ax.add_patch(plt.Rectangle((-25, 45), 50, 60, fill=False, color='black', lw=2))
            for pt in f_data['TaggedPitchType'].unique():
                sub = f_data[f_data['TaggedPitchType'] == pt]
                ax.scatter(sub['PlateLocSide'], sub['PlateLocHeight'], label=pt, alpha=0.6)
            ax.set_xlim(-80, 80); ax.set_ylim(-20, 150); ax.set_aspect('equal'); ax.grid(True, alpha=0.3); st.pyplot(fig)

    # --- 各タブの実行 ---
    with tabs[0]: # SBP: 左右・ランナーあり
        render_stats_tab(render_filters(df[df['DataCategory']=="SBP"], "sbp", show_side=True, show_runner=True))
    with tabs[1]: # オープン戦: 左右・ランナーあり
        render_stats_tab(render_filters(df[df['DataCategory']=="vs"], "vs", show_side=True, show_runner=True))
    with tabs[2]: # PBP: 左右・ランナーなし 💥
        render_visual_tab(render_filters(df[df['DataCategory']=="PBP"], "pbp", show_side=False, show_runner=False))
    with tabs[3]: # pitching: 左右・ランナーなし 💥
        render_visual_tab(render_filters(df[df['DataCategory']=="pitching"], "pitching", show_side=False, show_runner=False))
    # (比較タブ略...)
else:
    st.error("dataフォルダにCSVが見つかりません。")
