# Development and collaboration

GitHub is the source of truth. Live Share is useful for pair programming but is not needed to run the application.

Recommended branches are `main`, `backend/raspberry`, `frontend/dashboard`, `ai/gemini`, and `qa/demo`. Create a short-lived branch from the appropriate area, make one cohesive change, run the relevant checks, push it, and open a pull request into `main`.

```bash
git pull origin main
git checkout -b frontend/dashboard-map
git add dashboard_client
git commit -m "Add dashboard map state"
git push -u origin frontend/dashboard-map
```

Before merging, keep the API contract compatible, do not commit `.env`, and resolve conflicts locally. Use VS Code Live Share only to collaborate on the same machine/session; each contributor still commits their own work to Git.

