import requests
from bs4 import BeautifulSoup
import json
import re
import xml.etree.ElementTree as ET
import os
from urllib.parse import unquote
from urllib.parse import urlparse, urlunparse
from datetime import datetime
import unicodedata
import urllib3
import html

# Disable the InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_proxies(country_code):
    url = f"https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country={country_code}&ssl=all&anonymity=elite"
    response = requests.get(url)
    if response.status_code == 200:
        proxy_list = response.text.splitlines()
        return [f"socks4://{proxy}" for proxy in proxy_list]
    else:
        print(f"Failed to fetch proxies for {country_code}. Status code: {response.status_code}")
        return []

def fetch_channel_list(proxy, retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://tubitv.com',
        'Referer': 'https://tubitv.com/live-tv-shows',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site'
    }

    def fetch_with_retry(url, params=None):
        for attempt in range(retries):
            try:
                if proxy:
                    response = requests.get(url, params=params, proxies={"http": proxy, "https": proxy}, 
                                         headers=headers, verify=False, timeout=30)
                else:
                    response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
                
                if response.status_code == 200:
                    return response
                print(f"Failed request to {url}. Status: {response.status_code}")
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                if attempt == retries - 1:
                    print(f"Failed all retries for {url}")
        return None

    def replace_quotes(match):
        return '"' + match.group(1).replace('"', r'\"') + '"'

    # First get the live TV page to extract channel data
    response = fetch_with_retry("https://tubitv.com/live")
    if not response:
        print("Failed to fetch live TV page")
        return {'content': []}

    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")

    # Find the script with window.__data
    script_data = None
    for script in soup.find_all("script"):
        if script.string and script.string.strip().startswith("window.__data"):
            script_data = script.string
            break

    if not script_data:
        print("Could not find channel data in page")
        return {'content': []}

    # Extract JSON from script
    start_index = script_data.find("{")
    end_index = script_data.rfind("}") + 1
    json_string = script_data[start_index:end_index]

    # Clean up JSON
    json_string = re.sub(r'\bundefined\b', 'null', json_string)
    pattern = r'(new\s+Date\("[^"]*"\)|read\s+Date\("[^"]*"\))'
    json_string = re.sub(pattern, replace_quotes, json_string)

    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        return {'content': []}

    # Extract channel IDs
    epg = data.get('epg', {})
    content_by_container = epg.get('contentIdsByContainer', {})
    
    # Skip certain container types
    skip_slugs = ['favorite_linear_channels', 'recommended_linear_channels', 'featured_channels', 'recently_added_channels']
    
    # Get unique channel IDs
    channel_ids = []
    for container in content_by_container.values():
        for item in container:
            if item.get('container_slug') not in skip_slugs:
                channel_ids.extend(item.get('contents', []))
    channel_ids = list(set(channel_ids))
    print(f"Found {len(channel_ids)} unique channel IDs")

    # Fetch channel details in groups
    all_channels = []
    group_size = 150
    for i in range(0, len(channel_ids), group_size):
        group = channel_ids[i:i + group_size]
        params = {"content_id": ','.join(map(str, group))}
        
        response = fetch_with_retry("https://tubitv.com/oz/videos/ids", params=params)
        if not response:
            continue
            
        try:
            group_data = response.json()
            if isinstance(group_data, list):
                all_channels.extend(group_data)
                print(f"Added {len(group_data)} channels from group {i//group_size + 1}")
        except json.JSONDecodeError as e:
            print(f"Failed to parse channel group response: {e}")

    print(f"\nTotal channels found: {len(all_channels)}")
    return {'content': all_channels}

def fetch_epg_data(channel_list):
    epg_data = []
    group_size = 150
    grouped_ids = [channel_list[i:i + group_size] for i in range(0, len(channel_list), group_size)]

    for group in grouped_ids:
        url = "https://tubitv.com/oz/epg/programming"
        params = {
            "content_id": ','.join(map(str, group)),
            "start": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration": "24h"
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://tubitv.com/live'
        }
        
        response = requests.get(url, params=params, headers=headers)

        if response.status_code != 200:
            print(f"Failed to fetch EPG data for group. Status code: {response.status_code}")
            continue

        try:
            epg_json = response.json()
            epg_data.extend(epg_json.get('rows', []))
            print(f"Fetched EPG data for {len(epg_json.get('rows', []))} channels")
        except json.JSONDecodeError as e:
            print(f"Error decoding EPG JSON: {e}")

    return epg_data

def clean_stream_url(url):
    if not url:
        return ''
    # Remove any HTML content
    if '<' in url or '>' in url:
        return ''
    
    # Ensure we're getting a valid streaming URL
    if not url.endswith('.m3u8'):
        return ''
        
    parsed_url = urlparse(url)
    clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
    return clean_url

def normalize_text(text):
    if not text:
        return ''
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Convert HTML entities
    text = html.unescape(text)
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Remove any remaining special characters
    text = re.sub(r'[^\x20-\x7E]', '', text)
    return text.strip()

