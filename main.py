import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# 球種の指定順序
PITCH_ORDER = ["Fastball", "Slider", "Cutter", "Curveball", "ChangeUp", "Splitter", "TwoSeamFastBall", "OneSeam", "Sinker"]

# パステルカラーマップ
PITCH_COLORS = {
    "Fastball": "#AEC7E8", "Slider": "#FFBB78", "Cutter": "#98DF8A",
    "Curveball": "#FF9896", "ChangeUp": "#C5B0D5", "Splitter": "#C49C94",
    "TwoSeamFastBall": "#F7B6D2", "OneSeam": "#C7C7C7", "Sinker": "#DBDB8D", "Unknown": "#9EDAE5"
}

# 球種名の変換マップ (CSVの略称に対応)
PITCH_MAP = {'FB': 'Fastball', 'CB': 'Curveball', 'CU': 'Curveball', 'SL': 'Slider', 'CT': 'Cutter', 'CH': 'ChangeUp', 'SF': 'Splitter', 'SP': 'Splitter', 'SI': 'Sinker'}

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
        
        temp_df.columns = [c.strip() for c in temp_df.columns]
        
        # カラム名のリネーム
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight', 'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        
        # 投手名処理 (エラー防止のため文字列化を徹底)
        p_col = 'Pitcher First Name' if 'Pitcher First Name' in temp_df.columns else 'Pitcher'
        if p_col in temp_df.columns:
            temp_df['Pitcher'] = temp_df[p_col].fillna("Unknown").astype(str).str.strip()
        else:
            temp_df['Pitcher'] = "Unknown"

        # 球種処理
        if 'TaggedPitchType' in temp_df.columns:
            temp_df['TaggedPitchType'] = temp_df['TaggedPitchType'].replace(PITCH_MAP).fillna("Unknown").astype(str)
        else:
            temp_df['TaggedPitchType'] = "Unknown"

        # カテゴリ分け
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
            pc = temp_df['PitchCall'].fillna("").astype(str).str.upper()
            temp_df['is_strike'] = pc.apply(lambda x: 1 if x in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'].fillna(0).astype(int) == 0) & (temp_df['Strikes'].fillna(0).astype(int) == 0)).astype(int)
        
        # 日付
        for col in ['Date', 'Pitch Created At']:
            if col in temp_df.columns:
                temp_df['Date'] = pd.to_datetime(temp_df[col]).dt.date
                break
        if 'Date' not in temp_df.columns: temp_df['Date'] = pd.Timestamp.now().date()
        
        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True) if list_df else None

# --- 3. 分析コンポーネント ---

