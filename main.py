"""
╔══════════════════════════════════════════════════════════╗
║        YouTube Shorts Daily Auto-Sync Tool               ║
║                                                          ║
║  Developed by  : Abinash Rout                            ║
║  All Rights Reserved © Abinash Rout                      ║
║  Unauthorized copying, distribution or modification      ║
║  of this software is strictly prohibited.                ║
╚══════════════════════════════════════════════════════════╝

Fetches ALL Shorts uploaded TODAY from source YouTube channels
and re-uploads them to your authenticated YouTube channel automatically.

Requirements:
    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 yt-dlp

Setup:
    1. Go to https://console.cloud.google.com/
    2. Create a project → Enable YouTube Data API v3
    3. Create OAuth 2.0 credentials (Desktop App) → Download as client_secrets.json
    4. Place client_secrets.json in the same folder as this script
    5. Run: python main.py
"""

import os
import sys
import json
import time
import tempfile
import subprocess
import re
from datetime import datetime, timezone, timedelta

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
import googleapiclient.errors
import google.auth.transport.requests


# ─── CONFIG ────────────────────────────────────────────────────────────────────

CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE          = "token.json"
SYNCED_LOG_FILE     = "synced_videos.json"   # Tracks already-uploaded videos

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

SHORTS_MAX_DURATION_SECONDS = 60


# ─── HELPERS ─────────────────────────────────────────────────────────────────────

def log_section(title):
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


# ─── SYNCED LOG ──────────────────────────────────────────────────────────────────

def load_synced_log():
    if os.path.exists(SYNCED_LOG_FILE):
        with open(SYNCED_LOG_FILE, "r") as f:
            return json.load(f)
    return {}

def mark_synced(source_id, uploaded_id):
    data = load_synced_log()
    data[source_id] = {"uploaded_id": uploaded_id, "synced_at": datetime.now(timezone.utc).isoformat()}
    with open(SYNCED_LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def already_synced(source_id):
    return source_id in load_synced_log()


# ─── AUTHENTICATION ─────────────────────────────────────────────────────────────

def authenticate():
    credentials = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            creds_data = json.load(f)
        credentials = google.oauth2.credentials.Credentials(**creds_data)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("🔄 Refreshing token...")
            credentials.refresh(google.auth.transport.requests.Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"\n❌ '{CLIENT_SECRETS_FILE}' not found!")
                print("   → Go to console.cloud.google.com")
                print("   → Enable YouTube Data API v3")
                print("   → Create OAuth 2.0 Client ID (Desktop App)")
                print("   → Download JSON → rename to client_secrets.json\n")
                sys.exit(1)
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES
            )
            print("\n🌐 Opening browser for Google login...")
            print("   → Complete the login in the browser window that opens.")
            print("   → Do NOT close the browser until you see 'Authentication successful'.\n")

            # Try ports in sequence; fall back to console (copy-paste) flow
            credentials = None
            for port in [8080, 8090, 8888, 9000]:
                try:
                    credentials = flow.run_local_server(
                        port=port,
                        open_browser=True,
                        timeout_seconds=120
                    )
                    break
                except OSError:
                    print(f"   ⚠️  Port {port} busy, trying next...")
                except Exception:
                    pass

            if credentials is None:
                # Console fallback: user pastes the auth code manually
                print("\n⚠️  Local server failed. Using manual copy-paste flow instead.")
                print("   A URL will appear below. Open it in your browser,")
                print("   complete login, then paste the redirect URL back here.\n")
                credentials = flow.run_console()

        with open(TOKEN_FILE, "w") as f:
            json.dump({
                "token":         credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri":     credentials.token_uri,
                "client_id":     credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes":        list(credentials.scopes),
            }, f, indent=2)
        print(f"✅ Token saved to {TOKEN_FILE}")

    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)


# ─── CHANNEL RESOLUTION ─────────────────────────────────────────────────────────

def resolve_channel_id(youtube, channel_input):
    channel_input = channel_input.strip()

    if re.match(r"^UC[\w-]{22}$", channel_input):
        resp = youtube.channels().list(part="snippet", id=channel_input).execute()
        if resp.get("items"):
            return channel_input, resp["items"][0]["snippet"]["title"]
        raise ValueError(f"Channel ID not found: {channel_input}")

    match = re.search(r"youtube\.com/channel/(UC[\w-]{22})", channel_input)
    if match:
        cid = match.group(1)
        resp = youtube.channels().list(part="snippet", id=cid).execute()
        title = resp["items"][0]["snippet"]["title"] if resp.get("items") else cid
        return cid, title

    handle_match = re.search(r"youtube\.com/(?:@|c/|user/)([^/?&#]+)", channel_input)
    if handle_match:
        handle = handle_match.group(1)
    elif channel_input.startswith("@"):
        handle = channel_input[1:]
    else:
        handle = channel_input

    print(f"🔍 Resolving handle: @{handle}")

    try:
        resp = youtube.channels().list(part="id,snippet", forHandle=handle).execute()
        if resp.get("items"):
            ch = resp["items"][0]
            return ch["id"], ch["snippet"]["title"]
    except Exception:
        pass

    resp = youtube.search().list(part="snippet", q=handle, type="channel", maxResults=1).execute()
    if resp.get("items"):
        item = resp["items"][0]
        return item["snippet"]["channelId"], item["snippet"]["channelTitle"]

    raise ValueError(f"Could not resolve channel: {channel_input}")