def create_group_mapping(json_data):
    group_mapping = {}
    if not json_data or 'content' not in json_data:
        return group_mapping
        
    for item in json_data.get('content', []):
        content_id = str(item.get('id', ''))
        # Try multiple fields for category information
        category = None
        
        # Check tags
        tags = item.get('tags', [])
        for tag in tags:
            if tag.get('type') in ['category', 'genre']:
                category = tag.get('value')
                break
        
        # Check other potential category fields
        if not category:
            category = (
                item.get('category') or 
                item.get('genre') or 
                item.get('type') or 
                'Other'
            )
        
        group_mapping[content_id] = category
    
    return group_mapping

def create_m3u_playlist(epg_data, group_mapping, country):
    sorted_epg_data = sorted(epg_data, key=lambda x: x.get('title', '').lower())
    playlist = f"#EXTM3U url-tvg=\"https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_epg.xml\"\n"
    playlist += f"# Generated on {datetime.now().isoformat()}\n"
    seen_urls = set()

    for elem in sorted_epg_data:
        try:
            # Clean and validate channel data
            channel_name = normalize_text(elem.get('title', 'Unknown Channel'))
            if not channel_name:
                continue

            # Get and validate stream URL
            stream_url = ''
            if elem.get('video_resources'):
                manifest = elem['video_resources'][0].get('manifest', {})
                if isinstance(manifest, dict):
                    stream_url = manifest.get('url', '')
                elif isinstance(manifest, str):
                    stream_url = manifest

            stream_url = unquote(stream_url)
            clean_url = clean_stream_url(stream_url)
            if not clean_url or clean_url in seen_urls:
                continue

            # Get and clean metadata
            tvg_id = str(elem.get('content_id', ''))
            logo_url = elem.get('images', {}).get('thumbnail', [None])[0] or ''
            group_title = normalize_text(group_mapping.get(tvg_id, 'Other'))

            # Create M3U entry with cleaned data
            playlist += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo_url}" group-title="{group_title}",{channel_name}\n{clean_url}\n'
            seen_urls.add(clean_url)
            
        except Exception as e:
            print(f"Error processing channel {elem.get('title', 'Unknown')}: {str(e)}")
            continue

    return playlist

def convert_to_xmltv_format(iso_time):
    try:
        dt = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%SZ")
        xmltv_time = dt.strftime("%Y%m%d%H%M%S +0000")
        return xmltv_time
    except ValueError:
        return iso_time

def create_epg_xml(epg_data):
    root = ET.Element("tv")
    for station in epg_data:
        channel = ET.SubElement(root, "channel", id=str(station.get("content_id")))
        display_name = ET.SubElement(channel, "display-name")
        display_name.text = station.get("title", "Unknown Title")
        icon = ET.SubElement(channel, "icon", src=station.get("images", {}).get("thumbnail", [None])[0])

        for program in station.get('programs', []):
            programme = ET.SubElement(root, "programme", channel=str(station.get("content_id")))
            start_time = convert_to_xmltv_format(program.get("start_time", ""))
            stop_time = convert_to_xmltv_format(program.get("end_time", ""))
            programme.set("start", start_time)
            programme.set("stop", stop_time)
            title = ET.SubElement(programme, "title")
            title.text = program.get("title", "")
            if program.get("description"):
                desc = ET.SubElement(programme, "desc")
                desc.text = program.get("description", "")

    tree = ET.ElementTree(root)
    return tree

def save_file(content, filename):
    file_path = os.path.join(os.getcwd(), filename)  # Use current working directory
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    print(f"File saved: {file_path}")

def save_epg_to_file(tree, filename):
    file_path = os.path.join(os.getcwd(), filename)  # Use current working directory
    tree.write(file_path, encoding='utf-8', xml_declaration=True)
    print(f"EPG XML file saved: {file_path}")

def main():
    countries = ["US"]
    for country in countries:
        proxies = get_proxies(country)
        if not proxies:
            print(f"No proxies found for country {country}. Trying without proxy...")
            json_data = fetch_channel_list(None)
        else:
            for proxy in proxies:
                print(f"Trying proxy {proxy} for country {country}...")
                json_data = fetch_channel_list(proxy)
                if json_data:
                    break
            else:
                print(f"All proxies failed for {country}. Trying without proxy...")
                json_data = fetch_channel_list(None)

        if not json_data:
            print(f"Failed to fetch data for {country}")
            continue

        print(f"Successfully fetched data for country {country}")
        
        # Extract channel IDs from the content
        channel_list = [item['id'] for item in json_data.get('content', []) if 'id' in item]
        print(f"Found {len(channel_list)} channels")

        epg_data = fetch_epg_data(channel_list)
        if not epg_data:
            print("No EPG data found.")
            continue

        print(f"Successfully fetched EPG data for {len(epg_data)} channels")
        
        group_mapping = create_group_mapping(json_data)
        m3u_playlist = create_m3u_playlist(epg_data, group_mapping, country.lower())
        epg_tree = create_epg_xml(epg_data)

        save_file(m3u_playlist, "tubi_playlist.m3u")
        save_epg_to_file(epg_tree, "tubi_epg.xml")

if __name__ == "__main__":
    main()
