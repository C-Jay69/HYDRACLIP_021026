# ***VIDEO CONTENT SCHEDULED AUTOMATION PROMPT***

You are a senior full-stack SaaS engineer, Python media-pipeline engineer, DevOps architect, and product designer.

Build a production-ready, deployable full-stack SaaS platform similar in concept to https\://autoshorts.ai that allows users to generate, preview, schedule, and publish short-form and long-form videos to YouTube, Instagram, TikTok, and X.

The platform must be a real MVP that can be deployed and used, not a mockup or pseudo-project.

\====================================  
CORE GOAL  
\====================================

Create a full-stack application where users can:

1\. Sign up / log in  
2\. Choose a subscription plan via Stripe  
3\. Create a video project from a topic/prompt  
4\. Generate a short or long video using only free/open-source/local AI models  
5\. Edit metadata and preview the result  
6\. Schedule posts for YouTube, Instagram, TikTok, and X  
7\. Publish automatically where official APIs allow it  
8\. Fall back to compliant manual export/upload flows where APIs are limited  
9\. Manage everything through a clean dashboard  
10\. Allow admins to manage users, subscriptions, jobs, logs, and maintenance through a full admin panel

\====================================  
NON-NEGOTIABLE CONSTRAINTS  
\====================================

1\. Do NOT use paid AI APIs.  
   \- No OpenAI  
   \- No Anthropic  
   \- No ElevenLabs  
   \- No Runway  
   \- No AssemblyAI  
   \- No Replicate  
   \- No paid proprietary model APIs

2\. Use only free/open-source/self-hosted/local model tooling for content generation.  
   Preferred options:  
   \- LLM/text generation: Ollama with Llama 3.x / Mistral / similar open model  
   \- TTS: Piper or Coqui TTS  
   \- STT/subtitles: faster-whisper or whisper.cpp  
   \- Video rendering: FFmpeg \+ MoviePy or equivalent  
   \- Optional image generation: Stable Diffusion / SDXL locally if available  
   \- Optional thumbnail generation: local SD or template-based approach

3\. Social posting must use only official platform APIs where available.  
   \- No browser automation  
   \- No scraping  
   \- No Selenium hacks  
   \- No ToS-violating workarounds

4\. If a platform cannot be fully automated under common free developer access, build:  
   \- the OAuth/account connection layer  
   \- the publishing adapter interface  
   \- scheduling logic  
   \- status tracking  
   \- a compliant fallback export/manual upload flow  
   \- clear documentation about what is and is not possible

5\. Output real code, real architecture, real migrations, real Docker files, real deployment instructions.  
   \- No pseudocode  
   \- No “TODO” placeholders for core features  
   \- No fake integrations

\====================================  
RECOMMENDED STACK  
\====================================

Use this stack unless you have a clearly better production-ready alternative and explain why:

Frontend:  
\- Next.js 14+ with App Router  
\- TypeScript  
\- Tailwind CSS  
\- shadcn/ui or equivalent component library

Backend:  
\- FastAPI (Python 3.11+)

Background jobs / scheduling:  
\- Celery or RQ with Redis  
\- Cron or APScheduler for scheduled publishing

Database:  
\- PostgreSQL

ORM / migrations:  
\- SQLAlchemy \+ Alembic

Auth:  
\- Secure email/password auth  
\- Session or JWT auth with secure cookies  
\- Password reset flow  
\- Role-based access control (USER, ADMIN)

Storage:  
\- S3-compatible storage  
\- MinIO for local development  
\- Compatible with S3/R2 in production

Local/open-source model layer:  
\- Ollama for text generation  
\- Piper/Coqui for TTS  
\- faster-whisper for captions/subtitles  
\- FFmpeg for assembly/rendering  
\- optional Stable Diffusion for generated images/thumbnails

Deployment:  
\- Full Docker setup  
\- docker-compose for local development  
\- production-ready Dockerfiles  
\- deployable to a VPS / Render / Railway / Fly / self-hosted Docker server

Structure:  
\- Monorepo preferred:  
  \- apps/web  
  \- apps/api  
  \- apps/worker  
  \- shared config/types/utilities if needed

\====================================  
APP FEATURES  
\====================================

Build the following complete product:

1\. Marketing site  
\- Homepage  
\- Features page  
\- Pricing page  
\- FAQ  
\- Login/signup CTA  
\- Modern SaaS design  
\- Responsive and polished  
\- Dark mode

2\. Authentication and user system  
\- Sign up  
\- Log in  
\- Log out  
\- Reset password  
\- Email verification optional if practical  
\- User profile page  
\- Role system: USER and ADMIN  
\- User onboarding wizard

3\. User dashboard  
\- Overview metrics  
\- Recent projects  
\- Scheduled posts  
\- Published posts  
\- Failed jobs  
\- Usage quotas  
\- Subscription status  
\- Connected social accounts

4\. Project/video creation flow  
Users should be able to:  
\- Enter a topic, prompt, or script idea  
\- Choose:  
  \- short-form or long-form  
  \- target platform(s)  
  \- aspect ratio (9:16, 16:9, 1:1)  
  \- niche/category  
  \- language  
  \- tone  
  \- voice style  
  \- caption style  
  \- template/theme  
\- Generate:  
  \- script  
  \- title  
  \- description  
  \- hashtags  
  \- scene breakdown  
  \- thumbnail text  
  \- CTA  
\- Upload optional assets:  
  \- logo  
  \- music  
  \- images  
  \- short clips  
  \- brand colors

5\. Video generation pipeline  
The app must support a practical MVP generation flow using local/open tools:  
\- Generate script with local LLM  
\- Generate scene plan  
\- Generate voiceover locally  
\- Generate subtitles/captions locally  
\- Assemble video with FFmpeg  
\- Support at minimum:  
  \- short-form caption-heavy videos  
  \- long-form narrated slideshow/explainer videos  
\- Allow use of:  
  \- user-uploaded assets  
  \- generated background images  
  \- template-based motion/text scenes  
  \- intro/outro templates  
\- Produce downloadable final video file  
\- Produce preview before publishing

6\. Editor / preview flow  
\- Show rendered preview  
\- Allow metadata edits before publish:  
  \- title  
  \- description  
  \- hashtags  
  \- captions/subtitles  
  \- scheduled date/time  
\- Allow rerender/regenerate selected parts  
\- Allow change of voice, theme, colors, fonts

7\. Scheduling and publishing  
Build a publishing system with:  
\- platform connectors/adapters  
\- scheduled jobs  
\- retries  
\- status tracking  
\- per-platform metadata mapping  
\- timezone support

