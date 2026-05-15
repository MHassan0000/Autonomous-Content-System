# Modal Deployment Workflow

## Objective

Deploy the Autonomous Content Studio to Modal with a weekly schedule trigger.

## Schedule

- Cron: `0 6 * * 1`
- Timezone: `UTC`
- Meaning: every Monday at 06:00 UTC

## Change The Time

Set these in `.env.local`:

- `MODAL_WEEKLY_CRON=0 6 * * 1`
- `MODAL_TIMEZONE=UTC`

Examples:

- Every Monday at 9am UTC: `MODAL_WEEKLY_CRON=0 9 * * 1`
- Every Thursday at 4pm New York time: `MODAL_WEEKLY_CRON=0 16 * * 4` and `MODAL_TIMEZONE=America/New_York`
- Every day at 6am UTC: `MODAL_WEEKLY_CRON=0 6 * * *`

## Secure Secret Handling

For production, create a Modal secret and set:

- `MODAL_SECRET_NAME=<your-modal-secret-name>`

The app will use that secret instead of reading `.env.local` inside Modal.
Keep `.env.local` only on your machine.

## How to Change the Schedule

Edit the cron expression in `modal_app.py`.

Examples:

- Daily at 6am UTC: `0 6 * * *`
- Every Thursday at 9am UTC: `0 9 * * 4`
- Every 12 hours: use `modal.Period(hours=12)` instead of `modal.Cron`

## Deployment Steps

1. Install Modal: `pip install modal`
2. Authenticate: `modal setup`
3. Deploy: `python tools/modal_deploy.py`

## Outputs

- PDF report and JSON manifest saved to the Modal Volume mounted at `/data`
