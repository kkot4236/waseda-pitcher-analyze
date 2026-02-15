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
        
        # カラム名の前後スペース削除
        temp_df.columns = [c.strip() for c in temp_df.columns]
        
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight', 'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        
        # 投手名処理 (文字列型を徹底し、TypeErrorを防止)
        if 'Pitcher First Name' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher First Name'].fillna("Unknown").astype(str).str.strip()
        elif 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].fillna("Unknown").astype(str).str.strip()
        else:
            temp_df['Pitcher'] = "Unknown"

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
        
        # 指標フラグ作成
        if 'PitchCall' in temp_df.columns:
            pc = temp_df['PitchCall'].astype(str).str.upper()
            temp_df['is_strike'] = pc.apply(lambda x: 1 if x in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'].fillna(0).astype(int) == 0) & (temp_df['Strikes'].fillna(0).astype(int) == 0)).astype(int)
        
        # 日付処理
        for col in ['Date', 'Pitch Created At']:
            if col in temp_df.columns:
                temp_df['Date'] = pd.to_datetime(temp_df[col]).dt.date
                break
        if 'Date' not in temp_df.columns: temp_df['Date'] = pd.Timestamp.now().date()
        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True) if list_df else None

def get_safe_order(df):
    present = df['TaggedPitchType'].unique().tolist()
    ordered = [p for p in PITCH_ORDER_BASE if p in present]
    others = [p for p in present if p not in PITCH_ORDER_BASE]
    return ordered + others

# --- 3. グラフ表示関数 ---

def render_break_chart(f_data):
    st.divider()
    st.write("### ● 変化量分析 (Break Chart)")
    plot_df = f_data.dropna(subset=['InducedVertBreak', 'HorzBreak']).copy()
    if plot_df.empty:
        st.info("変化量データがありません。")
        return
    fig = px.scatter(plot_df, x='HorzBreak', y='InducedVertBreak', color='TaggedPitchType',
                     color_discrete_map=PITCH_COLORS, category_orders={'TaggedPitchType': get_safe_order(plot_df)})
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.7)
    fig.update_layout(width=600, height=600, xaxis=dict(range=[-80, 80], scaleanchor="y", scaleratio=1),
                      yaxis=dict(range=[-80, 80]), plot_bgcolor='white')
    st.plotly_chart(fig, use_container_width=False)

def render_count_analysis(f_data):
    st.divider()
    st.write("#### ● カウント別 投球割合")
    if 'Balls' not in f_data.columns or 'Strikes' not in f_data.columns:
        st.info("カウントデータが不足しているため表示できません。")
        return
    target_df = f_data.copy()
    target_df['Count'] = target_df['Balls'].fillna(0).astype(int).astype(str) + "-" + target_df['Strikes'].fillna(0).astype(int).astype(str)
    count_order = ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    count_list = []
    for cnt in count_order:
        df_cnt = target_df[target_df['Count'] == cnt]
        if not df_cnt.empty:
            counts = df_cnt['TaggedPitchType'].value_counts(normalize=True) * 100
            for pt, val in counts.items(): count_list.append({'カウント': cnt, '球種': pt, '割合(%)': val})
    if count_list:
        fig = px.bar(pd.DataFrame(count_list), x='カウント', y='割合(%)', color='球種', 
                     color_discrete_map=PITCH_COLORS, category_orders={'球種': get_safe_order(target_df)})
        st.plotly_chart(fig, use_container_width=True)

def render_risk_management(f_data):
    st.divider()
    st.write("#### ● リスク管理 (打球結果割合)")
    
    def classify_result(row):
        res = str(row.get('PlayResult', '')).lower()
        pc = str(row.get('PitchCall', '')).upper()
        if 'home' in res: return '本塁打'
        if any(x in res for x in ['single', 'double', 'triple']): return '安打'
        if 'out' in res: return '凡退'
        if pc == 'STRIKESWINGING': return '空振り'
        return 'その他'
    
    f_risk = f_data.copy()
    f_risk['結果'] = f_risk.apply(classify_result, axis=1)
    
    # 横向き100%積み上げ棒グラフ
    fig = px.bar(f_risk, y='TaggedPitchType', color='結果', orientation='h',
                 category_orders={'TaggedPitchType': get_safe_order(f_risk), 
                                  '結果': ['空振り', '凡退', '安打', '本塁打', 'その他']},
                 color_discrete_map={'空振り': '#1f77b4', '凡退': '#2ca02c', '安打': '#ff7f0e', '本塁打': '#d62728', 'その他': '#7f7f7f'},
                 barnorm='percent')
    fig.update_layout(xaxis_title="割合 (%)", yaxis_title="", barmode='stack', height=400)
    st.plotly_chart(fig, use_container_width=True)