Support the following target platforms:  
\- YouTube  
\- Instagram  
\- TikTok  
\- X

Each platform integration must support the following abstraction:  
\- connect()  
\- disconnect()  
\- validateConnection()  
\- refreshToken()  
\- prepareUploadPayload()  
\- uploadMedia()  
\- publish()  
\- getPublishStatus()

Important:  
\- Use official APIs only  
\- If a platform cannot truly auto-publish under normal free access, implement a fallback:  
  \- export-ready media  
  \- prefilled metadata  
  \- publish reminder  
  \- manual upload workflow  
  \- clear UI status showing “manual action required”

8\. Stripe integration  
Implement:  
\- Free plan  
\- Creator plan  
\- Pro plan  
\- Stripe Checkout  
\- Stripe Customer Portal  
\- Webhook handling  
\- Plan upgrades/downgrades  
\- Usage limits based on plan  
\- Billing history  
\- Subscription status in UI

9\. Admin panel  
Build a full admin dashboard with secure credentials and RBAC.

Admin panel must include:  
\- Admin login protection  
\- Seeded admin account from env variables  
\- Dashboard metrics:  
  \- total users  
  \- active subscriptions  
  \- MRR or estimated recurring revenue  
  \- queued jobs  
  \- failed jobs  
  \- published posts  
  \- storage usage  
\- User management:  
  \- view users  
  \- search/filter users  
  \- deactivate user  
  \- reset password  
  \- change user role  
  \- inspect user projects  
\- Billing management:  
  \- view subscription state  
  \- view Stripe events  
\- Job management:  
  \- inspect render jobs  
  \- inspect publish jobs  
  \- retry failed jobs  
  \- cancel queued jobs  
\- Settings:  
  \- maintenance mode toggle  
  \- feature flags  
  \- model/provider settings  
  \- default templates/prompts  
\- Logs:  
  \- system logs  
  \- audit logs  
  \- webhook logs  
\- Safe admin impersonation for support if practical

10\. Maintenance mode and ops  
Implement:  
\- maintenance mode toggle  
\- health check endpoint  
\- readiness check endpoint  
\- job queue monitoring  
\- structured logs  
\- idempotent background jobs  
\- retry/backoff logic  
\- graceful error handling if local model services are unavailable

\====================================  
DATABASE REQUIREMENTS  
\====================================

Design a complete PostgreSQL schema with migrations.

At minimum include tables/models for:  
\- users  
\- sessions  
\- roles or role field  
\- subscriptions  
\- billing\_events  
\- usage\_events  
\- projects  
\- project\_assets  
\- videos  
\- video\_jobs  
\- schedules  
\- published\_posts  
\- social\_accounts  
\- platform\_tokens  
\- admin\_audit\_logs  
\- system\_settings  
\- prompt\_templates  
\- webhook\_events

Make sure relationships are correct and production-sensible.

\====================================  
SECURITY REQUIREMENTS  
\====================================

Implement proper security, including:  
\- hashed passwords  
\- secure auth cookies or secure JWT handling  
\- role-based route protection  
\- admin-only routes locked down  
\- encrypted storage of social tokens/secrets  
\- CSRF protection where applicable  
\- input validation on all APIs  
\- safe file upload validation  
\- rate limiting on auth endpoints  
\- audit logging for admin actions

\====================================  
UX / UI REQUIREMENTS  
\====================================

Make the frontend look like a modern polished SaaS product.

Include:  
\- responsive layout  
\- clean dashboard UI  
\- empty states  
\- loading states  
\- toasts/alerts  
\- onboarding wizard  
\- pricing cards  
\- account settings  
\- billing page  
\- project library  
\- schedule/calendar view  
\- dark mode

\====================================  
FREE / OPEN-SOURCE AI REQUIREMENTS  
\====================================

The content generation pipeline must rely only on local/free/open-source components.

Implement modular provider services such as:  
\- TextGenerationProvider  
\- TTSProvider  
\- STTProvider  
\- ThumbnailProvider  
\- VideoRenderService

Default provider choices:  
\- Ollama for script/title/description generation  
\- Piper or Coqui for voiceover  
\- faster-whisper for subtitle generation  
\- FFmpeg for rendering  
\- optional Stable Diffusion for images/thumbnails

The system must still work in MVP form even on CPU-only machines, even if slower.  
Do not make GPU-only assumptions for the core workflow.

\====================================  
SOCIAL API REALISM REQUIREMENT  
\====================================

Be honest about real-world API limitations.

For each platform:  
\- implement the connector structure  
\- implement what can really work  
\- document restrictions  
\- if automation is blocked by platform access limitations, provide a compliant fallback in both code and docs

Do NOT pretend all four platforms have identical free upload capability.

\====================================  
DEPLOYMENT REQUIREMENTS  
\====================================

Provide everything needed to run locally and deploy.

Must include:  
\- docker-compose.yml for local development with:  
  \- web  
  \- api  
  \- worker  
  \- postgres  
  \- redis  
  \- minio  
  \- ollama  
\- production-ready Dockerfiles  
\- .env.example with all environment variables  
\- Alembic migrations  
\- seed script

Seed script must create:  
\- admin user from ADMIN\_EMAIL and ADMIN\_PASSWORD env vars  
\- sample regular user  
\- default subscription plans  
\- default templates/prompts  
\- sample project if useful

Provide a full README with:  
\- local setup  
\- model setup  
\- Stripe setup  
\- OAuth setup for social platforms  
\- database migration commands  
\- seed commands  
\- worker startup  
\- publishing/scheduling explanation  
\- deployment steps  
\- API limitations section  
\- troubleshooting

\====================================  
DEVELOPER EXPERIENCE  
\====================================

Include:  
\- clear folder structure  
\- linting/formatting config  
\- basic tests  
\- reusable services  
\- typed API responses where practical  
\- environment validation  
\- comments only where useful, not noise  
\- no dead code  
\- no fake code

\====================================  
WHAT TO OUTPUT  
\====================================

Output the project in this order:

1\. High-level architecture explanation  
2\. Final folder tree  
3\. Full implementation code, grouped by folders/files  
4\. Database models and migrations  
5\. Background worker and scheduling logic  
6\. Stripe integration  
7\. Social platform connector layer  
8\. Admin panel implementation  
9\. Docker and deployment files  
10\. Seed scripts  
11\. README  
12\. .env.example

If the full codebase is too large for one message:  
\- continue in the next message automatically  
\- never skip critical files  
\- do not summarize instead of coding  
\- continue until the entire project is complete

