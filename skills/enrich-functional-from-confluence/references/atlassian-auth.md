# Atlassian MCP Authentication

## Test first

Run `ToolSearch: "+confluence page"` to check if the session is already live.
If a usable `getConfluencePage` tool is returned, skip to **Fetch**.

Repo precedent for the tool name: `getConfluencePage` with `contentFormat: "markdown"`
(see `../generate-architecture/references/source-discovery.md`). Use the schema the
ToolSearch returns — it may require an instance hostname or cloud ID in addition to
`pageId`; supply whatever the loaded schema specifies.

## Start the OAuth flow

If the tool is not available or returns 401, call:

```
mcp__plugin_atlassian_atlassian__authenticate()
```

It returns an authorization URL. Share it with the user:

> *"Atlassian MCP requires sign-in. Open this URL in your browser:*
> `<authorization-url>`
>
> *Once the browser redirects (the page may fail to load — that's expected on
> remote sessions), copy the full URL from the address bar and paste it here."*

## Complete the handshake

When the user pastes the callback URL, call:

```
mcp__plugin_atlassian_atlassian__complete_authentication(
  callback_url: "<pasted-url>"
)
```

Re-run `ToolSearch: "+confluence page"` to verify. If the tool still doesn't load,
tell the user:

> *"Authentication did not complete. Please retry or check your Atlassian account
> permissions. You can also run `/breeze:project auth` to diagnose the Breeze MCP
> session separately."*

Then stop.