# --- 4. メインタブ描画 ---
def render_stats_tab(f_data, mode="full"):
    if f_data.empty: return st.warning("対象データがありません")
    
    m_cols = st.columns(5 if mode=="full" else 3)
    fb_data = f_data[f_data['TaggedPitchType'] == "Fastball"]
    m_cols[0].metric("投球数", f"{len(f_data)} 球")
    m_cols[1].metric("平均(直球)", f"{fb_data['RelSpeed'].mean():.1f}" if not fb_data.empty else "-")
    m_cols[2].metric("最速", f"{f_data['RelSpeed'].max():.1f}")
    if mode == "full":
        m_cols[3].metric("スト率", f"{(f_data['is_strike'].mean()*100):.1f} %")
        m_cols[4].metric("初球スト", f"{(f_data[f_data.get('is_first_pitch',0)==1]['is_strike'].mean()*100):.1f} %")

    # 集計処理
    agg_dict = {'RelSpeed': ['count', 'mean', 'max']}
    if mode == "full":
        agg_dict.update({'is_strike': 'mean', 'is_whiff': 'sum', 'is_swing': 'sum'})
    
    summary = f_data.groupby('TaggedPitchType').agg(agg_dict)
    summary.columns = [f"{c[0]}_{c[1]}" for c in summary.columns]
    summary = summary.reindex(get_safe_order(f_data)).dropna(subset=['RelSpeed_count'])

    disp = pd.DataFrame(index=summary.index)
    disp['投球数'] = summary['RelSpeed_count'].astype(int)
    disp['割合'] = (summary['RelSpeed_count'] / summary['RelSpeed_count'].sum() * 100).apply(lambda x: f"{x:.1f}%")
    disp['平均球速'] = summary['RelSpeed_mean'].apply(lambda x: f"{x:.1f}")
    disp['最速'] = summary['RelSpeed_max'].apply(lambda x: f"{x:.1f}")
    if mode == "full":
        disp['ストライク率'] = (summary['is_strike_mean'] * 100).apply(lambda x: f"{x:.1f}%")
        disp['Whiff%'] = (summary['is_whiff_sum'] / summary['is_swing_sum'].replace(0,1) * 100).apply(lambda x: f"{x:.1f}%")

    col_l, col_r = st.columns([2.6, 1])
    with col_l: st.table(disp)
    with col_r:
        fig, ax = plt.subplots(figsize=(2.8, 2.8))
        ax.pie(summary['RelSpeed_count'], labels=summary.index, autopct='%1.1f%%', 
               colors=[PITCH_COLORS.get(s, "#9EDAE5") for s in summary.index], startangle=90, counterclock=False)
        st.pyplot(fig)

    if mode == "pitching":
        render_break_chart(f_data)
    else:
        render_risk_management(f_data) # 横向き棒グラフ
        render_count_analysis(f_data)   # カウント別グラフ

# --- 5. メイン実行 ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tab_titles = ["● SBP", "● 紅白戦", "● オープン戦", "● PBP", "● pitching"]
    tabs = st.tabs(tab_titles)
    for i, cat in enumerate(["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty: continue
            
            c1, c2 = st.columns(2)
            # エラー防止: リスト内のNaNを除去し、全て文字列に変換してソート
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if pd.notna(p)])
            p = c1.selectbox("投手", ["すべて"] + p_list, key=f"p_{i}")
            
            p_sub = sub if p == "すべて" else sub[sub['Pitcher'] == p]
            date_list = sorted([str(d) for d in p_sub['Date'].unique() if pd.notna(d)], reverse=True)
            d = c2.selectbox("日付", ["すべて"] + date_list, key=f"d_{i}")
            
            final_df = p_sub if d == "すべて" else p_sub[p_sub['Date'].astype(str) == d]
            render_stats_tab(final_df, mode=("pitching" if cat=="pitching" else "full"))
else:
    st.error("CSVが見つかりません。")