\====================================  
QUALITY BAR  
\====================================

This must feel like a real bootstrap-friendly SaaS product that a founder could deploy, demo, and iterate on.

Optimize for:  
\- low operating cost  
\- open-source/self-hosted AI  
\- honest handling of platform limits  
\- practical MVP functionality  
\- clean code  
\- deployability

Now build the complete codebase.

* **\*\*Important: start with the architecture and folder tree, then generate the code in batches without skipping files. Do not ask me to confirm every step. Make reasonable implementation decisions and keep going until the whole app is complete.\*\***

\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

* # Claude Code Version (Full Platform)

* ## 

* \<anthropic\_thinking\>  
* You are a senior full-stack SaaS engineer, Python media-pipeline engineer,   
* DevOps architect, and product designer working inside OpenClaw.  
*   
* You have full access to the filesystem, terminal, and can run commands.  
* Build the complete platform described below by actually creating files,   
* running migrations, installing dependencies, and verifying the build works.  
*   
* Do not describe what you would do. Do the work.  
* \</anthropic\_thinking\>  
*   
* You are building a production-ready, deployable, bootstrap-friendly SaaS platform   
* similar to AutoShorts.ai. Users generate, schedule, and publish short and long-form   
* videos to YouTube, Instagram, TikTok, and X using only free/open-source AI tools.  
*   
* \====================================  
* WORKING STYLE FOR CLAUDE CODE  
* \====================================  
*   
* \- Create every file by actually writing it to disk  
* \- Run terminal commands to verify installs and builds  
* \- Run database migrations after creating them  
* \- Validate Docker builds  
* \- Check for import errors after writing each module  
* \- When you hit an error, fix it before continuing  
* \- Never skip a file — create it fully  
* \- Commit nothing, but verify everything runs  
* \- After each major section, run a health check  
* \- If a library has a version conflict, resolve it and continue  
*   
* \====================================  
* START SEQUENCE  
* \====================================  
*   
* Step 1: Create the monorepo structure  
* Step 2: Install all dependencies and verify  
* Step 3: Set up environment config and validation  
* Step 4: Build and migrate the database  
* Step 5: Build the FastAPI backend fully  
* Step 6: Build the Celery/Redis worker fully  
* Step 7: Build the AI generation pipeline  
* Step 8: Build the social platform connector layer  
* Step 9: Build the Stripe integration  
* Step 10: Build the Next.js frontend fully  
* Step 11: Build the admin panel  
* Step 12: Write Docker and docker-compose files  
* Step 13: Write seed scripts and run them  
* Step 14: Verify the full stack starts cleanly  
* Step 15: Write the README  
*   
* \====================================  
* CONSTRAINTS  
* \====================================  
*   
* Free/open-source AI only:  
* \- Ollama (Llama 3 / Mistral) for text generation  
* \- Piper or Coqui TTS for voiceover  
* \- faster-whisper for captions  
* \- FFmpeg \+ MoviePy for video rendering  
* \- Optional: local Stable Diffusion for images  
*   
* Official APIs only for social:  
* \- No scraping, no Selenium, no ToS violations  
* \- If a platform cannot fully auto-publish under free developer access:  
*   \- Build the full connector interface  
*   \- Build the compliant manual fallback  
*   \- Document it clearly  
*   
* Stack:  
* \- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui  
* \- Backend: FastAPI, Python 3.11+  
* \- Workers: Celery \+ Redis  
* \- Database: PostgreSQL \+ SQLAlchemy \+ Alembic  
* \- Storage: MinIO locally / S3-compatible in production  
* \- Auth: Secure JWT with httpOnly cookies, RBAC (USER, ADMIN)  
* \- Payments: Stripe Checkout \+ Customer Portal \+ Webhooks  
*   
* \====================================  
* DATABASE SCHEMA  
* \====================================  
*   
* Create full Alembic migrations for:  
*   
* users  
* \- id, email, password\_hash, name, role, is\_active,  
*   is\_verified, stripe\_customer\_id, created\_at, updated\_at  
*   
* sessions  
* \- id, user\_id, token\_hash, expires\_at, created\_at  
*   
* subscriptions  
* \- id, user\_id, stripe\_subscription\_id, plan\_id,  
*   status, current\_period\_start, current\_period\_end,  
*   cancel\_at\_period\_end, created\_at, updated\_at  
*   
* plans  
* \- id, name, stripe\_price\_id, video\_limit\_monthly,  
*   storage\_limit\_gb, features\_json, price\_cents,  
*   is\_active, created\_at  
*   
* usage\_events  
* \- id, user\_id, event\_type, quantity, metadata\_json, created\_at  
*   
* projects  
* \- id, user\_id, title, topic, niche, platform\_targets,  
*   format, aspect\_ratio, tone, language, status,  
*   created\_at, updated\_at  
*   
* project\_assets  
* \- id, project\_id, asset\_type, storage\_key, original\_filename,  
*   metadata\_json, created\_at  
*   
* videos  
* \- id, project\_id, user\_id, status, storage\_key,  
*   duration\_seconds, resolution, format,  
*   generation\_params\_json, error\_message,  
*   created\_at, updated\_at  
*   
* video\_jobs  
* \- id, video\_id, job\_type, celery\_task\_id, status,  
*   progress\_pct, log\_text, started\_at, completed\_at,  
*   error\_message, created\_at  
*   
* schedules  
* \- id, video\_id, user\_id, platform, scheduled\_at,  
*   timezone, status, created\_at, updated\_at  
*   
* published\_posts  
* \- id, video\_id, schedule\_id, user\_id, platform,  
*   platform\_post\_id, platform\_url, title,  
*   description, tags, status, published\_at,  
*   error\_message, created\_at  
*   
* social\_accounts  
* \- id, user\_id, platform, account\_name, account\_id,  
*   is\_active, connected\_at, expires\_at, created\_at  
*   
* platform\_tokens  
* \- id, social\_account\_id, access\_token\_encrypted,  
*   refresh\_token\_encrypted, token\_type, scope,  
*   expires\_at, created\_at, updated\_at  
*   
* prompt\_templates  
* \- id, name, category, platform\_target, format,  
*   script\_template, title\_template, description\_template,  
*   hashtag\_template, is\_default, created\_at, updated\_at  
*   
* system\_settings  
* \- id, key, value, value\_type, description, updated\_by, updated\_at  
*   
* webhook\_events  
* \- id, provider, event\_id, event\_type, payload\_json,  
*   processed, processed\_at, error\_message, created\_at  
*   
* admin\_audit\_logs  
* \- id, admin\_id, action, target\_type, target\_id,  
*   metadata\_json, ip\_address, created\_at  
*   
* \====================================  
* BACKEND API ROUTES  
* \====================================  
*   
* Auth:  
* POST   /api/auth/register  
* POST   /api/auth/login  
* POST   /api/auth/logout  
* POST   /api/auth/refresh  
* POST   /api/auth/reset-password/request  
* POST   /api/auth/reset-password/confirm  
* GET    /api/auth/me  
*   
* Users:  
* GET    /api/users/me  
* PUT    /api/users/me  
* GET    /api/users/me/usage  
* GET    /api/users/me/social-accounts  
* DELETE /api/users/me/social-accounts/{platform}  
*   
* Projects:  
* GET    /api/projects  
* POST   /api/projects  
* GET    /api/projects/{id}  
* PUT    /api/projects/{id}  
* DELETE /api/projects/{id}  
* POST   /api/projects/{id}/assets  
*   
* Videos:  
* GET    /api/videos  
* POST   /api/videos/generate  
* GET    /api/videos/{id}  
* GET    /api/videos/{id}/status  
* DELETE /api/videos/{id}  
* POST   /api/videos/{id}/regenerate  
* GET    /api/videos/{id}/download  
*   
* Schedule:  
* GET    /api/schedules  
* POST   /api/schedules  
* PUT    /api/schedules/{id}  
* DELETE /api/schedules/{id}  
* POST   /api/schedules/{id}/publish-now  
*   
* Publishing:  
* GET    /api/published  
* GET    /api/published/{id}  
*   
* OAuth:  
* GET    /api/oauth/{platform}/connect  
* GET    /api/oauth/{platform}/callback  
* DELETE /api/oauth/{platform}/disconnect  
*   
* Billing:  
* GET    /api/billing/plans  
* POST   /api/billing/checkout  
* GET    /api/billing/portal  
* GET    /api/billing/subscription  
* POST   /api/webhooks/stripe  
*   
* Templates:  
* GET    /api/templates  
* GET    /api/templates/{id}  
*   
* Admin:  
* GET    /api/admin/metrics  
* GET    /api/admin/users  
* GET    /api/admin/users/{id}  
* PUT    /api/admin/users/{id}  
* POST   /api/admin/users/{id}/deactivate  
* POST   /api/admin/users/{id}/reset-password  
* GET    /api/admin/jobs  
* POST   /api/admin/jobs/{id}/retry  
* DELETE /api/admin/jobs/{id}  
* GET    /api/admin/webhooks  
* GET    /api/admin/settings  
* PUT    /api/admin/settings/{key}  
* GET    /api/admin/logs  
* POST   /api/admin/maintenance/toggle  
*   
* Health:  
* GET    /health  
* GET    /ready  
*   
* \====================================  
* AI GENERATION PIPELINE  
* \====================================  
*   
* Build a modular pipeline with these provider interfaces:  
*   
* TextGenerationProvider:  
* \- provider: OllamaProvider  
* \- methods: generate\_script(), generate\_title(),   
*   generate\_description(), generate\_hashtags(),  
*   generate\_scene\_plan(), generate\_cta()  
*   
* TTSProvider:  
* \- provider: PiperTTSProvider (fallback: CoquiTTSProvider)  
* \- methods: synthesize(text, voice, language) \-\> audio\_file  
*   
* STTProvider:  
* \- provider: FasterWhisperProvider  
* \- methods: transcribe(audio\_file) \-\> transcript\_with\_timestamps  
*   
* VideoRenderService:  
* \- uses: FFmpeg, MoviePy  
* \- methods: render\_short\_form(), render\_long\_form(),  
*   add\_captions(), add\_intro\_outro(), add\_music(),  
*   add\_logo\_overlay(), export\_for\_platform()  
*   
* ThumbnailProvider:  
* \- methods: generate\_thumbnail() using template \+ text overlay  
*   
* VideoGenerationOrchestrator:  
* \- coordinates the full pipeline  
* \- updates job progress in database  
* \- handles errors per step  
* \- emits WebSocket events for real-time progress  
*   
* \====================================  
* SOCIAL PLATFORM CONNECTORS  
* \====================================  
*   
* Build a BasePlatformConnector with this interface:  
* \- connect()  
* \- disconnect()  
* \- validate\_connection()  
* \- refresh\_token()  
* \- prepare\_upload\_payload(video, metadata)  
* \- upload\_media(payload)  
* \- publish(upload\_id, metadata)  
* \- get\_publish\_status(post\_id)  
* \- get\_fallback\_export(video, metadata)  
*   
* Implement for each platform:  
* \- YouTubeConnector  
* \- InstagramConnector  
* \- TikTokConnector  
* \- XConnector  
*   
* For each connector:  
* \- use official API only  
* \- implement what is genuinely possible under standard API access  
* \- document what requires elevated access or approval  
* \- build compliant fallback for anything that cannot be fully automated  
* \- return structured PlatformResult with status, url, fallback\_needed  
*   
* \====================================  
* STRIPE INTEGRATION  
* \====================================  
*   
* Plans:  
* \- Free: 3 videos/month, 1GB storage, watermark  
* \- Creator (\$19/month): 25 videos/month, 10GB storage, no watermark  
* \- Pro (\$49/month): unlimited videos, 50GB storage, priority queue  
*   
* Implement:  
* \- stripe.checkout.Session creation  
* \- stripe.billing\_portal.Session creation  
* \- webhook handler for:  
*   \- checkout.session.completed  
*   \- customer.subscription.updated  
*   \- customer.subscription.deleted  
*   \- invoice.payment\_failed  
*   \- invoice.payment\_succeeded  
* \- subscription status sync  
* \- plan limits enforced on API routes  
* \- usage tracking per user per month  
*   
* \====================================  
* ADMIN PANEL  
* \====================================  
*   
* Separate admin section within Next.js app at /admin/\*  
*   
* Pages:  
* \- /admin (dashboard with metrics)  
* \- /admin/users (table with search/filter/actions)  
* \- /admin/users/\[id\] (user detail)  
* \- /admin/jobs (render and publish jobs)  
* \- /admin/billing (subscriptions and Stripe events)  
* \- /admin/settings (system settings, maintenance mode, flags)  
* \- /admin/logs (system logs, audit logs, webhook logs)  
* \- /admin/templates (prompt templates)  
*   
* Admin dashboard metrics:  
* \- total users, new users (7d, 30d)  
* \- active subscriptions by plan  
* \- MRR estimate  
* \- videos generated today / this month  
* \- jobs queued, running, failed  
* \- storage used  
* \- published posts by platform  
*   
* Admin auth:  
* \- seeded from ADMIN\_EMAIL \+ ADMIN\_PASSWORD env vars  
* \- all /admin/\* routes require ADMIN role  
* \- full audit logging on all admin actions  
*   
* \====================================  
* FRONTEND PAGES  
* \====================================  
*   
* Public:  
* \- / (marketing homepage)  
* \- /features  
* \- /pricing  
* \- /faq  
* \- /login  
* \- /register  
* \- /forgot-password  
* \- /reset-password  
*   
* App (authenticated):  
* \- /dashboard  
* \- /projects  
* \- /projects/new  
* \- /projects/\[id\]  
* \- /videos  
* \- /videos/\[id\]  
* \- /videos/\[id\]/editor  
* \- /schedule  
* \- /schedule/calendar  
* \- /published  
* \- /connect (social account connections)  
* \- /settings  
* \- /settings/billing  
* \- /settings/profile  
* \- /onboarding  
*   
* Admin:  
* \- /admin/\*  
*   
* \====================================  
* DOCKER SETUP  
* \====================================  
*   
* docker-compose.yml services:  
* \- web (Next.js, port 3000\)  
* \- api (FastAPI, port 8000\)  
* \- worker (Celery)  
* \- beat (Celery Beat for scheduled publishing)  
* \- flower (Celery monitoring, port 5555\)  
* \- postgres (port 5432\)  
* \- redis (port 6379\)  
* \- minio (port 9000 \+ 9001 console)  
* \- ollama (port 11434\)  
*   
* Volumes:  
* \- postgres\_data  
* \- redis\_data  
* \- minio\_data  
* \- ollama\_models  
* \- generated\_videos  
* \- uploaded\_assets  
*   
* Networks:  
* \- internal (api, worker, postgres, redis, minio, ollama)  
* \- public (web, api)  
*   
* \====================================  
* ENVIRONMENT VARIABLES  
* \====================================  
*   
* Create a full .env.example with every variable needed:  
*   
* Database, Redis, MinIO, Ollama config  
* JWT secret, token expiry  
* Stripe keys (publishable, secret, webhook secret)  
* Admin credentials  
* YouTube OAuth (client\_id, client\_secret)  
* Instagram OAuth  
* TikTok OAuth  
* X OAuth  
* SMTP config for email  
* App URL, allowed origins  
* Model names, voices, defaults  
* Feature flags  
* Maintenance mode flag  
* Storage bucket names  
* Max file sizes  
* Plan limits override option  
*   
* Build an env validator that runs at startup and crashes   
* with a clear message if required vars are missing.  
*   
* \====================================  
* SEED SCRIPT  
* \====================================  
*   
* Create a seed.py that:  
* \- creates admin user from env vars  
* \- creates sample regular user (test@example.com / testpassword123)  
* \- creates Free, Creator, and Pro plans in DB  
* \- creates default prompt templates for short-form and long-form  
* \- creates default system settings  
* \- creates sample project and video record for demo  
* \- is idempotent (safe to run multiple times)  
*   
* \====================================  
* FOLDER STRUCTURE  
* \====================================  
*   
* Create this exact structure:  
*   
* hydraclip/
* ├── apps/  
* │   ├── web/                          \# Next.js frontend  
* │   │   ├── app/  
* │   │   │   ├── (marketing)/  
* │   │   │   │   ├── page.tsx  
* │   │   │   │   ├── features/page.tsx  
* │   │   │   │   ├── pricing/page.tsx  
* │   │   │   │   └── faq/page.tsx  
* │   │   │   ├── (auth)/  
* │   │   │   │   ├── login/page.tsx  
* │   │   │   │   ├── register/page.tsx  
* │   │   │   │   └── forgot-password/page.tsx  
* │   │   │   ├── (app)/  
* │   │   │   │   ├── dashboard/page.tsx  
* │   │   │   │   ├── projects/  
* │   │   │   │   ├── videos/  
* │   │   │   │   ├── schedule/  
* │   │   │   │   ├── published/  
* │   │   │   │   ├── connect/page.tsx  
* │   │   │   │   ├── settings/  
* │   │   │   │   └── onboarding/page.tsx  
* │   │   │   ├── admin/  
* │   │   │   │   ├── page.tsx  
* │   │   │   │   ├── users/  
* │   │   │   │   ├── jobs/page.tsx  
* │   │   │   │   ├── billing/page.tsx  
* │   │   │   │   ├── settings/page.tsx  
* │   │   │   │   ├── logs/page.tsx  
* │   │   │   │   └── templates/page.tsx  
* │   │   │   ├── layout.tsx  
* │   │   │   └── globals.css  
* │   │   ├── components/  
* │   │   │   ├── ui/  
* │   │   │   ├── marketing/  
* │   │   │   ├── dashboard/  
* │   │   │   ├── video/  
* │   │   │   ├── admin/  
* │   │   │   └── shared/  
* │   │   ├── lib/  
* │   │   │   ├── api.ts  
* │   │   │   ├── auth.ts  
* │   │   │   ├── stripe.ts  
* │   │   │   └── utils.ts  
* │   │   ├── hooks/  
* │   │   ├── types/  
* │   │   ├── Dockerfile  
* │   │   ├── package.json  
* │   │   ├── tailwind.config.ts  
* │   │   ├── tsconfig.json  
* │   │   └── next.config.ts  
* │   │  
* │   ├── api/                          \# FastAPI backend  
* │   │   ├── app/  
* │   │   │   ├── main.py  
* │   │   │   ├── config.py  
* │   │   │   ├── database.py  
* │   │   │   ├── dependencies.py  
* │   │   │   ├── models/  
* │   │   │   │   ├── \_\_init\_\_.py  
* │   │   │   │   ├── user.py  
* │   │   │   │   ├── project.py  
* │   │   │   │   ├── video.py  
* │   │   │   │   ├── schedule.py  
* │   │   │   │   ├── billing.py  
* │   │   │   │   ├── social.py  
* │   │   │   │   └── system.py  
* │   │   │   ├── schemas/  
* │   │   │   │   ├── \_\_init\_\_.py  
* │   │   │   │   ├── auth.py  
* │   │   │   │   ├── user.py  
* │   │   │   │   ├── project.py  
* │   │   │   │   ├── video.py  
* │   │   │   │   ├── schedule.py  
* │   │   │   │   ├── billing.py  
* │   │   │   │   └── admin.py  
* │   │   │   ├── routers/  
* │   │   │   │   ├── \_\_init\_\_.py  
* │   │   │   │   ├── auth.py  
* │   │   │   │   ├── users.py  
* │   │   │   │   ├── projects.py  
* │   │   │   │   ├── videos.py  
* │   │   │   │   ├── schedules.py  
* │   │   │   │   ├── publishing.py  
* │   │   │   │   ├── oauth.py  
* │   │   │   │   ├── billing.py  
* │   │   │   │   ├── webhooks.py  
* │   │   │   │   ├── templates.py  
* │   │   │   │   ├── admin.py  
* │   │   │   │   └── health.py  
* │   │   │   ├── services/  
* │   │   │   │   ├── auth\_service.py  
* │   │   │   │   ├── user\_service.py  
* │   │   │   │   ├── project\_service.py  
* │   │   │   │   ├── video\_service.py  
* │   │   │   │   ├── schedule\_service.py  
* │   │   │   │   ├── billing\_service.py  
* │   │   │   │   ├── storage\_service.py  
* │   │   │   │   ├── email\_service.py  
* │   │   │   │   └── admin\_service.py  
* │   │   │   ├── core/  
* │   │   │   │   ├── security.py  
* │   │   │   │   ├── encryption.py  
* │   │   │   │   ├── rate\_limiter.py  
* │   │   │   │   ├── middleware.py  
* │   │   │   │   └── exceptions.py  
* │   │   │   └── utils/  
* │   │   │       ├── validators.py  
* │   │   │       └── helpers.py  
* │   │   ├── migrations/  
* │   │   │   ├── env.py  
* │   │   │   ├── script.py.mako  
* │   │   │   └── versions/  
* │   │   ├── tests/  
* │   │   │   ├── test\_auth.py  
* │   │   │   ├── test\_projects.py  
* │   │   │   ├── test\_billing.py  
* │   │   │   └── conftest.py  
* │   │   ├── Dockerfile  
* │   │   ├── requirements.txt  
* │   │   └── alembic.ini  
* │   │  
* │   └── worker/                       \# Celery workers  
* │       ├── tasks/  
* │       │   ├── \_\_init\_\_.py  
* │       │   ├── video\_generation.py  
* │       │   ├── publishing.py  
* │       │   ├── scheduling.py  
* │       │   └── maintenance.py  
* │       ├── pipeline/  
* │       │   ├── \_\_init\_\_.py  
* │       │   ├── orchestrator.py  
* │       │   ├── providers/  
* │       │   │   ├── \_\_init\_\_.py  
* │       │   │   ├── base.py  
* │       │   │   ├── text\_generation.py  
* │       │   │   ├── tts.py  
* │       │   │   ├── stt.py  
* │       │   │   ├── thumbnail.py  
* │       │   │   └── video\_render.py  
* │       │   └── connectors/  
* │       │       ├── \_\_init\_\_.py  
* │       │       ├── base\_connector.py  
* │       │       ├── youtube.py  
* │       │       ├── instagram.py  
* │       │       ├── tiktok.py  
* │       │       └── x.py  
* │       ├── celery\_app.py  
* │       ├── beat\_schedule.py  
* │       ├── Dockerfile  
* │       └── requirements.txt  
* │  
* ├── docker-compose.yml  
* ├── docker-compose.prod.yml  
* ├── .env.example  
* ├── seed.py  
* ├── Makefile  
* └── README.md  
*   
* \====================================  
* MAKEFILE COMMANDS  
* \====================================  
*   
* Include a Makefile with:  
* make setup         \# copy .env, build images  
* make up            \# docker-compose up \-d  
* make down          \# docker-compose down  
* make migrate       \# run alembic upgrade head  
* make seed          \# run seed.py  
* make logs          \# tail all logs  
* make worker-logs   \# tail worker logs  
* make shell-api     \# exec into api container  
* make shell-worker  \# exec into worker container  
* make test          \# run tests  
* make pull-model    \# pull default Ollama model  
*   
* \====================================  
* README SECTIONS  
* \====================================  
*   
* Write a complete README with:  
* 1\. Project overview  
* 2\. Tech stack  
* 3\. Prerequisites  
* 4\. Quick start (5 steps to running locally)  
* 5\. Environment variables guide  
* 6\. AI model setup (Ollama, Piper)  
* 7\. Stripe setup (keys, webhook, plans)  
* 8\. Social platform OAuth setup (per platform)  
* 9\. API limitations per platform (honest section)  
* 10\. Admin panel access  
* 11\. Architecture overview diagram (ASCII)  
* 12\. Background workers explanation  
* 13\. Deployment guide (VPS, Railway, Render, Fly.io)  
* 14\. Troubleshooting  
* 15\. Contributing (if teaching use case)  
* 16\. License  
*   
* \====================================  
* QUALITY REQUIREMENTS  
* \====================================  
*   
* \- All code must be real, runnable, and importable  
* \- No pseudocode  
* \- No placeholder functions  
* \- No TODO for core features  
* \- Type hints on all Python functions  
* \- TypeScript strict mode on frontend  
* \- All routes protected correctly by role  
* \- All secrets encrypted or hashed in DB  
* \- All background jobs idempotent  
* \- All API endpoints validated  
* \- Graceful degradation if Ollama is offline  
* \- Graceful degradation if a social platform connector fails  
*   
* Begin now. Start with Step 1: create the monorepo   
* folder structure on disk, then proceed sequentially   
* through all steps without stopping.  
* Quick tip  
* If you want better output from the coding LLM, paste this first, then follow it with:  
* text  
* Important: start with the architecture and folder tree, then generate the code in batches without skipping files. Do not ask me to confirm every step. Make reasonable implementation decisions and keep going until the whole app is complete.  
* My recommendation  
* If you want this to actually ship faster for your audience, I’d strongly recommend positioning the MVP like this:  
  1. Fully automated first: YouTube  
  2. Best-effort / fallback flows: Instagram, TikTok, X  
  3. AI generation: fully local/open-source  
  4. Publishing: official APIs only, no hacks  
