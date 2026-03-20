# CLAUDE.md

## Project Overview

Personal portfolio website for James Calby — Data Systems Specialist, HMIS Administrator, and Technical Consultant. Hosted on GitHub Pages at jamescalby.com.

## Tech Stack

- **Static site** — pure HTML/CSS, no build tools or frameworks
- **Fonts** — Google Fonts (Outfit, JetBrains Mono)
- **Hosting** — GitHub Pages with custom domain (CNAME: jamescalby.com)
- **No JavaScript frameworks** — vanilla JS only (scroll animations, mobile nav toggle)

## Project Structure

```
index.html          — Main single-page site (hero, about, skills, projects, contact)
blog/               — Blog post HTML pages
projects/           — Project files (Python, SQL, HTML)
CNAME               — GitHub Pages custom domain config
BingSiteAuth.xml    — Bing site verification
```

## Key Conventions

- All styling is inline in `<style>` within `index.html` (no external CSS files)
- CSS uses custom properties defined in `:root` (dark theme with blue accent)
- Font families: `--sans` (Outfit) for body, `--mono` (JetBrains Mono) for code/labels
- Responsive breakpoint at 768px
- Sections use `.fade-in` class with IntersectionObserver for scroll animations
- No external JS dependencies

## Development Notes

- Edit `index.html` directly for site content and styling changes
- Blog posts are standalone HTML files in `blog/`
- Project demo files live in `projects/`
- No build step required — changes are live on push to the deployed branch
