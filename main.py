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

# --- パステル調のカラーマップ ---
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

# 球種略称の変換マップ
PITCH_MAP = {
    'FB': 'Fastball', 'CB': 'Curveball', 'SL': 'Slider', 
    'CT': 'Cutter', 'CH': 'ChangeUp', 'SF': 'Splitter', 'SI': 'Sinker'
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
        
        # 列名の名寄せ
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 
            'RelSpeed (KMH)': 'RelSpeed', 
            'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 
            'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        
        # --- 投手名の処理 ---
        if 'Pitcher First Name' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher First Name'].astype(str).str.strip()
        elif 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip()
        else:
            temp_df['Pitcher'] = "Unknown"

        # --- 球種名の変換 ---
        if 'TaggedPitchType' in temp_df.columns:
            temp_df['TaggedPitchType'] = temp_df['TaggedPitchType'].replace(PITCH_MAP)

        # カテゴリ分け
        fname = os.path.basename(filename).lower()
        if "紅白戦" in fname: category = "紅白戦"
        elif "sbp" in fname: category = "SBP"
        elif "vs" in fname: category = "オープン戦"
        elif "pbp" in fname: category = "実戦/PBP"
        elif "pitching" in fname: category = "pitching"
        else: category = "その他"
        temp_df['DataCategory'] = category
        
        # 日付の処理
        if 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date
        elif 'Pitch Created At' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Pitch Created At']).dt.date
        else:
            temp_df['Date'] = pd.Timestamp.now().date()

        list_df.append(temp_df)
    
    if not list_df: return None
    # pd.NAによるエラーを避けるため convert_dtypes は使用せず結合
    return pd.concat(list_df, axis=0, ignore_index=True)

# --- 3. 変化量グラフ (Break Chart) ---
def render_break_chart(f_data):
    st.divider()
    st.write("### ● 変化量分析 (Break Chart)")
    
    if 'InducedVertBreak' not in f_data.columns or 'HorzBreak' not in f_data.columns:
        return st.info("変化量データがありません。")

    # 【修正ポイント】グラフ描画の前に、球種や数値が欠損している行を除外する
    plot_df = f_data.dropna(subset=['TaggedPitchType', 'InducedVertBreak', 'HorzBreak']).copy()
    
    # さらに TaggedPitchType が "<NA>" や空文字のものを除外
    plot_df = plot_df[plot_df['TaggedPitchType'].astype(str).str.strip() != ""]
    plot_df = plot_df[plot_df['TaggedPitchType'].astype(str) != "<NA>"]

    if plot_df.empty:
        return st.warning("有効な変化量データがありません。")

    # 散布図の作成
    fig = px.scatter(
        plot_df, 
        x='HorzBreak', 
        y='InducedVertBreak', 
        color='TaggedPitchType',
        color_discrete_map=PITCH_COLORS,
        category_orders={'TaggedPitchType': PITCH_ORDER},
        labels={'HorzBreak': '横の変化量 (cm)', 'InducedVertBreak': '縦の変化量 (cm)'},
        hover_data={'RelSpeed': ':.1f', 'Pitcher': True}
    )

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.7)
    
    fig.update_layout(
        height=600,
        xaxis=dict(range=[-60, 60], zeroline=False),
        yaxis=dict(range=[-60, 60], zeroline=False),
        legend_title="球種",
        plot_bgcolor='white'
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

    st.plotly_chart(fig, use_container_width=True)

# --- 4. 統計タブ描画 ---
def render_stats_tab(f_data):
    if f_data.empty: return st.warning("表示するデータがありません。")
    
    m1, m2, m3 = st.columns(3)
    fb = f_data[f_data['TaggedPitchType'] == "Fastball"]
    m1.metric("投球数", f"{len(f_data)} 球")
    m2.metric("平均(直球)", f"{fb['RelSpeed'].mean():.1f} km/h" if not fb.empty else "-")
    m3.metric("最速", f"{f_data['RelSpeed'].max():.1f} km/h")

    # 統計用データから欠損を除外
    clean_summary_df = f_data.dropna(subset=['TaggedPitchType'])
    summary = clean_summary_df.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean', 'max']})
    summary.columns = ['投球数', '平均球速', '最速']
    summary = summary.reindex([p for p in PITCH_ORDER if p in summary.index] + [p for p in summary.index if p not in PITCH_ORDER])
    summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
    
    disp = summary.copy()
    for col in ['平均球速', '最速']: disp[col] = summary[col].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "-")
    disp['投球割合'] = summary['投球割合'].apply(lambda x: f"{x:.1f} %")
    
    col_l, col_r = st.columns([2.3, 1])
    with col_l:
        st.write("### ● 球種別分析")
        st.table(disp[['投球数', '投球割合', '平均球速', '最速']])
    with col_r:
        st.write("### ● 投球割合")
        if not summary['投球数'].dropna().empty:
            labels = summary.index
            pie_colors = [PITCH_COLORS.get(label, "#9EDAE5") for label in labels]
            fig, ax = plt.subplots(figsize=(2.8, 2.8))
            ax.pie(summary['投球数'].fillna(0), labels=labels, autopct='%1.1f%%', startangle=90, 
                   counterclock=False, colors=pie_colors, textprops={'fontsize': 8})
            fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
            st.pyplot(fig)

    render_break_chart(f_data)

# --- 5. メインロジック ---
# フォルダパスを適切に取得
current_dir = os.path.dirname(__file__)
data_path = os.path.join(current_dir, "data")
df = load_all_data_from_folder(data_path)

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
            
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if str(p) != "nan" and str(p) != "<NA>"])
            c1, c2 = st.columns(2)
            p = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{i}")
            d = c2.selectbox("日付を選択", ["すべて"] + sorted(sub['Date'].unique().astype(str), reverse=True), key=f"d_{i}")
            
            if p != "すべて": sub = sub[sub['Pitcher'] == p]
            if d != "すべて": sub = sub[sub['Date'].astype(str) == d]
            
            render_stats_tab(sub)
else:
    st.error("dataフォルダ内にCSVファイルが見つかりません。")
