import pandas as pd
import streamlit as st
import os
import glob

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# 表（st.table）の見た目を整えるカスタムCSS
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

# --- 2. データの集計処理 (Pandasを使わず、安全な標準ループで処理) ---

def render_count_analysis_safe(f_data, key_suffix):
    if 'Balls' not in f_data.columns or f_data.empty: return
    st.divider()
    col_head, col_opt = st.columns([3, 1])
    with col_head: st.write("#### ● カウント別 投球割合")
    with col_opt: is_2s = st.checkbox("2ストライクのみ表示", key=f"2s_{key_suffix}")

    order = ["0-2", "1-2", "2-2", "3-2"] if is_2s else ["0-0", "1-0", "0-1", "2-0", "1-1", "0-2", "3-0", "2-1", "1-2", "3-1", "2-2", "3-2"]
    
    # 辞書を用いた手動集計 (Pandas groupbyのバグを回避)
    records = f_data.to_dict(orient='records')
    all_pitches = set()
    count_data = {}
    
    for cnt in order + ['全体']:
        count_data[cnt] = {}

    for r in records:
        p_type = str(r.get('TaggedPitchType', 'Unknown'))
        all_pitches.add(p_type)
        
        # 全体カウント
        count_data['全体'][p_type] = count_data['全体'].get(p_type, 0) + 1
        
        # 個別カウント
        b = int(r.get('Balls', 0) if pd.notna(r.get('Balls')) else 0)
        s = int(r.get('Strikes', 0) if pd.notna(r.get('Strikes')) else 0)
        cnt_str = f"{b}-{s}"
        if cnt_str in count_data:
            count_data[cnt_str][p_type] = count_data[cnt_str].get(p_type, 0) + 1

    # テーブル用のデータ作成
    table_rows = []
    display_cols = sorted(list(all_pitches))
    
    for cnt in order + ['全体']:
        total = sum(count_data[cnt].values())
        row = {'カウント': cnt}
        for p_type in display_cols:
            if total > 0:
                pct = (count_data[cnt].get(p_type, 0) / total) * 100
                row[p_type] = f"{pct:.1f}%" if pct > 0 else "0.0%"
            else:
                row[p_type] = "0.0%"
        table_rows.append(row)
        
    df_disp = pd.DataFrame(table_rows).set_index('カウント')
    st.table(df_disp)

def render_risk_management_safe(f_data):
    if f_data.empty: return
    st.divider()
    st.write("#### ● リスク管理 (打球割合データ)")
    
    records = f_data.to_dict(orient='records')
    result_counts = {}
    
    for r in records:
        res = str(r.get('PlayResult','')).lower()
        call = str(r.get('PitchCall','')).lower()
        hit = str(r.get('TaggedHitType','')).lower()
        
        cat = 'その他'
        if 'home' in res: cat = '本塁打'
        elif 'walk' in res or 'hitby' in res: cat = '四死球'
        elif 'strikeout' in res or 'strikeout' in call or 'popup' in hit or 'swinging' in call: cat = '三振・内野フライ'
        elif 'ground' in hit: cat = 'ゴロ'
        elif 'fly' in hit or 'line' in hit: cat = '外野フライ・ライナー'
        else: continue # 空白行などはスキップ
        
        result_counts[cat] = result_counts.get(cat, 0) + 1

    total = sum(result_counts.values())
    if total == 0:
        st.info("分析可能な打球データがありません。")
        return
        
    risk_rows = []
    for cat in ['三振・内野フライ', 'ゴロ', '外野フライ・ライナー', '四死球', '本塁打', 'その他']:
        count = result_counts.get(cat, 0)
        risk_rows.append({
            '結果カテゴリ': cat,
            '件数': count,
            '割合': f"{(count / total * 100):.1f}%"
        })
    st.table(pd.DataFrame(risk_rows).set_index('結果カテゴリ'))

def render_movement_safe(f_data):
    if 'HorzBreak' not in f_data.columns or 'InducedVertBreak' not in f_data.columns or f_data.empty: return
    st.divider()
    st.write("#### ● 球種別 平均変化量")
    
    records = f_data.to_dict(orient='records')
    move_data = {}
    for r in records:
        p_type = str(r.get('TaggedPitchType', 'Unknown'))
        h = r.get('HorzBreak')
        v = r.get('InducedVertBreak')
        if pd.notna(h) and pd.notna(v):
            if p_type not in move_data:
                move_data[p_type] = {'h_sum': 0.0, 'v_sum': 0.0, 'count': 0}
            move_data[p_type]['h_sum'] += float(h)
            move_data[p_type]['v_sum'] += float(v)
            move_data[p_type]['count'] += 1
            
    summary = []
    for p_type, d in move_data.items():
        summary.append({
            '球種': p_type,
            '横変化量 平均(cm)': f"{(d['h_sum']/d['count']):.1f}",
            '縦変化量 平均(cm)': f"{(d['v_sum']/d['count']):.1f}"
        })
    if summary:
        st.table(pd.DataFrame(summary).set_index('球種'))

