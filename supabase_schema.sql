-- Run once in the Supabase SQL Editor of your own project.
create table if not exists public.tem_products (
  id uuid primary key,
  data jsonb not null,
  image_base64 text not null,
  quality jsonb not null,
  created_at timestamptz not null default now()
);
create unique index if not exists tem_product_code_unique
  on public.tem_products (lower(data->>'product_code'));
create table if not exists public.tem_scans (
  id bigint generated always as identity primary key,
  status text not null,
  product_id uuid,
  score double precision,
  created_at timestamptz not null default now()
);
alter table public.tem_products enable row level security;
alter table public.tem_scans enable row level security;
revoke all on public.tem_products, public.tem_scans from anon, authenticated;
grant all on public.tem_products, public.tem_scans to service_role;
grant usage,select on all sequences in schema public to service_role;
-- No public SELECT policies. Only the Python server holds the service key.