* That makes it much more realistic for a bootstrap tutorial product.  
* If you want, I can also make you:  
  1. a Cursor-optimized version of this prompt,  
  2. a Claude Code version, or  
  3. a lighter MVP prompt that has a much higher chance of generating a working app in one go.

\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

# **Lighter MVP Prompt (Faster, Higher Success Rate)**

text

You are a senior full-stack developer. Build a working, deployable MVP   
of a video content scheduling SaaS called HydraClip.

This is for a bootstrap tutorial — use only free/open-source tools.   
No paid AI APIs.

\====================================  
WHAT THIS APP DOES  
\====================================

Users can:  
1\. Sign up and subscribe via Stripe  
2\. Enter a topic and generate a short-form video script  
3\. Generate a voiceover from that script  
4\. Assemble a basic captioned video  
5\. Schedule or immediately publish to YouTube  
6\. Download the video for manual upload elsewhere  
7\. View their video history

Admins can:  
1\. Log in to an admin panel  
2\. See platform metrics  
3\. Manage users  
4\. View and retry jobs

\====================================  
STRICT CONSTRAINTS  
\====================================

AI tools (free/open-source only):  
\- Ollama (Llama3 or Mistral) for script/title/tags generation  
\- Piper TTS for voiceover  
\- faster-whisper for subtitles  
\- FFmpeg for video assembly  
\- Template-based captions, not AI image generation  
\- The app must work on a CPU-only machine (slower is fine)

