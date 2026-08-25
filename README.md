# FinSavvy — Be smarter with money.

A financial literacy & awareness platform (prototype).

A working sample prototype for the "understand before you decide" financial literacy platform.

- **Frontend**: a single, dependency-free `index.html` — open it directly in a browser, no build step.
- **Backend** (optional): a small Flask + SQLite API in `backend/` that adds real accounts, saved learning progress, and a history of "Think Before You Decide" sessions.

The frontend works completely on its own (with sample/local progress data). The backend is only needed if you want progress and decisions to persist for a real signed-in user.

## 1. Running the frontend only

No installation needed.

1. Download `index.html`.
2. Double-click it, or drag it into any browser.

That's it — the whole app (navigation, 6 modules, scenarios, Think Before You Decide, 3 calculators, Money Moments, Progress) runs client-side. Without the backend running, Progress shows sample data and Think Before You Decide still fully works, it just doesn't save your inputs anywhere.

If you'd rather serve it locally (e.g. to test on your phone over Wi-Fi):
```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```

## 1b. Running the backend (for real accounts + saved progress)

Requires Python 3.9+.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

This starts the API at `http://localhost:5000` and creates a `finsavvy.db` SQLite file automatically on first run — no separate database install needed.

Leave this running in a terminal, then open `index.html` (or serve it as above) in a browser. Click **Sign in** in the nav, choose **Sign up**, and create an account. Once signed in:
- **Progress** loads live from the API instead of sample data.
- On a module page, **Mark module as complete** saves that module's progress (100%) to your account.
- In **Think Before You Decide**, choosing a reflection option ("I'll reconsider," etc.) on Step 4 saves that whole decision session to your account.

### API reference

| Method | Endpoint | Auth? | Purpose |
|---|---|---|---|
| POST | `/api/signup` | No | Create an account, returns a token |
| POST | `/api/login` | No | Log in, returns a token |
| GET | `/api/progress` | Yes | List this user's module progress |
| POST | `/api/progress` | Yes | Upsert `{module_id, percent}` |
| GET | `/api/decisions` | Yes | List this user's saved decisions |
| POST | `/api/decisions` | Yes | Save a Think Before You Decide session |
| GET | `/api/health` | No | Health check |

Auth uses a simple bearer token (`Authorization: Bearer <token>`), stored in the browser's `localStorage` after sign-in. Passwords are hashed with Werkzeug's `generate_password_hash` — never stored in plain text.

**Note:** this backend is set up for local development (CORS wide open, Flask's built-in dev server, SQLite). Before deploying it anywhere public, you'd want to restrict CORS to your actual frontend origin, add rate limiting on `/api/login`, and move to a production WSGI server (e.g. gunicorn) — worth doing once you're past prototype stage.

## 2. What's implemented

| Spec section | Status |
|---|---|
| Home / hero / Earn→Spend→Save→Borrow→Invest→Plan visual | ✅ |
| 6 learning modules with lessons | ✅ (3 lessons each, expandable structure) |
| Think Before You Decide (4-step decision engine) | ✅ rule-based, no AI |
| Scenarios — "What Would You Do?" (6 scenarios) | ✅ |
| Money Tools — Budget / EMI / Savings Goal calculators | ✅ |
| Money Moments | ✅ rotating card |
| Progress tracker | ✅ (mock data, not a "financial health score") |
| Disclaimer | ✅ footer |
| Responsive layout | ✅ down to mobile |

## 3. Where things live (single-file structure for now)

Everything is in `index.html`, organized top-to-bottom:

- **`<style>` block** — design tokens as CSS variables at the top (`--teal`, `--amber`, `--bg`, etc.), then component styles.
- **HTML body** — one `<div class="page" id="page-X">` per screen (home, learn, module, scenarios, think, tools, progress). Only one is visible at a time; `goPage()` toggles them. This mimics client-side routing without a router library.
- **`<script>` block, in order:**
  1. **`MODULES`, `SCENARIOS`, `MOMENTS`, `PROGRESS`** — the mock data layer. This is the part meant to move to a database later.
  2. **Navigation** (`goPage`)
  3. **Module rendering** (`moduleCardHTML`, `openModule`)
  4. **Scenario rendering** (`scenarioCardHTML`, `revealOutcome`)
  5. **The decision engine** (`calcEMI`, `tbydGo`) — this is the rule-based logic described in spec section 21. It reads structured inputs, runs calculations, and generates "things to consider," never a verdict.
  6. **Money Tools** (`calcBudget`, `calcEMIStandalone`, `calcGoal`)
  7. **Money Moments** and **Progress** rendering

## 4. How to add a new scenario

Open `index.html`, find the `SCENARIOS` array, and add an object in the same shape:

```js
{id:7, title:'Your Scenario Title', amount:'₹XX,000', prompt:'One-sentence situation.',
  choices:[
    {label:'Choice A', outcome:'What tends to follow — no right/wrong framing.'},
    {label:'Choice B', outcome:'...'},
    {label:'Choice C', outcome:'...'}
  ]}
```
It will automatically appear in both the Scenarios page and (if within the first 3) the homepage.

## 5. How to add a new module

Add an object to the `MODULES` array with `id`, `num`, `title`, `topics`, `desc`, and a `lessons` array (`h` = heading, `body` = explanation, `ex` = optional real-life example). Update `progressFor()` and the `PROGRESS` array if you want it tracked.

## 6. How the decision engine's rules work (spec section 21)

`tbydGo(2)` in the script is the engine. Today it implements:
- IF method = EMI or credit → calculate EMI, total repayment, total interest
- IF the monthly payment is a large share of income (>30%) → flag it as worth watching
- IF savings are below one month of expenses → surface a caution about unexpected costs
- Every output is phrased as "things to consider," never an instruction

To add a new rule, add another `considerations.push({watch: <boolean>, text: <string>})` inside `tbydGo`.

## 7. Moving to a real React/Vite project (Phase 8+)

This prototype is intentionally framework-free so it's instantly runnable. When you're ready to build the fuller version described in the spec (routing, component reuse, animations, accessibility polish, backend):

```bash
npm create vite@latest finsavvy -- --template react
cd finsavvy
npm install
npm run dev
```
Then port each `MODULES` / `SCENARIOS` / `MOMENTS` / `PROGRESS` array into `src/data/*.js` files, and turn each `page-X` div into a component (`Home.jsx`, `Learn.jsx`, `ThinkBeforeYouDecide.jsx`, etc.) using React Router for navigation instead of `goPage()`.

## 8. Connecting a backend later

Progress and any user-entered decisions currently live only in memory (nothing is saved between visits). To persist them:
- Add a lightweight backend (Node/Express, or a BaaS like Supabase/Firebase) with a `users`, `progress`, and `decisions` table.
- Replace the in-memory `PROGRESS` array with a fetch call on load, and update it via API calls when a lesson is completed.

## 9. Where AI could plug in later (without becoming the decision-maker)

Per spec section 11, AI should only ever help **parse input**, never **make the call**. A safe integration point: replace the manual Step 1 form in Think Before You Decide with a free-text box, send it to an LLM with a system prompt asking it to extract `{income, purchase, method, rate, tenure}` as structured JSON, then feed that JSON into the exact same `tbydGo()` calculation logic that already exists. The rules engine — not the AI — still produces the considerations and outcomes.

## 10. Known simplifications in this pass

- Only 3 sample lessons per module (spec allows for more depth later).
- No persistence (localStorage or backend) yet — refreshing resets Progress/inputs.
- Credit card "EMI" in Think Before You Decide uses a simplified 3-month default split for illustration; a real build would model minimum-payment behavior separately from EMI loans.
