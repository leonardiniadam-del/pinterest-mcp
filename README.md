# Pinterest connection for Claude

Lets Claude read your Pinterest boards and pins, save a pin's image to a folder, make boards,
and pin images (from the web or from this computer). It uses Pinterest's own developer access
and your own token. Nothing else holds the token.

Built 2026-11-20. Registered in Claude Code as `pinterest` for all projects.

## What you do, once

1. Go to developers.pinterest.com and sign in with your Pinterest account.
   (If it asks you to switch to a business account first, that is free and keeps your pins.)
2. Create an app (My apps, then Connect app). Any name, such as "My research".
3. Request **Trial access** for it. Approval usually takes one or two days, sometimes longer.
4. When it is approved, open the app's page and generate an access token with these permissions:
   `boards:read`, `boards:write`, `pins:read`, `pins:write`, `user_accounts:read`,
   and for secret boards and pins: `boards:read_secret`, `boards:write_secret`,
   `pins:read_secret`, `pins:write_secret`.
5. Open `.env` in this folder in Notepad, replace `paste-your-token-here` with the token,
   save, and restart Claude.
6. Ask Claude: "check the Pinterest connection". It runs `whoami` and shows your username.

## What Trial access allows

- Reading your boards and pins, up to 1,000 requests a day.
- Pins and boards made through it are visible only to you. Making them public needs
  Pinterest's "Standard" access, which they grant after you send a short video demo.
- The token from the app page lasts about 30 days. When Claude says the token expired,
  make a new one (step 4) and paste it in again (step 5).
- If a working token gets "not found" or "unauthorized" on every call, Pinterest may want Trial
  tokens sent to its sandbox: in `.env`, change the address to
  `https://api-sandbox.pinterest.com/v5`. (Not yet confirmed which one your token needs.)

## Tools

| Tool | What it does |
|---|---|
| whoami | checks the connection |
| list_boards | your boards |
| list_board_pins | the pins on one board, with image links |
| get_pin | one pin |
| save_pin_image | saves a pin's image into a folder |
| create_board | a new board, secret by default |
| create_pin | pins an image (web address or a jpg/png file here) to a board |

Never share `.env`; it holds the token.
