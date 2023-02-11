#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
import time
import threading

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

class ServerHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    response_code = 200

    qs=""
    response = {
      "speed": 45,
      "active": 1
    }
    response["speed"] = ServerHandler.get_fan_speed()
    response["active"] = ServerHandler.get_power_state()

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
        ret_fan_speed = ServerHandler.set_fan_speed(json_payload['speed'])
        response['speed'] = int(ret_fan_speed)
      if 'active' in json_payload:
        ret_power_state = ServerHandler.set_power_state(json_payload['active'])
        response["active"] = ret_power_state

      self.send_response(response_code)
      self.send_header("Content-Type", "application/json")
      self.end_headers()
    else:
      self.send_response(201)
      self.send_header("Content-Type", "application/json")
      self.end_headers()

    self.wfile.write(bytes(json.dumps(response), "utf-8"))

  def get_power_state():
    try:
      response = requests.get(PING2_URL+"/a1.html", data={'0001': USERNAME, '0002': PASSWORD})
      soup = BeautifulSoup(response.text, 'html.parser')
      state = soup.find("td", {"id": "mod"}).text.rstrip()
      active = 1
      if state == 'Off':
        active = 0
      updated_state_file({'active': active})
      return active
    except:
      return int(read_state_file()['active'])

  def set_power_state(new_state):
    current_state = ServerHandler.get_power_state()
    if type(current_state) == bool and current_state == False:
      return False

    if (current_state == new_state):
      print("Power is already set to", new_state, ", not doing anything.")
      return new_state
    else:
      try:
        r = requests.get(PING2_URL+"/a1.html", data={'0001': USERNAME, '0002': PASSWORD, '0003': '1'})
        if r.status_code == 200:
          updated_state_file({'active': new_state})
          return new_state
        else:
          return current_state
      except:
        return current_state

  # Function to get the speed of the fan
  def get_fan_speed():
    try:
      response = requests.get(PING2_URL+"/b1.html", data={'0001': USERNAME, '0002': PASSWORD})
      soup = BeautifulSoup(response.text, 'html.parser')
      current_speed = int(soup.find('input', attrs={'name': '0011'})['value'].rstrip())
      updated_state_file({'speed': current_speed})
      return current_speed
    except:
      return int(read_state_file()['speed'])

  def set_fan_speed(speed):
    try:
      r = requests.post(PING2_URL+"/speed", data={'0001': USERNAME, '0002': PASSWORD, DOMEKT_MODE2_IN: speed, DOMEKT_MODE2_EX: speed})
      if r.status_code == 200:
        return int(speed)
        updated_state_file({'speed': current_speed})
      else:
        return int(read_state_file()['speed']) 
    except:
      return int(read_state_file()['speed'])

  def parse_QS(path):
    url_parts = urllib.parse.urlparse(path)
    #print( f"{url_parts=}" )
    query_parts = urllib.parse.parse_qs(url_parts.query)
    #print( f"{query_parts=}" )

    return query_parts

def schedule_polling(handler):
  schedule.every(POLLING).seconds.do(poll, handler)
  while True:
    schedule.run_pending()
    time.sleep(1)

def poll(handler):
  handler.power_state = handler.get_power_state()
  handler.fan_speed = handler.get_fan_speed()
  

def run_httpserver():
  webServer = HTTPServer((hostName, serverPort), ServerHandler)
  print("Server started http://%s:%s" % (hostName, serverPort))

  try:
    webServer.serve_forever()
  except KeyboardInterrupt:
    pass

  webServer.server_close()
  print("Server stopped.")

def update_state_file(payload):
  data = {}
  with open(STATE_FILE_PATH, "r") as rf:
    data = json.load(rf)

  data = data | payload
  with open(STATE_FILE_PATH, "w") as wf:
    f.write(json.dumps(data))

def read_state_file():
  data = {}
  with open(STATE_FILE_PATH, "r") as rf:
    data = json.load(rf)

  return data

if __name__ == "__main__":
  handler = ServerHandler()
  polling_thread = threading.Thread(target=schedule_polling, args=(handler,))
  polling_thread.start()

  run_httpserver()
