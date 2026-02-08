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
            'PlateLocHeight (CM)': 'PlateLocHeight'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        temp_df['DataCategory'] = category

        if 'Pitcher First Name' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher First Name'].fillna("Unknown").astype(str)
        elif 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip()
        else:
            temp_df['Pitcher'] = "Unknown"

        # 基本指標フラグ
        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)

        # 💥 初球判定フラグ（Balls=0 かつ Strikes=0）
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)
        else:
            temp_df['is_first_pitch'] = 0

        if 'Pitch Created At' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Pitch Created At']).dt.date
        elif 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date
        else:
            temp_df['Date'] = pd.Timestamp.now().date()

        list_df.append(temp_df)
    
    data = pd.concat(list_df, axis=0, ignore_index=True)
    data['Pitcher'] = data['Pitcher'].fillna("Unknown").astype(str)
    data['DateLabel'] = data.apply(lambda row: f"{row['Date']} ({row['DataCategory']})", axis=1)
    
    for col in ['RelSpeed', 'InducedVertBreak', 'HorzBreak', 'PlateLocSide', 'PlateLocHeight', 'Balls', 'Strikes']:
        if col in data.columns: data[col] = pd.to_numeric(data[col], errors='coerce')
    
    return data

df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))

if df is not None:
    PITCH_ORDER = ["Fastball", "FB", "Slider", "SL", "Cutter", "CT", "Curveball", "CB", "Splitter", "SPL", "ChangeUp", "CH", "TwoSeamFastBall", "OneSeam"]
    tabs = st.tabs(["🔹 SBP", "🔹 オープン戦", "⚾ 実戦/PBP", "🔥 pitching", "📊 比較(SBP vs オープン戦)"])

    def render_filters(data_subset, key_suffix, show_runner_filter=True):
        raw_p_list = data_subset['Pitcher'].unique()
        p_list = sorted([str(p) for p in raw_p_list if str(p).strip().lower() not in ['0', '0.0', 'nan', 'unknown', 'none', '']])
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col1: sel_pitcher = st.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{key_suffix}")
        with col2:
            d_list = sorted([str(d) for d in data_subset['DateLabel'].unique()], reverse=True)
            sel_date = st.selectbox("日付を選択", ["すべて"] + d_list, key=f"d_{key_suffix}")
        f = data_subset.copy()
        if sel_pitcher != "すべて": f = f[f['Pitcher'] == sel_pitcher]
        if sel_date != "すべて": f = f[f['DateLabel'] == sel_date]
        if show_runner_filter:
            with col3:
                st.write("ランナー状況")
                sel_runner = st.radio("", ["すべて", "通常", "クイック"], horizontal=True, key=f"r_{key_suffix}", label_visibility="collapsed")
            runner_col = next((col for col in f.columns if "runn" in col.lower()), None)
            if runner_col:
                f['has_runner'] = f[runner_col].apply(lambda x: 0 if pd.isna(x) or str(x).strip().lower() in ['0', '0.0', 'none', '', 'nan'] else 1)
                if sel_runner == "通常": f = f[f['has_runner'] == 0]
                elif sel_runner == "クイック": f = f[f['has_runner'] == 1]
        return f

    def render_stats_tab(f_data):
        if f_data.empty: return st.warning("データがありません。")
        
        # 💥 指標計算（初球ストライク率を追加）
        m1, m2, m3, m4 = st.columns(4)
        first_pitches = f_data[f_data['is_first_pitch'] == 1]
        f_strike_pct = (first_pitches['is_strike'].mean() * 100) if not first_pitches.empty else 0.0
        
        m1.metric("投球数", f"{len(f_data)} 球")
        m2.metric("平均球速", f"{f_data['RelSpeed'].mean():.1f} km/h")
        m3.metric("ストライク率", f"{(f_data['is_strike'].mean() * 100):.1f} %")
        m4.metric("初球ストライク率", f"{f_strike_pct:.1f} %")
        
        summary = f_data.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean', 'max'], 'is_strike': 'mean', 'is_swing': 'mean', 'is_whiff': 'sum'})
        summary.columns = ['投球数', '平均球速', '最速', 'ストライク率', 'スイング率', '空振り数']
        summary = summary.reindex([p for p in PITCH_ORDER if p in summary.index] + [p for p in summary.index if p not in PITCH_ORDER]).dropna(subset=['投球数'])
        summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
        summary['Whiff %'] = (summary['空振り数'] / f_data.groupby('TaggedPitchType')['is_swing'].sum() * 100).fillna(0)
        summary['ストライク率'] *= 100; summary['スイング率'] *= 100
        
        col_table, col_pie = st.columns([2, 1])
        with col_table:
            st.table(summary[['投球数', '投球割合', '平均球速', '最速', 'ストライク率', 'スイング率', 'Whiff %']].style.format('{:.1f}'))
            st.caption("※ Whiff % = 空振り数 ÷ スイング数 × 100")
        with col_pie:
            st.write("球種別投球割合"); plt.clf(); fig_p, ax_p = plt.subplots(figsize=(4, 4)); ax_p.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, colors=plt.get_cmap('Pastel1').colors); st.pyplot(fig_p)

        st.subheader("🗓 カウント別 投球割合")
        f_data['Count'] = f_data['Balls'].fillna(0).astype(int).astype(str) + "-" + f_data['Strikes'].fillna(0).astype(int).astype(str)
        count_data = pd.crosstab(f_data['Count'], f_data['TaggedPitchType']).reindex(index=["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"], fill_value=0)
        if not count_data.empty:
            st.bar_chart(count_data.div(count_data.sum(axis=1).replace(0, 1), axis=0) * 100)

    def render_visual_tab(f_data):
        if f_data.empty: return st.warning("データがありません。")
        m1, m2, m3 = st.columns(3); m1.metric("投球数", f"{len(f_data)} 球"); m2.metric("平均球速", f"{f_data['RelSpeed'].mean():.1f} km/h"); m3.metric("最高速度", f"{f_data['RelSpeed'].max():.1f} km/h")
        st.write("📍 **到達位置**")
        plt.clf(); fig, ax = plt.subplots(figsize=(5, 5)); ax.add_patch(plt.Rectangle((-25, 45), 50, 60, fill=False, color='black', lw=2))
        for pt in [p for p in PITCH_ORDER if p in f_data['TaggedPitchType'].unique()]:
            sub = f_data[f_data['TaggedPitchType'] == pt]
            if 'PlateLocSide' in sub.columns: ax.scatter(sub['PlateLocSide'], sub['PlateLocHeight'], label=pt, alpha=0.6)
        ax.set_xlim(-80, 80); ax.set_ylim(-20, 150); ax.set_aspect('equal'); ax.legend(); ax.grid(True, alpha=0.3); st.pyplot(fig)

    def render_comparison_tab(all_data):
        sbp_pitchers = set(all_data[all_data['DataCategory']=="SBP"]['Pitcher'].unique())
        vs_pitchers = set(all_data[all_data['DataCategory']=="vs"]['Pitcher'].unique())
        common_pitchers = sorted(list(sbp_pitchers & vs_pitchers))
        if not common_pitchers: return st.info("SBPとオープン戦の両方にデータがある投手がまだいません。")
        
        sel_p = st.selectbox("比較する投手を選択", common_pitchers, key="comp_p")
        c_sbp = all_data[(all_data['Pitcher'] == sel_p) & (all_data['DataCategory']=="SBP")]
        c_vs = all_data[(all_data['Pitcher'] == sel_p) & (all_data['DataCategory']=="vs")]
        
        st.subheader(f"📊 {sel_p}投手の練習(SBP) vs 実戦(オープン戦)")
        m1, m2, m3, m4 = st.columns(4)
        def get_delta(v1, v2): return f"{(v1-v2)*100:+.1f}%" if pd.notnull(v1) and pd.notnull(v2) else "N/A"
        
        fs_vs = c_vs[c_vs['is_first_pitch']==1]['is_strike'].mean()
        fs_sbp = c_sbp[c_sbp['is_first_pitch']==1]['is_strike'].mean()
        m1.metric("初球ｽﾄﾗｲｸ率 (実戦)", f"{(fs_vs or 0)*100:.1f}%", delta=get_delta(fs_vs or 0, fs_sbp or 0))
        m2.metric("全体ｽﾄﾗｲｸ率 (実戦)", f"{c_vs['is_strike'].mean()*100:.1f}%", delta=get_delta(c_vs['is_strike'].mean(), c_sbp['is_strike'].mean()))
        m3.metric("スイング率 (実戦)", f"{c_vs['is_swing'].mean()*100:.1f}%", delta=get_delta(c_vs['is_swing'].mean(), c_sbp['is_swing'].mean()))
        whiff_vs = c_vs['is_whiff'].sum() / c_vs['is_swing'].sum() if c_vs['is_swing'].sum() > 0 else 0
        whiff_sbp = c_sbp['is_whiff'].sum() / c_sbp['is_swing'].sum() if c_sbp['is_swing'].sum() > 0 else 0
        m4.metric("Whiff % (実戦)", f"{whiff_vs*100:.1f}%", delta=get_delta(whiff_vs, whiff_sbp))

        st.write("### 📈 球種別 初球の傾向")
        fcol1, fcol2 = st.columns(2)
        for title, data, col in [("SBP(練習) 初球内訳", c_sbp[c_sbp['is_first_pitch']==1], fcol1), ("オープン戦(実戦) 初球内訳", c_vs[c_vs['is_first_pitch']==1], fcol2)]:
            with col:
                if not data.empty:
                    counts = data['TaggedPitchType'].value_counts()
                    plt.clf(); fig, ax = plt.subplots(figsize=(4, 3))
                    ax.pie(counts, labels=counts.index, autopct='%1.0f%%', startangle=90, colors=plt.get_cmap('Set3').colors); ax.set_title(title); st.pyplot(fig)
                else: st.write(f"{title}: データなし")

    # --- 各タブの描画 ---
    with tabs[0]: render_stats_tab(render_filters(df[df['DataCategory']=="SBP"], "sbp"))
    with tabs[1]: render_stats_tab(render_filters(df[df['DataCategory']=="vs"], "vs"))
    with tabs[2]: render_visual_tab(render_filters(df[df['DataCategory']=="PBP"], "pbp", show_runner_filter=False))
    with tabs[3]: render_visual_tab(render_filters(df[df['DataCategory']=="pitching"], "pitching", show_runner_filter=False))
    with tabs[4]: render_comparison_tab(df)
else:
    st.error("dataフォルダにCSVが見つかりません。")
