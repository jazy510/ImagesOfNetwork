import logging
import threading
import traceback
import webbrowser
from urllib.parse import parse_qs
from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue

import click
import praw

from images_of import settings, OAUTH_SCOPE

class RedditRedirectRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parts = parse_qs(self.path)
            code = parts['code'][0]
            self.looking_good(code)
        except:
            self.shit()

    def looking_good(self, code):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Good to go.")
        self.server.q.put(('ok', code))

    def shit(self):
        self.send_response(500)
        self.end_headers()

        self.wfile.write('{}'.format(traceback.format_exc()).encode())
        self.server.q.put(('err', None))

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    def __init__(self, *args, q, **kwargs):
        super().__init__(*args, **kwargs)
        self.q = q

@click.command() # just so we have --help available
@click.option('-h', '--host', default='127.0.0.1', help='hostname to listen on')
@click.option('-p', '--port', default=65010, type=int, help='port to listen on')
def main(host, port):
    # Step 1: Prop up a web server.
    q = Queue()

    handler = RedditRedirectRequestHandler
    # XXX figure out how to get this from settings.REDIRECT_URI.
    #  in the mean time, I put it in the arguments list.
    addr = (host, port)

    server = ThreadedHTTPServer(addr, handler, q=q)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()


    # Step 2: Send the user on over to reddit to say OK.
    r = praw.Reddit(user_agent='ION Oauth Setup /u/{}'.format(settings.USERNAME))
    r.set_oauth_app_info(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            redirect_uri=settings.REDIRECT_URI)

    url = r.get_authorize_url('uniqueKey', OAUTH_SCOPE, True)
    webbrowser.open(url)

    # Step 3: Get access ID from server
    status, code = q.get()
    logging.info('Shutting down server.')
    server.shutdown()
    server.server_close()

    if status == 'err':
        logging.error('Failed to collect access information')
        return

    logging.info('Gathering access information.')
    access_info = r.get_access_information(code)

    print("Write this down, y'hear!? Like put it in your local_settings.py")
    print()
    print("REFRESH_TOKEN = '{}'".format(access_info['refresh_token']))

if __name__ == '__main__':
    main()
