create extension if not exists pgcrypto;

create table if not exists public.fred_series_metadata (
  series_id text primary key,
  name text not null,
  description text,
  frequency text,
  source text default 'FRED',
  is_active boolean default true,
  created_at timestamptz default now()
);

create table if not exists public.fred_observations (
  id uuid primary key default gen_random_uuid(),
  series_id text not null references public.fred_series_metadata(series_id),
  observation_date date not null,
  value numeric,
  realtime_start date,
  realtime_end date,
  created_at timestamptz default now(),
  unique(series_id, observation_date)
);
create index if not exists idx_fred_observations_date
  on public.fred_observations(observation_date);

create table if not exists public.daily_macro_features (
  feature_date date primary key,
  us_10y_yield numeric,
  us_2y_yield numeric,
  us_10y_real_yield numeric,
  fed_funds_rate numeric,
  us_cpi numeric,
  broad_usd_index numeric,
  sp500 numeric,
  high_yield_spread numeric,
  yield_curve_10y_2y numeric,
  real_yield_change_1d numeric,
  real_yield_change_5d numeric,
  real_yield_change_20d numeric,
  nominal_10y_change_1d numeric,
  nominal_10y_change_5d numeric,
  broad_usd_return_1d numeric,
  broad_usd_return_5d numeric,
  sp500_return_1d numeric,
  sp500_return_5d numeric,
  credit_stress_change_1d numeric,
  credit_stress_change_5d numeric,
  cpi_yoy numeric,
  cpi_mom numeric,
  fed_funds_change numeric,
  macro_stress_score numeric,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- La service role se usa únicamente en backend/Actions. No debe exponerse al cliente.
