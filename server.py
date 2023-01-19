#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from bs4 import BeautifulSoup
import json
import os
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
    if response["speed"] == False or response["active"] == False:
      response_code = 503
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
        if ret_fan_speed == False:
          response_code = 503
        else:
          response['speed'] = ret_fan_speed
      if 'active' in json_payload:
        ret_power_state = ServerHandler.set_power_state(json_payload['active'])
        if ret_power_state == False:
          response_code = 503
        else:
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
      if state == 'Off':
        return 0
      else:
        return 1
    except:
      return False

  def set_power_state(new_state):
    current_state = ServerHandler.get_power_state()
    if current_state == False:
      return False

    if (current_state == new_state):
      print("Power is already set to", new_state, ", not doing anything.")
      return True
    else:
      try:
        r = requests.get(PING2_URL+"/a1.html", data={'0001': USERNAME, '0002': PASSWORD, '0003': '1'})
        if r.status_code == 200:
          return new_state
        else:
          return False
      except:
        return False

  # Function to get the speed of the fan
  def get_fan_speed():
    try:
      response = requests.post(PING2_URL+"/b1.html", data={'0001': USERNAME, '0002': PASSWORD})
      soup = BeautifulSoup(response.text, 'html.parser')
      current_speed = soup.find('input', attrs={'name': '0011'})['value'].rstrip()

      return current_speed
    except:
      return False

  def set_fan_speed(speed):
    try:
      r = requests.post(PING2_URL+"/speed", data={'0001': USERNAME, '0002': PASSWORD, DOMEKT_MODE2_IN: speed, DOMEKT_MODE2_EX: speed})
      if r.status_code == 200:
        return ServerHandler.get_fan_speed()
      else:
        return False
    except:
      return False

  def parse_QS(path):
    url_parts = urllib.parse.urlparse(path)
    #print( f"{url_parts=}" )
    query_parts = urllib.parse.parse_qs(url_parts.query)
    #print( f"{query_parts=}" )

    return query_parts

if __name__ == "__main__":        
  webServer = HTTPServer((hostName, serverPort), ServerHandler)
  print("Server started http://%s:%s" % (hostName, serverPort))

  try:
    webServer.serve_forever()
  except KeyboardInterrupt:
    pass

  webServer.server_close()
  print("Server stopped.")
