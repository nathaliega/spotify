import requests
from urllib.parse import urlencode, urlparse, parse_qs
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import base64
from bs4 import BeautifulSoup
from concurrent.futures import as_completed
from requests_futures.sessions import FuturesSession
import langid
from rauth import OAuth2Service
from aiohttp import ClientSession
import asyncio
import json

CLIENT_ID = "31410dfff44243bb84d61ea5d4f296ae"
SECRET_KEY = "805513f767f440859bbf0c8d0546dc17"
BASE_URL = "https://api.spotify.com/v1/"

class Song:
    def __init__(self, name, artist, uri):
        self.name = name
        self.artist = artist
        self.lan = None
        self.uri = uri
        # self.lyrics = self.get_lyrics()


class SpotifyHandler:

    def __init__(self, client_id, secret_key):
        self.client_id = client_id
        self.secret_key = secret_key
        self.token = ""
        self.api_headers = {}
        self.authorize()
        self.user_id = self.get_user_id()

    def get_code(self):
        class MyHandler(BaseHTTPRequestHandler):
            code = None

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", 'text/html')
                self.end_headers()
                if 'code' in parse_qs((urlparse(self.path)).query):
                    MyHandler.code = parse_qs((urlparse(self.path)).query)['code'][0]

        webbrowser.open("https://accounts.spotify.com/authorize?" + urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": "http://localhost:8888",
            "scope": "user-library-read playlist-modify-private"
        }))
        httpd = HTTPServer(('localhost', 8888), MyHandler)

        while not MyHandler.code:
            httpd.handle_request()

        httpd.server_close()

        return MyHandler.code

    def authorize(self):

        encoded_credentials = base64.b64encode(self.client_id.encode() + ':'.encode() +
                                               self.secret_key.encode()).decode()

        codes = self.get_code()
        response = requests.post(url="https://accounts.spotify.com/api/token", data={
            "grant_type": "authorization_code",
            "code": codes,
            "redirect_uri": "http://localhost:8888"
        }, headers={
            "Authorization": "Basic " + encoded_credentials,
            "Content-Type": "application/x-www-form-urlencoded"
        })

        self.token = response.json()['access_token']

        self.api_headers = {
            "Authorization": "Bearer " + self.token
        }
        print("Token: " + self.token)
        return self.token

    # Actual API calls
    def make_call(self, method, endpoint, headers=None, data=None, params=None):
        if not headers:
            headers = self.api_headers

        response = getattr(requests, method)(BASE_URL + endpoint, headers=headers, params=params, data=data)

        return response.json()

    def get_resource(self, endpoint, headers=None, data=None, params=None):

        items = []

        total = self.make_call('get', endpoint, headers, data, params)['total']/50

        for page in range(round(total / 50)):
            items.extend(self.make_call('get', endpoint, headers, data,
                                        params={"offset": page * 50, "limit": 50})['items'])

        return items


    def get_albums(self):
        return self.get_resource('me/albums')
        # return [item['album'] for item in self.get_resource('me/albums')]
        # albs = self.make_call('get', 'me/albums', params={})

        # return [album['album'] for album in albs['items']]

    def get_songs(self):
        return [Song(song['track']['name'], song['track']['artists'][0]['name'], song['track']['uri']) for song in self.get_resource('me/tracks')]


    def get_user_id(self):
        return self.make_call('get', 'me', headers=self.api_headers)['id']

    def create_playlist(self, lan, songs):
        playlist_id = self.make_call('post', f"users/{self.user_id}/playlists", headers=self.api_headers, data=json.dumps({
                'name': lan,
                'public': False
            }))['id']

        for i in range(round(len(songs)/90)):
            uris = {
                    "uris": [song.uri for song in songs[i*90:(i+1)*90]], 
                    "position": i*90
                }
            
            self.make_call('post', f'playlists/{playlist_id}/tracks', headers=self.api_headers, 
                data=json.dumps(uris))

        return True

    def identify_languages(self, songs):
        with FuturesSession(max_workers=2) as session:
            for song in songs:
                song.lan = session.get(f"http://api.genius.com/search?q={song.name}%20{song.artist}", 
                    headers={"Authorization": f"Bearer ticNcbIdYkprjA2F9QPwfr5sB0gc-dsfJveYzLxrYXwHksvCD05nvSnie1L4RMY6"})
            
            
            # for future in as_completed(futures):
                # response = future.result()
                # print(response)

        for song in songs:
            try:
                song.lan = song.lan.result().json()['response']['hits'][0]['result']['language']
            except:
                song.lan = "unidentified"

    # def get_lan(self):
    #     url = requests.get("https://genius.com/{}-{}-lyrics".format(str(self.artist).replace(' ', '-'),
    #         str(self.name).replace(' ', '-')))

    #     soup = BeautifulSoup(url.text, 'html.parser')
    #     lyrics = soup.find("div", class_="Lyrics__Container-sc-1ynbvzw-6 YYrds")
    #     if lyrics:
    #         return str(lyrics.get_text())
    #     return None


handler = SpotifyHandler(CLIENT_ID, SECRET_KEY)
# handler.authorize()
songs = handler.get_songs()
handler.create_playlist("test", songs)
# playlist = handler.create_playlist('i love you')
# handler.add_songs(playlist, songs)








    # def find_language(self):
    #     if self.lyrics:
    #         return langid.classify(self.lyrics)[0]
    #     return langid.classify(self.name)[0]


# tracks = handler.get_songs()
# all_songs = [(track['name'], track['artists'][0]['name']) for track in tracks]
# songs = [Song(song['name'], song['artists'][0]['name']) for song in handler.get_songs()]


# print("Done")
# async def resolve_list(list_of_songs):
#     async with ClientSession(headers=headers) as session:
#     # {"Authorization":)
# with FuturesSession(max_workers=30) as session:
    # for song in songs:
        
    # print(f"song: {song.name}, by {song.artist}, lan: {song.lan}, lyrics: {song.lyrics}")

# headers = {
#     "accept": "application/json",
#     "Authorization": "Bearer ticNcbIdYkprjA2F9QPwfr5sB0gc-dsfJveYzLxrYXwHksvCD05nvSnie1L4RMY6",
# }
# async def get_lyrics(song: Song, session: ClientSession):
#     response = await session.get("http://api.genius.com/search?q=scientist%20coldplay")
#     json = await response.json()
#     print(json)
#     song.lan = json['response']['hits'][0]['language']

# async def resolve_list(list_of_songs):
#     async with ClientSession(headers=headers) as session:
#     # {"Authorization": "Bearer ticNcbIdYkprjA2F9QPwfr5sB0gc-dsfJveYzLxrYXwHksvCD05nvSnie1L4RMY6"}) as session:

#         s = []
#         for song in list_of_songs:
#             s.append(get_lyrics(song, session))
#         await asyncio.gather(*s)

# asyncio.run(resolve_list(songs))

print("Done")
