# agy-statusline 📊

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-brightgreen.svg)](https://www.python.org/)
[![Platform: Antigravity](https://img.shields.io/badge/Antigravity-CLI-orange.svg)](https://github.com/google-deepmind)

A Claude Code-style interactive statusline for the [Google Antigravity](https://github.com/google-deepmind) CLI (`agy`).

Display your context window bar, 5-hour rolling session limit, weekly quota, and Auto-Mode classifier capacity in real time directly within your terminal.

---

## Preview

```text
[████░░░░░░] 38%  │  5h: 84% left (2h 14m) · Week: 92% left · Auto: 1482 left
```

### Visual Breakdown

| Element | Description |
| :--- | :--- |
| `[████░░░░░░] 38%` | **Context Window Usage**: Visual progress bar tracking active context consumption. |
| `5h: 84% left (2h 14m)` | **5-Hour Rolling Quota**: Real-time remaining session quota and countdown to window reset. |
| `Week: 92% left` | **Weekly Quota**: Long-term quota capacity. |
| `Auto: 1482 left` | **Auto-Mode Classifier**: Remaining daily free classifier requests (from `agy-auto-mode`). |

---

## Key Features

- **⚡ Zero UI Lag:** Runs asynchronously; when reset timestamps elapse, a detached background process synchronizes fresh quota from Google's backend without blocking the CLI.
- **🎨 Color-Coded Health Indicators:** Automatically shifts colors based on usage:
  - 🟢 **Green (>= 50%):** Healthy quota capacity.
  - 🟡 **Yellow (20% - 49%):** Approaching limits.
  - 🔴 **Bold Red (< 20%):** Near exhaustion.
- **📱 Responsive Width Collapse:** Automatically contracts to a compact view (`Ctx: 38% │ 5h: 84% · Wk: 92%`) on split screens or narrow terminal windows.
- **🔒 Standalone & Private:** Reads directly from piped stdin with zero telemetry, zero dependencies, and no remote calls outside local CLI querying.

---

## Quick Install

### One-Line Install (Recommended)

```bash
git clone https://github.com/marmarmamark/agy-statusline.git ~/.gemini/config/agy-statusline \
  && bash ~/.gemini/config/agy-statusline/install.sh --yes
```

### For AI Coding Agents

Give this prompt to your agent in `agy`:

```text
Clone https://github.com/marmarmamark/agy-statusline.git and run bash install.sh --yes to install the Claude Code-style statusline for Antigravity.
```

---

## Manual Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/marmarmamark/agy-statusline.git
   cd agy-statusline
   ```

2. Run the installer:
   ```bash
   bash install.sh
   ```

3. The installer copies the script to `~/.gemini/config/scripts/statusline.py` and registers it in `~/.gemini/config/settings.json`:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 ~/.gemini/config/scripts/statusline.py"
     }
   }
   ```

4. Launch `agy` to see your new statusline!

---

## Running Tests

Run the automated test suite:

```bash
python3 tests/test_statusline.py
```

Expected output:
```text
.......
----------------------------------------------------------------------
Ran 7 tests in 0.001s

OK
```

---

## Uninstall

To remove the statusline and restore default settings:

```bash
bash install.sh --uninstall
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
