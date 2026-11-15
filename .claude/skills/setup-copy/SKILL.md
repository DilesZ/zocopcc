---
name: setup-copy
description: >
  Guide a user through creating an independent copy of this price comparison
  project in their own GitHub, Vercel, and cron-job.org accounts. Use for a new
  account setup, repo migration, or independent deployment of this project.
---

# Set up an independent copy

Use this skill when the user wants a new installation owned by them. Read
`CLAUDE.md`, `docs/duplicar-proyecto.md`, and the current `api/refresh.js`,
`.github/workflows/refresh-precios.yml`, `vercel.json`, and `.gitignore` before
guiding the setup. Treat the source repo and the new installation as separate
systems.

## Working style

- Guide the user one service at a time and say exactly where to click or what
  command to run. Wait for each confirmation before moving to steps that depend
  on it. Continue with independent preparation while the user signs in.
- The user creates or signs into their own GitHub, Vercel, and cron-job.org
  accounts. Never request passwords, verification codes, personal access tokens,
  or cron secrets in chat. Do not read a secret from a terminal or screenshot.
  Ask the user to enter secret values directly into the relevant service.
- Never use the original maintainer's credentials, Vercel project, cron job, or
  deployment domain. Do not change or disable those original resources.
- Confirm the new GitHub owner, repository name, Vercel production URL, and
  cron-job.org task are all the user's. Do not assume the source repo name or
  domain is the new destination.
- Keep `/price-monitor` guidance for code changes and product/store integrations.

## Setup sequence

1. Create an independent repository owned by the user. Prefer GitHub's repository
   import flow for copying the source and its history; otherwise clone the source,
   create a new empty destination repo, change `origin` to the destination, and
   push `main`. Do not create a fork if the user asked for an independent project.
   Confirm `git remote -v` points only to the new destination before the first
   push. Do not overwrite a destination that already contains user work.
2. Open the new repository in Claude Code. Confirm its checked-out root and
   `origin` before any push. Check that `.env.local` and `.vercel/` are not
   versioned and that the workflow file is present.
3. In Vercel, import the new GitHub repository as a new project. Use the repo
   root, no framework preset/build command, and `public` as output directory as
   described by `vercel.json`. Do not link it to the original Vercel project.
4. In the new GitHub account, create a fine-grained token restricted to the new
   repository with **Actions: Read and write**. The user enters it directly into
   the new Vercel project's **Production** environment as `GITHUB_ACTIONS_TOKEN`.
   Also set plain Production variables `GITHUB_OWNER` and `GITHUB_REPO` to the
   new GitHub owner and repository name. These repository coordinates are not
   secrets. Never put tokens in workflow YAML, Git files, browser code, or
   `NEXT_PUBLIC_*` variables.
5. Generate a new unique `PRICE_CRON_SECRET` for this installation, using a
   password manager or another private local method. The user enters the same
   value directly in the new Vercel Production environment and the new
   cron-job.org task's `Authorization: Bearer …` header. Never reuse the
   original job's secret or echo the generated value into the chat or terminal
   output visible to Claude.
6. Redeploy the new Vercel project after environment variables are saved. Obtain
   its Production `*.vercel.app` URL from the dashboard. No custom origin setting
   is needed; the API validates same-origin browser requests from the current
   deployment host.
7. In the new GitHub repo, confirm Actions are allowed, the `Refresh prices`
   workflow appears, its default branch is `main`, and workflow permissions allow
   the declared `contents: write`. Run `workflow_dispatch` once. Inspect the run
   and confirm it publishes data to the new repo and Vercel automatically
   redeploys it.
8. Test the website's manual refresh button once and verify the new repo's Actions
   run and updated timestamp. Only after that succeeds, create a cron-job.org
   task targeting the new site's `/api/refresh?skip_search=1&source=automatic`
   endpoint: HTTP POST, every 15 minutes, timezone `Europe/Madrid`, with the
   bearer header. Save it enabled and run/test it once.
9. Verify cron-job.org's execution history, the matching run in the new
   repository's Actions page (event should be `workflow_dispatch`), and the
   site's new automatic-update timestamp. Keep GitHub's native `schedule` as a
   secondary trigger; verify actual runs instead of assuming it is active.

## Stop and diagnose before changing settings

- If a value is missing, report the exact variable name and where it belongs;
  do not invent or copy a credential.
- If the workflow dispatch reaches the original repo, stop immediately. Check
  `GITHUB_OWNER` and `GITHUB_REPO` in the new Vercel project's Production env.
- If the manual button returns 403, verify the page and API share the same
  Production host. If automatic calls return 403, the two cron secret values do
  not match or the header is not `Authorization: Bearer …`.
- If calls return 502, inspect the new GitHub token's repository selection and
  Actions permission. If they return 202, follow through in GitHub Actions; 202
  only means the workflow dispatch was accepted or an active run already exists.
- If Actions succeeds but the site does not change, inspect the push to `main`,
  Vercel's Git integration and latest production deployment.
- Do not use full scraping as an initial diagnostic. First inspect logs and use
  a bounded/manual workflow run when possible. Do not bypass CAPTCHA, login, or
  access controls.
