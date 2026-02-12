import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# 球種の指定順序定義
PITCH_ORDER = [
    "Fastball", "Slider", "Cutter", "Curveball", "ChangeUp", 
    "Splitter", "TwoSeamFastBall", "OneSeam", "Sinker"
]

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
        
        if "紅白戦" in fname:
            category = "紅白戦"
        elif "sbp" in fname_lower:
            category = "SBP"
        elif "vs" in fname_lower:
            category = "オープン戦"
        elif "pbp" in fname_lower:
            category = "実戦/PBP"
        elif "pitching" in fname_lower:
            category = "pitching"
        else:
            category = "その他"
        
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
    
    data = pd.concat(list_df, axis=0, ignore_index=True)
    return data.convert_dtypes(dtype_backend="numpy_nullable")

# --- 3. リスク管理セクション (分類を5項目に修正) ---
def render_risk_management_section(f_data):
    st.divider()
    st.write("#### 📊 リスク管理 (打球結果)")
    
    # ユーザー指定の5分類ロジック
    def classify_result(row):
        res = str(row.get('PlayResult','')).lower()
        call = str(row.get('PitchCall','')).lower()
        hit_type = str(row.get('TaggedHitType','')).lower()
        
        # 1. 本塁打
        if 'home' in res: return '本塁打'
        # 2. 四死球
        if 'walk' in res or 'hitby' in res: return '四死球'
        # 3. 完全アウト (三振 or 内野フライ)
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit_type: return '完全アウト'
        # 4. ゴロ
        if 'ground' in hit_type: return 'ゴロ'
        # 5. 外野フライ・ライナー
        if 'fly' in hit_type or 'line' in hit_type: return '外野フライ・ライナー'
        
        return None

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    f_risk = f_risk.dropna(subset=['ResultCategory'])
    
    if f_risk.empty:
        return st.info("分析用の打球データがありません。")

    # 指定の分類順序と色設定
    cat_order = ['完全アウト', 'ゴロ', '外野フライ・ライナー', '四死球', '本塁打']
    color_map = {
        '完全アウト': '#6495ED',            # 青
        'ゴロ': '#ADFF2F',                # 黄緑
        '外野フライ・ライナー': '#FFD700',   # 黄色
        '四死球': '#F4A460',              # オレンジ
        '本塁打': '#FF4B4B'               # 赤
    }

    c1, c2 = st.columns([1, 1])
    common_margins = dict(l=100, r=20, t=10, b=10)

    with c1:
        side_list = []
        # 並び順：上から 全体 -> 右 -> 左 (Plotly仕様でリストを反転)
        left_display_order = ['対左打者', '対右打者', '全体合計']
        
        for label in ['全体合計', '対右打者', '対左打者']:
            if label == '全体合計': sd = f_risk
            elif label == '対右打者': sd = f_risk[f_risk['BatterSide'] == 'Right']
            else: sd = f_risk[f_risk['BatterSide'] == 'Left']
            
            if not sd.empty:
                counts = sd['ResultCategory'].value_counts(normalize=True) * 100
                for cat, val in counts.items():
                    side_list.append({'対象': label, 'カテゴリ': cat, '割合(%)': val})
        
        if side_list:
            fig_side = px.bar(pd.DataFrame(side_list), y='対象', x='割合(%)', color='カテゴリ', orientation='h', 
                              color_discrete_map=color_map, 
                              category_orders={'カテゴリ': cat_order, '対象': left_display_order})
            fig_side.update_layout(xaxis=dict(range=[0, 100], title="割合 (%)"), yaxis=dict(title=""), margin=common_margins, height=280, showlegend=False, barmode='stack')
            st.plotly_chart(fig_side, use_container_width=True)

    with c2:
        pitch_list = []
        # 並び順：上から PITCH_ORDER 順
        existing_pitches = [p for p in PITCH_ORDER if p in f_risk['TaggedPitchType'].unique()]
        other_pitches = [p for p in f_risk['TaggedPitchType'].unique() if p not in PITCH_ORDER]
        sorted_pitches = existing_pitches + other_pitches
        right_display_order = sorted_pitches[::-1]

        for pt in sorted_pitches:
            pd_sub = f_risk[f_risk['TaggedPitchType'] == pt]
            if not pd_sub.empty:
                for c, v in (pd_sub['ResultCategory'].value_counts(normalize=True)*100).items():
                    pitch_list.append({'球種': pt, 'カテゴリ': c, '割合(%)': v})
        
        if pitch_list:
            fig_pt = px.bar(pd.DataFrame(pitch_list), y='球種', x='割合(%)', color='カテゴリ', orientation='h', 
                            color_discrete_map=color_map, 
                            category_orders={'カテゴリ': cat_order, '球種': right_display_order})
            fig_pt.update_layout(xaxis=dict(range=[0, 100], title="割合 (%)"), yaxis=dict(title=""), margin=common_margins, height=280, 
                                showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, title=""), barmode='stack')
            st.plotly_chart(fig_pt, use_container_width=True)

# --- 4. その他統計タブ (変更なし) ---
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
    available_order = [p for p in PITCH_ORDER if p in summary.index]
    others = [p for p in summary.index if p not in PITCH_ORDER]
    summary = summary.reindex(available_order + others)
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
            fig, ax = plt.subplots(figsize=(2.8, 2.8))
            ax.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, colors=plt.get_cmap('Pastel1').colors, textprops={'fontsize': 8})
            fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
            st.pyplot(fig)

    render_risk_management_section(f_data)

# --- 5. メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tab_titles = ["🔹 SBP", "🔴 紅白戦", "🔹 オープン戦", "⚾ 実戦/PBP", "🔥 pitching"]
    tabs = st.tabs(tab_titles)
    tab_categories = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]

    for i, cat in enumerate(tab_categories):
        with tabs[i]:
            sub_df = df[df['DataCategory'] == cat]
            if sub_df.empty:
                st.info(f"{cat}のデータはありません。")
                continue
            p_list = sorted([str(p) for p in sub_df['Pitcher'].unique() if p != "Unknown"])
            c1, c2 = st.columns(2)
            p = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{i}")
            d = c2.selectbox("日付を選択", ["すべて"] + sorted(sub_df['Date'].unique().astype(str), reverse=True), key=f"d_{i}")
            if p != "すべて": sub_df = sub_df[sub_df['Pitcher'] == p]
            if d != "すべて": sub_df = sub_df[sub_df['Date'].astype(str) == d]
            render_stats_tab(sub_df, f"tab_{i}")
else:
    st.error("dataフォルダにCSVが見つかりません。")
