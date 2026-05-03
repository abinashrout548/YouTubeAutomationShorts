# 🎬 YouTube Channel Auto-Sync Tool

Fetches the latest video (title, description, tags) from any YouTube channel
and re-uploads it to your authenticated YouTube channel — all from the terminal.

---

## 📁 Project Structure

```
yt-sync/
├── main.py               ← Main script (run this)
├── requirements.txt      ← Python dependencies
├── client_secrets.json   ← YOU create this (see Step 2 below)
└── token.json            ← Auto-created after first login
```

---

## ✅ Step-by-Step Setup

### Step 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

Also make sure **yt-dlp** is accessible in your terminal:
```bash
yt-dlp --version
```

---

### Step 2 — Create Google Cloud credentials

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Navigate to **APIs & Services → Library**
4. Search for **"YouTube Data API v3"** → Click **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **+ Create Credentials → OAuth 2.0 Client ID**
7. Application type: **Desktop app**
8. Name it anything (e.g. `yt-sync`)
9. Click **Download JSON**
10. Rename the downloaded file to **`client_secrets.json`**
11. Place it in the **same folder** as `main.py`

> ⚠️ Also go to **APIs & Services → OAuth consent screen**
> - Set to **External**
> - Add your Gmail as a **Test User** under "Test users"

---

### Step 3 — Run the script

```bash
python main.py
```

**First run only:** A browser window will open asking you to log in with the
Google account that OWNS the destination channel. Grant the permissions.
A `token.json` is saved — future runs won't need the browser.

---

## 🚀 How It Works

```
Run python main.py
        │
        ▼
Authenticate with Google OAuth
        │
        ▼
Paste any YouTube channel URL / handle
        │
        ▼
Fetches latest video metadata (title, description, tags, category)
        │
        ▼
Downloads the video using yt-dlp (up to 1080p MP4)
        │
        ▼
Uploads to YOUR YouTube channel with all original metadata
        │
        ▼
Prints the new video URL 🎉
```

---

## 🔗 Supported Source Channel Formats

| Format | Example |
|--------|---------|
| Handle URL | `https://www.youtube.com/@MrBeast` |
| Channel URL | `https://www.youtube.com/channel/UCxxxxxx` |
| Custom URL | `https://www.youtube.com/c/ChannelName` |
| Raw Channel ID | `UCxxxxxx` |

---

## ⚙️ Privacy Options

When prompted, choose privacy for the uploaded video:
- `1` → **private** (only you can see it) ← default
- `2` → **unlisted** (anyone with the link)
- `3` → **public** (visible to everyone)

---

## ❗ Common Issues

| Problem | Fix |
|---------|-----|
| `client_secrets.json not found` | Download OAuth credentials from Google Cloud Console |
| `yt-dlp not found` | Run `pip install yt-dlp` |
| `quota exceeded` | YouTube API has a daily quota of 10,000 units. Uploads cost ~1,600 units each |
| `403 forbidden on upload` | Make sure your Google account is added as a Test User in OAuth consent screen |
| Browser doesn't open | Run `python main.py` from terminal, not VS Code Run button |

---

## 📌 Notes

- This tool copies **video file + all metadata** (title, description, tags, category)
- It does **not** copy thumbnails, subtitles, or comments
- Downloaded video is stored temporarily and deleted after upload
- You must be the owner of the **destination** channel
- Source channel can be **any public** YouTube channel

---

## 🛠️ VS Code Tips

1. Open the `yt-sync/` folder in VS Code
2. Open integrated terminal: `Ctrl+\`` (backtick)
3. Run: `pip install -r requirements.txt`
4. Run: `python main.py`