def render_count_analysis(f_data, key_suffix):
    st.divider()
    col_head, col_opt = st.columns([3, 1])
    with col_head: st.write("#### ● カウント別 投球割合")
    with col_opt: is_two_strikes = st.checkbox("2ストライクのみ表示", key=f"2s_{key_suffix}")

    if 'Balls' not in f_data.columns or 'Strikes' not in f_data.columns:
        return st.info("カウントデータがありません。")

    target_df = f_data.copy()
    target_df['Balls'] = target_df['Balls'].fillna(0).astype(int)
    target_df['Strikes'] = target_df['Strikes'].fillna(0).astype(int)
    target_df['Count'] = target_df['Balls'].astype(str) + "-" + target_df['Strikes'].astype(str)
    
    count_order = ["0-2", "1-2", "2-2", "3-2"] if is_two_strikes else ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    count_display_order = count_order + ["全体"]

    count_list = []
    # 各カウントの集計
    for cnt in count_order:
        df_cnt = target_df[target_df['Count'] == cnt]
        if not df_cnt.empty:
            counts = df_cnt['TaggedPitchType'].value_counts(normalize=True) * 100
            for pt, val in counts.items():
                count_list.append({'項目': cnt, '球種': pt, '割合(%)': val})
    
    # 全体の集計
    total_counts = target_df['TaggedPitchType'].value_counts(normalize=True) * 100
    for pt, val in total_counts.items():
        count_list.append({'項目': "全体", '球種': pt, '割合(%)': val})
    
    if count_list:
        # 球種の表示順序を安全に作成
        present_pitches = [str(p) for p in target_df['TaggedPitchType'].unique()]
        safe_p_order = [p for p in PITCH_ORDER if p in present_pitches] + [p for p in present_pitches if p not in PITCH_ORDER]
        
        fig = px.bar(pd.DataFrame(count_list), x='項目', y='割合(%)', color='球種', 
                     category_orders={'項目': count_display_order, '球種': safe_p_order},
                     color_discrete_map=PITCH_COLORS)
        fig.update_layout(yaxis=dict(range=[0, 100]), height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

def render_risk_management_section(f_data):
    st.divider()
    st.write("#### ● リスク管理 (打球結果)")
    
    def classify_result(row):
        res = str(row.get('PlayResult','')).lower()
        call = str(row.get('PitchCall','')).lower()
        hit = str(row.get('TaggedHitType','')).lower()
        if 'home' in res: return '本塁打'
        if 'walk' in res or 'hitby' in res: return '四死球'
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit: return '完全アウト(内野フライ+三振)'
        if 'ground' in hit: return 'ゴロ'
        if 'fly' in hit or 'line' in hit: return '外野フライ・ライナー'
        if 'swinging' in call: return '空振り'
        return 'その他'

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    
    cat_order = ['完全アウト(内野フライ+三振)', '空振り', 'ゴロ', '外野フライ・ライナー', '四死球', '本塁打', 'その他']
    color_map_risk = {
        '完全アウト(内野フライ+三振)': '#87CEEB', '空振り': '#AEC7E8', 'ゴロ': '#9ACD32', 
        '外野フライ・ライナー': '#F0E68C', '四死球': '#FFB444', '本塁打': '#F08080', 'その他': '#C7C7C7'
    }

    c1, c2 = st.columns(2)
    common_margins = dict(l=120, r=20, t=10, b=10)

    with c1:
        st.write("**左右別結果**")
        side_list = []
        draw_order_left = ['対左打者', '対右打者', '全体合計']
        for label in draw_order_left:
            sd = f_risk if label == '全体合計' else f_risk[f_risk['BatterSide'] == ('Right' if label == '対右打者' else 'Left')]
            if not sd.empty:
                counts = sd['ResultCategory'].value_counts(normalize=True) * 100
                for cat in cat_order:
                    side_list.append({'対象': label, 'カテゴリ': cat, '割合(%)': counts.get(cat, 0)})
        if side_list:
            fig_side = px.bar(pd.DataFrame(side_list), y='対象', x='割合(%)', color='カテゴリ', orientation='h', 
                              color_discrete_map=color_map_risk, category_orders={'カテゴリ': cat_order})
            fig_side.update_layout(xaxis=dict(range=[0, 100]), margin=common_margins, height=280, showlegend=False)
            st.plotly_chart(fig_side, use_container_width=True)

    with c2:
        st.write("**球種別結果**")
        pitch_list = []
        present_pitches = f_risk['TaggedPitchType'].unique()
        draw_order_right = [p for p in PITCH_ORDER if p in present_pitches] + [p for p in present_pitches if p not in PITCH_ORDER]
        draw_order_right = draw_order_right[::-1] # 下から上に並べる
        for pt in draw_order_right:
            pd_sub = f_risk[f_risk['TaggedPitchType'] == pt]
            if not pd_sub.empty:
                counts = pd_sub['ResultCategory'].value_counts(normalize=True) * 100
                for cat in cat_order:
                    pitch_list.append({'球種': pt, 'カテゴリ': cat, '割合(%)': counts.get(cat, 0)})
        if pitch_list:
            fig_pt = px.bar(pd.DataFrame(pitch_list), y='球種', x='割合(%)', color='カテゴリ', orientation='h', 
                            color_discrete_map=color_map_risk, category_orders={'カテゴリ': cat_order})
            fig_pt.update_layout(xaxis=dict(range=[0, 100]), margin=common_margins, height=280,
                                 legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title=""))
            st.plotly_chart(fig_pt, use_container_width=True)