Platform publishing:  
\- YouTube: implement full upload via YouTube Data API v3  
\- Instagram, TikTok, X: build the connector interface   
  and deliver a compliant download \+ prefilled metadata   
  export workflow only  
\- No scraping, no Selenium, no ToS violations

Stack (keep it simple):  
\- Next.js 14 App Router \+ TypeScript \+ Tailwind \+ shadcn/ui  
\- FastAPI \+ Python 3.11  
\- Celery \+ Redis for video generation jobs  
\- PostgreSQL \+ SQLAlchemy \+ Alembic  
\- MinIO for local file storage  
\- Stripe for billing

\====================================  
DATABASE (keep it lean)  
\====================================

Tables:  
\- users (id, email, password\_hash, name, role, stripe\_customer\_id,   
  is\_active, created\_at)  
\- subscriptions (id, user\_id, stripe\_subscription\_id, plan, status,   
  period\_end, created\_at)  
\- projects (id, user\_id, topic, status, settings\_json, created\_at)  
\- videos (id, project\_id, user\_id, status, storage\_key,   
  script\_text, error\_message, created\_at)  
\- video\_jobs (id, video\_id, status, progress\_pct,   
  celery\_task\_id, error, created\_at)  
\- schedules (id, video\_id, user\_id, platform, scheduled\_at,   
  status, created\_at)  
