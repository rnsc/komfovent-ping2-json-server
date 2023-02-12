#!/usr/bin/env python3

from bs4 import BeautifulSoup
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import redis
import requests
import schedule
import threading
import time
import urllib.parse

hostName = os.environ['SERVER_HOSTNAME'] or "0.0.0.0"
serverPort = int(os.environ['SERVER_PORT']) or 8080

# The base URL of the PING2
PING2_URL = os.environ['PING2_URL'] or 'http://localhost'

# The username and password
USERNAME = os.environ['PING2_USERNAME'] or 'user'
PASSWORD = os.environ['PING2_PASSWORD'] or 'password'

DOMEKT_MODE2_IN = "0011"
DOMEKT_MODE2_EX = "0012"

POLLING = 120
SETTINGS_SCHEDULE = 10

DEFAULT_DATA = {
  'speed': 45,
  'active': 1,
  'time': int(time.time())-POLLING-1
}

REDIS_PORT = os.environ['REDIS_PORT'] or 6379
REDIS_HOST = os.environ['REDIS_HOST'] or "redis-komfovent-status"
REDIS_KEY_STATUS = "status"
REDIS_KEY_SETTINGS_SPEED_LIST = "settings_speed"
REDIS_KEY_SETTINGS_ACTIVE_LIST = "settings_active"
R = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

class ServerHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    response_code = 200

    response = { }

    state = KomfoventStatus.read_state()
    now = int(time.time())

    if (now - int(state['time'])) > POLLING:
      print("getting fresh info")
      response["speed"] = KomfoventStatus.get_fan_speed()
      response["active"] = KomfoventStatus.get_active_state()
    else:
      print("getting info from state")
      response["speed"] = int(state['speed'])
      response["active"] = int(state['active'])

    self.send_response(response_code)
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    self.wfile.write(bytes(json.dumps(response), "utf-8"))

  def do_PUT(self):
    #print(self.headers)
    response = {}
    if self.headers.get('Content-Length') != None:
      content_length = int(self.headers.get('Content-Length'))
      payload = self.rfile.read(content_length)

      json_payload = json.loads(payload)
      response_code = 200

      if 'speed' in json_payload:
        R.lpush(REDIS_KEY_SETTINGS_SPEED_LIST, int(json_payload['speed']))
        response['speed'] = json_payload['speed']
      if 'active' in json_payload:
        R.lpush(REDIS_KEY_SETTINGS_ACTIVE_LIST, int(json_payload['active']))
        response["active"] = json_payload['active']

      self.send_response(response_code)
      self.send_header("Content-Type", "application/json")
      self.end_headers()
    else:
      self.send_response(201)
      self.send_header("Content-Type", "application/json")
      self.end_headers()

    self.wfile.write(bytes(json.dumps(response), "utf-8"))

class KomfoventStatus():
  def get_active_state():
    try:
      response = requests.get(PING2_URL+"/a1.html", data={'0001': USERNAME, '0002': PASSWORD})
      soup = BeautifulSoup(response.text, 'html.parser')
      state = soup.find("td", {"id": "mod"}).text.rstrip()
      active = 1
      if state == 'Off':
        active = 0
      KomfoventStatus.update_state({'active': active})
      return active
    except:
      return int(KomfoventStatus.read_state()['active'])

  def set_active_state(active):
    state_active = int(KomfoventStatus.read_state()['active'])

    try:
      r = requests.get(PING2_URL+"/a1.html", data={'0001': USERNAME, '0002': PASSWORD, '0003': '1'})
      if r.status_code == 200:
        KomfoventStatus.update_state({'active': active})
        return active
      else:
        return state_active
    except:
      return state_active

  # Function to get the speed of the fan
  def get_fan_speed():
    try:
      response = requests.get(PING2_URL+"/b1.html", data={'0001': USERNAME, '0002': PASSWORD})
      soup = BeautifulSoup(response.text, 'html.parser')
      current_speed = int(soup.find('input', attrs={'name': '0011'})['value'].rstrip())
      KomfoventStatus.update_state({'speed': current_speed})
      return current_speed
    except:
      return int(KomfoventStatus.read_state()['speed'])

  def set_fan_speed(speed):
    state_speed = int(KomfoventStatus.read_state()['speed'])
    try:
      r = requests.post(PING2_URL+"/speed", data={'0001': USERNAME, '0002': PASSWORD, DOMEKT_MODE2_IN: speed, DOMEKT_MODE2_EX: speed})
      if r.status_code == 200:
        KomfoventStatus.update_state({'speed': speed})
        return int(speed)
      else:
        return state_speed
    except:
      return state_speed

  def parse_QS(path):
    url_parts = urllib.parse.urlparse(path)
    #print( f"{url_parts=}" )
    query_parts = urllib.parse.parse_qs(url_parts.query)
    #print( f"{query_parts=}" )

    return query_parts

  def update_state(payload):
    data = { }
    try:
      data = R.hgetall(REDIS_KEY_STATUS)
    except:
      data = DEFAULT_DATA
      print("update_state - Couldn't get hash", REDIS_KEY_STATUS)

    data = data | payload | { 'time': int(time.time()) }

    try:
      R.hset(REDIS_KEY_STATUS, mapping=data)
    except:
      print("update_state - Couldn't update hash", REDIS_KEY_STATUS)

  def read_state():
    data = {}
    try:
      data = R.hgetall(REDIS_KEY_STATUS)
      if not data:
        data = DEFAULT_DATA
    except:
      data = DEFAULT_DATA
      print(json.dumps(data))
      print("read_state - Couldn't read ", REDIS_KEY_STATUS)

    return data

def schedule_polling():
  schedule.every(POLLING).seconds.do(poll)
  schedule.every(SETTINGS_SCHEDULE).seconds.do(settings)
  while True:
    schedule.run_pending()
    time.sleep(1)

def poll():
  KomfoventStatus.get_active_state()
  KomfoventStatus.get_fan_speed()

def settings():
  llen_speed = R.llen(REDIS_KEY_SETTINGS_SPEED_LIST)
  llen_active = R.llen(REDIS_KEY_SETTINGS_ACTIVE_LIST)
  
  current_state = KomfoventStatus.read_state()

  if llen_speed > 0 :
    last_speed = int(R.lpop(REDIS_KEY_SETTINGS_SPEED_LIST, llen_speed)[-1])
    if last_speed != int(current_state['speed']):
      KomfoventStatus.set_fan_speed(last_speed)

  if llen_active > 0 :
    last_active = int(R.lpop(REDIS_KEY_SETTINGS_ACTIVE_LIST, llen_active)[-1])
    if last_active != int(current_state['active']):
      KomfoventStatus.set_active_state(last_active)

def run_httpserver():
  webServer = HTTPServer((hostName, serverPort), ServerHandler)
  print("Server started http://%s:%s" % (hostName, serverPort))

  try:
    webServer.serve_forever()
  except KeyboardInterrupt:
    pass

  webServer.server_close()
  print("Server stopped.")

if __name__ == "__main__":
  polling_thread = threading.Thread(target=schedule_polling)
  polling_thread.start()

  run_httpserver()
