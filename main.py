import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

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
            
        fname_lower = os.path.basename(filename).lower()
        if "sbp" in fname_lower: category = "SBP"
        elif "vs" in fname_lower: category = "vs"
        elif "pbp" in fname_lower: category = "PBP"
        elif "pitching" in fname_lower: category = "pitching"
        else: category = "その他"
        
        # 💥 TaggedHitType をそのまま使うため、リネームせず保持
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight',
            'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        temp_df['DataCategory'] = category

        # Pitcher名の抽出
        if 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip()
        else:
            temp_df['Pitcher'] = "Unknown"

        # 指標フラグ作成
        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)

        # 初球判定
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)

        # 日付処理
        if 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date
        else:
            temp_df['Date'] = pd.Timestamp.now().date()

        list_df.append(temp_df)
    
    if not list_df: return None
    data = pd.concat(list_df, axis=0, ignore_index=True)
    return data

# --- リスク管理グラフの描画関数 ---
def render_risk_management(f_data):
    st.write("### 📊 リスク管理")
    
    def classify_result(row):
        res = str(row.get('PlayResult', '')).lower()
        call = str(row.get('PitchCall', '')).lower()
        hit_type = str(row.get('TaggedHitType', '')).lower() # CSVの列を利用
        
        # 1. 完全アウト
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit_type:
            return '完全アウト(三振+内野フライ)'
        # 2. 本塁打
        elif 'home' in res:
            return '本塁打'
        # 3. 四死球
        elif 'walk' in res or 'hitby' in res:
            return '四死球'
        # 4. ゴロ
        elif 'ground' in hit_type:
            return 'ゴロ'
        # 5. 外野フライ+ライナー
        elif 'fly' in hit_type or 'line' in hit_type:
            return '外野フライ+ライナー'
        return None

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    f_risk = f_risk.dropna(subset=['ResultCategory'])

    if f_risk.empty:
        return st.info("リスク管理グラフを表示するための結果データ（PlayResult/TaggedHitType）が不足しています。")

    risk_summary = []
    # 左右別
    for side in ['Left', 'Right']:
        side_data = f_risk[f_risk['BatterSide'] == side]
        if not side_data.empty:
            counts = side_data['ResultCategory'].value_counts(normalize=True) * 100
            for cat, val in counts.items():
                risk_summary.append({'対象': f'対{side}打者', 'カテゴリ': cat, '割合(%)': val})
    
    # 全体
    total_counts = f_risk['ResultCategory'].value_counts(normalize=True) * 100
    for cat, val in total_counts.items():
        risk_summary.append({'対象': '全体平均', 'カテゴリ': cat, '割合(%)': val})

    risk_df = pd.DataFrame(risk_summary)
    color_map = {
        '完全アウト(三振+内野フライ)': '#6495ED', 'ゴロ': '#ADFF2F',
        '外野フライ+ライナー': '#FFD700', '四死球': '#F4A460', '本塁打': '#FF0000'
    }

    fig = px.bar(risk_df, y='対象', x='割合(%)', color='カテゴリ', 
                 orientation='h', color_discrete_map=color_map,
                 category_orders={'カテゴリ': ['完全アウト(三振+内野フライ)', 'ゴロ', '外野フライ+ライナー', '四死球', '本塁打']},
                 height=350)
    fig.update_layout(xaxis_title="割合 (%)", yaxis_title="", legend_title="", margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

# --- (render_stats_tab などの表示部分は前回と同様) ---
# ※ 以前のコードの render_stats_tab 内の最後に render_risk_management(f_data) を追加してください

# メイン処理 (例)
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    # 簡略化のためSBPタブのみ例示
    f = df[df['DataCategory']=="SBP"]
    # ... フィルター処理 ...
    # render_stats_tab(f, "sbp")
