""" Spotify song sorter """
import base64
import json
import math
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import requests
from requests_futures.sessions import FuturesSession

CLIENT_ID = "31410dfff44243bb84d61ea5d4f296ae"
SECRET_KEY = "805513f767f440859bbf0c8d0546dc17"
BASE_URL = "https://api.spotify.com/v1/"

#pylint: disable=R0903
class Song:
    """ song datatype """
    def __init__(self, name, artist, uri):
        self.name = name
        self.artist = artist
        self.lan = None
        self.uri = uri

    def __str__(self) -> str:
        return f"{self.name} by {self.artist}"


class Playlist:
    """ playlist datatype """
    def __init__(self, name, playlist_id, songs=None) -> None:
        self.name = name
        self.songs = songs if songs else []
        self.playlist_id = playlist_id

    def __str__(self) -> str:
        return f"{self.name} with id: {self.playlist_id}"
#pylint: enable=R0903

class SpotifyHandler:
    """ makes api calls """
    def __init__(self, client_id, secret_key):
        self.client_id = client_id
        self.secret_key = secret_key
        self.token = ""
        self.api_headers = {}
        self.authorize()
        self.user_id = self.get_user_id()

    def get_code(self):
        """ gets code used for authorization """
        class MyHandler(BaseHTTPRequestHandler):
            """ HTTP server """
            code = None

            #pylint: disable=C0103
            def do_GET(self):
                """ adding data to already existing funcion """
                self.send_response(200)
                self.send_header("Content-type", 'text/html')
                self.end_headers()
                if 'code' in parse_qs((urlparse(self.path)).query):
                    MyHandler.code = parse_qs((urlparse(self.path)).query)['code'][0]
            #pylint: enable=C0103

        webbrowser.open("https://accounts.spotify.com/authorize?" + urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": "http://localhost:8888",
            "scope": "user-library-read playlist-modify-private playlist-read-private"
        }))
        httpd = HTTPServer(('localhost', 8888), MyHandler)

        while not MyHandler.code:
            httpd.handle_request()

        httpd.server_close()

        return MyHandler.code

    def authorize(self):
        """ authorizes app to connect to spotify account """
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
        }, timeout=10)

        self.token = response.json()['access_token']

        self.api_headers = {
            "Authorization": "Bearer " + self.token
        }
        return self.token

    #pylint: disable=R0913
    def make_call(self, method, endpoint, headers=None, data=None, params=None):
        """ actual api calls """
        if not headers:
            headers = self.api_headers

        response = getattr(requests, method)(BASE_URL + endpoint, headers=headers,
                    params=params, data=data)

        return response.json()
    #pylint: enable=R0913

    def get_resource(self, endpoint, headers=None, data=None, params=None):
        """ gets items using pagination """
        items = []

        total = self.make_call('get', endpoint, headers, data, params)['total']

        for page in range(round(total / 50) or 1):
            items.extend(self.make_call('get', endpoint, headers, data,
                                        params={"offset": page * 50, "limit": 50})['items'])

        return items


    def get_songs(self):
        """ Creates song objects with its name, artist and uri. """
        return [Song(song['track']['name'],song['track']['artists'][0]['name'],
                song['track']['uri']) for song in self.get_resource('me/tracks')]


    def get_user_id(self):
        """ gets id for user """
        return self.make_call('get', 'me', headers=self.api_headers)['id']


    def get_songs_and_lan(self):
        """ gets songs and assigns them their language """
        tracks = self.get_songs()
        with FuturesSession(max_workers=3) as session:
            for track in tracks:
                track.lan = session.get(f"http://api.genius.com/search \
                    ?q={track.name}%20{track.artist}",
                    headers={
                        "Authorization":
                        "Bearer ticNcbIdYkprjA2F9QPwfr5sB0gc-dsfJveYzLxrYXwHksvCD05nvSnie1L4RMY6"
                    })

        for track in tracks:
            try:
                track.lan = track.lan.result().json()['response']['hits'][0]['result']['language']
            except KeyError:
                track.lan = "unidentified"

        return tracks

    def get_playlists(self):
        """ creates playlist objects with name and id """
        return [Playlist(playlist['name'], playlist['id']) for playlist
            in self.get_resource(f"users/{self.user_id}/playlists")]

    def empty_playlist(self, playlist_id):
        """ empty playlists for already existing languages"""

        for _ in range(math.ceil((self.make_call('get',
            f'playlists/{playlist_id}/tracks')['total']/50))):

            self.make_call('delete', f'playlists/{playlist_id}/tracks', data=json.dumps(
                {
                    'tracks': [{'uri': track['track']['uri']
                } for track in self.make_call('get', f'playlists/{playlist_id}/tracks',
                params={"limit": 50})['items']]
            }))

    def update_playlist(self, playlist_id, songs):
        """ repopulates already existing playlists """
        for i in range(math.ceil(len(songs)/90)):
            self.make_call('post', f'playlists/{playlist_id}/tracks', data= json.dumps(
                {
                    'uris': songs[i*90:i*90+90]
                }
            ))


    def create_playlist(self, lans, songs):
        """ creates playlist and adds songs to it """
        playlist_id = self.make_call('post', f"users/{self.user_id}/playlists", data=json.dumps({
                'name': lans,
                'public': False
            })).get('id')

        if not playlist_id:
            print(f"Error adding playlist for language {lans}")
            return False

        for i in range(math.ceil(len(songs)/90)):
            uris = {
                "uris": songs[i*90:(i+1)*90],
                "position": i*90
                }
            self.make_call('post', f'playlists/{playlist_id}/tracks', headers=self.api_headers,
                data=json.dumps(uris))

        return True



handler = SpotifyHandler(CLIENT_ID, SECRET_KEY)

all_songs = handler.get_songs_and_lan()
lan_and_songs = {lan: [] for lan in set(song.lan for song in all_songs)}

for song in all_songs:
    lan_and_songs[song.lan].append(song.uri)

playlists = handler.get_playlists()
playlist_names = {playlist.name: playlist.playlist_id for playlist in playlists}

for lan in lan_and_songs.keys():
    if lan in playlist_names.keys():
        handler.empty_playlist(playlist_names[lan])
        handler.update_playlist(playlist_names[lan], lan_and_songs[lan])
    else:
        handler.create_playlist(lan, lan_and_songs[lan])
