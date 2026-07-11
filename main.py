import pandas as pd
import streamlit as st
import os
import glob

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# 表（st.table）の縦の幅（行の高さ）を完全に均等に揃えるためのカスタムCSS
st.markdown("""
    <style>
    div[data-testid="stTable"] table {
        width: 100% !important;
    }
    div[data-testid="stTable"] th, div[data-testid="stTable"] td {
        height: 48px !important;
        vertical-align: middle !important;
        padding: 6px 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

PITCH_ORDER = ["Fastball", "Slider", "Cutter", "Curveball", "ChangeUp", "Splitter", "TwoSeamFastBall", "OneSeam", "Sinker"]
PITCH_MAP = {'FB': 'Fastball', 'CB': 'Curveball', 'CU': 'Curveball', 'SL': 'Slider', 'CT': 'Cutter', 'CH': 'ChangeUp', 'SF': 'Splitter', 'SP': 'Splitter', 'SI': 'Sinker'}

@st.cache_data(ttl=10)
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
            temp_df['is_strike'] = pc.apply(lambda x: 1 if x in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY', 'STRIKE'] else 0)
            temp_df['is_swing'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = pc.apply(lambda x: 1 if x in ['STRIKESWINGING'] else 0)
        else:
            temp_df['is_strike'] = 0
            temp_df['is_swing'] = 0
            temp_df['is_whiff'] = 0
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'].fillna(0).astype(int) == 0) & (temp_df['Strikes'].fillna(0).astype(int) == 0)).astype(int)
        
        for col in ['Date', 'Pitch Created At']:
            if col in temp_df.columns:
                try:
                    temp_df['Date'] = pd.to_datetime(temp_df[col]).dt.date
                    break
                except:
                    continue
        if 'Date' not in temp_df.columns: temp_df['Date'] = pd.Timestamp.now().date()
        list_df.append(temp_df)
    
    return pd.concat(list_df, axis=0, ignore_index=True) if list_df else None

# --- 分析コンポーネント (テキスト・データテーブルのみの安全構成) ---

def render_count_analysis(f_data, key_suffix):
    if 'Balls' not in f_data.columns or f_data.empty: return
    st.divider()
    st.write("#### ● カウント別 投球割合")
    
    df_c = f_data.copy()
    df_c['Count'] = df_c['Balls'].fillna(0).astype(int).astype(str) + "-" + df_c['Strikes'].fillna(0).astype(int).astype(str)
    
    pivot_df = df_c.groupby(['Count', 'TaggedPitchType']).size().unstack(fill_value=0)
    total_series = df_c['TaggedPitchType'].value_counts()
    pivot_df.loc['全体'] = total_series
    pivot_df = pivot_df.fillna(0)
    
    pivot_pct = pivot_df.div(pivot_df.sum(axis=1), axis=0) * 100
    pivot_pct_str = pivot_pct.round(1).astype(str) + "%"
    st.table(pivot_pct_str)

def render_risk_management_section(f_data, key_suffix):
    if f_data.empty: return
    st.divider()
    st.write("#### ● リスク管理 (打球結果集計)")
    
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
    
    if f_risk.empty: 
        st.info("分析用の打球データがありません。")
        return

    piv_pitch = f_risk.groupby(['TaggedPitchType', 'ResultCategory']).size().unstack(fill_value=0)
    piv_pitch_pct = (piv_pitch.div(piv_pitch.sum(axis=1), axis=0) * 100).round(1).astype(str) + "%"
    st.table(piv_pitch_pct)

def render_movement_plot(f_data, key_suffix):
    if 'HorzBreak' not in f_data.columns or 'InducedVertBreak' not in f_data.columns or f_data.empty:
        return
    st.divider()
    st.write("#### ● 平均変化量データ")
    move_summary = f_data.groupby('TaggedPitchType')[['HorzBreak', 'InducedVertBreak']].mean()
    move_summary.columns = ['横変化量 平均(cm)', '縦変化量 平均(cm)']
    st.table(move_summary.round(1))

def render_stats_tab(f_data, key_suffix, is_pitching=False):
    if f_data is None or f_data.empty: 
        st.warning("表示できるデータがありません。")
        return
    
    df_stat = f_data.copy()

    fb = df_stat[df_stat['TaggedPitchType'] == "Fastball"] if 'TaggedPitchType' in df_stat.columns else pd.DataFrame()
    avg_speed = fb['RelSpeed'].mean() if not fb.empty and 'RelSpeed' in fb.columns else None
    max_speed = df_stat['RelSpeed'].max() if 'RelSpeed' in df_stat.columns else None
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("投球数", f"{len(df_stat)} 球")
    m2.metric("平均(直球)", f"{avg_speed:.1f} km/h" if pd.notna(avg_speed) else "-")
    m3.metric("最速", f"{max_speed:.1f} km/h" if pd.notna(max_speed) else "-")
    m4.metric("スト率", f"{(df_stat['is_strike'].mean()*100):.1f} %" if 'is_strike' in df_stat.columns else "-")
    first_pitch_data = df_stat[df_stat.get('is_first_pitch', 0) == 1]
    m5.metric("初球スト", f"{(first_pitch_data['is_strike'].mean()*100):.1f} %" if not first_pitch_data.empty and 'is_strike' in first_pitch_data.columns else "-")

    unique_pitches = df_stat['TaggedPitchType'].unique() if 'TaggedPitchType' in df_stat.columns else []
    p_present = [p for p in PITCH_ORDER if p in unique_pitches] + [p for p in unique_pitches if p not in unique_pitches]
    
    summary_list = []
    for p in p_present:
        sub = df_stat[df_stat['TaggedPitchType'] == p]
        if sub.empty: continue
        
        g_count, b_count = 0, 0
        if 'TaggedHitType' in sub.columns:
            hit_series = sub['TaggedHitType'].fillna("").astype(str).str.lower()
            g_count = hit_series.str.contains('ground').sum()
            b_count = hit_series.isin(['ground', 'fly', 'line', 'popup']).sum()
            
        summary_list.append({
            '球種': p, '投球数': len(sub),
            '平均球速': sub['RelSpeed'].mean() if 'RelSpeed' in sub.columns else None,
            '最速': sub['RelSpeed'].max() if 'RelSpeed' in sub.columns else None,
            'ストライク率': sub['is_strike'].mean() if 'is_strike' in sub.columns else 0,
            'スイング数': sub['is_swing'].sum() if 'is_swing' in sub.columns else 0,
            '空振り数': sub['is_whiff'].sum() if 'is_whiff' in sub.columns else 0,
            'ゴロ数': g_count, '打球数': b_count
        })
    
    summary = pd.DataFrame(summary_list)
    if summary.empty:
        st.info("集計可能な球種データがありません。")
        return
        
    summary.set_index('球種', inplace=True)

    disp = pd.DataFrame(index=summary.index)
    disp['投球数'] = summary['投球数']
    total_pitches = summary['投球数'].sum()
    disp['投球割合'] = summary['投球数'].apply(lambda x: f"{(x / total_pitches * 100):.1f}%" if total_pitches > 0 else "0.0%")
    disp['平均球速'] = summary.apply(lambda r: f"{r['平均球速']:.1f}" if pd.notna(r['平均球速']) and r['平均球速'] > 0 else "-", axis=1)
    disp['最速'] = summary.apply(lambda r: f"{r['最速']:.1f}" if pd.notna(r['最速']) and r['最速'] > 0 else "-", axis=1)
    disp['ストライク率'] = summary.apply(lambda r: f"{(r['ストライク率'] * 100):.1f}%" if pd.notna(r['ストライク率']) else "-", axis=1)
    disp['Whiff %'] = summary.apply(lambda r: f"{(r['空振り数'] / r['スイング数'] * 100):.1f}%" if r['スイング数'] > 0 else "-", axis=1)
    disp['ゴロ率'] = summary.apply(lambda r: f"{(r['ゴロ数'] / r['打球数'] * 100):.1f}%" if r['打球数'] > 0 else "-", axis=1)

    disp_clean = disp.astype(str).replace({'nan': '-', 'None': '-', 'nan%': '-', '': '-'})
    st.table(disp_clean)

    if is_pitching:
        render_movement_plot(df_stat, key_suffix)
    else:
        render_risk_management_section(df_stat, key_suffix)
        render_count_analysis(df_stat, key_suffix)

# --- メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    cats = ["SBP", "紅白戦", "オープン戦", "実戦/PBP", "pitching"]
    tabs = st.tabs([f"● {c}" for c in cats])
    
    for i, cat in enumerate(cats):
        with tabs[i]:
            sub = df[df['DataCategory'] == cat]
            if sub.empty: 
                st.info(f"{cat} のデータは現在ありません。")
                continue
            
            p_list = sorted([str(p) for p in sub['Pitcher'].unique() if p != "Unknown" and str(p).strip() != ""])
            c1, c2 = st.columns(2)
            p_sel = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"sel_p_{i}")
            d_sel = c2.selectbox("日付を選択", ["すべて"] + sorted(sub['Date'].unique().astype(str), reverse=True), key=f"sel_d_{i}")
            
            f_sub = sub.copy()
            if p_sel != "すべて": f_sub = f_sub[f_sub['Pitcher'] == p_sel]
            if d_sel != "すべて": f_sub = f_sub[f_sub['Date'].astype(str) == d_sel]
            
            render_stats_tab(f_sub, f"tab_{i}_{p_sel}_{d_sel}", is_pitching=(cat == "pitching"))
else:
    st.error("dataフォルダ内にCSVファイルが見つかりません。")
