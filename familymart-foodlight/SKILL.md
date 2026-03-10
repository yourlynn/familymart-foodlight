---
name: familymart-foodlight
description: >
  掃描台灣全家便利商店的「友善食光」即期品（七折商品），查詢指定座標附近門市有哪些即將到期的特價商品。
  支援門市探索、商品白名單／黑名單篩選、多區域（家裡／公司）排程設定。
  當使用者提到以下情境時，請使用此技能：全家便利商店、友善食光、即期品、七折、惜食、
  FamilyMart、foodlight、「附近全家有什麼」、「今天有什麼即期品」、「幫我看全家」、
  「設定我常去的門市」、「加到白名單」、「不想看到某商品」、「幫我掃描」、
  「便利商店特價」、「即期品通知」。即使使用者沒有明確說出「友善食光」，
  只要語意涉及全家便利商店的即期品或特價食品查詢，都應觸發此技能。
---

# 全家友善食光掃描器

掃描使用者指定座標附近的全家便利商店，取得「友善食光」即期品資訊（每日 17:00–23:59 七折），
並根據使用者的偏好（常去門市、喜好商品）產出篩選後的報告。

## 技能結構

```
familymart-foodlight/
├── SKILL.md              ← 你正在讀的檔案
├── config.example.json   ← 設定檔範本
└── scripts/
    └── scanner.py        ← 核心掃描腳本（僅依賴 Python 標準庫）
```

## Agent 行為總覽

這個技能的核心價值是**幫使用者省下每天手動查全家 APP 的時間**。
Agent 在不同情境下應採取不同行動：

| 使用者意圖 | Agent 應執行的動作 |
|---|---|
| 首次使用、尚無設定檔 | → 執行「初始化流程」 |
| 「幫我掃描」、「今天有什麼」 | → 執行「日常掃描」 |
| 「加門市」、「我搬家了」 | → 執行「修改設定」 |
| 「加白名單」、「不要看到 X」 | → 執行「修改設定」 |
| 「附近有哪些門市」 | → 執行「探索模式」 |

---

## 設定檔（config.json）

技能運作的一切依據來自 `config.json`。若使用者尚無此檔案，Agent 必須先引導建立。

設定檔位置：`{skillDir}/config.json`
範本檔案：`{skillDir}/config.example.json`

### 結構說明

```jsonc
{
  "project": {
    "name": "familymart-foodlight",
    "project_code": "202106302"     // 友善食光專案代碼（固定值，不需更改）
  },
  "search_radius_m": 500,            // 搜尋半徑（公尺），建議 300–800
  "areas": {                          // 可定義多個區域
    "home": {
      "name": "🏠 家裡",              // 顯示名稱
      "points": [                     // 座標點（可多個，結果會合併）
        {"lat": 25.0478, "lon": 121.5170}
      ],
      "store_watchlist": ["芝玉店"]   // 只看這些門市（空陣列 = 顯示全部）
    }
  },
  "schedule": {                       // 排程設定（供自動化工具使用）
    "weekday": {"time": "18:00", "areas": ["work", "home"]},
    "weekend": {"time": "17:00", "areas": ["home"]}
  },
  "watchlist": ["可頌", "咖哩"],      // 喜好商品關鍵字 → 報告中標記 ⭐
  "blacklist": ["飯糰", "手卷"]       // 屏蔽商品關鍵字 → 報告中不顯示
}
```

### 重要欄位行為

- **`store_watchlist`**：陣列為空時，會顯示半徑內所有門市；填入門市名稱後，只會顯示名稱匹配的門市。匹配規則是「包含」，例如填 `"芝玉"` 會匹配 `"全家芝玉店"`。
- **`watchlist`** / **`blacklist`**：用商品名稱的子字串做匹配。blacklist 優先於 watchlist（被屏蔽的不會出現在任何地方）。
- **`points`**：同一區域可放多個座標點，scanner 會對每個點分別呼叫 API 再合併結果，適合要涵蓋較大範圍的場景。

---

## 流程一：初始化設定

當使用者第一次使用、或尚無 config.json 時，按以下步驟引導：

### Step 1：確認座標

詢問使用者想掃描的地點。取得座標的方式：
- 使用者直接提供經緯度
- 使用者提供地址或地標 → Agent 協助轉換為座標（可用 geocoding 或請使用者從 Google Maps 複製）
- 常見場景：「家裡附近」、「公司附近」

### Step 2：建立 config.json

用 `config.example.json` 當範本，填入使用者的座標，寫入 `{skillDir}/config.json`：

```bash
cp {skillDir}/config.example.json {skillDir}/config.json
# 然後用程式或手動編輯 config.json，填入正確座標
```

如果使用者只提供一個地點，只需保留一個 area（例如 `home`），移除不需要的 area。

### Step 3：探索附近門市

執行探索模式，讓使用者看到半徑內有哪些門市：

```bash
python3 {skillDir}/scripts/scanner.py --config {skillDir}/config.json --discover
```

輸出會列出所有門市名稱、距離、即期品數量的表格。

### Step 4：設定常去門市

將使用者挑選的門市名稱填入 config.json 對應 area 的 `store_watchlist`。
提醒使用者：不設 store_watchlist（空陣列）會顯示所有門市，設了之後只看指定門市。

