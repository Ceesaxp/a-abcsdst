import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

"""
This is a simple script to download mp3 files from a website.
"""

url = "https://example.com/mp3/dir"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

audio_tags = soup.find_all("audio")
for audio in audio_tags:
    sorce_tags = audio.find_all("source")
    for source in sorce_tags:
        src = source.get("src")
        if src:
            print(src)
            # ... and download it to mp3/ directory

            # Create mp3 directory if it doesn't exist
            os.makedirs("mp3", exist_ok=True)

            # Extract filename from URL
            filename = os.path.basename(urllib.parse.urlparse(src).path)
            filepath = os.path.join("mp3", filename)

            # Download the file
            print(f"Downloading {filename}...")
            r = requests.get(src, stream=True)
            r.raise_for_status()  # Ensure the request was successful

            # Save the file
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Saved to {filepath}")