# --- 4. 統計タブメイン ---
def render_stats_tab(f_data, key_suffix):
    if f_data.empty: return st.warning("表示するデータがありません。")
    
    # 指標表示
    m1, m2, m3, m4, m5 = st.columns(5)
    fb = f_data[f_data['TaggedPitchType'] == "Fastball"]
    m1.metric("投球数", f"{len(f_data)} 球")
    m2.metric("平均(直球)", f"{fb['RelSpeed'].mean():.1f} km/h" if not fb.empty else "-")
    m3.metric("最速", f"{f_data['RelSpeed'].max():.1f} km/h")
    m4.metric("スト率", f"{(f_data['is_strike'].mean()*100):.1f} %")
    m5.metric("初球スト", f"{(f_data[f_data.get('is_first_pitch',0)==1]['is_strike'].mean()*100):.1f} %")

    # テーブル集計
    summary = f_data.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean', 'max'], 'is_strike': 'mean', 'is_swing': 'sum', 'is_whiff': 'sum'})
    summary.columns = ['投球数', '平均球速', '最速', 'ストライク率', 'スイング数', '空振り数']
    summary = summary.reindex([p for p in PITCH_ORDER if p in summary.index] + [p for p in summary.index if p not in PITCH_ORDER]).dropna(subset=['投球数'])
    
    summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
    summary['Whiff %'] = (summary['空振り数'] / summary['スイング数'].replace(0, 1) * 100)

    # 表示用フォーマット
    disp = summary.copy()
    disp['平均球速'] = summary['平均球速'].apply(lambda x: f"{x:.1f}")
    disp['最速'] = summary['最速'].apply(lambda x: f"{x:.1f}")
    disp['投球割合'] = summary['投球割合'].apply(lambda x: f"{x:.1f}%")
    disp['ストライク率'] = (summary['ストライク率'] * 100).apply(lambda x: f"{x:.1f}%")
    disp['Whiff %'] = summary['Whiff %'].apply(lambda x: f"{x:.1f}%")

    col_l, col_r = st.columns([2.3, 1])
    with col_l:
        st.write("### ● 球種別分析")
        st.table(disp[['投球数', '投球割合', '平均球速', '最速', 'ストライク率', 'Whiff %']])
    with col_r:
        st.write("### ● 投球割合")
        fig, ax = plt.subplots(figsize=(2.8, 2.8))
        ax.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, 
               colors=[PITCH_COLORS.get(label, "#9EDAE5") for label in summary.index], textprops={'fontsize': 8})
        st.pyplot(fig)

    render_risk_management_section(f_data)
    render_count_analysis(f_data, key_suffix)

# --- 5. メイン実行 ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tab_titles = ["● SBP", "● 紅白戦", "● オープン戦", "● PBP", "● pitching"]
    tabs = st.tabs(tab_titles)
    categories = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]
    
    for i, cat in enumerate(categories):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty:
                st.info(f"{cat}のデータはまだありません。")
                continue
            
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if p != "Unknown"])
            c1, c2 = st.columns(2)
            p = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{i}")
            d = c2.selectbox("日付を選択", ["すべて"] + sorted(sub['Date'].unique().astype(str), reverse=True), key=f"d_{i}")
            
            f_sub = sub.copy()
            if p != "すべて": f_sub = f_sub[f_sub['Pitcher'] == p]
            if d != "すべて": f_sub = f_sub[f_sub['Date'].astype(str) == d]
            
            render_stats_tab(f_sub, f"tab_{i}")
else:
    st.error("データフォルダ内にCSVが見つかりませんでした。")
