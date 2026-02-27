# 🇪🇺 EU Pay Transparency Directive - Implementation Tracker

A comprehensive tracker showing the implementation status of the EU Pay Transparency Directive (2023/970) across all 27 EU member states.

## 📊 What's Included

- **Live countdown** to the 7 June 2026 deadline
- **Status badges** for all 27 EU countries (Draft published / Partial / No information)
- **Direct links** to official draft legislation where available
- **Baltic countries highlight** with verified ministry sources
- **EEA note** for Norway, Iceland, and Liechtenstein
- **Methodology transparency** explaining data limitations

## 🚀 Deployment

### Deploy to Vercel (Recommended)

1. Push this repository to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Click "New Project"
4. Import your GitHub repository
5. Click "Deploy" (no configuration needed)

### Local Development

```bash
# Install a simple server
npm install -g serve

# Run locally
serve .

# Or just open index.html in your browser
```

## 📁 Project Structure

```
├── index.html      # Main tracker page
├── package.json    # Project metadata
├── vercel.json     # Vercel deployment config
└── README.md       # This file
```

## 🔄 Updating the Tracker

The tracker is a single HTML file (`index.html`). To update:

1. Edit the country rows in the `<tbody>` section
2. Update the stats in the `.stats-bar` section if counts change
3. Update the "Last updated" date in the `.updated` section

### Status Categories

| Status | Badge Class | Meaning |
|--------|-------------|---------|
| Draft published | `badge-green` | Official draft legislation publicly available |
| Partial / Expected | `badge-yellow` | Some measures in place or draft expected soon |
| No information currently | `badge-red` | No public transposition documentation found |

## 📋 Data Sources

### Primary Sources
- [EUR-Lex](https://eur-lex.europa.eu/eli/dir/2023/970/oj/eng) - Official EU law database
- National ministry portals (linked per country)
- European Commission statements

### Tracking Sources
- [Pinsent Masons](https://www.pinsentmasons.com/out-law/guides/eu-pay-transparency-directive-eu-member-states)
- [Addleshaw Goddard](https://www.addleshawgoddard.com/globalassets/insights/employment/eu-pay-transparency-directive-implementation-tracker.pdf)
- [Eurofound](https://www.eurofound.europa.eu/)

## 🇪🇪🇱🇻🇱🇹 Baltic Focus

This tracker has special focus on Baltic countries with verified ministry links:

| Country | Ministry | Status |
|---------|----------|--------|
| 🇱🇹 Lithuania | [socmin.lrv.lt](https://socmin.lrv.lt/) | ✅ Draft published |
| 🇪🇪 Estonia | [mkm.ee](https://www.mkm.ee/en/work-and-equal-opportunities/employment-relationships-and-work-environment/pay-transparency) | 🟡 Draft expected |
| 🇱🇻 Latvia | [lm.gov.lv](https://www.lm.gov.lv/) | 🔴 No information |

## ⚠️ Disclaimer

"No information currently" indicates that no publicly available transposition documentation was found. This does **not** mean a country is taking no action — preparatory work may be underway without public documentation.

This tracker is for informational purposes only and does not constitute legal advice.

## 📄 License

MIT License - Feel free to use and adapt with attribution.

---

**Last updated:** 27 February 2026  
**Next review:** March 2026  
**Corrections welcome** - Open an issue or submit a PR
