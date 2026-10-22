# mark

Personal portfolio of **Mark — DevOps & Platform Engineer**: case studies and
walkthrough decks for my infrastructure, automation and platform engineering
projects.

The site is plain static HTML on GitHub Pages. There is no site generator and
no build step in CI: what is committed in `_deploy/` is what gets published.

## What's on the site

| Section | Path | What it is |
|---|---|---|
| Home | `_deploy/index.html` | Introduction, featured projects, contact links |
| Projects | `_deploy/projects/` | One card per project case study |
| Case studies | `_deploy/docs/<project>/` | Overview, Architecture, How It Works, Lessons & Next Steps |
| Walkthroughs | `_deploy/walkthroughs/`, `_deploy/presentations/<slug>/` | reveal.js slide decks |
| About | `_deploy/about/` | Skills, certifications, experience, CV |

Projects currently written up:

- [Packer Golden Image Pipeline](https://github.com/natsuichigo/packer-image-pipeline)
- [Ansible Execution Environment Pipeline](https://github.com/natsuichigo/ansible-execution-image-pipeline)
- [Platform Lab](https://github.com/natsuichigo/platform-lab) (in progress)
- This portfolio site

## How it's built

- **Deployment:** `.github/workflows/deploy-pages.yml` uploads `_deploy/` to
  GitHub Pages on every push to `main`. Pull requests build but do not deploy.
  It needs no secrets. One-time setup: Settings → Pages → Source: **GitHub Actions**.
- **Case studies:** written in Markdown in `_deploy/docs/<project>/_src/` and
  turned into pages by the `md-to-docs` Claude Code skill.
- **Decks:** built from a JSON plan by the `docs-to-deck` Claude Code skill.
- **Branding:** every colour comes from `_deploy/assets/theme.css`.

Both skills live in `.claude/skills/`, so they come with the repo. Open Claude
Code in this folder and ask it to "write up <project> as a case study" or
"make an overview deck for <project>", or run the scripts directly.

## Adding a project

```bash
S=.claude/skills/md-to-docs/scripts

# 1. Scaffold the case study
python3 $S/scaffold_project.py --repo-root . --project my-project --like portfolio-site \
  --site-name "My Project" --docidx-label "My Project" --footer-name "My Project — Mark"

# 2. Add the four pages to _deploy/docs/my-project/_src/docs.config.json and write
#    overview.md, architecture.md, how-it-works.md and lessons.md beside it

# 3. Build and check
python3 $S/build_project.py --project my-project
python3 $S/validate_pages.py --project my-project
```

Then fill in the project's `index.html` (subtitle, repo button, one card per
page) and add a card to `_deploy/projects/index.html`.

## Preview locally

```bash
python3 -m http.server -d _deploy 8000
# open http://localhost:8000
```

Nothing in CI checks the pages, so run `validate_pages.py --all` and
`validate_deck.py --all` before pushing.

## License

MIT. See [LICENSE](LICENSE).
