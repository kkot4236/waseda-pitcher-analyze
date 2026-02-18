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

PITCH_MAP = {'FB': 'Fastball', 'CB': 'Curveball', 'CU': 'Curveball', 'SL': 'Slider', 'CT': 'Cutter', 'CH': 'ChangeUp', 'SF': 'Splitter', 'SP': 'Splitter', 'SI': 'Sinker'}

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
        
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'Batter Side': 'BatterSide',
            'PlateLocSide (CM)': 'PlateLocSide', 'PlateLocHeight (CM)': 'PlateLocHeight'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        
        p_col = 'Pitcher First Name' if 'Pitcher First Name' in temp_df.columns else 'Pitcher'
        temp_df['Pitcher'] = temp_df[p_col].fillna("Unknown").astype(str).str.strip() if p_col in temp_df.columns else "Unknown"
        
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
        
        if 'PitchCall' in temp_df.columns:
            pc = temp_df['PitchCall'].fillna("").astype(str).str.upper()
            temp_df['is_strike'] = pc.apply(lambda x: 1 if x in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'].fillna(0).astype(int) == 0) & (temp_df['Strikes'].fillna(0).astype(int) == 0)).astype(int)
        
        for col in ['Date', 'Pitch Created At']:
            if col in temp_df.columns:
                temp_df['Date'] = pd.to_datetime(temp_df[col]).dt.date
                break
        if 'Date' not in temp_df.columns: temp_df['Date'] = pd.Timestamp.now().date()
        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True) if list_df else None

# --- 分析コンポーネント ---

def render_count_analysis(f_data, key_suffix):
    st.divider()
    col_head, col_opt = st.columns([3, 1])
    with col_head: st.write("#### ● カウント別 投球割合")
    with col_opt: is_2s = st.checkbox("2ストライクのみ表示", key=f"2s_{key_suffix}")

    if 'Balls' not in f_data.columns: return st.info("カウントデータ不足")

    df_c = f_data.copy()
    df_c['Count'] = df_c['Balls'].fillna(0).astype(int).astype(str) + "-" + df_c['Strikes'].fillna(0).astype(int).astype(str)
    
    order = ["0-2", "1-2", "2-2", "3-2"] if is_2s else ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    display_order = order + ["全体"]

    data_list = []
    for c in order:
        sub = df_c[df_c['Count'] == c]
        if not sub.empty:
            vc = sub['TaggedPitchType'].value_counts(normalize=True) * 100
            for pt, val in vc.items(): data_list.append({'項目': c, '球種': pt, '割合(%)': val})
    
    total_vc = df_c['TaggedPitchType'].value_counts(normalize=True) * 100
    for pt, val in total_vc.items(): data_list.append({'項目': "全体", '球種': pt, '割合(%)': val})
    
    if data_list:
        fig = px.bar(pd.DataFrame(data_list), x='項目', y='割合(%)', color='球種', 
                     category_orders={'項目': display_order}, color_discrete_map=PITCH_COLORS)
        fig.update_layout(yaxis=dict(range=[0, 100]), height=350)
        st.plotly_chart(fig, use_container_width=True, key=f"chart_cnt_{key_suffix}")

def render_risk_management_section(f_data, key_suffix):
    st.divider()
    st.write("#### ● リスク管理 (打球結果)")
    
    def classify_result(row):
        res = str(row.get('PlayResult','')).lower()
        call = str(row.get('PitchCall','')).lower()
        hit = str(row.get('TaggedHitType','')).lower()
        if 'home' in res: return '本塁打'
        if 'walk' in res or 'hitby' in res: return '四死球'
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit or 'swinging' in call: 
            return '完全アウト(内野フライ+三振)'
        if 'ground' in hit: return 'ゴロ'
        if 'fly' in hit or 'line' in hit: return '外野フライ・ライナー'
        return None

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    f_risk = f_risk.dropna(subset=['ResultCategory'])
    
    cat_order = ['完全アウト(内野フライ+三振)', 'ゴロ', '外野フライ・ライナー', '四死球', '本塁打']
    color_map_risk = {
        '完全アウト(内野フライ+三振)': '#87CEEB', 'ゴロ': '#9ACD32', 
        '外野フライ・ライナー': '#F0E68C', '四死球': '#FFB444', '本塁打': '#F08080'
    }

    if f_risk.empty: return st.info("分析用の打球データがありません。")

    c1, c2 = st.columns(2)
    with c1:
        st.write("**左右別**")
        side_list = []
        for label in ['対左打者', '対右打者', '全体合計']:
            sd = f_risk if label == '全体合計' else f_risk[f_risk['BatterSide'] == ('Right' if label == '対右打者' else 'Left')]
            if not sd.empty:
                vc = sd['ResultCategory'].value_counts(normalize=True) * 100
                for cat in cat_order: side_list.append({'対象': label, 'カテゴリ': cat, '割合(%)': vc.get(cat, 0)})
        if side_list:
            fig_s = px.bar(pd.DataFrame(side_list), y='対象', x='割合(%)', color='カテゴリ', orientation='h', 
                           color_discrete_map=color_map_risk, category_orders={'カテゴリ': cat_order})
            fig_s.update_layout(xaxis=dict(range=[0, 100]), height=280, showlegend=False)
            st.plotly_chart(fig_s, use_container_width=True, key=f"risk_s_{key_suffix}")

    with c2:
        st.write("**球種別**")
        pitch_list = []
        p_present = f_risk['TaggedPitchType'].unique()
        p_draw = ([p for p in PITCH_ORDER if p in p_present] + [p for p in p_present if p not in PITCH_ORDER])[::-1]
        for pt in p_draw:
            sub = f_risk[f_risk['TaggedPitchType'] == pt]
            if not sub.empty:
                vc = sub['ResultCategory'].value_counts(normalize=True) * 100
                for cat in cat_order: pitch_list.append({'球種': pt, 'カテゴリ': cat, '割合(%)': vc.get(cat, 0)})
        if pitch_list:
            fig_p = px.bar(pd.DataFrame(pitch_list), y='球種', x='割合(%)', color='カテゴリ', orientation='h', 
                           color_discrete_map=color_map_risk, category_orders={'カテゴリ': cat_order})
            fig_p.update_layout(xaxis=dict(range=[0, 100]), height=280, legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title=""))
            st.plotly_chart(fig_p, use_container_width=True, key=f"risk_p_{key_suffix}")