# ─── DURATION PARSER ─────────────────────────────────────────────────────────────

def parse_duration_seconds(iso_duration):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0
    return int(match.group(1) or 0) * 3600 + int(match.group(2) or 0) * 60 + int(match.group(3) or 0)


# ─── FETCH TODAY'S SHORTS ────────────────────────────────────────────────────────

def get_todays_shorts(youtube, channel_id, channel_title):
    local_now   = datetime.now()
    today_start = datetime(local_now.year, local_now.month, local_now.day, tzinfo=timezone.utc)
    today_end   = today_start + timedelta(days=1)

    log_section(f"Scanning: {channel_title}")
    print(f"  Date  : {local_now.strftime('%Y-%m-%d')} (today)")
    print(f"  Window: {today_start.strftime('%H:%M UTC')} → {today_end.strftime('%H:%M UTC')}")

    ch_resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    if not ch_resp.get("items"):
        raise ValueError(f"Channel not found: {channel_id}")

    uploads_playlist = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    shorts_today    = []
    next_page_token = None
    total_checked   = 0
    stop_scanning   = False

    print(f"\n  Scanning uploads...")

    while not stop_scanning:
        pl_resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        items = pl_resp.get("items", [])
        if not items:
            break

        video_ids = [item["contentDetails"]["videoId"] for item in items]

        vids_resp = youtube.videos().list(
            part="snippet,contentDetails",
            id=",".join(video_ids)
        ).execute()

        for video in vids_resp.get("items", []):
            total_checked += 1
            vid_id       = video["id"]
            snippet      = video["snippet"]
            published_at = snippet.get("publishedAt", "")
            duration_sec = parse_duration_seconds(video["contentDetails"].get("duration", ""))

            try:
                pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except Exception:
                continue

            if pub_time < today_start:
                print(f"  ⏹  Reached videos older than today — stopping.")
                stop_scanning = True
                break

            if pub_time >= today_end:
                continue

            is_short = 0 < duration_sec <= SHORTS_MAX_DURATION_SECONDS
            label    = "✅ SHORT" if is_short else f"⏭  LONG ({duration_sec}s)"
            print(f"  {label} | {pub_time.strftime('%H:%M')} | {snippet['title'][:52]}")

            if is_short:
                shorts_today.append({
                    "id":          vid_id,
                    "url":         f"https://www.youtube.com/shorts/{vid_id}",
                    "title":       snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "tags":        snippet.get("tags", []),
                    "category_id": snippet.get("categoryId", "22"),
                    "published_at": published_at,
                    "duration_sec": duration_sec,
                })

        if not stop_scanning:
            next_page_token = pl_resp.get("nextPageToken")
            if not next_page_token:
                break

    print(f"\n  Checked  : {total_checked} video(s)")
    print(f"  Shorts   : {len(shorts_today)} found today")
    return shorts_today


# ─── DOWNLOAD ────────────────────────────────────────────────────────────────────

def download_video(url, output_dir, title):
    """
    Download using yt-dlp Python API directly.
    No subprocess, no ffmpeg required.
    """
    print(f"\n  ⬇️  Downloading: {title[:60]}")

    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        # Best single-file mp4 — no merging, no ffmpeg needed
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Find downloaded file
    for fname in os.listdir(output_dir):
        if fname.endswith((".mp4", ".webm", ".mkv", ".mov")):
            fpath = os.path.join(output_dir, fname)
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            print(f"     ✅ Downloaded: {fname} ({size_mb:.1f} MB)")
            return fpath

    raise FileNotFoundError("Downloaded file not found after yt-dlp.")


# ─── UPLOAD ──────────────────────────────────────────────────────────────────────

def upload_video(youtube, video_path, video_info, privacy):
    print(f"\n  ⬆️  Uploading: {video_info['title'][:60]}")

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":       video_info["title"],
                "description": video_info["description"],
                "tags":        video_info["tags"],
                "categoryId":  video_info["category_id"],
            },
            "status": {
                "privacyStatus":           privacy,
                "selfDeclaredMadeForKids": False,
            }
        },
        media_body=googleapiclient.http.MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024
        )
    )

    response, last_pct = None, -1
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            if pct != last_pct:
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"     [{bar}] {pct}%", end="\r")
                last_pct = pct

    print()
    new_id = response["id"]
    print(f"     ✅ Uploaded → https://www.youtube.com/shorts/{new_id}")
    return new_id


# ─── CHANNELS CONFIG FILE ────────────────────────────────────────────────────────

CHANNELS_FILE = "source_channels.txt"

def load_source_channels():
    """
    Load source channels from source_channels.txt.
    One channel URL/handle per line. Lines starting with # are comments.
    If file doesn't exist, prompts user to enter channels interactively.
    """
    if os.path.exists(CHANNELS_FILE):
        channels = []
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    channels.append(line)
        if channels:
            print(f"\n📄 Loaded {len(channels)} channel(s) from {CHANNELS_FILE}:")
            for i, ch in enumerate(channels, 1):
                print(f"   {i}. {ch}")
            return channels

    # Interactive entry
    log_section("Source Channels")
    print("Enter YouTube channel URLs one by one.")
    print("Accepted formats:")
    print("  • https://www.youtube.com/@ChannelHandle")
    print("  • https://www.youtube.com/channel/UCxxxxxx")
    print("  • @ChannelHandle   or   UCxxxxxx")
    print("\nPress ENTER on an empty line when done.\n")

    channels = []
    while True:
        entry = input(f"  Channel {len(channels)+1} (or ENTER to finish): ").strip()
        if not entry:
            if not channels:
                print("  ❌ Please enter at least one channel.")
                continue
            break
        channels.append(entry)
        print(f"  ✅ Added: {entry}")

    # Save for future runs
    save = input(f"\n💾 Save these channels to {CHANNELS_FILE} for next run? (yes/no): ").strip().lower()
    if save in ("yes", "y"):
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            f.write("# YouTube Shorts Auto-Sync — Source Channels\n")
            f.write("# One channel URL or handle per line\n")
            f.write("# Lines starting with # are ignored\n\n")
            for ch in channels:
                f.write(ch + "\n")
        print(f"  ✅ Saved to {CHANNELS_FILE}")

    return channels


# ─── MAIN ────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  🎬 YouTube Shorts Daily Auto-Sync")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d  %H:%M')}")
    print("  👤 Developed by Abinash Rout")
    print("  © All Rights Reserved")
    print("=" * 60)

    youtube = authenticate()
    print("\n✅ Authenticated with YouTube API")

    # ── Privacy setting
    log_section("Upload Privacy")
    print("  1. private   ← default (only you can see)")
    print("  2. unlisted  (anyone with the link)")
    print("  3. public    (visible to everyone)")
    privacy = {"1": "private", "2": "unlisted", "3": "public"}.get(
        input("\nChoose [1/2/3] (default 1): ").strip(), "private"
    )
    print(f"  → {privacy}")

    # ── Load source channels
    channel_inputs = load_source_channels()

    # ── Resolve all channels first
    print("\n" + "─" * 60)
    print("  Resolving channels...")
    resolved_channels = []
    for ch_input in channel_inputs:
        try:
            ch_id, ch_title = resolve_channel_id(youtube, ch_input)
            resolved_channels.append((ch_id, ch_title))
            print(f"  ✅ {ch_title} ({ch_id})")
        except Exception as e:
            print(f"  ❌ Could not resolve '{ch_input}': {e}")

    if not resolved_channels:
        print("\n❌ No valid channels found. Exiting.")
        sys.exit(1)

    # ── Collect ALL shorts from ALL channels
    all_new_shorts = []
    for ch_id, ch_title in resolved_channels:
        try:
            shorts = get_todays_shorts(youtube, ch_id, ch_title)
            new    = [s for s in shorts if not already_synced(s["id"])]
            all_new_shorts.extend(new)
            print(f"  → {len(new)} new Short(s) to upload from {ch_title}")
        except Exception as e:
            print(f"  ❌ Error scanning {ch_title}: {e}")

    # ── Show full sync plan
    log_section("Sync Plan")
    print(f"  Channels scanned : {len(resolved_channels)}")
    print(f"  Total to upload  : {len(all_new_shorts)}")

    if not all_new_shorts:
        print("\n✅ Nothing new to sync today.")
        sys.exit(0)

    print("\n  Queue:")
    for i, s in enumerate(all_new_shorts, 1):
        print(f"  {i}. [{s['duration_sec']}s] {s['title'][:52]}")

    if input("\n▶  Proceed with all uploads? (yes/no): ").strip().lower() not in ("yes", "y"):
        print("❌ Cancelled.")
        sys.exit(0)

    # ── Download & upload
    success, failed = 0, 0

    for i, short in enumerate(all_new_shorts, 1):
        log_section(f"[{i}/{len(all_new_shorts)}] {short['title'][:48]}")
        print(f"  URL      : {short['url']}")
        print(f"  Duration : {short['duration_sec']}s")
        print(f"  Tags     : {', '.join(short['tags'][:5]) if short['tags'] else 'None'}")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                path   = download_video(short["url"], tmp, short["title"])
                new_id = upload_video(youtube, path, short, privacy)
            mark_synced(short["id"], new_id)
            success += 1
            if i < len(all_new_shorts):
                print("  ⏳ Waiting 3s before next upload...")
                time.sleep(3)
        except Exception as e:
            print(f"\n  ❌ Error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print("  🎉 Sync Complete!")
    print(f"  ✅ Uploaded  : {success}")
    if failed:
        print(f"  ❌ Failed    : {failed}")
    print(f"  📋 Log       : {SYNCED_LOG_FILE}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()