\- published\_posts (id, video\_id, platform, platform\_url,   
  status, published\_at, error\_message)  
\- social\_accounts (id, user\_id, platform, account\_name,   
  access\_token\_encrypted, refresh\_token\_encrypted, expires\_at)  
\- system\_settings (key, value, updated\_at)  
\- admin\_audit\_logs (id, admin\_id, action, target, created\_at)

\====================================  
BACKEND API ROUTES  
\====================================

Auth:  
POST /api/auth/register  
POST /api/auth/login  
POST /api/auth/logout  
GET  /api/auth/me

Projects:  
GET  /api/projects  
POST /api/projects  
GET  /api/projects/{id}

Videos:  
POST /api/videos/generate  
GET  /api/videos/{id}/status  
GET  /api/videos/{id}/download  
GET  /api/videos

Schedule:  
POST /api/schedules  
GET  /api/schedules  
POST /api/schedules/{id}/publish-now

OAuth:  
GET  /api/oauth/youtube/connect  
GET  /api/oauth/youtube/callback

Billing:  
GET  /api/billing/plans  
POST /api/billing/checkout  
GET  /api/billing/portal  
POST /api/webhooks/stripe

Admin:  
GET  /api/admin/metrics  
GET  /api/admin/users  
PUT  /api/admin/users/{id}  
GET  /api/admin/jobs  
POST /api/admin/jobs/{id}/retry  
GET  /api/admin/settings  
PUT  /api/admin/settings/{key}

