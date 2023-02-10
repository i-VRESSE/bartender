# User management

For secure auth add `BARTENDER_SECRET=<some random string>` to `.env` file.

The web service can be configured to authenticated via GitHub and/or Orcid.

After you have setup a social login described in sub chapter below then you can
authenticate with

```text
curl -X 'GET' \
  'http://localhost:8000/auth/<name of social login>/authorize' \
  -H 'accept: application/json'
```

This will return an authorization URL, which should be opened in web browser.

Make sure the authorization URL and the callback URL configured in the social
platform have the same scheme, domain (like localhost or 127.0.0.1) and port.

After visiting social authentication page you will get a JSON response with an
access token.

This access token can be used on protected routes with

```text
curl -X 'GET' \
  'http://localhost:8000/api/users/profile' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <the access token>'
```

## GitHub login

The web service can be configured to login with your
[GitHub](https://gibhub.com) account.

To enable perform following steps:

1. Create a GitHub app

   1. Goto <https://github.com/settings/apps/new>
   2. Set Homepage URL to `http://localhost:8000/`
   3. Set Callback URL to `http://localhost:8000/auth/github/callback`
   4. Check `Request user authorization (OAuth) during installation`
   5. In Webhook section

      * Uncheck `Active`

   6. In User permissions section

      * Set `Email addresses` to `Read-only`

   7. Press `Create GitHub App` button
   8. After creation

      * Generate a new client secret
      * (Optionally) Restrict app to certain IP addresses

2. Append GitHub app credentials to `.env` file

   1. Add `BARTENDER_GITHUB_CLIENT_ID=<Client id of GitHub app>`
   2. Add `BARTENDER_GITHUB_CLIENT_SECRET=<Client secret of GitHub app>`

## Orcid sandbox login

The web service can be configured to login with your [Orcid
sandbox](https://sandbox.orcid.org/) account.

To enable perform following steps:

1. Create Orcid account for yourself

   1. Go to [https://sandbox.orcid.org/](https://sandbox.orcid.org/)

      Use `<something>@mailinator.com` as email, because to register app you
      need a verified email and Orcid sandbox only sends mails to
      `mailinator.com`.

   2. Go to
      [https://www.mailinator.com/v4/public/inboxes.jsp](https://www.mailinator.com/v4/public/inboxes.jsp)

      Search for `<something>` and verify your email address

   3. Go to [https://sandbox.orcid.org/account](https://sandbox.orcid.org/account)

      Make email public for everyone

2. Create application

   Goto
   [https://sandbox.orcid.org/developer-tools](https://sandbox.orcid.org/developer-tools)
   to register app.

   * Only one app can be registered per orcid account, so use alternate account
     when primary account already has an registered app.

   * Your website URL does not allow localhost URL, so use
     `https://github.com/i-VRESSE/bartender`

   * Redirect URI: for dev deployments set to
     `http://localhost:8000/auth/orcidsandbox/callback`

3. Append Orcid sandbox app credentials to `.env` file

   1. Add `BARTENDER_ORCIDSANDBOX_CLIENT_ID=<Client id of Orcid sandbox app>`
   2. Add `BARTENDER_ORCIDSANDBOX_CLIENT_SECRET=<Client secret of Orcid sandbox
      app>`

The `GET /api/users/profile` route will return the Orcid ID in
`oauth_accounts[oauth_name=sandbox.orcid.org].account_id`.

## Orcid login

The web service can be configured to login with your [Orcid](https://orcid.org/)
account.

Steps are similar to [Orcid sandbox login](#orcid-sandbox-login), but

* Callback URL must use **https** scheme
* Account emails don't have to be have be from `@mailinator.com` domain.
* In steps

  * Replace `https://sandbox.orcid.org/` with `https://orcid.org/`
  * In redirect URL replace `orcidsandbox` with `orcid`.
  * In `.env` replace `_ORCIDSANDBOX_` with `_ORCID_`

## Super user

When a user has `is_superuser is True` then he/she can manage users and make
other users also super users.

However you need a first super user. This can be done by running

```text
bartender super <email address of logged in user>
```
