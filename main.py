import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# 球種の指定順序
PITCH_ORDER = [
    "Fastball", "Slider", "Cutter", "Curveball", "ChangeUp", 
    "Splitter", "TwoSeamFastBall", "OneSeam", "Sinker"
]

# --- 🔴 パステル調のカラーマップに変更 ---
PITCH_COLORS = {
    "Fastball": "#AEC7E8",        # 薄い青
    "Slider": "#FFBB78",          # 薄いオレンジ
    "Cutter": "#98DF8A",          # 薄い緑
    "Curveball": "#FF9896",       # 薄い赤
    "ChangeUp": "#C5B0D5",        # 薄い紫
    "Splitter": "#C49C94",        # 薄い茶
    "TwoSeamFastBall": "#F7B6D2", # 薄いピンク
    "OneSeam": "#C7C7C7",         # 薄いグレー
    "Sinker": "#DBDB8D",          # 薄い黄緑
    "Unknown": "#9EDAE5"          # 薄い水色
}

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
        
        fname = os.path.basename(filename)
        fname_lower = fname.lower()
        if "紅白戦" in fname: category = "紅白戦"
        elif "sbp" in fname_lower: category = "SBP"
        elif "vs" in fname_lower: category = "オープン戦"
        elif "pbp" in fname_lower: category = "実戦/PBP"
        elif "pitching" in fname_lower: category = "pitching"
        else: category = "その他"
        
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight', 'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        temp_df['DataCategory'] = category
        temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip() if 'Pitcher' in temp_df.columns else "Unknown"
        
        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)
        
        temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date if 'Date' in temp_df.columns else pd.Timestamp.now().date()
        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True).convert_dtypes(dtype_backend="numpy_nullable")

# --- 3. カウント別分析 (全体割合追加版) ---
def render_count_analysis(f_data, key_suffix):
    st.divider()
    col_head, col_opt = st.columns([3, 1])
    with col_head:
        st.write("#### 📊 カウント別 投球割合")
    with col_opt:
        is_two_strikes = st.checkbox("2ストライクのみ表示", key=f"2s_{key_suffix}")

    if 'Balls' not in f_data.columns or 'Strikes' not in f_data.columns:
        return st.info("カウントデータがありません。")

    target_df = f_data.copy()
    if is_two_strikes:
        count_order = ["0-2", "1-2", "2-2", "3-2"]
    else:
        count_order = ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    
    # 🔴 最後に「全体」を追加
    count_display_order = count_order + ["全体"]

    target_df['Count'] = target_df['Balls'].astype(str) + "-" + target_df['Strikes'].astype(str)
    
    count_list = []
    # カウントごとの計算
    for cnt in count_order:
        df_cnt = target_df[target_df['Count'] == cnt]
        if not df_cnt.empty:
            counts = df_cnt['TaggedPitchType'].value_counts(normalize=True) * 100
            for pt, val in counts.items():
                count_list.append({'項目': cnt, '球種': pt, '割合(%)': val})
    
    # 🔴 「全体」の割合を計算して追加
    total_counts = target_df['TaggedPitchType'].value_counts(normalize=True) * 100
    for pt, val in total_counts.items():
        count_list.append({'項目': "全体", '球種': pt, '割合(%)': val})
    
    if count_list:
        fig_cnt = px.bar(pd.DataFrame(count_list), x='項目', y='割合(%)', color='球種', 
                         category_orders={'項目': count_display_order},
                         color_discrete_map=PITCH_COLORS)
        fig_cnt.update_layout(yaxis=dict(range=[0, 100]), margin=dict(l=20, r=20, t=20, b=20), height=350)
        st.plotly_chart(fig_cnt, use_container_width=True)

