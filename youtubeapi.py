import httplib2
import os
import sys
import dateutil.parser

from datetime import datetime, timezone

from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

class YouTube():
	MISSING_CLIENT_SECRETS_MESSAGE = """
	WARNING: Please configure OAuth 2.0
	To make this sample run you will need to provide a client_secrets.json file
	"""

	CLIENT_SECRETS_FILE = "client_secrets.json"

	YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
	YOUTUBE_API_SERVICE_NAME = "youtube"
	YOUTUBE_API_VERSION = "v3"

	def __init__(self):
		flow = flow_from_clientsecrets(self.CLIENT_SECRETS_FILE,
			message = self.MISSING_CLIENT_SECRETS_MESSAGE,
			scope = self.YOUTUBE_READONLY_SCOPE)

		storage = Storage("%s-oauth2.json" % sys.argv[0])
		self.credentials = storage.get()

		if self.credentials is None or self.credentials.invalid:
			flags = argparser.parse_args()
			self.credentials = run_flow(flow, storage, flags)

		self.api = build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION,
			http = self.credentials.authorize(httplib2.Http()))

	def channel_from_response(self, response):
		for channel in response['items']:
			result = dict()
			result['id'] = channel['id']
			result['username'] = None
			result['title'] = channel['snippet']['title']
			result['added_on'] = datetime.utcnow().isoformat()
			result['last_checked'] = result['added_on']
			return result
		return None


	def get_channel_by_id(self, id):
		channels_response = self.api.channels().list(
			id = id,
			part = "snippet",
			fields = 'items(id,snippet(title))'
		).execute()
		return self.channel_from_response(channels_response)

	def get_channel_by_username(self, username):
		channels_response = self.api.channels().list(
			forUsername = username,
			part = "snippet",
			fields = 'items(id,snippet(title))'
		).execute()
		channel = self.channel_from_response(channels_response)
		if channel is not None:
			channel['username'] = username
		return channel

	def get_uploads_playlist(self, uploads_list_id, last_checked):
		playlistitems_request = self.api.playlistItems().list(
			playlistId = uploads_list_id,
			part = "snippet",
			fields = 'items(id,snippet(title,publishedAt,resourceId(videoId)))',
			maxResults = 50
		)

		while playlistitems_request:
			playlistitems_response = playlistitems_request.execute()

			for playlist_item in playlistitems_response["items"]:
				publishedAt = dateutil.parser.parse(playlist_item['snippet']['publishedAt'])
				if (publishedAt > last_checked):
					video = dict()
					video['id'] = playlist_item["snippet"]["resourceId"]["videoId"]
					video['published_at'] = playlist_item["snippet"]["publishedAt"]
					video['title'] = playlist_item["snippet"]["title"]
					yield video
				else:
					return

			playlistitems_request = self.api.playlistItems().list_next(
				playlistitems_request, playlistitems_response
			)

	def get_uploads(self, channels):
		channels_response = self.api.channels().list(
			id = ",".join(channels.keys()),
			part = "contentDetails",
			fields = "items(id,contentDetails(relatedPlaylists(uploads)))"
		).execute()

		for channel in channels_response["items"]:
			uploads_list_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
			last_checked = dateutil.parser.parse(channels[channel['id']])
			last_checked = last_checked.replace(tzinfo = timezone.utc)
			for upload in self.get_uploads_playlist(uploads_list_id, last_checked):
				yield upload
