# Tubi TV Playlist Generator

This script generates M3U playlists and EPG (Electronic Program Guide) data for Tubi TV channels. It's part of a larger project that generates playlists for multiple streaming services including PlutoTV, Plex, Samsung TV Plus, Roku, Stirr, PBS Kids, and PBS.

## Features

- Fetches live channel data from Tubi TV
- Generates M3U playlist with channel information
- Creates XMLTV-format EPG data
- Supports proxy usage for region-specific content
- Groups channels by categories
- Handles UTF-8 encoding and special characters
- Removes duplicate streams
- Sorts channels alphabetically

## Requirements

- Python 3.7+
- Required packages listed in `requirements.txt`

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Simply run the script:
```bash
python tubi_playlist_generator.py
```

The script will generate two files:
- `tubi_playlist.m3u`: Contains the M3U playlist with channel information
- `tubi_epg.xml`: Contains the EPG data in XMLTV format

## Output Format

### M3U Playlist
The M3U playlist includes:
- Channel name
- Channel ID
- Channel logo URL
- Group/category information
- Stream URL

### EPG XML
The EPG data includes:
- Channel information (ID, name, logo)
- Program schedules
- Program titles and descriptions
- Start and end times in XMLTV format

## Note
This script uses proxies to handle region-specific content. If no proxies are available or if they fail, it will attempt to fetch data without a proxy.

## Automated Updates
This repository includes a GitHub Actions workflow that automatically:
- Runs the playlist generator every 8 hours
- Updates the M3U playlist and EPG data
- Cleans the repository history to maintain only the latest data
- Pushes updates to the main branch

The automated workflow ensures that the playlist and EPG data stay current without manual intervention. You can also trigger the workflow manually through the GitHub Actions interface if needed.

To use the automated updates:
1. Fork this repository
2. Enable GitHub Actions in your fork
3. The playlist and EPG files will be automatically updated every 8 hours

The latest files can always be accessed at:
- M3U Playlist: `https://raw.githubusercontent.com/YOUR_USERNAME/tubi-playlist-generator/main/tubi_playlist.m3u`
- EPG Data: `https://raw.githubusercontent.com/YOUR_USERNAME/tubi-playlist-generator/main/tubi_epg.xml`