def render_stats_tab(f_data, key_suffix, is_pitching=False):
    if f_data is None or f_data.empty: 
        st.warning("表示できるデータがありません。")
        return
    
    # メトリクスの手動計算
    records = f_data.to_dict(orient='records')
    total_count = len(records)
    
    fb_speeds = []
    all_speeds = []
    strike_count = 0
    first_pitch_count = 0
    first_pitch_strike = 0
    
    pitch_stats = {}
    
    for r in records:
        p_type = str(r.get('TaggedPitchType', 'Unknown'))
        speed = r.get('RelSpeed')
        is_stk = int(r.get('is_strike', 0))
        is_swg = int(r.get('is_swing', 0))
        is_whf = int(r.get('is_whiff', 0))
        is_1st = int(r.get('is_first_pitch', 0))
        
        # 球速リスト作成
        if pd.notna(speed) and float(speed) > 0:
            all_speeds.append(float(speed))
            if p_type == "Fastball":
                fb_speeds.append(float(speed))
                
        if is_stk: strike_count += 1
        if is_1st:
            first_pitch_count += 1
            if is_stk: first_pitch_strike += 1
            
        # 球種別統計
        if p_type not in pitch_stats:
            pitch_stats[p_type] = {'count': 0, 'speeds': [], 'strike': 0, 'swing': 0, 'whiff': 0, 'ground': 0, 'hit_total': 0}
            
        stat = pitch_stats[p_type]
        stat['count'] += 1
        if pd.notna(speed) and float(speed) > 0:
            stat['speeds'].append(float(speed))
        if is_stk: stat['strike'] += 1
        if is_swg: stat['swing'] += 1
        if is_whf: stat['whiff'] += 1
        
        hit_type = str(r.get('TaggedHitType', '')).lower()
        if hit_type in ['ground', 'fly', 'line', 'popup']:
            stat['hit_total'] += 1
            if 'ground' in hit_type:
                stat['ground'] += 1

    # 1. 上部メトリクス表示
    avg_fb = sum(fb_speeds) / len(fb_speeds) if fb_speeds else None
    max_sp = max(all_speeds) if all_speeds else None
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("投球数", f"{total_count} 球")
    m2.metric("平均(直球)", f"{avg_fb:.1f} km/h" if avg_fb else "-")
    m3.metric("最速", f"{max_sp:.1f} km/h" if max_sp else "-")
    m4.metric("スト率", f"{(strike_count / total_count * 100):.1f} %" if total_count > 0 else "-")
    m5.metric("初球スト", f"{(first_pitch_strike / first_pitch_count * 100):.1f} %" if first_pitch_count > 0 else "-")

    # 2. メインテーブルのデータ構築
    summary_rows = []
    for p in PITCH_ORDER + [pt for pt in pitch_stats if pt not in PITCH_ORDER]:
        if p not in pitch_stats: continue
        st_data = pitch_stats[p]
        
        cnt = st_data['count']
        p_pct = f"{(cnt / total_count * 100):.1f}%" if total_count > 0 else "0.0%"
        avg_v = f"{(sum(st_data['speeds']) / len(st_data['speeds'])):.1f}" if st_data['speeds'] else "-"
        max_v = f"{max(st_data['speeds'] or [0]):.1f}" if st_data['speeds'] else "-"
        st_pct = f"{(st_data['strike'] / cnt * 100):.1f}%" if cnt > 0 else "0.0%"
        whf_pct = f"{(st_data['whiff'] / st_data['swing'] * 100):.1f}%" if st_data['swing'] > 0 else "-"
        g_pct = f"{(st_data['ground'] / st_data['hit_total'] * 100):.1f}%" if st_data['hit_total'] > 0 else "-"
        
        summary_rows.append({
            '球種': p, '投球数': cnt, '投球割合': p_pct, '平均球速': avg_v, 
            '最速': max_v, 'ストライク率': st_pct, 'Whiff %': whf_pct, 'ゴロ率': g_pct
        })
        
    st.table(pd.DataFrame(summary_rows).set_index('球種'))

    # 各サブセクションの描画
    if is_pitching:
        render_movement_safe(f_data)
    else:
        render_risk_management_safe(f_data)
        render_count_analysis_safe(f_data, key_suffix)

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
