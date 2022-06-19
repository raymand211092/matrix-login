# matrix-login

This is a simple script to authenticate with a Matrix server. It supports password and SSO login. This can be used to easily login to a Matrix server if you're making a bot or some other client where you want to avoid implementing the login logic.

# Usage

```
$ python3 matrix-login.py <Matrix ID> <login file name>
```

Follow the instructions. If you choose SSO login, you will need a local web browser. (Remember you can run the script locally and then transfer the login file to another remote machine, if you need to do that.)

The login file (with the name you supplied) will contain the access token and device ID for the newly signed in login session.
