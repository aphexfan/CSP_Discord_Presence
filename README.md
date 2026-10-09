# CSP Discord Presence

Show what you're working on in **Clip Studio Paint** as your Discord status.

```
Playing Clip Studio Paint
Painting: character_sheet
00:42 elapsed
```

It runs quietly in your system tray, picks up the file you have open, and clears your status when CSP closes.

## Features

- Shows the name of the file you're working on (or hide it with one click)
- Pick your activity from the tray: **Painting**, **Editing** or **Drafting** (or add your own)
- Elapsed timer that starts when you open CSP
- Pause button to hide your status without closing anything
- Optional "Start with Windows" toggle
- Only one copy can run at a time

## Setup

### 1. Create a Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Name it **Clip Studio Paint**. This name is what appears after "Playing".
3. Copy the **Application ID** from the General Information page.
4. Under **Rich Presence → Art Assets**, upload an icon and name the key `csp`. New assets can take a few minutes to appear.

### 2. Install Python

Download Python 3.10 or newer from [python.org](https://www.python.org/downloads/). On Windows, check **"Add python.exe to PATH"** in the installer.

### 3. Download and install

Download this repo (green **Code** button → **Download ZIP**) and unzip it somewhere permanent, such as `Documents\csp-discord-presence`. Then open a terminal in that folder and run:

```
py -m pip install -r requirements.txt
```

(On Mac or Linux, use `python3 -m pip install -r requirements.txt`.)

### 4. Run it

Double-click `csp_presence.pyw`. On the first run, `config.json` opens in Notepad. Paste your Application ID into `client_id`, save the file, then right-click the tray icon and choose **Reload settings**.

If you don't see the tray icon, click the **^** arrow next to the clock.

## Tray menu

| Item | What it does |
|---|---|
| *Status line* | Shows what's currently being sent to Discord |
| Activity | Choose Painting / Editing / Drafting |
| Show file name | Toggle between `Painting: sketch` and just `Painting` |
| Pause | Hide your status until you unpause |
| Start with Windows | Launch automatically when you log in |
| Open settings | Edit `config.json` |
| Reload settings | Apply changes made to `config.json` |
| Quit | Clear your status and exit |

## Settings (`config.json`)

| Key | Default | Description |
|---|---|---|
| `client_id` | `""` | Your Discord Application ID |
| `large_image` | `"csp"` | Art asset key for the big icon |
| `large_text` | `"Clip Studio Paint"` | Text shown when hovering the icon |
| `activity` | `"Painting"` | Current activity (also set from the tray) |
| `activities` | `["Painting", "Editing", "Drafting"]` | Options in the Activity menu. Add your own, e.g. `"Inking"` |
| `show_file_name` | `true` | Include the file name |
| `show_extension` | `false` | Show `sketch.clip` instead of `sketch` |
| `update_seconds` | `15` | How often to check (minimum 5) |
| `art_folders` | Documents, Pictures, Desktop | Where to look for recently saved files |
| `recent_minutes` | `120` | How recent a save has to be to count |

`config.example.json` shows the full format.

## How the file name is found

Clip Studio Paint doesn't put the file name in its window title, so the app tries these in order:

1. Files the CSP process currently has open
2. Canvas tab / window titles (Windows)
3. The most recently saved `.clip` file in your `art_folders`

If only method 3 works on your setup, the name updates when you save. Press Ctrl+S after opening a different file.

## Troubleshooting

- **Nothing happens when I double-click.** Run `py csp_presence.pyw` in a terminal to see the error.
- **`No module named ...`** Run the install command from step 3 again.
- **Status doesn't show in Discord.** Make sure the Discord desktop app is open and **Settings → Activity Privacy → Share my activity** is on.
- **Icon is blank in Discord.** Check that the art asset key matches `large_image`, and give new uploads a few minutes.
- **Custom tray icon.** Put a square `tray_icon.png` next to the script and restart.

## Privacy

Rich Presence is visible to anyone who can see your Discord profile. Turn off **Show file name** if your file names are private.

## License

MIT. See [LICENSE](LICENSE).

*Not affiliated with or endorsed by CELSYS or Discord. Clip Studio Paint is a trademark of CELSYS, Inc.*

## About this project

I'm not a programmer. This tool was made with the help of Claude. It works on my setup, but I may not be able to fix complicated bugs myself. Contributions are always welcome!!! ⚞^•⩊•^⚟