### Step 5：設定商品偏好（可選）

詢問使用者有沒有特別想追蹤或想屏蔽的商品類型，填入 `watchlist` / `blacklist`。
這步是可選的，可以之後再慢慢調整。

---

## 流程二：日常掃描

使用者想查看即期品時，執行：

```bash
python3 {skillDir}/scripts/scanner.py --config {skillDir}/config.json
```

Scanner 會根據今天是平日或假日，自動選擇對應的區域（由 `schedule` 決定）。

### 可用的 CLI 參數

| 參數 | 用途 | 範例 |
|---|---|---|
| `--area <name>` | 指定掃描區域（覆蓋自動排程），可重複 | `--area home --area work` |
| `--radius <m>` | 覆蓋搜尋半徑 | `--radius 800` |
| `--watch <keyword>` | 臨時加入白名單關鍵字，可重複 | `--watch 可頌 --watch 咖哩` |
| `--discover` | 探索模式：列出所有門市 | `--discover` |
| `--out <path>` | 輸出到檔案（預設印到 stdout） | `--out report.md` |

### 解讀輸出

掃描結果是 Markdown 格式，結構如下：

```
🌱 友善食光通知 - 2026/03/10 18:00 (週二)

📍 🏠 家裡

🏪 全家芝玉店
⭐ 白名單商品：黃金奶油鹽可頌、沙茶豬肉炒麵
📦 其他商品：和風咖哩豬肉麵包、皮蛋辣拌麵...等 43 項
```

- **⭐ 白名單商品**：匹配 `watchlist` 關鍵字的商品，全部列出
- **📦 其他商品**：非白名單、非黑名單的商品，最多顯示 3 個 + 總數
- 如果白名單門市都沒有即期品，會顯示「白名單店家都沒有即期品」

Agent 在呈現結果時，可以做額外的整理，例如：
- 高亮使用者特別想要的商品
- 提醒商品數量特別多的門市（可能品項更豐富）
- 如果結果為空，建議使用者擴大搜尋半徑或檢查時段（17:00 前通常沒有資料）

---

## 流程三：修改設定

使用者想調整偏好時，Agent 應直接編輯 `{skillDir}/config.json`。

常見場景與對應操作：

| 使用者說 | Agent 應修改的欄位 |
|---|---|
| 「加一個門市」、「也看 XX 店」 | `areas.{area}.store_watchlist` 加入門市名稱 |
| 「不要看 XX 店了」 | `areas.{area}.store_watchlist` 移除門市名稱 |
| 「我想追蹤可頌」 | `watchlist` 加入 `"可頌"` |
| 「不想看到飯糰」 | `blacklist` 加入 `"飯糰"` |
| 「我搬家了」、「換新座標」 | `areas.{area}.points` 更新座標 |
| 「加一個新區域」 | `areas` 加入新的 area 物件，並更新 `schedule` |
| 「搜尋範圍太小」 | `search_radius_m` 調大（建議不超過 1000） |

修改完成後，建議跑一次 `--discover` 驗證門市清單是否符合預期。

---

## API 背景知識

供 Agent 理解底層原理（不需要向使用者解釋，除非被問到）：

Scanner 呼叫的是全家便利商店友善食光的公開 API：

```
POST https://stamp.family.com.tw/api/maps/MapProductInfo

Request Body:
{
  "Latitude": 25.0478,
  "Longitude": 121.5170,
  "ProjectCode": "202106302",
  "OldPKeys": []           // 已取得的門市 key，避免重複回傳
}
```

- API 不需要認證
- 回傳內容包含每間門市的名稱、地址、距離、以及各商品的名稱與數量
- `ProjectCode` 是友善食光專案的固定代碼
- 友善食光的有效時段是每日 17:00–23:59，時段外 API 可能回傳空結果

---

## 常見問題與排錯

| 問題 | 可能原因 | 解決方式 |
|---|---|---|
| 掃描結果完全為空 | 現在不在 17:00–23:59 時段 | 提醒使用者友善食光的營業時段 |
| 掃描結果為空（在時段內） | 座標錯誤或半徑太小 | 用 `--discover` 確認附近是否有門市 |
| `store_watchlist` 的門市沒出現 | 門市名稱不匹配 | 用 `--discover` 確認正確的門市全名 |
| 網路錯誤 | 無法連到全家 API | 檢查網路連線；確認 `stamp.family.com.tw` 可存取 |
| Python 執行失敗 | 缺少 Python 3 | scanner.py 僅依賴標準庫，確保有 Python 3.7+ |

---

## 自動排程整合（進階）

Scanner 可搭配任何排程工具（cron、n8n、自動化平台）定時執行。
`schedule` 欄位定義了建議的執行時間與區域，排程工具可參考此設定。

Cron 範例：
```bash
# 平日 18:00
0 18 * * 1-5  python3 {skillDir}/scripts/scanner.py --config {skillDir}/config.json

# 假日 17:00
0 17 * * 0,6  python3 {skillDir}/scripts/scanner.py --config {skillDir}/config.json
```

Agent 平台整合時，可將 scanner 的 stdout 輸出直接作為通知內容傳送給使用者。
