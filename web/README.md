# Citewise: web

Next.js (App Router) + Tailwind + React Flow. All data comes from the FastAPI backend.

- Env: copy `.env.example` to `.env.local`; `NEXT_PUBLIC_API_URL` is the API origin (default `http://localhost:8000`).
- Dev: `npm install && npm run dev` (http://localhost:3000). The API must allow this origin via CORS.
- Build: `npm run build && npm start`; checks: `npm run lint` and `npx tsc --noEmit`.
- Vercel: import the repo, set Root Directory to `web`, add `NEXT_PUBLIC_API_URL`, deploy. Add the Vercel domain to the API's CORS origins.
- Student id lives in `localStorage` (`student_id`); the Library admin token stays in React state/sessionStorage only.
