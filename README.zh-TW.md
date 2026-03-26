# Claude Stats

[English](./README.md)

本地網頁儀表板，視覺化呈現你的 [Claude Code](https://claude.ai/code) 使用狀況——Token 消耗、活躍時長、模型分佈、各專案明細。

直接讀取 `~/.claude/projects/` 的本地資料，除了 Docker（或 Python）之外不需要任何額外設定。

![dark and light theme](https://img.shields.io/badge/theme-dark%20%7C%20light-1e2130?style=flat-square)
![python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square)
![flask](https://img.shields.io/badge/flask-latest-green?style=flat-square)

![Overview dark](docs/screenshot-overview-dark.png)

![Overview light](docs/screenshot-overview-light.png)

## 功能

**總覽頁**
- **活動熱力圖** — GitHub 風格的 53 週日曆，點擊任一格可展開當天明細
- **16 張 KPI 卡片** — 今日 Token / 輸出 / Session / 活躍時長、本週活躍時長、連續天數、累計統計、本週 / 本月、每日平均、Cache 命中率、最常用 Model / 最活躍專案
- **模型分佈** — Token 用量的圓餅圖
- **熱門專案** — Output vs Input 的水平堆疊長條圖
- **首頁捷徑** — 點左上角 `Claude Stats` 可直接回到總覽頁並結束 drilldown

**Token 頁**
- **每日堆疊長條圖** — 每天的 Input + Output（Cache 已合併進 Input），點擊任一長條可展開 15 分鐘粒度明細
- **各模型輸出量** — 每日各模型的 Output 堆疊圖
- **24H 細項** — 15 分鐘粒度的長條圖，並顯示當天 KPI（總量、Output、Input、Session 數、Active Time、Models Used、最常用 Model / 最活躍專案）
- **高解析下載** — 可將單日 24H 明細直接下載成高解析 PNG
- 支援 7 天 / 30 天 / 全部 篩選

**專案頁**
- 所有專案依 Token 用量排行
- 支援 1D / 7D / 30D / ALL 時間範圍篩選

**通用**
- **活躍時長追蹤** — 透過合併所有 request 的時間區間（去掉平行 agent 的重疊）來計算 Claude Code 真正執行的牆鐘時間
- **專案篩選** — 導覽列下拉選單，可將所有圖表限縮至單一專案
- **自動時區** — 所有時間戳記自動轉換為瀏覽器的本地時區
- **匯出 / 匯入** — 可依專案與天數範圍匯出或匯入 Claude 原始資料，將多台電腦的使用紀錄彙整到同一個 dashboard
- **匯入預覽** — 匯入前可先讀取 zip 內有哪些專案，再選擇要合併的專案與天數範圍
- **深色 / 淺色模式** — 點擊導覽列的 ☀️/🌙 按鈕切換，偏好設定儲存於 `localStorage`
- **自動重新整理** — 每 5 分鐘自動更新資料，也可點擊導覽列的重新整理按鈕手動觸發

![Tokens dark](docs/screenshot-tokens-dark.png)

## 快速開始（Docker）

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats
./run.sh
```

互動式選單：

```
╔══════════════════════════════════╗
║        Claude Stats Runner       ║
╚══════════════════════════════════╝

  1) Start (default port 5050)
  2) Start on custom port
  3) Stop
  4) Rebuild & Start
  5) Exit
```

直接按 **Enter** 以預設 port 5050 啟動，然後開啟 **http://localhost:5050**。

> **需求：** 已安裝並執行 [Docker](https://docs.docker.com/get-docker/)。

## 手動安裝（Python）

```bash
git clone https://github.com/littlehsun/claude-stats
cd claude-stats

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./start.sh
```

## 資料來源

所有資料從本機 `~/.claude/projects/` 讀取，每個子目錄是一個專案，每個 `.jsonl` 檔案是一段對話。程式對每個檔案做兩次解析——第一次建立 `uuid → timestamp` 對照表，第二次擷取 Token 用量並計算每個 request 的實際執行時間區間。

如果你有多台電腦，可以在其中一台按 `Export` 匯出 zip，再到另一台用 `Import` 匯入。匯出與匯入都支援依專案與最近幾天做篩選；匯入前也會先預覽 zip 內有哪些專案，讓你選擇要合併的範圍。匯入時資料會直接合併進單一本機儲存區；相同 assistant 訊息會依訊息識別立即去重，所以磁碟上最後只會保留一份。

| 欄位 | 來源 |
|------|------|
| `input_tokens` | `message.usage.input_tokens` |
| `output_tokens` | `message.usage.output_tokens` |
| `cache_read` | `message.usage.cache_read_input_tokens` |
| `cache_create` | `message.usage.cache_creation_input_tokens` |
| request 持續時間 | `assistant.timestamp − parent_user.timestamp` |

所有資料都不會離開你的電腦。

## 時區

原始資料中的時間戳記以 UTC 儲存。儀表板會自動偵測瀏覽器的本地時區，並將所有日期與小時轉換為對應的本地時間——每日圖表、熱力圖、每小時細項及今日統計均反映你的當地時間，無需任何設定。
