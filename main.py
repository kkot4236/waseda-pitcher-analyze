import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import numpy as np
import glob

# --- 1. ページ設定 ---
st.set_page_config(page_title="Baseball Analytics Dashboard", layout="wide")

# --- 2. データ読み込み（投手・打者両対応） ---
@st.cache_data
def load_all_data():
    folder_path = os.path.join(os.path.dirname(__file__), "data")
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not all_files: return None
    
    list_df = []
    for filename in all_files:
        try:
            temp_df = pd.read_csv(filename, encoding='utf-8')
        except:
            temp_df = pd.read_csv(filename, encoding='cp932')
            
        # 共通カラム変換
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight', 'Batter Side': 'BatterSide',
            'Batter Name': 'Batter', 'Exit Speed (KMH)': 'ExitSpeed'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        
        # 投手名・打者名のクレンジング
        if 'Pitcher' in temp_df.columns:
            temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip()
        if 'Batter' in temp_df.columns:
            temp_df['Batter'] = temp_df['Batter'].astype(str).str.strip()
            
        # 打球速度の数値化
        if 'ExitSpeed' in temp_df.columns:
            temp_df['ExitSpeed'] = pd.to_numeric(temp_df['ExitSpeed'], errors='coerce')
        
        list_df.append(temp_df)
    
    data = pd.concat(list_df, axis=0, ignore_index=True)
    # 座標をcm単位として扱いやすくする
    data['PlateLocSide_cm'] = pd.to_numeric(data['PlateLocSide'], errors='coerce')
    data['PlateLocHeight_cm'] = pd.to_numeric(data['PlateLocHeight'], errors='coerce')
    return data

df = load_all_data()

# --- 3. 描画パーツ ---
def draw_stylish_batter(ax, batter_side='Right', view_mode="投手目線"):
    """投手/捕手目線と打席に応じたシルエット描画"""
    if view_mode == "投手目線":
        x_offset = 50 if batter_side == 'Right' else -50
        flip = -1 if batter_side == 'Right' else 1
    else: # 捕手目線
        x_offset = -50 if batter_side == 'Right' else 50
        flip = 1 if batter_side == 'Right' else -1

    color, alpha = '#333333', 0.12
    ax.add_patch(plt.Circle((x_offset, 130), 5, color=color, alpha=alpha, zorder=0))
    ax.add_patch(plt.Polygon(np.array([[x_offset-8, 80], [x_offset+8, 80], [x_offset+12, 125], [x_offset-12, 125]]), color=color, alpha=alpha, zorder=0))
    ax.add_patch(plt.Polygon(np.array([[x_offset-8, 80], [x_offset-4, 80], [x_offset-12, 20], [x_offset-20, 20]]), color=color, alpha=alpha, zorder=0))
    ax.add_patch(plt.Polygon(np.array([[x_offset+4, 80], [x_offset+8, 80], [x_offset+15, 20], [x_offset+8, 20]]), color=color, alpha=alpha, zorder=0))
    ax.add_patch(plt.Polygon(np.array([[x_offset+(10*flip), 115], [x_offset+(40*flip), 155], [x_offset+(43*flip), 152], [x_offset+(13*flip), 112]]), color=color, alpha=0.18, zorder=0))

def render_heatmaps(subset, target_name, view_mode):
    """3枚並びのヒートマップを描画"""
    plot_df = subset.copy()
    if view_mode == "捕手目線":
        plot_df['PlateLocSide_cm'] *= -1
    
    batter_hand = plot_df['BatterSide'].mode()[0] if not plot_df.empty and 'BatterSide' in plot_df.columns else 'Right'
    
    x_edges = [-36.5, -21.5, -7.17, 7.17, 21.5, 36.5]
    y_edges = [30.0, 45.0, 65.0, 85.0, 105.0, 120.0]
    V_MIN, V_MAX = 110, 155

    fig, axes = plt.subplots(1, 3, figsize=(20, 8), facecolor='white')
    filters = [plot_df, plot_df[plot_df['PitcherThrows'] == 'Right'], plot_df[plot_df['PitcherThrows'] == 'Left']]
    titles = ['TOTAL', 'VS RIGHT PITCHER', 'VS LEFT PITCHER']

    for i, ax in enumerate(axes):
        sub = filters[i]
        draw_stylish_batter(ax, batter_hand, view_mode)
        
        for r in range(5):
            for c in range(5):
                x_min, x_max = x_edges[c], x_edges[c+1]
                y_min, y_max = y_edges[4-r], y_edges[5-r]
                
                zone_data = sub[(sub['PlateLocSide_cm'] >= x_min) & (sub['PlateLocSide_cm'] < x_max) &
                                (sub['PlateLocHeight_cm'] >= y_min) & (sub['PlateLocHeight_cm'] < y_max)]
                
                avg_v = zone_data['ExitSpeed'].mean()
                count = len(zone_data)
                
                if count > 0:
                    norm = (avg_v - V_MIN) / (V_MAX - V_MIN)
                    color = plt.cm.Reds(np.clip(norm, 0, 1))
                    ax.add_patch(plt.Rectangle((x_min, y_min), x_max-x_min, y_max-y_min, color=color, alpha=0.9, ec='white', lw=0.5))
                    text_col = 'white' if norm > 0.6 else 'black'
                    ax.text((x_min + x_max)/2, (y_min + y_max)/2, f"{avg_v:.1f}\n$n$={count}", ha='center', va='center', fontweight='bold', fontsize=8, color=text_col)

        ax.add_patch(plt.Rectangle((-21.5, 45.0), 43.0, 60.0, fill=False, edgecolor='black', lw=2))
        ax.set_xlim(-75, 75); ax.set_ylim(15, 165); ax.set_aspect('equal'); ax.axis('off')
        ax.set_title(titles[i], fontsize=12, fontweight='bold')
    
    return fig

# --- 4. メイン UI ---
if df is not None:
    tab_pitcher, tab_batter = st.tabs(["🔥 投手分析", "⚾ 打者分析"])

    # --- 投手タブ ---
    with tab_pitcher:
        p_list = sorted(df['Pitcher'].dropna().unique())
        sel_p = st.selectbox("分析対象投手を選択", p_list)
        f_p = df[df['Pitcher'] == sel_p]
        
        # 既存コードの統計表やムーブメントチャートをここに配置
        st.write(f"### {sel_p} の投球統計")
        # (以前の render_stats_tab 等の内容をここに入れる)
        st.info("ここに従来の投手分析（変化量・球速・カウント別割合）が表示されます")

    # --- 打者タブ ---
    with tab_batter:
        # Batter Nameから選択
        b_list = sorted(df['Batter'].dropna().unique())
        sel_b = st.selectbox("分析対象打者を選択 (Batter Name)", b_list)
        
        view_mode = st.radio("表示視点", ["投手目線", "捕手目線"], horizontal=True)
        
        f_b = df[(df['Batter'] == sel_b) & (df['ExitSpeed'].notna())]
        
        if not f_b.empty:
            st.write(f"### {sel_b} コース別平均打球速度ヒートマップ")
            st.pyplot(render_heatmaps(f_b, sel_b, view_mode))
            
            c1, c2, c3 = st.columns(3)
            c1.metric("計測打球数", f"{len(f_b)} 球")
            c2.metric("平均速度", f"{f_b['ExitSpeed'].mean():.1f} km/h")
            c3.metric("最速", f"{f_b['ExitSpeed'].max():.1f} km/h")
        else:
            st.warning("この打者の打球速度データ（Exit Speed）が見つかりません。")
else:
    st.error("dataフォルダにCSVが見つかりません。")