def render_movement_plot(f_data, key_suffix):
    st.divider()
    st.write("#### ● 変化量プロット (Movement)")
    
    if 'HorzBreak' not in f_data.columns or 'InducedVertBreak' not in f_data.columns:
        return st.info("変化量データ（HorzBreak, InducedVertBreak）が不足しています。")

    # 散布図
    fig = px.scatter(
        f_data, x='HorzBreak', y='InducedVertBreak', color='TaggedPitchType',
        color_discrete_map=PITCH_COLORS,
        category_orders={'TaggedPitchType': PITCH_ORDER},
        hover_data=['RelSpeed'],
        labels={'HorzBreak': '横の変化 (cm)', 'InducedVertBreak': '縦の変化 (cm)'}
    )
    # レイアウト設定
    fig.update_layout(
        height=550,
        xaxis=dict(title="Horizontal Break (cm)", zeroline=True, zerolinewidth=1, zerolinecolor='black'),
        yaxis=dict(title="Induced Vertical Break (cm)", zeroline=True, zerolinewidth=1, zerolinecolor='black'),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"move_{key_suffix}")

def render_stats_tab(f_data, key_suffix, is_pitching=False):
    if f_data.empty: return st.warning("データなし")
    
    # 🔴 小数点第一位にフォーマット
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
    
    # 🔴 テーブル内も小数点第一位に修正
    disp = summary.copy()
    disp['平均球速'] = summary['平均球速'].apply(lambda x: f"{x:.1f}")
    disp['最速'] = summary['最速'].apply(lambda x: f"{x:.1f}")
    disp['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100).apply(lambda x: f"{x:.1f}%")
    disp['ストライク率'] = (summary['ストライク率'] * 100).apply(lambda x: f"{x:.1f}%")
    disp['Whiff %'] = (summary['空振り数'] / summary['スイング数'].replace(0, 1) * 100).apply(lambda x: f"{x:.1f}%")

    cl, cr = st.columns([2.3, 1])
    with cl: st.table(disp[['投球数', '投球割合', '平均球速', '最速', 'ストライク率', 'Whiff %']])
    with cr:
        fig, ax = plt.subplots(figsize=(2.8, 2.8))
        ax.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, colors=[PITCH_COLORS.get(l, "#9EDAE5") for l in summary.index])
        st.pyplot(fig)

    # カテゴリによって表示を分岐
    if is_pitching:
        render_movement_plot(f_data, key_suffix)
    else:
        render_risk_management_section(f_data, key_suffix)
        render_count_analysis(f_data, key_suffix)

# --- メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    cats = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]
    tabs = st.tabs([f"● {c}" for c in cats])
    
    for i, cat in enumerate(cats):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty: 
                st.info(f"{cat} のデータがありません。")
                continue
            
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if p != "Unknown"])
            c1, c2 = st.columns(2)
            p_sel = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"sel_p_{i}")
            d_sel = c2.selectbox("日付を選択", ["すべて"] + sorted(sub['Date'].unique().astype(str), reverse=True), key=f"sel_d_{i}")
            
            f_sub = sub.copy()
            if p_sel != "すべて": f_sub = f_sub[f_sub['Pitcher'] == p_sel]
            if d_sel != "すべて": f_sub = f_sub[f_sub['Date'].astype(str) == d_sel]
            
            # pitchingタブの場合のみ is_pitching=True を渡す
            render_stats_tab(f_sub, f"tab_{i}_{p_sel}_{d_sel}", is_pitching=(cat == "pitching"))
else:
    st.error("CSVなし")
