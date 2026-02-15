import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

PITCH_ORDER = ["Fastball", "Slider", "Cutter", "Curveball", "ChangeUp", "Splitter", "TwoSeamFastBall", "OneSeam", "Sinker"]

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
        
        if 'Pitcher First Name' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher First Name'].astype(str).str.strip()
        else:
            temp_df['Pitcher'] = temp_df.get('Pitcher', "Unknown")

        if 'TaggedPitchType' in temp_df.columns:
            temp_df['TaggedPitchType'] = temp_df['TaggedPitchType'].replace(PITCH_MAP)

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
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)
        
        if 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date
        elif 'Pitch Created At' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Pitch Created At']).dt.date
        else:
            temp_df['Date'] = pd.Timestamp.now().date()

        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True) if list_df else None

# --- 3. グラフ・セクション関数群 ---
def render_break_chart(f_data):
    st.divider()
    st.write("### ● 変化量分析 (Break Chart)")
    plot_df = f_data.dropna(subset=['TaggedPitchType', 'InducedVertBreak', 'HorzBreak']).copy()
    plot_df = plot_df[plot_df['TaggedPitchType'].astype(str).str.strip() != ""]
    if plot_df.empty: return st.info("変化量データがありません。")

    fig = px.scatter(plot_df, x='HorzBreak', y='InducedVertBreak', color='TaggedPitchType',
                     color_discrete_map=PITCH_COLORS, category_orders={'TaggedPitchType': PITCH_ORDER},
                     labels={'HorzBreak': '横の変化 (cm)', 'InducedVertBreak': '縦の変化 (cm)'})
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.update_layout(width=700, height=700, xaxis=dict(range=[-80, 80], scaleanchor="y", scaleratio=1),
                      yaxis=dict(range=[-80, 80]), plot_bgcolor='white')
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2: st.plotly_chart(fig, use_container_width=False)

def render_count_analysis(f_data, key_suffix):
    st.divider()
    st.write("#### ● カウント別 投球割合")
    if 'Balls' not in f_data.columns: return
    target_df = f_data.copy()
    target_df['Count'] = target_df['Balls'].astype(str) + "-" + target_df['Strikes'].astype(str)
    count_order = ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    count_list = []
    for cnt in count_order:
        df_cnt = target_df[target_df['Count'] == cnt]
        if not df_cnt.empty:
            counts = df_cnt['TaggedPitchType'].value_counts(normalize=True) * 100
            for pt, val in counts.items(): count_list.append({'項目': cnt, '球種': pt, '割合(%)': val})
    if count_list:
        fig = px.bar(pd.DataFrame(count_list), x='項目', y='割合(%)', color='球種', color_discrete_map=PITCH_COLORS)
        st.plotly_chart(fig, use_container_width=True)

def render_risk_management(f_data):
    st.divider()
    st.write("#### ● リスク管理 (打球結果)")
    def classify(row):
        res, hit = str(row.get('PlayResult','')).lower(), str(row.get('TaggedHitType','')).lower()
        if 'home' in res: return '本塁打'
        if 'ground' in hit: return 'ゴロ'
        if 'fly' in hit or 'line' in hit: return '外野フライ'
        return 'その他'
    f_risk = f_data.copy()
    f_risk['Result'] = f_risk.apply(classify, axis=1)
    fig = px.bar(f_risk, x='TaggedPitchType', color='Result', barmode='stack')
    st.plotly_chart(fig, use_container_width=True)

# --- 4. タブ描画メイン ---
def render_stats_tab(f_data, mode="full", key_suffix=""):
    if f_data.empty: return st.warning("データなし")
    
    # 指標カード
    m_cols = st.columns(5 if mode=="full" else 3)
    fb = f_data[f_data['TaggedPitchType'] == "Fastball"]
    m_cols[0].metric("投球数", f"{len(f_data)} 球")
    m_cols[1].metric("平均(直球)", f"{fb['RelSpeed'].mean():.1f}" if not fb.empty else "-")
    m_cols[2].metric("最速", f"{f_data['RelSpeed'].max():.1f}")
    if mode == "full":
        m_cols[3].metric("スト率", f"{(f_data['is_strike'].mean()*100):.1f} %")
        m_cols[4].metric("初球スト", f"{(f_data[f_data.get('is_first_pitch',0)==1]['is_strike'].mean()*100):.1f} %")

    # テーブル作成
    agg_dict = {'RelSpeed': ['count', 'mean', 'max']}
    if mode == "full":
        agg_dict.update({'is_strike': 'mean', 'is_whiff': 'sum', 'is_swing': 'sum'})
    
    summary = f_data.groupby('TaggedPitchType').agg(agg_dict)
    summary.columns = [c[0] + "_" + c[1] for c in summary.columns]
    summary['投球割合'] = (summary['RelSpeed_count'] / summary['RelSpeed_count'].sum() * 100)
    
    # 表示用整形
    disp = pd.DataFrame(index=summary.index)
    disp['投球数'] = summary['RelSpeed_count']
    disp['割合'] = summary['投球割合'].apply(lambda x: f"{x:.1f}%")
    disp['平均/最速'] = summary.apply(lambda r: f"{r['RelSpeed_mean']:.1f} / {r['RelSpeed_max']:.1f}", axis=1)
    if mode == "full":
        disp['ストライク率'] = (summary['is_strike_mean'] * 100).apply(lambda x: f"{x:.1f}%")
        disp['Whiff%'] = (summary['is_whiff_sum'] / summary['is_swing_sum'] * 100).fillna(0).apply(lambda x: f"{x:.1f}%")

    col_l, col_r = st.columns([2.3, 1])
    with col_l:
        st.write("### ● 球種別分析")
        st.table(disp)
    with col_r:
        st.write("### ● 投球割合")
        fig, ax = plt.subplots(figsize=(2.8, 2.8))
        ax.pie(summary['RelSpeed_count'], labels=summary.index, autopct='%1.1f%%', colors=[PITCH_COLORS.get(s) for s in summary.index])
        st.pyplot(fig)

    # モードによる分岐
    if mode == "pitching":
        render_break_chart(f_data)
    else:
        render_risk_management(f_data)
        render_count_analysis(f_data, key_suffix)

# --- 5. メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tab_titles = ["● SBP", "● 紅白戦", "● オープン戦", "● PBP", "● pitching"]
    tabs = st.tabs(tab_titles)
    categories = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]
    for i, cat in enumerate(categories):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty: continue
            p = st.selectbox("投手", ["すべて"] + sorted(sub['Pitcher'].unique().tolist()), key=f"p_{i}")
            if p != "すべて": sub = sub[sub['Pitcher'] == p]
            
            # pitchingタブだけ「シンプル+変化量」、他は「フル項目」
            render_stats_tab(sub, mode=("pitching" if cat=="pitching" else "full"), key_suffix=str(i))
else:
    st.error("CSVが見つかりません。")
