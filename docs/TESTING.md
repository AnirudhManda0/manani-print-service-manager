# Testing Checklist

Use this checklist before every production rollout.

## Print Detection

### Test: 1 page print

- Expected result: one transaction recorded with `pages = 1`
- Actual result:

### Test: 5 page print

- Expected result: one transaction recorded with `pages = 5`
- Actual result:

### Test: 50 page print

- Expected result: one transaction recorded with `pages = 50`
- Actual result:

### Test: 100 page print

- Expected result: one transaction recorded with `pages = 100`
- Actual result:

## Pricing

### Test: B&W pricing

- Expected result: `pages * bw_price_per_page`
- Actual result:

### Test: Color pricing

- Expected result: `pages * color_price_per_page`
- Actual result:

## Dashboard

### Test: dashboard totals after printing

- Expected result: dashboard cards update after refresh timer or manual refresh
- Actual result:

### Test: revenue trend chart

- Expected result: last 7 days chart renders without crash
- Actual result:

### Test: print vs service contribution chart

- Expected result: contribution bars render and match report totals
- Actual result:

## Services

### Test: service confirmation popup

- Expected result: clicking a service shows a Yes/No confirmation dialog
- Actual result:

### Test: service calculator expression

- Expected result: `10 * 2`, `5 + 5`, `20 / 2` evaluate correctly
- Actual result:

## Reports

### Test: daily report

- Expected result: totals match the day’s dashboard
- Actual result:

### Test: weekly report

- Expected result: totals match the 7-day range
- Actual result:

### Test: monthly report

- Expected result: totals match the full month range
- Actual result:

## Multi-Client

### Test: two clients print at the same time

- Expected result: both transactions appear, no duplicate entries
- Actual result:

## Recovery

### Test: missing settings file

- Expected result: default config recreated automatically
- Actual result:

### Test: corrupted DB fallback

- Expected result: corrupt DB quarantined and new DB created
- Actual result:
