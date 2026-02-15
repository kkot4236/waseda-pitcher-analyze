import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# 固定したい球種の順序
PITCH_ORDER_BASE = ["Fastball", "Slider", "Cutter", "Curveball", "ChangeUp", "Splitter", "TwoSeamFastBall", "OneSeam", "Sinker"]

PITCH_COLORS = {
    "Fastball": "#AEC7E8", "Slider": "#FFBB78", "Cutter": "#98DF8A",
    "Curveball": "#FF9896", "ChangeUp": "#C5B0D5", "Splitter": "#C49C94",
    "TwoSeamFastBall": "#F7B6D2", "OneSeam": "#C7C7C7", "Sinker": "#DBDB8D", "Unknown": "#9EDAE5"
}

PITCH_MAP = {'FB': 'Fastball', 'CB': 'Curveball', 'SL': 'Slider', 'CT': 'Cutter', 'CH': 'ChangeUp', 'SF': 'Splitter', 'SI': 'Sinker'}

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
        
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight', 'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        
        # 投手名処理
        if 'Pitcher First Name' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher First Name'].fillna("Unknown").astype(str).str.strip()
        else:
            temp_df['Pitcher'] = temp_df.get('Pitcher', "Unknown")

        # 球種クレンジング
        if 'TaggedPitchType' in temp_df.columns:
            temp_df['TaggedPitchType'] = temp_df['TaggedPitchType'].replace(PITCH_MAP).fillna("Unknown").astype(str)
        else:
            temp_df['TaggedPitchType'] = "Unknown"

        fname = os.path.basename(filename).lower()
        if "紅白戦" in fname: category = "紅白戦"
        elif "sbp" in fname: category = "SBP"
        elif "vs" in fname: category = "オープン戦"
        elif "pbp" in fname: category = "実戦/PBP"
        elif "pitching" in fname: category = "pitching"
        else: category = "その他"
        temp_df['DataCategory'] = category
        
        # 指標フラグ
        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].astype(str).str.upper().apply(lambda x: 1 if x in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].astype(str).str.upper().apply(lambda x: 1 if x in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].astype(str).str.upper().apply(lambda x: 1 if x in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)
        
        # 日付処理
        for col in ['Date', 'Pitch Created At']:
            if col in temp_df.columns:
                temp_df['Date'] = pd.to_datetime(temp_df[col]).dt.date
                break
        if 'Date' not in temp_df.columns:
            temp_df['Date'] = pd.Timestamp.now().date()

        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True) if list_df else None

# --- 3. 共通ユーティリティ ---
def get_safe_order(df):
    present = df['TaggedPitchType'].unique().tolist()
    ordered = [p for p in PITCH_ORDER_BASE if p in present]
    others = [p for p in present if p not in PITCH_ORDER_BASE]
    return ordered + others

# --- 4. 各種グラフ表示関数 ---

def render_break_chart(f_data):
    st.divider()
    st.write("### ● 変化量分析 (Break Chart)")
    plot_df = f_data.dropna(subset=['InducedVertBreak', 'HorzBreak']).copy()
    if plot_df.empty: return st.info("変化量データがありません。")
    
    fig = px.scatter(plot_df, x='HorzBreak', y='InducedVertBreak', color='TaggedPitchType',
                     color_discrete_map=PITCH_COLORS, category_orders={'TaggedPitchType': get_safe_order(plot_df)},
                     labels={'HorzBreak': '横の変化 (cm)', 'InducedVertBreak': '縦の変化 (cm)'})
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.update_layout(width=700, height=700, xaxis=dict(range=[-80, 80], scaleanchor="y", scaleratio=1),
                      yaxis=dict(range=[-80, 80]), plot_bgcolor='white')
    c1, col2, c3 = st.columns([1, 4, 1])
    with col2: st.plotly_chart(fig, use_container_width=False)

def render_count_analysis(f_data):
    st.divider()
    st.write("#### ● カウント別 投球割合")
    if 'Balls' not in f_data.columns or 'Strikes' not in f_data.columns:
        return st.info("カウントデータ（Balls/Strikes）が含まれていません。")
    
    target_df = f_data.copy()
    target_df['Count'] = target_df['Balls'].astype(int).astype(str) + "-" + target_df['Strikes'].astype(int).astype(str)
    
    count_order = ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    count_list = []
    for cnt in count_order:
        df_cnt = target_df[target_df['Count'] == cnt]
        if not df_cnt.empty:
            counts = df_cnt['TaggedPitchType'].value_counts(normalize=True) * 100
            for pt, val in counts.items():
                count_list.append({'カウント': cnt, '球種': pt, '割合(%)': val})
    
    if count_list:
        plot_df = pd.DataFrame(count_list)
        fig = px.bar(plot_df, x='カウント', y='割合(%)', color='球種', 
                     color_discrete_map=PITCH_COLORS,
                     category_orders={'球種': get_safe_order(target_df)})
        st.plotly_chart(fig, use_container_width=True)