# --- 4. リスク管理セクション (変更なし) ---
def render_risk_management_section(f_data):
    st.divider()
    st.write("#### 📊 リスク管理 (打球結果)")
    
    def classify_result(row):
        res = str(row.get('PlayResult','')).lower()
        call = str(row.get('PitchCall','')).lower()
        hit = str(row.get('TaggedHitType','')).lower()
        if 'home' in res: return '本塁打'
        if 'walk' in res or 'hitby' in res: return '四死球'
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit: return '完全アウト(内野フライ+三振)'
        if 'ground' in hit: return 'ゴロ'
        if 'fly' in hit or 'line' in hit: return '外野フライ・ライナー'
        return None

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    f_risk = f_risk.dropna(subset=['ResultCategory'])
    
    cat_order = ['完全アウト(内野フライ+三振)', 'ゴロ', '外野フライ・ライナー', '四死球', '本塁打']
    # リスク管理の色も少しパステルに
    color_map_risk = {
        '完全アウト(内野フライ+三振)': '#87CEEB', 'ゴロ': '#9ACD32', 
        '外野フライ・ライナー': '#F0E68C', '四死球': '#FFB444', '本塁打': '#F08080'
    }

    if f_risk.empty: return st.info("分析用の打球データがありません。")

    c1, c2 = st.columns([1, 1])
    common_margins = dict(l=150, r=20, t=10, b=10)

    with c1:
        side_list = []
        draw_order_left = ['対左打者', '対右打者', '全体合計']
        for label in draw_order_left:
            sd = f_risk if label == '全体合計' else f_risk[f_risk['BatterSide'] == ('Right' if label == '対右打者' else 'Left')]
            if not sd.empty:
                counts = sd['ResultCategory'].value_counts(normalize=True) * 100
                for cat in cat_order: side_list.append({'対象': label, 'カテゴリ': cat, '割合(%)': counts.get(cat, 0)})
        
        if side_list:
            fig_side = px.bar(pd.DataFrame(side_list), y='対象', x='割合(%)', color='カテゴリ', orientation='h', 
                              color_discrete_map=color_map_risk, category_orders={'カテゴリ': cat_order})
            fig_side.update_layout(xaxis=dict(range=[0, 100]), yaxis=dict(categoryorder='array', categoryarray=draw_order_left), 
                                   margin=common_margins, height=280, showlegend=False, barmode='stack')
            st.plotly_chart(fig_side, use_container_width=True)

    with c2:
        pitch_list = []
        existing = [p for p in PITCH_ORDER if p in f_risk['TaggedPitchType'].unique()]
        others = [p for p in f_risk['TaggedPitchType'].unique() if p not in PITCH_ORDER]
        draw_order_right = (existing + others)[::-1]
        for pt in draw_order_right:
            pd_sub = f_risk[f_risk['TaggedPitchType'] == pt]
            if not pd_sub.empty:
                counts = pd_sub['ResultCategory'].value_counts(normalize=True) * 100
                for cat in cat_order: pitch_list.append({'球種': pt, 'カテゴリ': cat, '割合(%)': counts.get(cat, 0)})
        
        if pitch_list:
            fig_pt = px.bar(pd.DataFrame(pitch_list), y='球種', x='割合(%)', color='カテゴリ', orientation='h', 
                            color_discrete_map=color_map_risk, category_orders={'カテゴリ': cat_order})
            fig_pt.update_layout(xaxis=dict(range=[0, 100]), yaxis=dict(categoryorder='array', categoryarray=draw_order_right), 
                                   margin=common_margins, height=280, showlegend=True, 
                                   legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, title=""), barmode='stack')
            st.plotly_chart(fig_pt, use_container_width=True)

# --- 5. 統計タブ描画 ---
def render_stats_tab(f_data, key_suffix):
    if f_data.empty: return st.warning("表示するデータがありません。")
    m1, m2, m3, m4, m5 = st.columns(5)
    fb = f_data[f_data['TaggedPitchType'].isin(["Fastball", "FB"])]
    m1.metric("投球数", f"{len(f_data)} 球")
    m2.metric("平均(直球)", f"{fb['RelSpeed'].mean():.1f} km/h" if not fb.empty else "-")
    m3.metric("最速", f"{f_data['RelSpeed'].max():.1f} km/h")
    m4.metric("スト率", f"{(f_data['is_strike'].mean()*100):.1f} %")
    m5.metric("初球スト", f"{(f_data[f_data['is_first_pitch']==1]['is_strike'].mean()*100):.1f} %")

    summary = f_data.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean', 'max'], 'is_strike': 'mean', 'is_swing': 'mean', 'is_whiff': 'sum'})
    summary.columns = ['投球数', '平均球速', '最速', 'ストライク率', 'スイング率', '空振り数']
    summary = summary.reindex([p for p in PITCH_ORDER if p in summary.index] + [p for p in summary.index if p not in PITCH_ORDER])
    summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
    summary['Whiff %'] = (summary['空振り数'] / f_data.groupby('TaggedPitchType')['is_swing'].sum() * 100).fillna(0)
    
    disp = summary.copy()
    for col in ['平均球速', '最速']: disp[col] = summary[col].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "-")
    disp['投球割合'] = summary['投球割合'].apply(lambda x: f"{x:.1f} %")
    disp['ストライク率'] = (summary['ストライク率'] * 100).apply(lambda x: f"{x:.1f} %")
    disp['Whiff %'] = summary['Whiff %'].apply(lambda x: f"{x:.1f} %")
    
    col_l, col_r = st.columns([2.3, 1])
    with col_l:
        st.write("### 📊 球種別分析")
        st.table(disp[['投球数', '投球割合', '平均球速', '最速', 'ストライク率', 'Whiff %']])
    with col_r:
        st.write("### 🥧 投球割合")
        if not summary.empty:
            labels = summary.index
            pie_colors = [PITCH_COLORS.get(label, "#9EDAE5") for label in labels]
            fig, ax = plt.subplots(figsize=(2.8, 2.8))
            ax.pie(summary['投球数'], labels=labels, autopct='%1.1f%%', startangle=90, 
                   counterclock=False, colors=pie_colors, textprops={'fontsize': 8})
            fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
            st.pyplot(fig)

    render_risk_management_section(f_data)
    render_count_analysis(f_data, key_suffix)

# --- 6. メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tab_titles = ["🔹 SBP", "🔴 紅白戦", "🔹 オープン戦", "⚾ 実戦/PBP", "🔥 pitching"]
    tabs = st.tabs(tab_titles)
    categories = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]
    for i, cat in enumerate(categories):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty: continue
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if p != "Unknown"])
            c1, c2 = st.columns(2)
            p = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{i}")
            d = c2.selectbox("日付を選択", ["すべて"] + sorted(sub['Date'].unique().astype(str), reverse=True), key=f"d_{i}")
            if p != "すべて": sub = sub[sub['Pitcher'] == p]
            if d != "すべて": sub = sub[sub['Date'].astype(str) == d]
            render_stats_tab(sub, f"tab_{i}")
