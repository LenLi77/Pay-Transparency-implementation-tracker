# Updating the tracker

`index.html` is **not** static HTML. All 27 countries live in a single
`COUNTRIES` JavaScript array near the bottom of the file. Both tables
(Implementation Status + Requirements by Country) **and** the stats-bar counts
are generated from that array at runtime.

**Edit a country once, in the array, and everything updates.** Do not hand-edit
`<tr>` table rows or the stat numbers — there aren't any to edit.

> ⚠️ The daily checker (`update_checker.py`) reads the baseline it feeds to
> Claude by **parsing this `COUNTRIES` array**. If `index.html` is ever replaced
> with the old static-HTML structure, the checker breaks with
> `RuntimeError: Could not parse any country rows`. Keep the array structure.

## Country object shape

```js
{
  name: 'Latvia',
  code: 'LV',
  flag: '🇱🇻',
  baltic: true,                 // optional — highlights the row + adds a BALTIC badge
  cat: 'partial',               // adopted | draft | partial | noinfo
  status: 'Draft (delayed)',    // badge label text
  laws: 'Salary in job ads (2018)',  // existing national law, or '' if none
  expected: 'Delayed ⚠️',       // free text: 'June 2026', 'Jan 2027 ⚠️', '✅ Done', '—'
  verified: 'Jul 2026',
  details: `Prose describing the current state...`,   // backtick string
  draft: { u: 'https://...', t: 'Link label' },        // source link, or null
  req: [ /* 12 entries, see below */ ],
}
```

- **`cat`** drives the badge colour and which stat the country counts toward:
  `adopted` + `draft` are green, `partial` is yellow, `noinfo` is red.
  The four stat numbers are just the counts of each `cat`.
- **`expected`** colour is derived from the text: contains `✅` → green,
  contains `⚠` → red, `—` → grey, otherwise neutral.

### The 12 `req` columns (in order)

Each entry is `[icon, tooltip]` where icon is
`yes` (✅) | `partial` (⚠️) | `pending` (🔄) | `no` (❌) | `na` (—).

| # | Column |
|---|--------|
| 1 | Salary in job ad / before interview |
| 2 | Salary history ban |
| 3 | Transparency obligations in collective agreements |
| 4 | Right to pay info (colleagues' avg) |
| 5 | Pay secrecy clause ban |
| 6 | Pay structure required |
| 7 | Criteria available to employees |
| 8 | Reporting 250+ (annual) |
| 9 | Reporting 100–249 (triennial) |
| 10 | Pay audit if 5%+ unexplained gap |
| 11 | Burden of proof reversed |
| 12 | Sanctions defined |

## `og:description`

The `<meta property="og:description">` counts (`N laws adopted, N drafts
published, ...`) are read by crawlers **before** the JavaScript runs, so they
can't be generated from the array. Update them by hand only on a major status
shift, to mirror the stats bar.

## Workflow: applying an update from a separate chat

Research/drafting often happens in a separate Claude Chat that doesn't know this
structure and will output old-style static HTML. To avoid the mismatch, ask that
chat to emit **only the changes as a list**, not HTML:

```
The tracker's index.html stores all 27 countries in one COUNTRIES JS array;
both tables and the stats are generated from it. Do NOT output HTML or <tr> rows.
Output ONLY the countries that changed, as:  Country | field | new value
Fields: status, cat (adopted|draft|partial|noinfo), laws, expected, verified,
details, draft link, or any of the 12 requirement cells (yes|partial|pending|no|na).
```

Then that list gets applied to the `COUNTRIES` array. The stats bar and
`og:description` follow automatically.
