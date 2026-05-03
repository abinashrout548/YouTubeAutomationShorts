"""
build.py — Run this once to create the .exe
Usage: python build.py
"""

import subprocess
import sys
import os
import shutil

APP_NAME    = "YouTubeShortsSync"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Abinash Rout"
APP_COPYRIGHT = "Copyright (c) Abinash Rout. All Rights Reserved."

def main():
    print("=" * 55)
    print("  🔨 Building YouTubeShortsSync.exe")
    print("=" * 55)

    # Step 1: Install PyInstaller
    print("\n📦 Installing PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # Step 2: Write version info file for Windows exe metadata
    version_file = "version_info.txt"
    with open(version_file, "w", encoding="utf-8") as vf:
        vf.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1,0,0,0), prodvers=(1,0,0,0),
    mask=0x3f, flags=0x0, OS=0x40004,
    fileType=0x1, subtype=0x0,
    date=(0,0)
  ),
  kids=[
    StringFileInfo([StringTable(u'040904B0',[
      StringStruct(u'CompanyName', u'Abinash Rout'),
      StringStruct(u'FileDescription', u'YouTube Shorts Daily Auto-Sync'),
      StringStruct(u'FileVersion', u'1.0.0'),
      StringStruct(u'InternalName', u'YouTubeShortsSync'),
      StringStruct(u'LegalCopyright', u'Copyright (c) Abinash Rout. All Rights Reserved.'),
      StringStruct(u'OriginalFilename', u'YouTubeShortsSync.exe'),
      StringStruct(u'ProductName', u'YouTube Shorts Auto-Sync'),
      StringStruct(u'ProductVersion', u'1.0.0'),
    ])]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)""")

    # Step 3: Build the exe
    print("\n🔨 Building exe (this takes 1-2 minutes)...")
    # Use 'python -m PyInstaller' to avoid PATH issues on Windows
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                         # Single .exe file
        "--console",                         # Keep terminal window (needed for input prompts)
        f"--name={APP_NAME}",
        f"--version-file={version_file}",    # Embed copyright metadata
        "--hidden-import=yt_dlp",
        "--hidden-import=yt_dlp.utils",
        "--hidden-import=yt_dlp.extractor",
        "--hidden-import=yt_dlp.extractor.youtube",
        "--hidden-import=google.auth",
        "--hidden-import=google.auth.transport.requests",
        "--hidden-import=google_auth_oauthlib",
        "--hidden-import=google_auth_oauthlib.flow",
        "--hidden-import=googleapiclient",
        "--hidden-import=googleapiclient.discovery",
        "--hidden-import=googleapiclient.http",
        "--hidden-import=httplib2",
        "--hidden-import=uritemplate",
        "main.py",
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\n❌ Build failed. Check errors above.")
        sys.exit(1)

    # Step 3: Copy required files next to the exe
    exe_path    = os.path.join("dist", f"{APP_NAME}.exe")
    bundle_dir  = os.path.join("dist", "YouTubeShortsSync_Bundle")
    os.makedirs(bundle_dir, exist_ok=True)

    shutil.copy(exe_path, bundle_dir)

    # Copy source_channels.txt if it exists
    if os.path.exists("source_channels.txt"):
        shutil.copy("source_channels.txt", bundle_dir)
    else:
        # Create a blank template
        with open(os.path.join(bundle_dir, "source_channels.txt"), "w") as f:
            f.write("# YouTube Shorts Auto-Sync — Source Channels\n")
            f.write("# One channel URL or handle per line\n")
            f.write("# Lines starting with # are ignored\n\n")
            f.write("# https://www.youtube.com/@ChannelHandle\n")
            f.write("# https://www.youtube.com/@AnotherChannel\n")

    # Create README for the bundle
    with open(os.path.join(bundle_dir, "HOW_TO_USE.txt"), "w", encoding="utf-8") as f:
        f.write("""YouTube Shorts Daily Auto-Sync
==============================
Developed by  : Abinash Rout
All Rights Reserved (c) Abinash Rout

FIRST TIME SETUP (required once):
-----------------------------------
1. Go to https://console.cloud.google.com
2. Create a project
3. Enable "YouTube Data API v3"
4. Go to Credentials → Create OAuth 2.0 Client ID (Desktop App)
5. Download the JSON file
6. Rename it to:  client_secrets.json
7. Place client_secrets.json in THIS folder (same folder as the .exe)
8. Go to OAuth consent screen → Test Users → add your Gmail

ADD SOURCE CHANNELS:
---------------------
Open source_channels.txt and add one YouTube channel per line:

    https://www.youtube.com/@ChannelHandle
    https://www.youtube.com/@AnotherChannel

HOW TO RUN:
-----------
Double-click:  YouTubeShortsSync.exe

Or run from terminal:
    YouTubeShortsSync.exe

WHAT IT DOES:
-------------
- Reads all channels from source_channels.txt
- Finds all Shorts uploaded TODAY from each channel
- Downloads and re-uploads them to YOUR YouTube channel
- Skips already-synced videos automatically (synced_videos.json)

FILES IN THIS FOLDER:
---------------------
YouTubeShortsSync.exe   ← Main program
client_secrets.json     ← YOU add this (Google API credentials)
source_channels.txt     ← List of source channels to monitor
token.json              ← Auto-created after first login (do not delete)
synced_videos.json      ← Auto-created, tracks uploaded videos

SHARING WITH OTHERS:
--------------------
Share the entire YouTubeShortsSync_Bundle folder.
Each person must add their OWN client_secrets.json from their Google account.
""")

    print(f"""
{'=' * 55}
✅ Build Complete!

📁 Your shareable bundle is ready at:
   dist\\YouTubeShortsSync_Bundle\\

Contents:
   YouTubeShortsSync.exe   ← The program
   source_channels.txt     ← Edit to add channels
   HOW_TO_USE.txt          ← Instructions

⚠️  Each user must add their own client_secrets.json
   (downloaded from Google Cloud Console)

📦 To share: zip the entire bundle folder and send it!
{'=' * 55}
""")

if __name__ == "__main__":
    main()