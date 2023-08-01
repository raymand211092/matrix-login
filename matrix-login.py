import os
from dotenv import load_dotenv
import requests
from aiohttp import ClientSession, TCPConnector
import json
import re
import urllib.parse
from flask import Flask, request, redirect, render_template, session

load_dotenv()


def get_env_variable(var_name):
    value = os.getenv(var_name)
    if not value:
        raise Exception(f"{var_name} not found in environment variables")
    return value


app = Flask(__name__)
app.secret_key = get_env_variable("SECRET_KEY")
hcaptcha_secret = get_env_variable("HCAPTCHA_SECRET")


def lookup_well_known(server_name):
    try:
        r = requests.get(f"https://{server_name}/.well-known/matrix/client").json()
        return r['m.homeserver']['base_url']
    except (requests.exceptions.ConnectionError, KeyError):
        return None


async def token_login(base_url, token):
    try:
        session = ClientSession(connector=TCPConnector(ssl=False))
        r = await session.post(f"{base_url}/_matrix/client/r0/login", json={"type": "m.login.token", "token": token})
        if r.status != 200:
            error_message = await r.text()
            print(f"Failed to login: {r.status} {error_message}")
            return {"error": f"Failed to login: {r.status} {error_message}"}
        else:
            data = await r.json()
            return data
    except Exception as e:
        print(f"Failed to login: {e}")
        error_message = f"Failure, {e}"
        return render_template("error.html", error_message=error_message)
    finally:
        await session.close()


@app.route('/')
def index():
    return render_template('mxid_form.html')


@app.route('/login', methods=['POST'])
def process_login():
    hcaptcha_response = request.form.get('h-captcha-response')
    if not validate_hcaptcha(hcaptcha_response):
        return render_template('error.html', error_message='Invalid CAPTCHA')

    mxid = request.form.get('mxid')

    matches = re.findall('@([^:]+):(.+)', mxid)

    if len(matches) != 1 or len(matches[0]) != 2:
        error_message = 'Invalid Matrix ID format!'
        return render_template('error.html', error_message=error_message)

    localpart, server_name = matches[0][0], matches[0][1]

    base_url = lookup_well_known(server_name)
    if base_url is None:
        error_message = 'Automatic server lookup failed! Please enter homeserver client API base URL:'
        return render_template('error.html', error_message=error_message)

    base_url = base_url.rstrip('/')

    session['base_url'] = base_url

    login_types = None
    try:
        login_types = requests.get(f"{base_url}/_matrix/client/r0/login").json()['flows']
    except:
        error_message = "Failed to get login flows! Are you sure this is a Matrix server?"
        return render_template('error.html', error_message=error_message)

    login_types = [flow['type'] for flow in login_types if
                   flow['type'] in ['m.login.password', 'm.login.sso', 'm.login.token']]

    login_type = ""
    if 'm.login.sso' in login_types and 'm.login.token' in login_types:
        login_type = "sso"
    else:
        error_message: "Server doesn't support SSO login! Can't login."
        return render_template('error.html', error_message=error_message)

    if login_type == "sso":
        redirect_url = urllib.parse.quote(request.url_root + 'sso_callback')
        return redirect(f"/sso_login?base_url={base_url}&redirect_url={redirect_url}")


def validate_hcaptcha(hcaptcha_response):
    payload = {
        'response': hcaptcha_response,
        'secret': hcaptcha_secret
    }
    response = requests.post('https://hcaptcha.com/siteverify', data=payload)
    response_data = json.loads(response.text)
    return response_data['success']


@app.route('/sso_login')
def sso_login():
    base_url = request.args.get('base_url')
    redirect_url = request.args.get('redirect_url')
    if base_url and redirect_url:
        sso_url = f"{base_url}/_matrix/client/r0/login/sso/redirect?redirectUrl={urllib.parse.quote(redirect_url)}"
        return redirect(sso_url)
    else:
        return "Bad Request", 400


@app.route('/sso_callback')
async def sso_callback():
    base_url = session.get('base_url')
    token = request.args.get('loginToken')
    token_login_data = await token_login(base_url, token)
    if "error" in token_login_data:
        return render_template('error.html', error_message=token_login_data["error"])
    if "user_id" not in token_login_data:
        return render_template('error.html', error_message="Invalid login token")
    return render_template('response_page.html', token=token)


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8080, debug=True)
