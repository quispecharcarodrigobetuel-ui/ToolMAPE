create extension if not exists pgcrypto;

create table if not exists public.news_sources (
  source_id text primary key,
  name text not null,
  url text not null unique,
  expected_language text,
  reliability_weight double precision not null default 1,
  suggested_frequency_minutes integer not null default 60,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.news_raw (
  news_id uuid primary key,
  source_id text not null references public.news_sources(source_id),
  source_name text not null,
  source_url text not null,
  url text not null unique,
  title text not null,
  summary text,
  published_at timestamptz,
  category text,
  scraped_at timestamptz not null,
  language text,
  content_hash text not null unique,
  reliability_weight double precision not null default 1,
  collector_method text not null,
  updated_at timestamptz not null default now()
);
create index if not exists idx_news_raw_published_at on public.news_raw(published_at);
create index if not exists idx_news_raw_source_id on public.news_raw(source_id);

create table if not exists public.news_gpt_enriched (
  news_id uuid primary key references public.news_raw(news_id) on delete cascade,
  enriched_at timestamptz not null,
  provider text not null default 'openai',
  model text not null,
  enrichment_status text not null check (enrichment_status in ('completed', 'pending', 'error')),
  error text,
  tipo_activo text,
  subtipo_evento text,
  pais_region jsonb,
  sentido_oro text,
  sentido_dolar text,
  sentido_usd_pen text,
  sentido_precio_oro_soles text,
  impacto_esperado text,
  horizonte_probable text,
  confianza_gpt double precision check (confianza_gpt between 0 and 1),
  resumen_estandarizado text,
  escenario_base text,
  escenario_diferente text,
  condicion_de_cambio text,
  variables_afectadas jsonb,
  actores_clave jsonb,
  razonamiento_resumido text,
  updated_at timestamptz not null default now()
);

alter table public.news_gpt_enriched
  add column if not exists provider text not null default 'openai';

create table if not exists public.news_market_labels (
  news_id uuid primary key references public.news_raw(news_id) on delete cascade,
  reference_date date not null,
  reference_price double precision not null,
  price_1d double precision,
  return_1d double precision,
  direction_1d text,
  impact_class_1d text,
  price_3d double precision,
  return_3d double precision,
  direction_3d text,
  impact_class_3d text,
  labeled_at timestamptz not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.daily_news_features (
  feature_date date primary key,
  news_count_total integer not null default 0,
  news_count_gold integer not null default 0,
  news_count_dollar integer not null default 0,
  news_count_fed integer not null default 0,
  news_count_geopolitics integer not null default 0,
  news_count_mining_peru integer not null default 0,
  gold_bullish_score double precision not null default 0,
  gold_bearish_score double precision not null default 0,
  dollar_bullish_score double precision not null default 0,
  dollar_bearish_score double precision not null default 0,
  fed_hawkish_score double precision not null default 0,
  fed_dovish_score double precision not null default 0,
  geopolitical_risk_score double precision not null default 0,
  avg_impact_expected double precision not null default 0,
  max_impact_expected double precision not null default 0,
  avg_confidence_gpt double precision not null default 0,
  news_conflict_score double precision not null default 0,
  updated_at timestamptz not null default now()
);

create table if not exists public.news_pipeline_runs (
  run_id uuid primary key,
  timestamp timestamptz not null,
  stage text not null,
  source text,
  news_found integer not null default 0,
  news_new integer not null default 0,
  news_duplicates integer not null default 0,
  news_enriched integer not null default 0,
  errors jsonb not null default '[]'::jsonb,
  duration_seconds double precision not null default 0,
  mode text not null,
  created_at timestamptz not null default now()
);

-- La service role omite RLS. Si se habilita acceso desde clientes, active RLS y cree
-- políticas de solo lectura explícitas; no exponga SUPABASE_SERVICE_ROLE_KEY al frontend.
