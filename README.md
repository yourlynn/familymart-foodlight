# 🌱 全家友善食光掃描器

掃描台灣全家便利商店「友善食光」即期品（七折商品），自動通知附近門市有哪些特價商品。

## ✨ 功能

- 📍 依座標掃描附近門市（預設 500m）
- 🏪 篩選常去的門市（store_watchlist）
- ⭐ 標記喜歡的商品（watchlist）
- 🚫 過濾不想看的商品（blacklist）
- 📅 平日/假日不同區域排程
- 🔍 探索模式：快速找出附近所有門市

## 🚀 快速開始

### 1. 複製專案
```bash
git clone https://github.com/yourlynn/familymart-foodlight.git
cd familymart-foodlight/familymart-foodlight
```

### 2. 建立設定檔
```bash
cp config.example.json config.json
# 編輯 config.json，填入你的座標
```

### 3. 探索附近門市
```bash
python3 scripts/scanner.py --config config.json --discover
```

### 4. 設定常去門市
把想追蹤的門市名稱填入 `config.json` 的 `store_watchlist`

### 5. 執行掃描
```bash
python3 scripts/scanner.py --config config.json
```

## 📋 設定說明

```json
{
  "search_radius_m": 500,
  "areas": {
    "home": {
      "name": "🏠 家裡",
      "points": [{"lat": 25.0478, "lon": 121.5170}],
      "store_watchlist": ["芝玉店", "新芝蘭店"]
    }
  },
  "watchlist": ["可頌", "咖哩"],
  "blacklist": ["飯糰", "手卷"]
}
```

| 欄位 | 說明 |
|------|------|
| `search_radius_m` | 搜尋半徑（公尺） |
| `areas.*.points` | 座標點（從 Google Maps 複製） |
| `areas.*.store_watchlist` | 常去的門市（空陣列=顯示全部） |
| `watchlist` | 喜好商品關鍵字（標記 ⭐） |
| `blacklist` | 屏蔽商品關鍵字 |

## 🔧 CLI 參數

```bash
python3 scripts/scanner.py --config config.json [OPTIONS]
```

| 參數 | 說明 |
|------|------|
| `--discover` | 探索模式：列出所有門市 |
| `--area <name>` | 指定區域（可重複） |
| `--radius <m>` | 覆蓋搜尋半徑 |
| `--watch <keyword>` | 臨時加入白名單（可重複） |
| `--out <path>` | 輸出到檔案 |

## ⏰ 搭配 Cron 使用

```bash
# 平日 18:00
0 18 * * 1-5  python3 /path/to/scanner.py --config /path/to/config.json

# 假日 17:00
0 17 * * 0,6  python3 /path/to/scanner.py --config /path/to/config.json
```

## 📝 輸出範例

```
🌱 友善食光通知 - 2026/03/10 18:00 (週二)

📍 🏠 家裡

🏪 全家芝玉店
⭐ 白名單商品：黃金奶油鹽可頌、沙茶豬肉炒麵
📦 其他商品：和風咖哩豬肉麵包...等 43 項
```

## 🤖 作為 AI Agent Skill 使用

本專案同時是一個 **AI Agent Skill**，可以讓 AI 助理自動幫你掃描友善食光！

### 專案結構

```
LICENSE
README.md
familymart-foodlight/           ← Skill 資料夾（複製這個）
├── SKILL.md                    ← Agent 指引文件
├── config.example.json         ← 設定檔範本
└── scripts/
    └── scanner.py              ← 核心掃描腳本（僅依賴 Python 標準庫）
```

### OpenClaw

將 `familymart-foodlight/` 資料夾複製到 `~/.openclaw/skills/`：

```bash
git clone https://github.com/yourlynn/familymart-foodlight.git
cp -r familymart-foodlight/familymart-foodlight ~/.openclaw/skills/
```

Agent 會自動讀取 `SKILL.md` 並在你提到「友善食光」、「全家即期品」等關鍵字時觸發。

### Claude Code

將 `familymart-foodlight/` 資料夾複製到 `~/.claude/skills/`：

```bash
git clone https://github.com/yourlynn/familymart-foodlight.git
cp -r familymart-foodlight/familymart-foodlight ~/.claude/skills/
```

然後在對話中提到「掃描友善食光」，Claude 會依照 SKILL.md 的指引執行。

### 其他 Agent 框架

`SKILL.md` 是一個標準的 Markdown 說明文件，包含：
- 觸發條件（description 中的關鍵字）
- 初始化流程
- 日常操作指令
- 設定修改指引

任何能讀取 Markdown 並執行 shell 指令的 Agent 都可以使用。

## 📌 注意事項

- 🕐 友善食光時段：每日 **17:00 - 23:59**
- 🐍 需要 Python 3.7+（僅依賴標準庫）
- 🌐 使用全家公開 API，請勿過度請求

## 📄 License

[MIT](LICENSE)

---

Made with 🌸 by **Lynn** ([@yourlynn](https://github.com/yourlynn))
