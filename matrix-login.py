import requests
import asyncio
from aiohttp import ClientSession, web
import json
import argparse
import re
import sys
from getpass import getpass
import urllib.parse
import webbrowser

response_page = """
<!DOCTYPE html>
<html>
<head><title>Login successful</title></head>
<body style="text-align: center"><h1>Done!</h1><h3>You can close this tab and return to the terminal.<h3></body>
</html>
"""

def lookup_well_known(server_name):
    try:
        r = requests.get(f"https://{server_name}/.well-known/matrix/client").json()
        return r['m.homeserver']['base_url']
    except (requests.exceptions.ConnectionError, KeyError):
        return None

def password_login(localpart, mxid, base_url):
    password = getpass()

    r = requests.post(f"{base_url}/_matrix/client/r0/login", json={
        "type": "m.login.password",
        "identifier": {
            "type": "m.id.user",
            "user": localpart
        },
        "password": password
    })

    if r.status_code != 200:
        print(f"Failed to login: {r.status_code} {r.text}")
        return
    else:
        data = r.json()
        global filepath
        with open(filepath, "w") as f:
            json.dump(data, f)
        print(f"Success! Login data written to {filepath}")

async def token_login(base_url, token):
    try:
        session = ClientSession()
        r = await session.post(f"{base_url}/_matrix/client/r0/login", json={"type": "m.login.token", "token": token})
        if r.status != 200:
            print(f"Failed to login: {r.status} {await r.text()}")
        else:
            data = await r.json()
            global filepath
            with open(filepath, "w") as f:
                json.dump(data, f)
            print(f"Success! Login data written to {filepath}")
    except Exception as e:
        print(f"Failed to login: {e}")
    await session.close()
    loop = asyncio.get_event_loop()
    loop.stop()

routes = web.RouteTableDef()
app = web.Application()

@routes.get('/')
async def root(request):
    try:
        token = request.rel_url.query['loginToken']
        asyncio.create_task(token_login(base_url, token))
        await app.shutdown()
        return web.Response(content_type="text/html", text=response_page)
    except KeyError:
        return web.Response(status=400)
app.add_routes(routes)

async def sso_login(localpart, mxid, base_url):
    print("Opening browser to perform SSO login...")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    redirect_url = urllib.parse.quote(f"http://localhost:{runner.addresses[0][1]}")
    webbrowser.open(f"{base_url}/_matrix/client/r0/login/sso/redirect?redirectUrl={redirect_url}")
    print(f"If it didn't automatically open, manually open the following URL:\n{base_url}/_matrix/client/r0/login/sso/redirect?redirectUrl={redirect_url}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mxid")
    parser.add_argument("filepath")
    args = parser.parse_args()
    
    global filepath
    filepath = args.filepath

    matches = re.findall('@([^:]+):(.+)', args.mxid)

    if len(matches) != 1 or len(matches[0]) != 2:
        raise Exception('Not a Matrix ID!')

    localpart = matches[0][0]
    server_name = matches[0][1]

    base_url = lookup_well_known(server_name)
    if base_url == None:
        print("Automatic server lookup failed!")
        base_url = input("Enter homeserver client API base URL: ")
    
    base_url = base_url.rstrip('/')

    login_types = None
    try:
        login_types = requests.get(f"{base_url}/_matrix/client/r0/login").json()['flows']
    except:
        print("Failed to get login flows! Are you sure this is a Matrix server?")
        sys.exit(1)

    login_types = [flow['type'] for flow in login_types if flow['type'] in ['m.login.password', 'm.login.sso', 'm.login.token']]

    login_type = ""
    if 'm.login.password' in login_types and 'm.login.sso' in login_types and 'm.login.token' in login_types:
        print("Server supports both password and SSO login.")
        while login_type.lower() not in ['password', 'sso']:
            login_type = input("Choose login method (password, sso): ")
    elif 'm.login.password' in login_types:
        print("Server supports password login.")
        login_type = "password"
    elif 'm.login.sso' in login_types and 'm.login.token' in login_types:
        print("Server supports SSO login.")
        login_type = "sso"
    else:
        print("Server doesn't support either password or SSO login! Can't login.")
        sys.exit(1)

    if login_type == "password":
        password_login(localpart, args.mxid, base_url)
    elif login_type == "sso":
        loop = asyncio.get_event_loop()
        loop.create_task(sso_login(localpart, args.mxid, base_url))
        loop.run_forever()
