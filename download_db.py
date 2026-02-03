import urllib.request

url = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
output = "chinook.sqlite"

print("Downloading Chinook database...")
urllib.request.urlretrieve(url, output)
print(f"✅ Downloaded: {output}")