# Discogs to Tidal Sync

This project fetches tracks from your Discogs library and adds them to a Tidal playlist using Python.

## Features
- Fetch tracks from your Discogs collection via the Discogs API
- Search and add tracks to a Tidal playlist using an unofficial Tidal API
- CLI for authentication and running the sync process

## Setup
1. Clone this repository and open it in VS Code.
2. Ensure you have Python 3.8+ installed.
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Obtain your Discogs API token and Tidal credentials.

## Usage
Run the main script to start the sync process:
```sh
python main.py
```

You will be prompted for your Discogs token and Tidal login if not already configured.

## Notes
- This project uses unofficial Tidal APIs. Use at your own risk.
- Contributions welcome!
