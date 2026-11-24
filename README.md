# Tactix

Analisi tattica avanzata della Serie A 2026/27. Hosting 100% free tier: Next.js su Vercel, PostgreSQL su Supabase, pipeline Python su GitHub Actions.

| Percorso | Contenuto |
|---|---|
| `src/` | Frontend Next.js 16 (App Router, TypeScript strict, Tailwind v4, Recharts) |
| `src/types/tactics.ts` | Contratti condivisi, allineati allo schema SQL (verificati da `schema-alignment.ts`) |
| `src/lib/mock-data.ts` | Dati fittizi tipizzati (giornate 12–13) per lo sviluppo UI |
| `pipeline/` | ETL Python 3.12: `adapters/`, `engine/`, `ai/`, `db/` |
| `supabase/migrations/` | Schema PostgreSQL + RLS (sola lettura pubblica) |
| `DESIGN.md` | Design system e standard dei grafici |

## Frontend

```bash
npm install
npm run dev
npm run typecheck   # include il controllo di allineamento con lo schema DB
npm run db:types    # rigenera src/types/database.types.ts dopo ogni migrazione
```

## Pipeline

```bash
cd pipeline
uv sync
uv run pytest
```

Variabili d'ambiente: vedi `.env.example`. La service role key vive solo nei secret di GitHub Actions.
