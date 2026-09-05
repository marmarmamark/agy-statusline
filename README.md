# agy-statusline 📊

[![tests](https://github.com/marmarmamark/agy-statusline/actions/workflows/test.yml/badge.svg)](https://github.com/marmarmamark/agy-statusline/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-brightgreen.svg)](https://www.python.org/)
[![Platform: Antigravity](https://img.shields.io/badge/Antigravity-CLI-orange.svg)](https://github.com/google-deepmind)

A Claude Code-style interactive statusline for the [Google Antigravity](https://github.com/google-deepmind) CLI (`agy`).

Display your context window bar, 5-hour rolling session limit, weekly quota, and Auto-Mode classifier capacity in real time directly within your terminal.

---

## Requirements

| Dependency | Required? | Why | Get it |
| :--- | :--- | :--- | :--- |
| **Google Antigravity (`agy`)** | **Required** | `agy` is what renders the statusline and supplies the context and quota data it displays. Without it the script installs but never runs. | [antigravity.google](https://antigravity.google/) |
| **Python 3.9+** | **Required** | The statusline is a single stdlib-only script. | [python.org](https://www.python.org/) |
| **[`agy-auto-mode`](https://github.com/marmarmamark/agy-auto-mode)** | Optional | Supplies the classifier usage ledger behind the `Auto: N left` segment. Without it that one segment is hidden; everything else works. | [marmarmamark/agy-auto-mode](https://github.com/marmarmamark/agy-auto-mode) |

`install.sh` checks for each of these and tells you what to download if something
is missing, rather than installing a statusline that quietly never appears.

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

- **⚡ Zero UI Lag:** Runs asynchronously; when reset timestamps elapse, a background process detached into its own session (so it outlives the millisecond-long statusline render that spawned it) synchronizes fresh quota from Google's backend without blocking the CLI.
- **🔁 Freshest Reading Wins:** Quota is merged per bucket by reset timestamp, so a long-lived `agy` session piping the figures it read at startup cannot overwrite a newer sync. A reading whose window has rolled over is shown as the last measured value marked `(syncing)` rather than being reported as a full 100%.
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

3. The installer copies the script to `~/.gemini/config/scripts/statusline.py` and registers it in the settings file `agy` actually reads, `~/.gemini/antigravity-cli/settings.json` (falling back to `~/.gemini/config/settings.json` only if the `antigravity-cli` directory does not exist). Existing `statusLine` keys are merged, not overwritten:
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
python3 -m unittest discover -s tests -v
```

Expected output:
```text
----------------------------------------------------------------------
Ran 15 tests in 0.2s

OK
```

---

## Uninstall

To remove the statusline and restore default settings:

```bash
bash install.sh --uninstall
```

---

## Related Tools

`agy-statusline` is one of four independent tools for Antigravity. Each works on
its own; installed together they share quota state through
`/tmp/agy_statusline_cache.json`.

| Tool | What it does |
| :--- | :--- |
| [**agy-auto-mode**](https://github.com/marmarmamark/agy-auto-mode) | Security classifier that removes routine permission prompts. Supplies this statusline's `Auto:` segment. |
| [**agy-auto-resume**](https://github.com/marmarmamark/agy-auto-resume) | Waits out a 100% 5-hour quota and resumes the session automatically. |
| [**gemini-worker**](https://github.com/marmarmamark/gemini-worker) | Delegates grunt work from Claude Code to `agy`. |

---

## License

MIT License. See [LICENSE](LICENSE) for details.