Health:  
GET  /health

\====================================  
VIDEO GENERATION PIPELINE  
\====================================

The Celery worker runs this pipeline per job:

Step 1 \- Generate script:  
  Call Ollama with prompt template  
  Store script in video record

Step 2 \- Generate voiceover:  
  Pass script to Piper TTS  
  Save .wav file to storage

Step 3 \- Generate subtitles:  
  Pass .wav to faster-whisper  
  Output .srt file

Step 4 \- Assemble video:  
  Use FFmpeg \+ MoviePy to:  
  \- Create background (solid color or gradient)  
  \- Burn in subtitles  
  \- Add audio track  
  \- Add logo watermark if free plan  
  \- Output .mp4 at 9:16 for short-form  
  Store final .mp4 in MinIO

Step 5 \- Update job record:  
  Mark complete  
  Emit WebSocket event to frontend for real-time progress

Error handling:  
  On failure at any step, mark job failed with error message  
  Allow retry from admin panel

\====================================  
STRIPE PLANS  
\====================================

Free:  
\- 3 videos/month  
\- watermark on videos  
\- download only (no auto-publish)

Creator (\$19/month):  
\- 25 videos/month  
\- no watermark  
\- YouTube auto-publish  
\- 10GB storage

Pro (\$49/month):  
\- unlimited videos  
\- all features  
\- priority queue  
\- 50GB storage

Enforce limits in the POST /api/videos/generate route.

\====================================  
ADMIN PANEL  
\====================================

Pages at /admin/\*:  
\- /admin — metrics dashboard  
\- /admin/users — user table with search, deactivate, role change  
\- /admin/jobs — video job table with retry button  
\- /admin/settings — key/value system settings editor  
\- /admin/logs — recent admin audit logs

Metrics:  
\- total users, new last 7d  
\- active subscriptions  
\- videos generated today and this month  
\- queued/running/failed jobs

Admin login:  
\- seeded from ADMIN\_EMAIL \+ ADMIN\_PASSWORD env vars  
\- ADMIN role required for all /admin/\* routes  
\- every admin action logged to admin\_audit\_logs

\====================================  
FRONTEND PAGES  
\====================================

Public:  
\- / — simple marketing homepage with hero, features, pricing, CTA  
\- /pricing — plan cards with Stripe Checkout links  
\- /login  
\- /register

App (auth required):  
\- /dashboard — recent projects, usage meter, subscription status  
\- /projects/new — topic form, settings (tone, style, format)  
\- /videos — list of videos with status, preview, download  
\- /videos/\[id\] — video detail, preview player, schedule form  
\- /schedule — list of upcoming scheduled posts  
\- /connect — connect YouTube, download guides for others  
\- /settings — profile, billing link

Admin:  
\- /admin/\*

\====================================  
FOLDER STRUCTURE  
\====================================