def render_risk_management(f_data):
    st.divider()
    st.write("#### ● リスク管理 (球種別打球結果割合)")
    
    def classify_result(row):
        res = str(row.get('PlayResult', '')).lower()
        hit = str(row.get('TaggedHitType', '')).lower()
        if 'home' in res: return '本塁打'
        if 'ground' in hit: return 'ゴロ'
        if 'fly' in hit or 'line' in hit: return '外野フライ'
        if 'out' in res: return '凡退'
        return '安打/その他'
    
    f_risk = f_data.copy()
    f_risk['結果'] = f_risk.apply(classify_result, axis=1)
    
    # 横向きの積み上げ棒グラフ (orientation='h')
    fig = px.bar(f_risk, y='TaggedPitchType', color='結果', 
                 orientation='h',
                 category_orders={'TaggedPitchType': get_safe_order(f_risk)},
                 labels={'TaggedPitchType': '球種', 'count': '投球数'})
    fig.update_layout(barmode='stack', xaxis_title="投球数", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

# --- 5. タブ描画メイン ---
def render_stats_tab(f_data, mode="full"):
    if f_data.empty: return st.warning("データなし")
    
    # 指標カード
    m_cols = st.columns(5 if mode=="full" else 3)
    fb_data = f_data[f_data['TaggedPitchType'] == "Fastball"]
    m_cols[0].metric("投球数", f"{len(f_data)} 球")
    m_cols[1].metric("平均(直球)", f"{fb_data['RelSpeed'].mean():.1f}" if not fb_data.empty else "-")
    m_cols[2].metric("最速", f"{f_data['RelSpeed'].max():.1f}")
    if mode == "full":
        m_cols[3].metric("スト率", f"{(f_data['is_strike'].mean()*100):.1f} %")
        m_cols[4].metric("初球スト", f"{(f_data[f_data.get('is_first_pitch',0)==1]['is_strike'].mean()*100):.1f} %")

    # テーブル集計
    agg_dict = {'RelSpeed': ['count', 'mean', 'max']}
    if mode == "full":
        agg_dict.update({'is_strike': 'mean', 'is_whiff': 'sum', 'is_swing': 'sum'})
    
    summary = f_data.groupby('TaggedPitchType').agg(agg_dict)
    summary.columns = [c[0] + "_" + c[1] for c in summary.columns]
    summary = summary.reindex(get_safe_order(f_data)).dropna(subset=['RelSpeed_count'])

    summary['割合'] = (summary['RelSpeed_count'] / summary['RelSpeed_count'].sum() * 100)
    disp = pd.DataFrame(index=summary.index)
    disp['投球数'] = summary['RelSpeed_count'].astype(int)
    disp['割合'] = summary['割合'].apply(lambda x: f"{x:.1f}%")
    disp['平均球速'] = summary['RelSpeed_mean'].apply(lambda x: f"{x:.1f}")
    disp['最速'] = summary['RelSpeed_max'].apply(lambda x: f"{x:.1f}")
    if mode == "full":
        disp['ストライク率'] = (summary['is_strike_mean'] * 100).apply(lambda x: f"{x:.1f}%")
        disp['Whiff%'] = (summary['is_whiff_sum'] / summary['is_swing_sum'].replace(0,1) * 100).apply(lambda x: f"{x:.1f}%")

    col_l, col_r = st.columns([2.6, 1])
    with col_l:
        st.write("### ● 球種別分析")
        st.table(disp)
    with col_r:
        st.write("### ● 投球割合")
        fig, ax = plt.subplots(figsize=(2.8, 2.8))
        ax.pie(summary['RelSpeed_count'], labels=summary.index, autopct='%1.1f%%', 
               colors=[PITCH_COLORS.get(s, "#9EDAE5") for s in summary.index], startangle=90, counterclock=False)
        st.pyplot(fig)

    # タブごとの表示切り替え
    if mode == "pitching":
        render_break_chart(f_data)
    else:
        render_risk_management(f_data) # 横向き棒グラフ
        render_count_analysis(f_data)   # カウント別グラフ

# --- 6. メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tab_titles = ["● SBP", "● 紅白戦", "● オープン戦", "● PBP", "● pitching"]
    tabs = st.tabs(tab_titles)
    categories = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]
    for i, cat in enumerate(categories):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty:
                st.info(f"{cat}のデータはありません。")
                continue
            
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if p not in ["nan", "Unknown"]])
            c1, c2 = st.columns(2)
            p = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{i}")
            
            p_sub = sub if p == "すべて" else sub[sub['Pitcher'] == p]
            date_list = sorted([str(d) for d in p_sub['Date'].unique()], reverse=True)
            d = c2.selectbox("日付を選択", ["すべて"] + date_list, key=f"d_{i}")
            
            final_df = p_sub if d == "すべて" else p_sub[p_sub['Date'].astype(str) == d]
            
            render_stats_tab(final_df, mode=("pitching" if cat=="pitching" else "full"))
else:
    st.error("CSVが見つかりません。")