backend/
├── web/                    \# Next.js  
│   ├── app/  
│   │   ├── (marketing)/  
│   │   ├── (auth)/  
│   │   ├── (app)/  
│   │   └── admin/  
│   ├── components/  
│   │   ├── ui/  
│   │   ├── dashboard/  
│   │   ├── video/  
│   │   └── admin/  
│   ├── lib/  
│   ├── hooks/  
│   ├── types/  
│   └── Dockerfile  
│  
├── api/                    \# FastAPI  
│   ├── app/  
│   │   ├── main.py  
│   │   ├── config.py  
│   │   ├── database.py  
│   │   ├── models/  
│   │   ├── schemas/  
│   │   ├── routers/  
│   │   ├── services/  
│   │   └── core/  
│   ├── migrations/  
│   ├── tests/  
│   ├── requirements.txt  
│   └── Dockerfile  
│  
├── worker/                 \# Celery  
│   ├── tasks/  
│   │   ├── video\_generation.py  
│   │   └── publishing.py  
│   ├── pipeline/  
│   │   ├── text\_generation.py  
│   │   ├── tts.py  
│   │   ├── stt.py  
│   │   ├── video\_render.py  
│   │   └── connectors/  
│   │       ├── base.py  
│   │       ├── youtube.py  
│   │       ├── instagram.py  
│   │       ├── tiktok.py  
│   │       └── x.py  
│   ├── celery\_app.py  
│   ├── requirements.txt  
│   └── Dockerfile  
│  
├── docker-compose.yml  
├── .env.example  
├── seed.py  
├── Makefile  
└── README.md

\====================================  
DOCKER SERVICES  
\====================================

docker-compose.yml:  
\- web (port 3000\)  
\- api (port 8000\)  
\- worker  
\- beat (scheduled job runner)  
\- postgres (port 5432\)  
\- redis (port 6379\)  
\- minio (port 9000\)  
\- ollama (port 11434\)

\====================================  
.env.example  
\====================================

Include every required variable:  
\- DATABASE\_URL  
\- REDIS\_URL  
\- MINIO\_ENDPOINT, MINIO\_ACCESS\_KEY, MINIO\_SECRET\_KEY, MINIO\_BUCKET  
\- SECRET\_KEY  
\- ADMIN\_EMAIL, ADMIN\_PASSWORD  
\- STRIPE\_PUBLISHABLE\_KEY, STRIPE\_SECRET\_KEY, STRIPE\_WEBHOOK\_SECRET  
\- STRIPE\_CREATOR\_PRICE\_ID, STRIPE\_PRO\_PRICE\_ID  
\- YOUTUBE\_CLIENT\_ID, YOUTUBE\_CLIENT\_SECRET, YOUTUBE\_REDIRECT\_URI  
\- OLLAMA\_BASE\_URL, OLLAMA\_MODEL  
\- PIPER\_MODEL\_PATH  
\- WHISPER\_MODEL\_SIZE  
\- APP\_URL  
\- NEXT\_PUBLIC\_APP\_URL  
\- NEXT\_PUBLIC\_STRIPE\_PUBLISHABLE\_KEY

\====================================  
SEED SCRIPT  
\====================================

seed.py must:  
\- create admin from ADMIN\_EMAIL \+ ADMIN\_PASSWORD  
\- create test user (test@example.com / password: testpassword123)  
\- create Free, Creator, Pro plans  
\- create default system settings  
\- be idempotent

\====================================  
MAKEFILE  
\====================================

make setup       \# copy .env.example to .env  
make up          \# start all services  
make down        \# stop all services    
make migrate     \# run alembic upgrade head  
make seed        \# run seed.py  
make logs        \# all logs  
make model       \# pull ollama model (llama3.2)  
make test        \# run pytest

\====================================  
QUALITY RULES  
\====================================

\- Real working code only, no pseudocode  
\- No placeholder functions for core features  
\- Password hashing with bcrypt  
\- JWT with httpOnly cookies  
\- All admin routes require ADMIN role check  
\- Social tokens encrypted in DB with Fernet  
\- Video jobs are idempotent and retryable  
\- FFmpeg errors caught and logged per job  
\- Graceful degradation if Ollama is not ready at startup  
\- TypeScript strict mode  
\- All API responses typed

\====================================  
OUTPUT ORDER  
\====================================

1\. Folder structure (create all directories)  
2\. docker-compose.yml  
3\. .env.example  
4\. api/ — config, models, schemas, routers, services fully  
5\. migrations/ — full Alembic setup and initial migration  
6\. worker/ — celery app, pipeline, tasks fully  
7\. web/ — all pages and components fully  
8\. seed.py  
9\. Makefile  
10\. README.md

Do not stop between sections.  
Do not summarize instead of writing code.  
Do not ask for confirmation.  
If output is cut off, continue from exactly where you stopped in the next message.

Write every file completely.

**FREE**

**\$0**

Creates **1 video**

1 Series

0 Motion Credits

~~Auto-post to channel                                                                          Background Music~~

~~Voice Cloning                                                                                        Edit & preview videos~~

~~No Watermark                                                                                      HD Video Resolution~~

**SCHEDULAR**

**\$16/month**

Billed yearly

Posts **3 times a week**                                                                         HD Video Resolution

1 Series                                                                                                            Background Music

                                                                  

27 Motion Credits

Auto-post to channel

Voice Cloning

No Watermark

**INTENSE**

**\$33/month**

Billed yearly

Posts **once a day**

1 Series

62 Motion Credits

Auto-post to channel

Edit & preview videos

HD Video Resolution

Background Music

Voice Cloning

No Watermark

**BEAST MODE**

**\$58**/month

Billed yearly

Posts **twice a day**

1 Series

124 Motion Credits

Auto-post to channel

Edit & preview videos

HD Video Resolution

Background Music

Voice Cloning

No Watermark

**Frequently Asked Questions**  
Have a question? We have answers.

**Series & Videos**

### **What is a Series?**

### **Can I create videos in any niche?**

### **What social media platforms do you support posting to?**

### **Are the videos unique?**

### **Can I edit the videos?**

### **How do custom prompts work?**

### **How many videos can I create per day?**

### **Why am I not getting many views?**

### **Can I replace an existing series with a new one?**

### **How do I create a video?**

### **Can I adjust the video length?**

### **Do I own the videos?**

### **Does the platform support multiple languages?**

### **Are there any types of content that are not allowed?**

### **Can this make long form content?**

### **What are image credits?**

### **What are motion credits?**

**Billing**

### **Is there a free trial?**

### **Can I cancel at anytime?**

### **How does the membership work?**

### **Can I get a refund?**

### **Can I upgrade or downgrade my subscription?**

### **Can I have multiple plans?**

